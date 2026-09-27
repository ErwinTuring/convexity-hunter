"""Small, bounded launcher for the pinned last30days skill.

The launcher is a controlled subprocess boundary, not an OS sandbox and not a
global HTTP/request limiter.  It only supplies the explicit source environment
names selected by the caller, disables the installed skill's ambient
credential/config loaders in a bootstrap, and captures child output by byte
count without retaining or exposing raw output.
"""

from __future__ import annotations

import hashlib
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Tuple


__all__ = (
    "ALLOWED_SOURCE_ENV_NAMES",
    "HostSkillLaunchError",
    "StageExecution",
    "StageRequest",
    "build_child_environment",
    "loader_guard_source",
    "run_stage",
)


# These are the only source credentials this fixed discovery controller may
# pass.  Reddit's historical ScrapeCreators service is available only when
# the host explicitly grants this name; X may use explicit cookie headers.
# Model, web-backend, Apify and all other provider keys stay absent.
ALLOWED_SOURCE_ENV_NAMES = frozenset(
    {
        "AUTH_TOKEN",
        "CT0",
        "SCRAPECREATORS_API_KEY",
    }
)
_ALLOWED_CHILD_ENV_NAMES = frozenset(
    {
        "LAST30DAYS_CONFIG_DIR",
        "LAST30DAYS_MEMORY_DIR",
        "LAST30DAYS_TRUST_PROJECT_CONFIG",
        "HOME",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
        "PYTHONNOUSERSITE",
        "PATH",
    }
).union(ALLOWED_SOURCE_ENV_NAMES)

_BOOTSTRAP = r'''
import runpy
import sys
from pathlib import Path

if sys.version_info < (3, 12):
    raise SystemExit(125)

_script = sys.argv[1]
sys.path.insert(0, str(Path(_script).parent))
from lib import env as _last30days_env

def _no_external_secret_loader(*_args, **_kwargs):
    return {}

def _no_model_auth(_file_env):
    return _last30days_env.OpenAIAuth(
        token=None,
        source=_last30days_env.AUTH_SOURCE_NONE,
        status=_last30days_env.AUTH_STATUS_MISSING,
    )

_last30days_env._load_keychain = _no_external_secret_loader
_last30days_env._load_pass = _no_external_secret_loader
_last30days_env.get_openai_auth = _no_model_auth

sys.argv = sys.argv[1:]
runpy.run_path(_script, run_name="__main__")
'''.strip()


