"""Current Core application boundary.

World and Event are source-injected, all-hypothesis paths.  Direct entry is
exact-contract/provider evidence driven.  This module owns orchestration and
identity binding only; economic records are owned by ``core_research``.
"""

import datetime as _datetime
import math as _math
from dataclasses import dataclass as _dataclass
from dataclasses import replace as _replace
from typing import Callable as _Callable
from typing import Optional as _Optional

from .core_futu import (
    FutuNativeDirectAskEvidence,
    NativeQuoteAuthority,
)
from .core_presentation import CoreCompactSummary, compact_summary, report
from .discovery_entry import (
    DiscoveryEntryHandoff,
    create_discovery_entry_handoff,
)
from .event_entry import UserEventInput
from .event_intelligence import (
    EventIntelligenceAcceptanceResult,
    EventIntelligenceAcceptanceStatus,
    EventIntelligenceSubmission,
    EventUnderlyingHypothesis,
    assess_event_intelligence_submission,
)
from .option_chain_discovery import (
    HypothesisMaturityAlignment,
    OptionChainDiscoveryRequest,
    OptionMaturityAuthority,
    create_option_chain_discovery_request,
)
from .providers import futu as _futu


__all__ = (
    "CoreOperationalBounds",
    "CoreResearchPolicy",
    "CoreWorldRequest",
    "SourceSubmissionBatch",
    "CoreCaseContext",
    "CoreCaseRecord",
    "CoreUnavailableCase",
    "CoreCaseSet",
    "StructuredCaseSet",
    "CoreRunResult",
    "CoreDirectResult",
    "run_world_core",
    "run_event_core",
    "run_direct_core",
)


def _nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be 0 or greater")
    return value


def _positive_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("quote_timeout_seconds must be a number")
    normalized = float(value)
    if not _math.isfinite(normalized) or normalized <= 0 or normalized > 60:
        raise ValueError("quote_timeout_seconds must be greater than 0 and at most 60")
    return normalized


@_dataclass(frozen=True)
class CoreOperationalBounds:
    """Explicit run-wide operational limits; no numeric policy is implicit."""

    max_submissions: int
    max_hypotheses: int
    max_browser_rows: int
    max_cases: int
    quote_timeout_seconds: float

    def __post_init__(self) -> None:
        for name in (
            "max_submissions",
            "max_hypotheses",
            "max_browser_rows",
            "max_cases",
        ):
            _nonnegative_int(name, getattr(self, name))
        _positive_timeout(self.quote_timeout_seconds)


def _validate_factory(value: object) -> _Callable:
    if not callable(value):
        raise TypeError("request_factory must be callable")
    return value  # type: ignore[return-value]


@_dataclass(frozen=True)
class CoreResearchPolicy:
    """Caller-declared application policy and per-case kernel request factory."""

    evaluation_date: _datetime.date
    maturity_authority: OptionMaturityAuthority
    generated_quantity: int
    bounds: CoreOperationalBounds
    request_factory: _Callable

    def __post_init__(self) -> None:
        if type(self.evaluation_date) is not _datetime.date:
            raise TypeError("evaluation_date must have exact type date")
        if type(self.maturity_authority) is not OptionMaturityAuthority:
            raise TypeError("maturity_authority must be OptionMaturityAuthority")
        if type(self.generated_quantity) is not int or isinstance(
            self.generated_quantity, bool
        ):
            raise TypeError("generated_quantity must be an integer")
        if self.generated_quantity <= 0:
            raise ValueError("generated_quantity must be greater than 0")
        if type(self.bounds) is not CoreOperationalBounds:
            raise TypeError("bounds must be CoreOperationalBounds")
        _validate_factory(self.request_factory)


@_dataclass(frozen=True)
class CoreWorldRequest:
    """Retained world input envelope; the contained object is never rewritten."""

    raw_request: object


def _validate_submission(value: object) -> EventIntelligenceSubmission:
    if type(value) is not EventIntelligenceSubmission:
        raise TypeError("submissions must contain EventIntelligenceSubmission values")
    return value


@_dataclass(frozen=True)
class SourceSubmissionBatch:
    """Injected source-backed submissions bound to one exact input object."""

    raw_input: object
    submissions: tuple

    def __post_init__(self) -> None:
        if type(self.submissions) is not tuple:
            raise TypeError("submissions must have exact type tuple")
        seen = set()
        for submission in self.submissions:
            _validate_submission(submission)
            if not submission.sources:
                raise ValueError("every submission must retain source records")
            if submission.submission_id in seen:
                raise ValueError("submission IDs must be unique")
            seen.add(submission.submission_id)


def _optional_exact(name: str, value: object, kind: object) -> None:
    if value is not None and type(value) is not kind:
        raise TypeError(f"{name} must have exact type {kind.__name__} or None")


def _identity_member(value: object, values: tuple) -> bool:
    return any(value is item for item in values)


