"""Local-only Tiger OpenAPI configuration and client initialization."""

import logging as _logging
import os as _os
import stat as _stat
from pathlib import Path as _Path
from typing import Optional as _Optional
from typing import Tuple as _Tuple
from typing import Type as _Type


__all__ = (
    "resolve_tiger_config_path",
    "initialize_tiger_quote_client",
)


_CONFIG_ENVIRONMENT_VARIABLE = "CONVEXITY_HUNTER_TIGER_CONFIG"
_DEFAULT_CONFIG_RELATIVE_PATH = _Path(
    ".config/tigeropen/tiger_openapi_config.properties"
)
_TOKEN_FILENAME = "tiger_openapi_token.properties"
_UNSUPPORTED_SDK_ENVIRONMENT_PREFIX = "TIGEROPEN_"

_NOT_FOUND_MESSAGE = (
    "Tiger OpenAPI configuration was not found. Place Tiger's official "
    "tiger_openapi_config.properties at "
    "~/.config/tigeropen/tiger_openapi_config.properties or set "
    "CONVEXITY_HUNTER_TIGER_CONFIG to an absolute local file path."
)
_INVALID_PATH_MESSAGE = "Tiger OpenAPI configuration path is invalid."
_NON_REGULAR_MESSAGE = "Tiger OpenAPI configuration must be a regular file."
_REPOSITORY_MESSAGE = (
    "Tiger OpenAPI configuration must be outside the repository worktree."
)
_PERMISSION_MESSAGE = (
    "Tiger OpenAPI configuration must be owner-readable and private to the "
    "current user."
)
_SDK_ENVIRONMENT_MESSAGE = (
    "Tiger SDK environment configuration is unsupported; use only "
    "CONVEXITY_HUNTER_TIGER_CONFIG as a local path override."
)
_SDK_UNAVAILABLE_MESSAGE = (
    "Tiger OpenAPI SDK is unavailable. Install convexity-hunter[tiger]."
)
_SDK_INITIALIZATION_MESSAGE = "Tiger OpenAPI client initialization failed."


def _home_directory() -> _Path:
    return _Path.home()


def _repository_root() -> _Optional[_Path]:
    module_path = _Path(__file__).resolve()
    for candidate in module_path.parents:
        if (candidate / ".git").exists():
            return candidate.resolve()
    return None


def _has_unsupported_sdk_environment() -> bool:
    return any(
        name.startswith(_UNSUPPORTED_SDK_ENVIRONMENT_PREFIX)
        for name in _os.environ
    )


def _canonical_path(raw_path: str) -> _Path:
    if not raw_path or not raw_path.strip():
        raise ValueError(_INVALID_PATH_MESSAGE)
    try:
        expanded = _Path(raw_path).expanduser()
        if not expanded.is_absolute():
            raise ValueError(_INVALID_PATH_MESSAGE)
        return expanded.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise ValueError(_INVALID_PATH_MESSAGE) from None


def _is_within(path: _Path, directory: _Path) -> bool:
    try:
        return _os.path.commonpath((str(path), str(directory))) == str(directory)
    except ValueError:
        return False


def _validate_external_file(
    path: _Path,
    *,
    missing_allowed: bool,
) -> _Optional[_Path]:
    try:
        canonical = path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise ValueError(_INVALID_PATH_MESSAGE) from None
    repository_root = _repository_root()
    if repository_root is not None and _is_within(canonical, repository_root):
        raise ValueError(_REPOSITORY_MESSAGE)

    try:
        file_stat = canonical.stat()
    except FileNotFoundError:
        if missing_allowed:
            return None
        raise FileNotFoundError(_NOT_FOUND_MESSAGE) from None
    except OSError:
        raise ValueError(_INVALID_PATH_MESSAGE) from None

    if not _stat.S_ISREG(file_stat.st_mode):
        raise ValueError(_NON_REGULAR_MESSAGE)

    if _os.name == "posix":
        mode = _stat.S_IMODE(file_stat.st_mode)
        owner_readable = bool(mode & _stat.S_IRUSR)
        unsafe_bits = mode & (
            _stat.S_IXUSR | _stat.S_IRWXG | _stat.S_IRWXO
        )
        if (
            file_stat.st_uid != _os.getuid()
            or not owner_readable
            or unsafe_bits
        ):
            raise ValueError(_PERMISSION_MESSAGE)

    return canonical


def _validate_adjacent_token_file(config_path: _Path) -> None:
    token_path = config_path.with_name(_TOKEN_FILENAME)
    _validate_external_file(token_path, missing_allowed=True)


def resolve_tiger_config_path() -> _Path:
    """Resolve one private external Tiger provider configuration path."""

    if _has_unsupported_sdk_environment():
        raise RuntimeError(_SDK_ENVIRONMENT_MESSAGE)

    if _CONFIG_ENVIRONMENT_VARIABLE in _os.environ:
        raw_path = _os.environ[_CONFIG_ENVIRONMENT_VARIABLE]
    else:
        raw_path = str(_home_directory() / _DEFAULT_CONFIG_RELATIVE_PATH)

    config_path = _validate_external_file(
        _canonical_path(raw_path),
        missing_allowed=False,
    )
    if config_path is None:  # pragma: no cover - excluded by missing_allowed
        raise FileNotFoundError(_NOT_FOUND_MESSAGE)
    _validate_adjacent_token_file(config_path)
    return config_path


def _load_tiger_sdk() -> _Tuple[_Type[object], _Type[object]]:
    try:
        from tigeropen.quote.quote_client import QuoteClient
        from tigeropen.tiger_open_config import TigerOpenClientConfig
    except Exception:
        raise RuntimeError(_SDK_UNAVAILABLE_MESSAGE) from None
    return TigerOpenClientConfig, QuoteClient


class _DiscardRootLogFilter(_logging.Filter):
    def filter(self, record: _logging.LogRecord) -> bool:
        return False


def _construct_client_config(config_type: _Type[object], config_path: _Path) -> object:
    root_logger = _logging.getLogger()
    discard_filter = _DiscardRootLogFilter()
    root_logger.addFilter(discard_filter)
    try:
        return config_type(
            props_path=str(config_path),
            enable_dynamic_domain=False,
        )
    finally:
        root_logger.removeFilter(discard_filter)


def _discard_logger() -> _logging.Logger:
    logger = _logging.Logger(
        "convexity_hunter.tigeropen.runtime",
        level=_logging.CRITICAL + 1,
    )
    logger.addHandler(_logging.NullHandler())
    logger.propagate = False
    return logger


def initialize_tiger_quote_client() -> object:
    """Construct a local Tiger QuoteClient without network or permission grab."""

    config_path = resolve_tiger_config_path()
    config_type, quote_client_type = _load_tiger_sdk()
    try:
        client_config = _construct_client_config(config_type, config_path)
        if not all(
            bool(getattr(client_config, field, None))
            for field in ("tiger_id", "account", "private_key")
        ):
            raise ValueError("required Tiger configuration fields are absent")
        setattr(client_config, "token_refresh_duration", 0)
        setattr(client_config, "log_path", None)
        setattr(client_config, "log_level", None)
        return quote_client_type(
            client_config,
            logger=_discard_logger(),
            is_grab_permission=False,
        )
    except Exception:
        raise RuntimeError(_SDK_INITIALIZATION_MESSAGE) from None
