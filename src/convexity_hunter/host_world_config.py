"""Strict external World configuration for the existing pinned controller."""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Union

from .core_application import CoreOperationalBounds
from .host_event import HostEventGrounderConfig
from .host_event_config import (
    HostEventConfigurationError,
    _parse_json,
    _read_external_config,
    _require_object,
)
from .host_skill import HostSkillConfig, Last30DaysSkillPin
from .host_world import HostWorldConfig
from .option_chain_discovery import OptionMaturityAuthority

HOST_WORLD_CONFIG_SCHEMA_VERSION = "host-world-config-v0.1"
APPROVED_SKILL_PATH = Path("/Users/erwinlee/.codex/skills/last30days")
APPROVED_SKILL_VERSION = "3.21.1"
APPROVED_SKILL_SHA256 = "74f97a97dcf4382bb4bf19521971bda4d6fbc09c2c0a656d1353eaf28e874920"
# Previously validated standalone CPython 3.12.14; the Host may use Python 3.9+.
APPROVED_SKILL_PYTHON = Path(
    "/Users/erwinlee/.local/share/convexity-hunter/runtimes/"
    "cpython-3.12.14+20260924-aarch64-apple-darwin/python/bin/python3.12"
)

_SKILL_FIELDS = frozenset((
    "skill_pin", "python_executable", "source_allowlist", "permitted_source_envs",
    "stage_timeout_seconds", "request_stage_budget", "max_stdout_bytes",
    "max_stderr_bytes", "days", "current_only", "no_as_of",
    "handoff_ttl_seconds", "max_handoff_bytes", "final_output_path",
))
_BOUNDS_FIELDS = frozenset((
    "max_submissions", "max_hypotheses", "max_browser_rows", "max_cases",
    "quote_timeout_seconds",
))


class HostWorldConfigurationError(HostEventConfigurationError):
    """Same closed loader diagnostics, with no configuration values exposed."""

    def __repr__(self) -> str:
        return "HostWorldConfigurationError(code={!r})".format(self.code)


def load_world_config(
    config_path: Union[str, os.PathLike],
    *,
    repo_root: Union[str, os.PathLike],
    grounder_config: HostEventGrounderConfig,
    evaluation_date: datetime.date,
    maturity_authority: OptionMaturityAuthority,
) -> HostWorldConfig:
    """Reuse Event's 64 KiB external/strict reader; never resolve credentials."""
    try:
        value = _require_object(
            _parse_json(_read_external_config(config_path, repo_root)),
            frozenset(("schema_version", "skill", "bounds")),
        )
        if value["schema_version"] != HOST_WORLD_CONFIG_SCHEMA_VERSION:
            raise HostWorldConfigurationError("UNSUPPORTED_SCHEMA_VERSION")
        skill = dict(_require_object(value["skill"], _SKILL_FIELDS))
        pin = _require_object(
            skill["skill_pin"], frozenset(("path", "version", "content_sha256"))
        )
        if pin != {
            "path": str(APPROVED_SKILL_PATH),
            "version": APPROVED_SKILL_VERSION,
            "content_sha256": APPROVED_SKILL_SHA256,
        }:
            raise HostWorldConfigurationError("INVALID_CONFIGURATION")
        if (
            type(skill["python_executable"]) is not str
            or not Path(skill["python_executable"]).is_absolute()
            or Path(skill["python_executable"]).resolve(strict=True)
            != APPROVED_SKILL_PYTHON.resolve(strict=True)
            or skill["final_output_path"] is not None
        ):
            raise HostWorldConfigurationError("INVALID_CONFIGURATION")
        skill["skill_pin"] = Last30DaysSkillPin(**pin)
        for field in ("source_allowlist", "permitted_source_envs"):
            if type(skill[field]) is not list:
                raise HostWorldConfigurationError("INVALID_CONFIGURATION")
            skill[field] = tuple(skill[field])
        return HostWorldConfig(
            skill=HostSkillConfig(**skill),
            grounder=grounder_config,
            evaluation_date=evaluation_date,
            maturity_authority=maturity_authority,
            bounds=CoreOperationalBounds(**_require_object(value["bounds"], _BOUNDS_FIELDS)),
        )
    except HostEventConfigurationError as error:
        raise HostWorldConfigurationError(error.code) from None
    except Exception:
        raise HostWorldConfigurationError("INVALID_CONFIGURATION") from None