@_dataclass(frozen=True)
class CoreCaseContext:
    """All retained lineage needed to reproduce one Core case."""

    raw_input: object
    maturity_authority: OptionMaturityAuthority
    submissions: _Optional[SourceSubmissionBatch] = None
    assessment: _Optional[EventIntelligenceAcceptanceResult] = None
    hypothesis: _Optional[EventUnderlyingHypothesis] = None
    automated_handoff: _Optional[DiscoveryEntryHandoff] = None
    discovery_request: _Optional[OptionChainDiscoveryRequest] = None
    browser: object = None
    listed_rows: tuple = ()
    listed_row: object = None
    native_verification: tuple = ()
    quote_batch: object = None
    native_quotes: tuple = ()
    provider_references: tuple = ()
    core_structure: object = None
    kernel_request: object = None
    kernel_result: object = None
    reasons: tuple = ()
    quote_reference_temporal_alignment: str = "not_established"
    cross_structure_quote_synchronicity: str = "not_established"

    def __post_init__(self) -> None:
        if type(self.maturity_authority) is not OptionMaturityAuthority:
            raise TypeError("maturity_authority must be OptionMaturityAuthority")
        if self.submissions is not None:
            if type(self.submissions) is not SourceSubmissionBatch:
                raise TypeError("submissions must be SourceSubmissionBatch or None")
            if self.submissions.raw_input is not self.raw_input:
                raise ValueError("submission batch must retain raw input identity")
        _optional_exact("assessment", self.assessment, EventIntelligenceAcceptanceResult)
        if self.assessment is not None:
            if self.submissions is None or self.assessment.submission not in self.submissions.submissions:
                raise ValueError("assessment submission is not retained by batch")
            if not any(
                self.assessment.submission is submission
                for submission in self.submissions.submissions
            ):
                raise ValueError("assessment submission identity is not retained")
        _optional_exact("hypothesis", self.hypothesis, EventUnderlyingHypothesis)
        if self.hypothesis is not None:
            if self.assessment is None or not any(
                self.hypothesis is hypothesis
                for hypothesis in self.assessment.submission.hypotheses
            ):
                raise ValueError("hypothesis identity is not retained by assessment")
        _optional_exact("automated_handoff", self.automated_handoff, DiscoveryEntryHandoff)
        if self.automated_handoff is not None:
            if self.assessment is None or self.automated_handoff.acceptance_result is not self.assessment:
                raise ValueError("handoff must retain assessment identity")
            if self.hypothesis is None or self.automated_handoff.selected_hypothesis is not self.hypothesis:
                raise ValueError("handoff must retain hypothesis identity")
        _optional_exact("discovery_request", self.discovery_request, OptionChainDiscoveryRequest)
        if self.discovery_request is not None:
            if self.automated_handoff is None or self.discovery_request.discovery_entry_handoff is not self.automated_handoff:
                raise ValueError("discovery request must retain handoff identity")
            if self.discovery_request.maturity_authority is not self.maturity_authority:
                raise ValueError("discovery request authority mismatch")
        if self.browser is not None:
            if type(self.browser) is not _futu.FutuExactContractBrowser:
                raise TypeError("browser must be a FutuExactContractBrowser")
            if self.discovery_request is None or self.browser.discovery_evidence.discovery_request is not self.discovery_request:
                raise ValueError("browser must retain discovery request identity")
        if type(self.listed_rows) is not tuple:
            raise TypeError("listed_rows must have exact type tuple")
        if self.browser is None and self.listed_rows:
            raise ValueError("listed rows require a retained Browser")
        if self.browser is not None:
            rows = self.browser.rows
            if any(not _identity_member(row, rows) for row in self.listed_rows):
                raise ValueError("listed rows must retain Browser row identity")
        if self.listed_row is not None and not _identity_member(
            self.listed_row, self.listed_rows
        ):
            raise ValueError("listed_row must retain listed_rows identity")
        if type(self.native_verification) is not tuple:
            raise TypeError("native_verification must have exact type tuple")
        if type(self.native_quotes) is not tuple:
            raise TypeError("native_quotes must have exact type tuple")
        if type(self.provider_references) is not tuple:
            raise TypeError("provider_references must have exact type tuple")
        if self.quote_batch is not None:
            if type(self.quote_batch) is not _futu.FutuBrowserQuoteBatchEvidence:
                raise TypeError(
                    "quote_batch must be a FutuBrowserQuoteBatchEvidence"
                )
            quote_browser = getattr(self.quote_batch, "browser", None)
            if quote_browser is not self.browser:
                raise ValueError("quote batch must retain Browser identity")
            if (
                self.quote_batch.authority
                is not _futu.FutuBrowserQuoteAuthority.INDICATIVE_ONLY
            ):
                raise ValueError("quote batch authority is not indicative-only")
        if self.core_structure is not None:
            if type(self.core_structure) is not _kernel_type("CoreStructure"):
                raise TypeError("core_structure must be CoreStructure or None")
        if self.kernel_request is not None:
            request_type = _kernel_type("CoreResearchRequest")
            if type(self.kernel_request) is not request_type:
                raise TypeError("kernel_request must be CoreResearchRequest")
            if self.core_structure is not None and self.kernel_request.structure is not self.core_structure:
                raise ValueError("kernel request must retain CoreStructure identity")
        if self.kernel_result is not None:
            result_type = _kernel_type("CoreResearchResult")
            if type(self.kernel_result) is not result_type:
                raise TypeError("kernel_result must be CoreResearchResult")
            if self.kernel_request is None or self.kernel_result.request is not self.kernel_request:
                raise ValueError("kernel result must retain request identity")
        if type(self.reasons) is not tuple or any(type(item) is not str for item in self.reasons):
            raise TypeError("reasons must be a tuple of strings")
        if self.quote_reference_temporal_alignment != "not_established":
            raise ValueError("quote-reference temporal alignment is not established")
        if self.cross_structure_quote_synchronicity != "not_established":
            raise ValueError("cross-structure quote synchronicity is not established")


def _validate_kernel_record_identity(request: object, result: object) -> None:
    if type(request) is not _kernel_type("CoreResearchRequest"):
        raise TypeError("request factory must return CoreResearchRequest")
    if type(result) is not _kernel_type("CoreResearchResult"):
        raise TypeError("kernel evaluator must return CoreResearchResult")
    if result.request is not request:
        raise ValueError("kernel result must retain request identity")


@_dataclass(frozen=True)
class CoreCaseRecord:
    case_id: str
    context: CoreCaseContext
    kernel_request: object
    kernel_result: object
    reasons: tuple = ()

    def __post_init__(self) -> None:
        if type(self.case_id) is not str or not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        if type(self.context) is not CoreCaseContext:
            raise TypeError("context must be CoreCaseContext")
        _validate_kernel_record_identity(self.kernel_request, self.kernel_result)
        if self.context.kernel_request is not self.kernel_request or self.context.kernel_result is not self.kernel_result:
            raise ValueError("case record must retain context request/result identity")
        if type(self.reasons) is not tuple or any(type(item) is not str for item in self.reasons):
            raise TypeError("reasons must be a tuple of strings")

    def __getattr__(self, name: str) -> object:
        if name in {
            "raw_input", "submissions", "assessment", "hypothesis",
            "automated_handoff", "discovery_request", "maturity_authority",
            "browser", "listed_rows", "listed_row", "native_verification",
            "quote_batch", "native_quotes", "provider_references",
            "core_structure",
            "quote_reference_temporal_alignment",
            "cross_structure_quote_synchronicity",
        }:
            return getattr(self.context, name)
        raise AttributeError(name)


@_dataclass(frozen=True)
class CoreUnavailableCase:
    case_id: str
    reasons: tuple
    context: _Optional[CoreCaseContext] = None
    failure: object = None

    def __post_init__(self) -> None:
        if type(self.case_id) is not str or not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        if type(self.reasons) is not tuple or not self.reasons or any(
            type(item) is not str for item in self.reasons
        ):
            raise TypeError("reasons must be a non-empty tuple of strings")
        if self.context is not None and type(self.context) is not CoreCaseContext:
            raise TypeError("context must be CoreCaseContext or None")

    @property
    def reason(self) -> str:
        return self.reasons[0]

    def __getattr__(self, name: str) -> object:
        if self.context is not None and name in {
            "raw_input", "submissions", "assessment", "hypothesis",
            "automated_handoff", "discovery_request", "maturity_authority",
            "browser", "listed_rows", "listed_row", "native_verification",
            "quote_batch", "native_quotes", "provider_references",
            "core_structure",
            "quote_reference_temporal_alignment",
            "cross_structure_quote_synchronicity",
        }:
            return getattr(self.context, name)
        raise AttributeError(name)


