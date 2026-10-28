"""Strict external World configuration for the existing pinned controller."""

from __future__ import annotations

from dataclasses import replace
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
_HOST_WORLD_CONFIG_SCHEMA_VERSION_V0_3 = "host-world-config-v0.3"
_HOST_WORLD_CONFIG_SCHEMA_VERSION_V0_4 = "host-world-config-v0.4"
_MAX_CATALOG_SCAN_PARAGRAPHS_V0_3 = 1024
_MAX_CATALOG_ENTRIES_V0_4 = 256
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
        parsed = _parse_json(_read_external_config(config_path, repo_root))
        v0_3 = (
            type(parsed) is dict
            and parsed.get("schema_version") == _HOST_WORLD_CONFIG_SCHEMA_VERSION_V0_3
        )
        v0_4 = (
            type(parsed) is dict
            and parsed.get("schema_version") == _HOST_WORLD_CONFIG_SCHEMA_VERSION_V0_4
        )
        v0_2 = (
            type(parsed) is dict
            and parsed.get("schema_version") == "host-world-config-v0.2"
        )
        if v0_4:
            fields = frozenset((
                "schema_version", "skill", "bounds", "grounder_budgets",
                "catalog_scan_paragraphs", "catalog_entries",
            ))
        elif v0_3:
            fields = frozenset((
                "schema_version", "skill", "bounds", "grounder_budgets",
                "catalog_scan_paragraphs",
            ))
        elif v0_2:
            fields = frozenset(("schema_version", "skill", "bounds", "grounder_budgets"))
        else:
            fields = frozenset(("schema_version", "skill", "bounds"))
        value = _require_object(parsed, fields)
        if (
            not (v0_2 or v0_3 or v0_4)
            and value["schema_version"] != HOST_WORLD_CONFIG_SCHEMA_VERSION
        ):
            raise HostWorldConfigurationError("UNSUPPORTED_SCHEMA_VERSION")
        world_grounder = grounder_config
        if v0_2 or v0_3 or v0_4:
            budgets = _require_object(
                value["grounder_budgets"],
                frozenset((
                    "source_requests",
                    "source_credits",
                    "discovery_requests",
                    "semantic_requests",
                )),
            )
            if any(
                type(budgets[name]) is not int or budgets[name] <= 0
                for name in (
                    "source_requests",
                    "source_credits",
                    "discovery_requests",
                    "semantic_requests",
                )
            ):
                raise HostWorldConfigurationError("INVALID_CONFIGURATION")
            catalog_scan_paragraphs = grounder_config.max_catalog_paragraphs
            if v0_3 or v0_4:
                catalog_scan_paragraphs = value["catalog_scan_paragraphs"]
                if (
                    type(catalog_scan_paragraphs) is not int
                    or not 1 <= catalog_scan_paragraphs <= _MAX_CATALOG_SCAN_PARAGRAPHS_V0_3
                ):
                    raise HostWorldConfigurationError("INVALID_CONFIGURATION")
            catalog_entries = grounder_config.max_catalog_entries
            run_input_bounds = grounder_config.run_input_bounds
            if v0_4:
                catalog_entries = value["catalog_entries"]
                if (
                    type(catalog_entries) is not int
                    or not 1 <= catalog_entries <= _MAX_CATALOG_ENTRIES_V0_4
                    or run_input_bounds.max_array_items > _MAX_CATALOG_ENTRIES_V0_4
                ):
                    raise HostWorldConfigurationError("INVALID_CONFIGURATION")
                run_input_bounds = replace(
                    run_input_bounds,
                    max_array_items=max(
                        run_input_bounds.max_array_items, catalog_entries
                    ),
                )
            world_grounder = replace(
                grounder_config,
                source=replace(
                    grounder_config.source,
                    request_budget=budgets["source_requests"],
                    credit_budget=budgets["source_credits"],
                ),
                discovery_model=replace(
                    grounder_config.discovery_model,
                    request_budget=budgets["discovery_requests"],
                ),
                semantic_model=replace(
                    grounder_config.semantic_model,
                    request_budget=budgets["semantic_requests"],
                ),
                max_catalog_paragraphs=catalog_scan_paragraphs,
                max_catalog_entries=catalog_entries,
                run_input_bounds=run_input_bounds,
            )
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
            grounder=world_grounder,
            evaluation_date=evaluation_date,
            maturity_authority=maturity_authority,
            bounds=CoreOperationalBounds(**_require_object(value["bounds"], _BOUNDS_FIELDS)),
        )
    except HostEventConfigurationError as error:
        raise HostWorldConfigurationError(error.code) from None
    except Exception:
        raise HostWorldConfigurationError("INVALID_CONFIGURATION") from None