class HostSkillLaunchError(RuntimeError):
    """Sanitized launcher failure; child output is never part of the error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return "HostSkillLaunchError(code={!r})".format(self.code)


@dataclass(frozen=True)
class StageRequest:
    """One already-validated skill invocation supplied to a runner."""

    phase: str
    argv: Tuple[str, ...]
    skill_path: Path
    python_executable: Path
    cwd: Path
    environment: Mapping[str, str]
    timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int


@dataclass(frozen=True)
class StageExecution:
    """Bounded execution metadata; stdout/stderr bytes are not returned."""

    returncode: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    timed_out: bool = False
    output_limited: bool = False


def loader_guard_source() -> str:
    """Return the fixed child bootstrap used to disable ambient loaders."""

    return _BOOTSTRAP


def _validate_source_names(names: Sequence[str]) -> Tuple[str, ...]:
    if type(names) is not tuple or any(type(name) is not str for name in names):
        raise HostSkillLaunchError("INVALID_SOURCE_ENV_ALLOWLIST")
    if len(set(names)) != len(names):
        raise HostSkillLaunchError("DUPLICATE_SOURCE_ENV_NAME")
    if any(name not in ALLOWED_SOURCE_ENV_NAMES for name in names):
        raise HostSkillLaunchError("SOURCE_ENV_NOT_PERMITTED")
    return names


def _validate_child_environment(environment: Mapping[str, str]) -> None:
    if not isinstance(environment, Mapping):
        raise HostSkillLaunchError("INVALID_CHILD_ENVIRONMENT")
    if any(
        type(name) is not str
        or type(value) is not str
        or name not in _ALLOWED_CHILD_ENV_NAMES
        for name, value in environment.items()
    ):
        raise HostSkillLaunchError("CHILD_ENV_NOT_PERMITTED")
    if environment.get("LAST30DAYS_CONFIG_DIR") != "":
        raise HostSkillLaunchError("CONFIG_DISCOVERY_NOT_DISABLED")
    if environment.get("LAST30DAYS_TRUST_PROJECT_CONFIG") != "0":
        raise HostSkillLaunchError("PROJECT_CONFIG_NOT_DISABLED")
    if environment.get("PYTHONNOUSERSITE") != "1":
        raise HostSkillLaunchError("USER_SITE_NOT_DISABLED")


def build_child_environment(
    source_env_names: Sequence[str],
    isolated_dir: Path,
) -> Mapping[str, str]:
    """Build a child env from a closed allowlist and isolated config roots."""

    names = _validate_source_names(source_env_names)
    if not isinstance(isolated_dir, Path) or not isolated_dir.is_absolute():
        raise HostSkillLaunchError("INVALID_ISOLATED_DIR")

    isolated_home = isolated_dir / "_home"
    environment = {
        # Empty means ``env.py`` sets CONFIG_DIR/CONFIG_FILE to None at import.
        "LAST30DAYS_CONFIG_DIR": "",
        "LAST30DAYS_MEMORY_DIR": str(isolated_dir),
        "LAST30DAYS_TRUST_PROJECT_CONFIG": "0",
        "HOME": str(isolated_home),
        "USERPROFILE": str(isolated_home),
        "XDG_CONFIG_HOME": str(isolated_home / ".config"),
        "PYTHONNOUSERSITE": "1",
    }
    # PATH is non-secret process plumbing.  It is copied only as this one
    # explicitly understood key; all other ambient variables are dropped.
    path_value = os.environ.get("PATH")
    if path_value:
        environment["PATH"] = path_value
    for name in names:
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


def _kill_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass


def _run_bounded(request: StageRequest) -> StageExecution:
    wrapped_argv = [
        str(request.python_executable),
        "-c",
        _BOOTSTRAP,
        str(request.skill_path),
    ] + list(request.argv[1:])
    try:
        process = subprocess.Popen(
            wrapped_argv,
            cwd=str(request.cwd),
            env=dict(request.environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=(os.name == "posix"),
        )
    except (OSError, ValueError):
        raise HostSkillLaunchError("SPAWN_FAILED") from None

    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {
        "stdout": request.max_stdout_bytes,
        "stderr": request.max_stderr_bytes,
    }
    total_sizes = {"stdout": 0, "stderr": 0}
    timed_out = False
    output_limited = False
    deadline = time.monotonic() + request.timeout_seconds

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                timed_out = True
                _kill_process(process)
            events = selector.select(max(0.0, min(0.05, remaining)))
            for key, _mask in events:
                label = key.data
                try:
                    chunk = os.read(key.fd, 8192)
                except OSError:
                    chunk = b""
                if not chunk:
                    try:
                        selector.unregister(key.fileobj)
                    except KeyError:
                        pass
                    try:
                        key.fileobj.close()
                    except OSError:
                        pass
                    continue
                total_sizes[label] += len(chunk)
                room = limits[label] + 1 - len(buffers[label])
                if room > 0:
                    buffers[label].extend(chunk[:room])
                if total_sizes[label] > limits[label] and not output_limited:
                    output_limited = True
                    _kill_process(process)
            if process.poll() is not None and not selector.get_map():
                break
    finally:
        try:
            selector.close()
        finally:
            if process.poll() is None:
                _kill_process(process)
            try:
                process.wait(timeout=0.5)
            except (subprocess.TimeoutExpired, OSError):
                pass
            for stream in (process.stdout, process.stderr):
                try:
                    stream.close()
                except OSError:
                    pass

    return StageExecution(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout_bytes=total_sizes["stdout"],
        stderr_bytes=total_sizes["stderr"],
        stdout_sha256=hashlib.sha256(bytes(buffers["stdout"])).hexdigest(),
        stderr_sha256=hashlib.sha256(bytes(buffers["stderr"])).hexdigest(),
        timed_out=timed_out,
        output_limited=output_limited,
    )


def run_stage(request: StageRequest) -> StageExecution:
    """Run one fixed stage with bounded output and no retry."""

    if not isinstance(request, StageRequest):
        raise HostSkillLaunchError("INVALID_STAGE_REQUEST")
    if not request.argv or request.argv[0] != str(request.skill_path):
        raise HostSkillLaunchError("SKILL_ARGV_PATH_MISMATCH")
    if not request.python_executable.is_absolute():
        raise HostSkillLaunchError("PYTHON_EXECUTABLE_MUST_BE_ABSOLUTE")
    if not request.skill_path.is_absolute():
        raise HostSkillLaunchError("SKILL_PATH_MUST_BE_ABSOLUTE")
    if not request.cwd.is_absolute():
        raise HostSkillLaunchError("ISOLATED_DIR_MUST_BE_ABSOLUTE")
    if any(type(value) is not str or "\x00" in value for value in request.argv):
        raise HostSkillLaunchError("INVALID_SKILL_ARGV")
    if request.timeout_seconds <= 0 or request.max_stdout_bytes <= 0 or request.max_stderr_bytes <= 0:
        raise HostSkillLaunchError("INVALID_STAGE_BUDGET")
    _validate_child_environment(request.environment)
    execution = _run_bounded(request)
    if execution.timed_out:
        raise HostSkillLaunchError("STAGE_TIMEOUT")
    if execution.output_limited:
        raise HostSkillLaunchError("STAGE_OUTPUT_LIMIT")
    if execution.returncode == 125:
        raise HostSkillLaunchError("PYTHON_VERSION_UNSUPPORTED")
    return execution