@_dataclass(frozen=True)
class CoreCaseSet:
    entry_origin: str
    raw_input: object
    submissions: _Optional[SourceSubmissionBatch]
    cases: tuple
    unavailable: tuple
    reasons: tuple = ()

    def __post_init__(self) -> None:
        if type(self.entry_origin) is not str or not self.entry_origin:
            raise ValueError("entry_origin must be a non-empty string")
        if self.submissions is not None and type(self.submissions) is not SourceSubmissionBatch:
            raise TypeError("submissions must be SourceSubmissionBatch or None")
        if self.submissions is not None and self.submissions.raw_input is not self.raw_input:
            raise ValueError("case set must retain raw input identity")
        if type(self.cases) is not tuple or any(type(item) is not CoreCaseRecord for item in self.cases):
            raise TypeError("cases must be a tuple of CoreCaseRecord")
        if type(self.unavailable) is not tuple or any(type(item) is not CoreUnavailableCase for item in self.unavailable):
            raise TypeError("unavailable must be a tuple of CoreUnavailableCase")
        if type(self.reasons) is not tuple or any(type(item) is not str for item in self.reasons):
            raise TypeError("reasons must be a tuple of strings")
        if "LIMIT_EXCEEDED" in self.reasons and self.cases:
            raise ValueError("limit-exceeded case sets must not retain a prefix")
        case_ids = tuple(item.case_id for item in self.cases)
        unavailable_ids = tuple(item.case_id for item in self.unavailable)
        all_ids = case_ids + unavailable_ids
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("case IDs must be unique within one case set")

    @property
    def status(self) -> str:
        if "LIMIT_EXCEEDED" in self.reasons:
            return "LIMIT_EXCEEDED"
        if not self.cases and not self.unavailable and self.reasons:
            return "BLOCKED"
        return "COMPLETE"


StructuredCaseSet = CoreCaseSet


@_dataclass(frozen=True)
class CoreRunResult:
    case_set: CoreCaseSet
    compact: CoreCompactSummary

    def __post_init__(self) -> None:
        if type(self.case_set) is not CoreCaseSet:
            raise TypeError("case_set must be CoreCaseSet")
        if type(self.compact) is not CoreCompactSummary:
            raise TypeError("compact must be CoreCompactSummary")

    @property
    def structured_case_set(self) -> CoreCaseSet:
        return self.case_set


@_dataclass(frozen=True)
class CoreDirectResult:
    raw_input: object
    core_structure: object
    exact_verifications: tuple
    native_quotes: tuple
    provider_references: tuple
    kernel_request: object
    kernel_result: object
    reasons: tuple
    full_report: str
    blocked: bool = False
    maturity_authority: OptionMaturityAuthority = (
        OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH
    )
    hypothesis_maturity_alignment: HypothesisMaturityAlignment = (
        HypothesisMaturityAlignment.NOT_ESTABLISHED
    )
    quote_reference_temporal_alignment: str = "not_established"
    cross_structure_quote_synchronicity: str = "not_established"

    def __post_init__(self) -> None:
        if type(self.core_structure) is not _kernel_type("CoreStructure"):
            raise TypeError("core_structure must be CoreStructure")
        if type(self.exact_verifications) is not tuple:
            raise TypeError("exact_verifications must have exact type tuple")
        if type(self.native_quotes) is not tuple:
            raise TypeError("native_quotes must have exact type tuple")
        if type(self.provider_references) is not tuple:
            raise TypeError("provider_references must have exact type tuple")
        if type(self.reasons) is not tuple or any(type(item) is not str for item in self.reasons):
            raise TypeError("reasons must be a tuple of strings")
        if type(self.full_report) is not str:
            raise TypeError("full_report must be a string")
        if type(self.maturity_authority) is not OptionMaturityAuthority:
            raise TypeError("maturity_authority must be OptionMaturityAuthority")
        if type(self.hypothesis_maturity_alignment) is not HypothesisMaturityAlignment:
            raise TypeError(
                "hypothesis_maturity_alignment must be HypothesisMaturityAlignment"
            )
        if self.quote_reference_temporal_alignment != "not_established":
            raise ValueError("quote-reference temporal alignment is not established")
        if self.cross_structure_quote_synchronicity != "not_established":
            raise ValueError("cross-structure quote synchronicity is not established")
        if self.kernel_request is None:
            if self.kernel_result is not None:
                raise ValueError("kernel result requires kernel request")
        else:
            _validate_kernel_record_identity(self.kernel_request, self.kernel_result)
            if self.kernel_request.structure is not self.core_structure:
                raise ValueError("direct result must retain CoreStructure identity")

    @property
    def report(self) -> str:
        return self.full_report


def _kernel_module():
    from . import core_research

    return core_research


def _kernel_type(name: str):
    try:
        return getattr(_kernel_module(), name)
    except AttributeError:
        raise RuntimeError(f"core_research does not export {name}") from None


def _bridge_method(value: object, name: str):
    method = getattr(value, name, None)
    if not callable(method):
        raise TypeError(f"bridge must provide {name}")
    return method


def _normalize_source_batch(raw_input: object, value: object) -> SourceSubmissionBatch:
    if type(value) is not SourceSubmissionBatch:
        raise TypeError("source producer must return SourceSubmissionBatch")
    if value.raw_input is not raw_input:
        raise ValueError("source producer must retain the exact raw input")
    return value


def _case_context(
    raw_input: object,
    policy: CoreResearchPolicy,
    *,
    submissions: object = None,
    assessment: object = None,
    hypothesis: object = None,
    handoff: object = None,
    discovery_request: object = None,
    browser: object = None,
    listed_rows: tuple = (),
    listed_row: object = None,
    native_verification: tuple = (),
    quote_batch: object = None,
    native_quotes: tuple = (),
    provider_references: tuple = (),
    core_structure: object = None,
    kernel_request: object = None,
    kernel_result: object = None,
    reasons: tuple = (),
) -> CoreCaseContext:
    return CoreCaseContext(
        raw_input=raw_input,
        maturity_authority=policy.maturity_authority,
        submissions=submissions,
        assessment=assessment,
        hypothesis=hypothesis,
        automated_handoff=handoff,
        discovery_request=discovery_request,
        browser=browser,
        listed_rows=listed_rows,
        listed_row=listed_row,
        native_verification=native_verification,
        quote_batch=quote_batch,
        native_quotes=native_quotes,
        provider_references=provider_references,
        core_structure=core_structure,
        kernel_request=kernel_request,
        kernel_result=kernel_result,
        reasons=reasons,
    )


def _unavailable(
    case_id: str,
    reasons: tuple,
    context: _Optional[CoreCaseContext] = None,
    failure: object = None,
) -> CoreUnavailableCase:
    return CoreUnavailableCase(case_id, reasons, context, failure)


def _limited_case_set(
    entry_origin: str,
    raw_input: object,
    submissions: _Optional[SourceSubmissionBatch],
    bound_name: str,
    observed: int,
    limit: int,
) -> CoreRunResult:
    case_set = CoreCaseSet(
        entry_origin,
        raw_input,
        submissions,
        (),
        (),
        ("LIMIT_EXCEEDED", f"{bound_name}:{observed}>{limit}"),
    )
    return CoreRunResult(case_set, compact_summary(case_set))


@_dataclass(frozen=True)
class _PendingBranch:
    raw_input: object
    submissions: SourceSubmissionBatch
    assessment: EventIntelligenceAcceptanceResult
    hypothesis: EventUnderlyingHypothesis
    handoff: DiscoveryEntryHandoff
    discovery_request: OptionChainDiscoveryRequest
    browser: object


def _enumerate_browser(browser: object) -> tuple:
    rows = browser.rows
    mode = browser.discovery_evidence.discovery_request.distribution_mode
    directional = {
        "event_directional_up": "call",
        "extreme_tail_up": "call",
        "event_directional_down": "put",
        "extreme_tail_down": "put",
    }
    mode_value = getattr(mode, "value", mode)
    if mode_value in directional:
        wanted = directional[mode_value]
        structures = tuple((row,) for row in rows if row.option_type == wanted)
        unavailable = tuple(
            ((row,), ("opposite_option_type",))
            for row in rows
            if row.option_type != wanted
        )
        return structures, unavailable
    if mode_value != "bidirectional_expansion":
        raise ValueError("distribution mode is unsupported")
    groups = {}
    for row in rows:
        key = (row.provider_underlying, row.expiration, row.strike, row.lot_size)
        groups.setdefault(key, []).append(row)
    structures = []
    unavailable = []
    consumed = set()
    row_positions = {id(row): index for index, row in enumerate(rows)}
    for row in rows:
        if id(row) in consumed:
            continue
        key = (row.provider_underlying, row.expiration, row.strike, row.lot_size)
        group = groups[key]
        calls = [item for item in group if item.option_type == "call"]
        puts = [item for item in group if item.option_type == "put"]
        if len(calls) > 1 or len(puts) > 1:
            raise ValueError("same-strike browser group is ambiguous")
        if len(calls) == 1 and len(puts) == 1:
            pair = (calls[0], puts[0])
            structures.append(pair)
            consumed.update(id(item) for item in pair)
        else:
            unavailable.append(((row,), ("unpaired_straddle_leg",)))
            consumed.add(id(row))
    structures.sort(
        key=lambda pair: min(row_positions[id(item)] for item in pair)
    )
    unavailable.sort(key=lambda item: row_positions[id(item[0][0])])
    return tuple(structures), tuple(unavailable)


def _factory_request(
    policy: CoreResearchPolicy,
    case_id: str,
    context: CoreCaseContext,
):
    if context.core_structure is None:
        raise ValueError("CoreStructure must be bound before request factory")
    request = policy.request_factory(
        case_id=case_id,
        structure=context.core_structure,
        context=context,
    )
    if type(request) is not _kernel_type("CoreResearchRequest"):
        raise TypeError("request factory must return CoreResearchRequest")
    if request.case_id != case_id:
        raise ValueError("request factory changed the application case_id")
    return request


def _evaluate_request(request: object):
    result = _kernel_module().evaluate_core_research(request)
    _validate_kernel_record_identity(request, result)
    return result


def _option_type_value(value: object) -> object:
    normalized = getattr(value, "value", value)
    return normalized.lower() if isinstance(normalized, str) else normalized


def _verification_key(verification: object):
    reference = getattr(verification, "contract_reference", None)
    return getattr(reference, "contract_key", None)


def _validate_verification_for_row(row: object, verification: object) -> None:
    if type(verification) is not _futu.FutuExactOptionContractVerification:
        raise TypeError(
            "exact verification must be a FutuExactOptionContractVerification"
        )
    key = _verification_key(verification)
    if key is None:
        raise ValueError("exact verification has no contract key")
    underlying_key = getattr(key, "underlying_key", None)
    if getattr(underlying_key, "symbol", None) != row.provider_underlying[3:]:
        raise ValueError("exact verification underlying mismatch")
    if getattr(key, "expiration", None) != row.expiration:
        raise ValueError("exact verification expiration mismatch")
    if _option_type_value(getattr(key, "option_type", None)) != row.option_type:
        raise ValueError("exact verification option type mismatch")
    if getattr(key, "strike", None) != row.strike:
        raise ValueError("exact verification strike mismatch")
    if getattr(key, "contract_multiplier", None) != row.lot_size:
        raise ValueError("exact verification multiplier mismatch")
    if getattr(verification, "provider_identifier", None) != row.provider_identifier:
        raise ValueError("exact verification identifier mismatch")


def _quote_for_row(quote_batch: object, row: object) -> object:
    if type(quote_batch) is not _futu.FutuBrowserQuoteBatchEvidence:
        raise TypeError("quote batch must be a FutuBrowserQuoteBatchEvidence")
    if quote_batch.authority is not _futu.FutuBrowserQuoteAuthority.INDICATIVE_ONLY:
        raise ValueError("quote batch authority is not indicative-only")
    quotes = tuple(getattr(quote_batch, "quotes", ()))
    matches = tuple(
        quote for quote in quotes if getattr(quote, "browser_row", None) is row
    )
    if len(matches) != 1:
        raise ValueError("quote batch row identity mismatch")
    return matches[0]


def _validate_core_leg_bindings(
    context: CoreCaseContext,
    request: object,
    *,
    expected_quantity: _Optional[int],
) -> None:
    structure = request.structure
    if context.core_structure is not None and structure is not context.core_structure:
        raise ValueError("request factory replaced the exact CoreStructure")
    legs = tuple(structure.legs)
    if len(legs) != len(context.native_verification):
        raise ValueError("kernel legs and exact verifications differ")
    for index, (leg, verification) in enumerate(zip(legs, context.native_verification)):
        key = _verification_key(verification)
        underlying_key = getattr(key, "underlying_key", None)
        if getattr(underlying_key, "symbol", None) != getattr(leg, "underlying", None):
            raise ValueError("kernel leg underlying does not retain provider identity")
        if _option_type_value(getattr(key, "option_type", None)) != _option_type_value(getattr(leg, "option_type", None)):
            raise ValueError("kernel leg option type does not retain provider identity")
        for field in ("strike", "expiration"):
            if getattr(leg, field, None) != getattr(key, field, None):
                raise ValueError(f"kernel leg {field} does not retain provider identity")
        if getattr(leg, "contract_multiplier", None) != getattr(key, "contract_multiplier", None):
            raise ValueError("kernel leg multiplier does not retain provider identity")
        if expected_quantity is not None and getattr(leg, "quantity", None) != expected_quantity:
            raise ValueError("kernel leg quantity does not retain caller quantity")
        quote = context.native_quotes[index] if context.native_quotes else None
        if quote is None and context.quote_batch is not None:
            quote = _quote_for_row(context.quote_batch, context.listed_rows[index])
        expected_ask = None
        if quote is not None:
            expected_ask = getattr(quote, "ask_per_underlying_unit", None)
            if expected_ask is None:
                expected_ask = getattr(quote, "ask_price", None)
            if expected_ask is None and type(quote) is _futu.FutuDirectEntryBboEvidence:
                expected_ask = quote.option_bbo.ask_price
        actual_ask = getattr(leg, "ask_per_underlying_unit", None)
        if expected_ask is None:
            if actual_ask is not None:
                raise ValueError("missing provider ask must remain missing in Core")
        elif actual_ask != expected_ask:
            raise ValueError("kernel leg ask does not retain provider quote identity")


def _validate_verification_for_leg(leg: object, verification: object) -> None:
    key = _verification_key(verification)
    if key is None:
        raise ValueError("exact verification has no contract key")
    provider_identifier = getattr(verification, "provider_identifier", None)
    if provider_identifier != getattr(leg, "leg_id", None):
        raise ValueError("exact verification identifier mismatch")
    underlying_key = getattr(key, "underlying_key", None)
    if getattr(underlying_key, "symbol", None) != getattr(leg, "underlying", None):
        raise ValueError("exact verification underlying mismatch")
    if _option_type_value(getattr(key, "option_type", None)) != _option_type_value(getattr(leg, "option_type", None)):
        raise ValueError("exact verification option type mismatch")
    for field in ("strike", "expiration"):
        if getattr(key, field, None) != getattr(leg, field, None):
            raise ValueError(f"exact verification {field} mismatch")
    if getattr(key, "contract_multiplier", None) != getattr(leg, "contract_multiplier", None):
        raise ValueError("exact verification multiplier mismatch")
    if provider_identifier is None:
        raise ValueError("exact verification identifier is missing")


def _provider_references(verifications: tuple, quote_batch: object, native_quotes: tuple) -> tuple:
    refs = []
    for verification in verifications:
        reference = getattr(verification, "contract_reference", None)
        if reference is not None:
            refs.append(reference)
    if quote_batch is not None:
        refs.append(quote_batch)
    refs.extend(item for item in native_quotes if item is not None)
    return tuple(refs)


def _branch_case_id(
    submission_id: str,
    hypothesis_id: str,
    rows: tuple,
) -> str:
    row_id = ":".join(row.provider_identifier for row in rows)
    return f"{submission_id}:{hypothesis_id}:{row_id}"


def _core_structure_from_verified_rows(
    rows: tuple,
    verifications: tuple,
    quote_batch: object,
    *,
    quantity: int,
):
    from .core_research import (
        CoreAskAuthority,
        CoreLeg,
        CoreOptionType,
        CoreProvenance,
        CoreStructure,
    )

    if len(rows) != len(verifications):
        raise ValueError("verified rows and contracts differ")
    legs = []
    for row, verification in zip(rows, verifications):
        if type(verification) is not _futu.FutuExactOptionContractVerification:
            raise TypeError("exact verification has an unsupported type")
        reference = verification.contract_reference
        key = reference.contract_key
        sources = tuple(reference.metadata.source_references)
        if not sources:
            raise ValueError("exact verification has no provider reference")
        ask = None
        if quote_batch is not None:
            quote = _quote_for_row(quote_batch, row)
            if type(quote) is not _futu.FutuBrowserQuoteEvidence:
                raise TypeError("quote batch contains an unsupported quote")
            if quote.availability in {
                _futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
                _futu.FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE,
            }:
                ask = quote.ask_price
        option_type = (
            CoreOptionType.CALL if row.option_type == "call" else CoreOptionType.PUT
        )
        legs.append(
            CoreLeg(
                leg_id=row.provider_identifier,
                underlying=key.underlying_key.symbol,
                currency=key.currency,
                option_type=option_type,
                strike=key.strike,
                expiration=key.expiration,
                quantity=quantity,
                contract_multiplier=key.contract_multiplier,
                ask_per_underlying_unit=ask,
                ask_authority=CoreAskAuthority.INDICATIVE_ONLY,
                description="provider-verified listed option leg",
                provenance=CoreProvenance(
                    source_reference=sources[0],
                    description="Futu exact contract verification reference",
                ),
            )
        )
    structure_source = legs[0].provenance.source_reference
    return CoreStructure(
        legs=tuple(legs),
        description="provider-verified exact Core option structure",
        provenance=CoreProvenance(
            source_reference=structure_source,
            description="Futu exact contract verification references",
        ),
    )


def _run_source_core(
    raw_input: object,
    source_result: object,
    *,
    entry_origin: str,
    market_bridge: object,
    policy: CoreResearchPolicy,
) -> CoreRunResult:
    submissions = _normalize_source_batch(raw_input, source_result)
    bounds = policy.bounds
    if len(submissions.submissions) > bounds.max_submissions:
        return _limited_case_set(
            entry_origin, raw_input, submissions, "submissions",
            len(submissions.submissions), bounds.max_submissions,
        )
    total_hypotheses = sum(len(item.hypotheses) for item in submissions.submissions)
    if total_hypotheses > bounds.max_hypotheses:
        return _limited_case_set(
            entry_origin, raw_input, submissions, "hypotheses",
            total_hypotheses, bounds.max_hypotheses,
        )

    unavailable = []
    enumerated = []
    browser_row_count = 0
    candidate_count = 0
    for submission in submissions.submissions:
        assessment = assess_event_intelligence_submission(submission)
        if assessment.status is not EventIntelligenceAcceptanceStatus.ACCEPTED:
            reasons = ("event_intelligence_not_accepted",) + tuple(
                getattr(issue.code, "value", str(issue.code))
                for issue in assessment.issues
            )
            context = _case_context(
                raw_input, policy, submissions=submissions, assessment=assessment,
                reasons=reasons,
            )
            unavailable.append(
                _unavailable(f"{submission.submission_id}:assessment", reasons, context)
            )
            continue
        for hypothesis in submission.hypotheses:
            case_prefix = f"{submission.submission_id}:{hypothesis.hypothesis_id}"
            try:
                handoff = create_discovery_entry_handoff(assessment, hypothesis)
                discovery_request = create_option_chain_discovery_request(
                    handoff,
                    evaluation_date=policy.evaluation_date,
                    maturity_authority=policy.maturity_authority,
                )
            except Exception as error:
                reasons = ("maturity_request_failure",)
                context = _case_context(
                    raw_input, policy, submissions=submissions, assessment=assessment,
                    hypothesis=hypothesis, reasons=reasons,
                )
                unavailable.append(_unavailable(case_prefix, reasons, context, error))
                continue
            try:
                browser = _bridge_method(market_bridge, "discover_browser")(
                    discovery_request
                )
                if type(browser) is not _futu.FutuExactContractBrowser:
                    raise TypeError("market bridge must return FutuExactContractBrowser")
                if browser.discovery_evidence.discovery_request is not discovery_request:
                    raise ValueError("Browser must retain exact discovery request")
            except Exception as error:
                reasons = ("browser_discovery_failure",)
                context = _case_context(
                    raw_input, policy, submissions=submissions, assessment=assessment,
                    hypothesis=hypothesis, handoff=handoff,
                    discovery_request=discovery_request, reasons=reasons,
                )
                unavailable.append(_unavailable(case_prefix, reasons, context, error))
                continue
            browser_row_count += len(browser.rows)
            if browser_row_count > bounds.max_browser_rows:
                return _limited_case_set(
                    entry_origin, raw_input, submissions, "browser_rows",
                    browser_row_count, bounds.max_browser_rows,
                )
            branch = _PendingBranch(
                raw_input, submissions, assessment, hypothesis, handoff,
                discovery_request, browser,
            )
            structures, non_structures = _enumerate_browser(branch.browser)
            candidate_count += len(structures)
            if candidate_count > bounds.max_cases:
                return _limited_case_set(
                    entry_origin, raw_input, submissions, "cases",
                    candidate_count, bounds.max_cases,
                )
            enumerated.append((branch, structures, non_structures))

    records = []
    for branch, structures, non_structures in enumerated:
        quote_batch = None
        quote_failure = None
        if branch.browser.rows and structures:
            try:
                quote_batch = _bridge_method(market_bridge, "quote_browser")(
                    branch.browser,
                    timeout_seconds=bounds.quote_timeout_seconds,
                )
                if type(quote_batch) is not _futu.FutuBrowserQuoteBatchEvidence:
                    raise TypeError(
                        "market bridge must return FutuBrowserQuoteBatchEvidence"
                    )
                if quote_batch.browser is not branch.browser:
                    raise ValueError("quote batch must retain Browser identity")
                if (
                    quote_batch.authority
                    is not _futu.FutuBrowserQuoteAuthority.INDICATIVE_ONLY
                ):
                    raise ValueError("quote batch authority is not indicative-only")
            except Exception as error:
                quote_failure = error
        for rows, row_reasons in non_structures:
            row_id = ":".join(row.provider_identifier for row in rows)
            context = _case_context(
                branch.raw_input, policy, submissions=branch.submissions,
                assessment=branch.assessment, hypothesis=branch.hypothesis,
                handoff=branch.handoff, discovery_request=branch.discovery_request,
                browser=branch.browser, listed_rows=rows, listed_row=rows[0],
                quote_batch=quote_batch, reasons=row_reasons,
            )
            unavailable.append(
                _unavailable(
                    f"{branch.assessment.submission.submission_id}:"
                    f"{branch.hypothesis.hypothesis_id}:{row_id}",
                    row_reasons, context,
                )
            )
        if quote_failure is not None:
            for rows, _ in structures:
                reasons = ("quote_operation_blocked",)
                context = _case_context(
                    branch.raw_input, policy, submissions=branch.submissions,
                    assessment=branch.assessment, hypothesis=branch.hypothesis,
                    handoff=branch.handoff, discovery_request=branch.discovery_request,
                    browser=branch.browser, listed_rows=rows,
                    listed_row=rows[0] if len(rows) == 1 else None,
                    reasons=reasons,
                )
                unavailable.append(
                    _unavailable(
                        _branch_case_id(
                            branch.assessment.submission.submission_id,
                            branch.hypothesis.hypothesis_id,
                            rows,
                        ),
                        reasons, context, quote_failure,
                    )
                )
            continue
        for rows in structures:
            case_id = _branch_case_id(
                branch.assessment.submission.submission_id,
                branch.hypothesis.hypothesis_id,
                rows,
            )
            verifications = []
            exact_failure = None
            for row in rows:
                try:
                    verification = _bridge_method(market_bridge, "verify_browser_row")(
                        branch.discovery_request, row
                    )
                    _validate_verification_for_row(row, verification)
                    verifications.append(verification)
                except Exception as error:
                    exact_failure = error
                    break
            if exact_failure is not None:
                reasons = ("exact_verification_failure",)
                context = _case_context(
                    branch.raw_input, policy, submissions=branch.submissions,
                    assessment=branch.assessment, hypothesis=branch.hypothesis,
                    handoff=branch.handoff, discovery_request=branch.discovery_request,
                    browser=branch.browser, listed_rows=rows,
                    listed_row=rows[0] if len(rows) == 1 else None,
                    native_verification=tuple(verifications), quote_batch=quote_batch,
                    provider_references=_provider_references(
                        tuple(verifications), quote_batch, ()
                    ),
                    reasons=reasons,
                )
                unavailable.append(_unavailable(case_id, reasons, context, exact_failure))
                continue
            verifications_tuple = tuple(verifications)
            provider_refs = _provider_references(verifications_tuple, quote_batch, ())
            try:
                core_structure = _core_structure_from_verified_rows(
                    rows,
                    verifications_tuple,
                    quote_batch,
                    quantity=policy.generated_quantity,
                )
            except Exception as error:
                reasons = ("core_structure_failure",)
                context = _case_context(
                    branch.raw_input, policy, submissions=branch.submissions,
                    assessment=branch.assessment, hypothesis=branch.hypothesis,
                    handoff=branch.handoff, discovery_request=branch.discovery_request,
                    browser=branch.browser, listed_rows=rows,
                    listed_row=rows[0] if len(rows) == 1 else None,
                    native_verification=verifications_tuple,
                    quote_batch=quote_batch, provider_references=provider_refs,
                    reasons=reasons,
                )
                unavailable.append(_unavailable(case_id, reasons, context, error))
                continue
            context = _case_context(
                branch.raw_input, policy, submissions=branch.submissions,
                assessment=branch.assessment, hypothesis=branch.hypothesis,
                handoff=branch.handoff, discovery_request=branch.discovery_request,
                browser=branch.browser, listed_rows=rows,
                listed_row=rows[0] if len(rows) == 1 else None,
                native_verification=verifications_tuple, quote_batch=quote_batch,
                provider_references=provider_refs, core_structure=core_structure,
            )
            try:
                request = _factory_request(policy, case_id, context)
                _validate_core_leg_bindings(
                    context, request, expected_quantity=policy.generated_quantity
                )
                result = _evaluate_request(request)
                context = _replace(
                    context, kernel_request=request, kernel_result=result
                )
                records.append(CoreCaseRecord(case_id, context, request, result, ()))
            except Exception as error:
                reasons = ("kernel_case_failure",)
                context = _replace(context, reasons=reasons)
                unavailable.append(_unavailable(case_id, reasons, context, error))
    case_set = CoreCaseSet(
        entry_origin, raw_input, submissions, tuple(records), tuple(unavailable),
        tuple(reason for item in unavailable for reason in item.reasons),
    )
    return CoreRunResult(case_set, compact_summary(case_set))


def _blocked_run(
    entry_origin: str,
    raw_input: object,
    policy: CoreResearchPolicy,
    reason: str,
) -> CoreRunResult:
    case_set = CoreCaseSet(entry_origin, raw_input, None, (), (), (reason,))
    return CoreRunResult(case_set, compact_summary(case_set))


def run_world_core(
    raw_request: object,
    *,
    source_producer: object,
    market_bridge: object,
    policy: CoreResearchPolicy,
) -> CoreRunResult:
    """Run every accepted hypothesis from one injected world producer."""

    if type(policy) is not CoreResearchPolicy:
        raise TypeError("policy must be CoreResearchPolicy")
    if source_producer is None:
        return _blocked_run("WORLD", raw_request, policy, "missing_source_producer")
    if not callable(source_producer):
        raise TypeError("source_producer must be callable")
    source_result = source_producer(raw_request)
    return _run_source_core(
        raw_request, source_result, entry_origin="WORLD",
        market_bridge=market_bridge, policy=policy,
    )


def run_event_core(
    user_input: UserEventInput,
    *,
    grounder: object,
    market_bridge: object,
    policy: CoreResearchPolicy,
) -> CoreRunResult:
    """Run every accepted hypothesis from one injected UserEventInput grounder."""

    if type(user_input) is not UserEventInput:
        raise TypeError("user_input must be UserEventInput")
    if type(policy) is not CoreResearchPolicy:
        raise TypeError("policy must be CoreResearchPolicy")
    if grounder is None:
        return _blocked_run("EVENT", user_input, policy, "missing_grounder")
    if not callable(grounder):
        raise TypeError("grounder must be callable")
    source_result = grounder(user_input)
    return _run_source_core(
        user_input, source_result, entry_origin="EVENT",
        market_bridge=market_bridge, policy=policy,
    )


def _direct_structure(value: object) -> object:
    request_type = _kernel_type("CoreResearchRequest")
    structure_type = _kernel_type("CoreStructure")
    if type(value) is request_type:
        return value.structure
    if type(value) is structure_type:
        return value
    raise TypeError("direct input must be CoreStructure or CoreResearchRequest")


def _make_direct_result(
    *,
    raw_input: object,
    structure: object,
    exact_verifications: tuple,
    native_quotes: tuple,
    provider_references: tuple,
    kernel_request: object,
    kernel_result: object,
    reasons: tuple,
    blocked: bool,
    policy: CoreResearchPolicy,
) -> CoreDirectResult:
    direct = CoreDirectResult(
        raw_input=raw_input,
        core_structure=structure,
        exact_verifications=exact_verifications,
        native_quotes=native_quotes,
        provider_references=provider_references,
        kernel_request=kernel_request,
        kernel_result=kernel_result,
        reasons=reasons,
        full_report="",
        blocked=blocked,
        maturity_authority=policy.maturity_authority,
        hypothesis_maturity_alignment=HypothesisMaturityAlignment.NOT_ESTABLISHED,
        quote_reference_temporal_alignment="not_established",
        cross_structure_quote_synchronicity="not_established",
    )
    return _replace(direct, full_report=report(direct))


def _call_exact_bridge(bridge: object, leg: object):
    return _bridge_method(bridge, "verify_exact_leg")(leg)


def _native_quote_for(
    source: object,
    verification: object,
    timeout_seconds: float,
) -> object:
    if type(source) is FutuNativeDirectAskEvidence:
        if source.provider_identifier != verification.provider_identifier:
            raise ValueError("native quote identifier mismatch")
        if source.receipt.provider_identifier != verification.provider_identifier:
            raise ValueError("native quote receipt identifier mismatch")
        if source.quote_authority is not NativeQuoteAuthority.INDICATIVE_ONLY:
            raise ValueError("native quote authority is not indicative-only")
        return source
    if type(source) is _futu.FutuDirectEntryBboEvidence:
        option_bbo = source.option_bbo
        if option_bbo.provider_identifier != verification.provider_identifier:
            raise ValueError("native quote identifier mismatch")
        if source.contract_verification is not verification:
            raise ValueError("native quote verification identity mismatch")
        return source
    raise TypeError("direct quote evidence has an unsupported type")


def _direct_quote_source(source: object, index: int, count: int) -> object:
    if source is None:
        return None
    if type(source) in {
        FutuNativeDirectAskEvidence,
        _futu.FutuDirectEntryBboEvidence,
    }:
        if count != 1 or index != 0:
            raise ValueError("direct quote evidence must retain every leg")
        return source
    if type(source) is tuple:
        if len(source) != count:
            raise ValueError("direct quote evidence must retain every leg")
        item = source[index]
        if type(item) not in {
            FutuNativeDirectAskEvidence,
            _futu.FutuDirectEntryBboEvidence,
        }:
            raise TypeError("direct quote evidence has an unsupported type")
        return item
    raise TypeError("direct quote evidence has an unsupported type")


def _direct_ask(source: object) -> _Optional[object]:
    if type(source) is FutuNativeDirectAskEvidence:
        return source.ask_per_underlying_unit
    if type(source) is _futu.FutuDirectEntryBboEvidence:
        return source.option_bbo.ask_price
    raise TypeError("direct quote evidence has an unsupported type")


def _core_structure_from_direct_legs(
    structure: object,
    verifications: tuple,
    native_quotes: tuple,
):
    from .core_research import (
        CoreAskAuthority,
        CoreLeg,
        CoreOptionType,
        CoreProvenance,
        CoreStructure,
    )

    if type(structure) is not CoreStructure:
        raise TypeError("direct structure must be a CoreStructure")
    source_legs = tuple(structure.legs)
    if len(source_legs) != len(verifications) or len(verifications) != len(native_quotes):
        raise ValueError("direct structure, verification, and quote counts differ")
    legs = []
    for source_leg, verification, native_quote in zip(
        source_legs, verifications, native_quotes
    ):
        if type(verification) is not _futu.FutuExactOptionContractVerification:
            raise TypeError(
                "exact verification must be a FutuExactOptionContractVerification"
            )
        reference = verification.contract_reference
        key = reference.contract_key
        sources = tuple(reference.metadata.source_references)
        if not sources:
            raise ValueError("exact verification has no provider reference")
        option_type = (
            CoreOptionType.CALL
            if key.option_type == "call"
            else CoreOptionType.PUT
        )
        legs.append(
            CoreLeg(
                leg_id=verification.provider_identifier,
                underlying=key.underlying_key.symbol,
                currency=key.currency,
                option_type=option_type,
                strike=key.strike,
                expiration=key.expiration,
                quantity=source_leg.quantity,
                contract_multiplier=key.contract_multiplier,
                ask_per_underlying_unit=_direct_ask(native_quote),
                ask_authority=CoreAskAuthority.INDICATIVE_ONLY,
                description=source_leg.description,
                provenance=CoreProvenance(
                    source_reference=sources[0],
                    description="Futu exact contract verification reference",
                ),
            )
        )
    structure_sources = tuple(leg.provenance.source_reference for leg in legs)
    return CoreStructure(
        legs=tuple(legs),
        description=structure.description,
        provenance=CoreProvenance(
            source_reference=structure_sources[0],
            description="Futu exact contract verification references",
        ),
    )


def run_direct_core(
    core_structure_or_leg_request: object,
    *,
    exact_provider_bridge: object,
    direct_quote_evidence: object,
    policy: CoreResearchPolicy,
) -> CoreDirectResult:
    """Verify exact legs, retain native option asks, and evaluate the same Core."""

    if type(policy) is not CoreResearchPolicy:
        raise TypeError("policy must be CoreResearchPolicy")
    structure = _direct_structure(core_structure_or_leg_request)
    raw_input = core_structure_or_leg_request
    verifications = []
    native_quotes = []
    reasons = []
    blocked = False
    if policy.maturity_authority is not OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH:
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=(),
            native_quotes=(),
            provider_references=(),
            kernel_request=None,
            kernel_result=None,
            reasons=("direct_maturity_authority_not_neutral",),
            blocked=True,
            policy=policy,
        )
    try:
        dtes = tuple(
            (leg.expiration - policy.evaluation_date).days
            for leg in tuple(structure.legs)
        )
    except Exception:
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=(),
            native_quotes=(),
            provider_references=(),
            kernel_request=None,
            kernel_result=None,
            reasons=("direct_maturity_policy_failure",),
            blocked=True,
            policy=policy,
        )
    if any(dte < 30 or dte > 150 for dte in dtes):
        reasons = ("direct_maturity_out_of_bounds",)
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=(),
            native_quotes=(),
            provider_references=(),
            kernel_request=None,
            kernel_result=None,
            reasons=reasons,
            blocked=True,
            policy=policy,
        )
    for leg in tuple(structure.legs):
        try:
            verification = _call_exact_bridge(exact_provider_bridge, leg)
            key = _verification_key(verification)
            _validate_verification_for_leg(leg, verification)
            verifications.append(verification)
        except Exception:
            reasons.append("exact_verification_failure")
            blocked = True
            break
    if blocked:
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=tuple(verifications),
            native_quotes=tuple(native_quotes),
            provider_references=_provider_references(
                tuple(verifications), None, tuple(native_quotes)
            ),
            kernel_request=None,
            kernel_result=None,
            reasons=tuple(dict.fromkeys(reasons)),
            blocked=True,
            policy=policy,
        )
    for verification in tuple(verifications):
        try:
            index = len(native_quotes)
            source = _direct_quote_source(
                direct_quote_evidence, index, len(verifications)
            )
            if source is None:
                source = _bridge_method(exact_provider_bridge, "quote_direct")(
                    verification,
                    timeout_seconds=policy.bounds.quote_timeout_seconds,
                )
            native_quotes.append(
                _native_quote_for(
                    source, verification, policy.bounds.quote_timeout_seconds
                )
            )
        except Exception as error:
            reasons.append("quote_operation_blocked")
            blocked = True
            break
    if blocked:
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=tuple(verifications),
            native_quotes=tuple(native_quotes),
            provider_references=_provider_references(
                tuple(verifications), None, tuple(native_quotes)
            ),
            kernel_request=None,
            kernel_result=None,
            reasons=tuple(dict.fromkeys(reasons)),
            blocked=True,
            policy=policy,
        )
    if any(item is None for item in native_quotes):
        reasons.append("missing_direct_quote_evidence")
    try:
        app_structure = _core_structure_from_direct_legs(
            structure, tuple(verifications), tuple(native_quotes)
        )
    except Exception:
        return _make_direct_result(
            raw_input=raw_input,
            structure=structure,
            exact_verifications=tuple(verifications),
            native_quotes=tuple(native_quotes),
            provider_references=_provider_references(
                tuple(verifications), None, tuple(native_quotes)
            ),
            kernel_request=None,
            kernel_result=None,
            reasons=tuple(dict.fromkeys(reasons + ["core_structure_failure"])),
            blocked=True,
            policy=policy,
        )
    context = _case_context(
        raw_input, policy, native_verification=tuple(verifications),
        native_quotes=tuple(native_quotes), core_structure=app_structure,
        provider_references=_provider_references(
            tuple(verifications), None, tuple(native_quotes)
        ), reasons=tuple(reasons),
    )
    case_id = "direct:" + ":".join(
        str(getattr(item, "provider_identifier")) for item in verifications
    )
    try:
        request = _factory_request(policy, case_id, context)
        _validate_core_leg_bindings(context, request, expected_quantity=None)
        result = _evaluate_request(request)
        context = _replace(context, kernel_request=request, kernel_result=result)
        return _make_direct_result(
            raw_input=raw_input,
            structure=app_structure,
            exact_verifications=tuple(verifications),
            native_quotes=tuple(native_quotes),
            provider_references=context.provider_references,
            kernel_request=request,
            kernel_result=result,
            reasons=tuple(reasons),
            blocked=False,
            policy=policy,
        )
    except Exception:
        reasons.append("kernel_case_failure")
        return _make_direct_result(
            raw_input=raw_input,
            structure=app_structure,
            exact_verifications=tuple(verifications),
            native_quotes=tuple(native_quotes),
            provider_references=context.provider_references,
            kernel_request=None,
            kernel_result=None,
            reasons=tuple(dict.fromkeys(reasons)),
            blocked=True,
            policy=policy,
        )
