"""Deterministic transformations from reviewed market data to research records."""

import datetime
import decimal
import math
from dataclasses import dataclass
from typing import Tuple

from .evidence import OptionLeg, OptionStructure
from .market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketDataBindingReference,
    MarketDataCategory,
    MarketDataFreshnessPolicy,
    MarketDataRelationshipAssessment,
    MarketDataRelationshipGroup,
    MarketDataRelationshipGroupKind,
    MarketDataRelationshipGroupMember,
    MarketDataRelationshipRequest,
    MarketDataRelationshipRole,
    MarketDataRelationshipSelection,
    MarketDataSelectionStatus,
    MarketDataSnapshotTimingAssessment,
    NormalizationQualityFlag,
    OptionContractKey,
    OptionOpenInterestObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    SelectedFreshMarketDataBinding,
    SourceQualityFlag,
    canonicalize_lineage_parameters,
    semantic_observation_key,
)
from .report import StructureLiquidity


__all__ = (
    "StructureLiquidityTransformationResult",
    "transform_structure_liquidity",
)


_REQUIRED_ROLES = (
    MarketDataRelationshipRole.OPTION_QUOTE,
    MarketDataRelationshipRole.OPTION_VOLUME,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
)
_RECORD_TYPE_BY_ROLE = {
    MarketDataRelationshipRole.OPTION_QUOTE: OptionQuoteObservation,
    MarketDataRelationshipRole.OPTION_VOLUME: OptionVolumeObservation,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
        OptionOpenInterestObservation
    ),
}
_FRESHNESS_CATEGORY_BY_ROLE = {
    MarketDataRelationshipRole.OPTION_QUOTE: MarketDataCategory.QUOTE,
    MarketDataRelationshipRole.OPTION_VOLUME: MarketDataCategory.ACTIVITY,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
        MarketDataCategory.ACTIVITY
    ),
}
_SELECTED_CORRECTION_REASONS = (
    CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
    CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
)
_QUOTE_METHODOLOGY = (
    "exact selected option quotes scaled by quantity and contract multiplier"
)


@dataclass(frozen=True)
class StructureLiquidityTransformationResult:
    record: StructureLiquidity
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not StructureLiquidity:
            raise TypeError("record must have exact type StructureLiquidity")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")


def _validate_calculation_id(value: object) -> str:
    if type(value) is not str:
        raise TypeError("calculation_id must have exact type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError("calculation_id must not be empty")
    return normalized


def _validate_structure(value: object) -> OptionStructure:
    if type(value) is not OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    return value


def _validate_relationship_selection(
    value: object,
) -> MarketDataRelationshipSelection:
    if type(value) is not MarketDataRelationshipSelection:
        raise TypeError(
            "relationship_selection must have exact type "
            "MarketDataRelationshipSelection"
        )
    return value


def _normalize_calculated_at(value: object) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        return value.astimezone(datetime.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("calculated_at must be representable in UTC") from error


def _validate_selection_status(
    selection: MarketDataRelationshipSelection,
) -> None:
    if selection.status is not MarketDataSelectionStatus.SELECTED:
        raise ValueError("relationship selection must have selected status")


def _resolve_selected_candidate(
    selection: MarketDataRelationshipSelection,
) -> MarketDataRelationshipAssessment:
    selected = selection.selected_candidate
    if selected is None:
        raise ValueError("relationship selection must have one selected candidate")
    if type(selected) is not MarketDataRelationshipAssessment:
        raise TypeError(
            "selected candidate must have exact type "
            "MarketDataRelationshipAssessment"
        )
    return selected


def _validate_selected_shape(
    selected: MarketDataRelationshipAssessment,
    structure: OptionStructure,
) -> Tuple[
    Tuple[MarketDataRelationshipGroup, ...],
    Tuple[SelectedFreshMarketDataBinding, ...],
]:
    if type(selected.request) is not MarketDataRelationshipRequest:
        raise TypeError(
            "selected request must have exact type MarketDataRelationshipRequest"
        )
    if type(selected.timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "selected timing assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )
    groups = selected.request.groups
    if type(groups) is not tuple:
        raise TypeError("selected request groups must have exact type tuple")
    if len(groups) != len(structure.legs):
        raise ValueError("selected assessment must have one group per structure leg")

    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "every selected group must have exact type "
                "MarketDataRelationshipGroup"
            )
    for group in groups:
        if type(group.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError(
                "group_kind must have exact type MarketDataRelationshipGroupKind"
            )
        if (
            group.group_kind
            is not MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1
        ):
            raise ValueError("every selected group must be an option activity group")
    for group in groups:
        if type(group.members) is not tuple:
            raise TypeError("selected group members must have exact type tuple")
        for member in group.members:
            if type(member) is not MarketDataRelationshipGroupMember:
                raise TypeError(
                    "every selected member must have exact type "
                    "MarketDataRelationshipGroupMember"
                )
    for group in groups:
        for member in group.members:
            if type(member.role) is not MarketDataRelationshipRole:
                raise TypeError(
                    "member role must have exact type MarketDataRelationshipRole"
                )
            if type(member.reference) is not MarketDataBindingReference:
                raise TypeError(
                    "member reference must have exact type "
                    "MarketDataBindingReference"
                )
    for group in groups:
        roles = tuple(member.role for member in group.members)
        if (
            len(roles) != len(_REQUIRED_ROLES)
            or set(roles) != set(_REQUIRED_ROLES)
        ):
            raise ValueError(
                "option activity group must contain exactly quote, volume, "
                "and open-interest roles"
            )

    bindings = selected.timing_assessment.bindings
    if type(bindings) is not tuple:
        raise TypeError("selected timing bindings must have exact type tuple")
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every selected binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
    for binding in bindings:
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError(
                "correction_selection must have exact type CorrectionSelection"
            )
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError(
                "freshness_assessment must have exact type FreshnessAssessment"
            )
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must have exact type MarketDataFreshnessPolicy"
            )
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError(
                "freshness_context must have exact type FreshnessContext"
            )
    if len(bindings) != len(groups) * len(_REQUIRED_ROLES):
        raise ValueError(
            "selected assessment must have exactly one binding per required role"
        )
    return groups, bindings


def _resolve_selected_objects(
    groups: Tuple[MarketDataRelationshipGroup, ...],
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> tuple:
    """Resolve all selected objects using record IDs and no proof semantics."""

    entries = []
    for group in groups:
        for member in group.members:
            selected_id = member.reference.selected_record_id
            matches = tuple(
                binding
                for binding in bindings
                if getattr(
                    getattr(binding, "correction_selection", None),
                    "selected_record_id",
                    None,
                )
                == selected_id
            )
            if len(matches) != 1:
                raise ValueError(
                    "member selected record ID must identify exactly one binding"
                )
            binding = matches[0]
            candidates = binding.candidate_records
            if type(candidates) is not tuple or not candidates:
                raise ValueError("binding has malformed candidate_records")
            selected_matches = tuple(
                candidate
                for candidate in candidates
                if getattr(
                    getattr(candidate, "metadata", None),
                    "record_id",
                    None,
                )
                == getattr(
                    binding.correction_selection,
                    "selected_record_id",
                    None,
                )
            )
            if len(selected_matches) != 1:
                raise ValueError(
                    "binding correction selected ID must resolve exactly one "
                    "candidate object"
                )
            entries.append((group, member, binding, selected_matches[0]))
    return tuple(entries)


def _validate_selected_record_types(entries: tuple) -> None:
    """Complete exact selected-record typing before any proof integrity."""

    for _group, member, _binding, record in entries:
        expected_type = _RECORD_TYPE_BY_ROLE[member.role]
        if type(record) is not expected_type:
            raise TypeError(
                f"{member.role.value} selected record must have exact type "
                f"{expected_type.__name__}"
            )


def _validate_candidate_universe(
    binding: SelectedFreshMarketDataBinding,
    selection: CorrectionSelection,
    selected_record: object,
) -> None:
    candidates = binding.candidate_records
    if type(candidates) is not tuple or not candidates:
        raise ValueError("binding candidate_records must be a nonempty exact tuple")
    candidate_ids = tuple(
        _validate_retained_id(
            "candidate metadata record_id",
            getattr(getattr(candidate, "metadata", None), "record_id", None),
        )
        for candidate in candidates
    )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("binding candidate record IDs must be unique")
    if type(selection.candidate_record_ids) is not tuple:
        raise TypeError("candidate_record_ids must have exact type tuple")
    selection_candidate_ids = tuple(
        _validate_retained_id("candidate_record_id", record_id)
        for record_id in selection.candidate_record_ids
    )
    if (
        tuple(sorted(candidate_ids)) != selection_candidate_ids
    ):
        raise ValueError(
            "binding candidate record IDs do not match correction selection"
        )
    selected_id = _validate_retained_id(
        "correction selected_record_id", selection.selected_record_id
    )
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate.metadata.record_id == selected_id
    )
    if len(matches) != 1 or matches[0] is not selected_record:
        raise ValueError(
            "correction selected ID must identify the exact selected object"
        )
    selected_object_id = _validate_retained_id(
        "selected record metadata record_id",
        selected_record.metadata.record_id,
    )
    if selected_object_id != selected_id:
        raise ValueError("selected object record ID does not match correction")


def _validate_retained_id(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact type str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be canonical and nonempty")
    return value


def _validate_correction_proof(
    binding: SelectedFreshMarketDataBinding,
    selection: CorrectionSelection,
) -> None:
    if type(selection.status) is not CorrectionSelectionStatus:
        raise ValueError(
            "correction status must have exact type CorrectionSelectionStatus"
        )
    if selection.status is not CorrectionSelectionStatus.SELECTED:
        raise ValueError("binding correction selection must be selected")
    reasons = selection.reason_codes
    if (
        type(reasons) is not tuple
        or len(reasons) != 1
        or type(reasons[0]) is not CorrectionSelectionReasonCode
        or reasons[0] not in _SELECTED_CORRECTION_REASONS
    ):
        raise ValueError(
            "binding correction selection must have one selected reason"
        )
    candidate_count = len(binding.candidate_records)
    if (
        reasons[0] is CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED
        and candidate_count != 1
    ):
        raise ValueError("only-candidate correction reason requires one candidate")
    if (
        reasons[0]
        is CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED
        and candidate_count < 2
    ):
        raise ValueError(
            "dominating-revision correction reason requires multiple candidates"
        )


def _validate_freshness_proof(
    role: MarketDataRelationshipRole,
    binding: SelectedFreshMarketDataBinding,
    selected_record: object,
) -> None:
    freshness = binding.freshness_assessment
    policy = binding.freshness_policy
    context = binding.freshness_context
    selection = binding.correction_selection
    if type(freshness.status) is not FreshnessStatus:
        raise ValueError("freshness status must have exact type FreshnessStatus")
    if type(freshness.category) is not MarketDataCategory:
        raise ValueError(
            "freshness category must have exact type MarketDataCategory"
        )
    reasons = freshness.reason_codes
    if (
        type(reasons) is not tuple
        or any(type(reason) is not FreshnessReasonCode for reason in reasons)
    ):
        raise ValueError(
            "freshness reasons must be exact FreshnessReasonCode values"
        )
    if not (
        freshness.status is FreshnessStatus.FRESH
        and reasons == (FreshnessReasonCode.FRESH_WITHIN_POLICY,)
    ):
        raise ValueError("binding freshness assessment must be exactly fresh")
    if freshness.category is not _FRESHNESS_CATEGORY_BY_ROLE[role]:
        raise ValueError("freshness assessment has the wrong market-data category")
    record_id = _validate_retained_id(
        "selected record metadata record_id",
        selected_record.metadata.record_id,
    )
    freshness_record_id = _validate_retained_id(
        "freshness record_id", freshness.record_id
    )
    correction_record_id = _validate_retained_id(
        "correction selected_record_id", selection.selected_record_id
    )
    if not (
        freshness_record_id == correction_record_id == record_id
    ):
        raise ValueError(
            "selected record IDs do not agree across retained proof sidecars"
        )
    freshness_policy_id = _validate_retained_id(
        "freshness policy_id", freshness.policy_id
    )
    retained_policy_id = _validate_retained_id(
        "retained policy_id", policy.policy_id
    )
    freshness_policy_version = _validate_retained_id(
        "freshness policy_version", freshness.policy_version
    )
    retained_policy_version = _validate_retained_id(
        "retained policy_version", policy.policy_version
    )
    if (
        freshness_policy_id != retained_policy_id
        or freshness_policy_version != retained_policy_version
        or freshness.evaluated_at != context.evaluation_at
    ):
        raise ValueError(
            "freshness assessment does not match retained policy and context"
        )
    if selection.evaluated_at > context.evaluation_at:
        raise ValueError(
            "correction selection must not follow freshness evaluation"
        )


def _validate_semantic_proof(
    member: MarketDataRelationshipGroupMember,
    binding: SelectedFreshMarketDataBinding,
    selected_record: object,
) -> None:
    selection = binding.correction_selection
    expected = semantic_observation_key(selected_record)
    if not (
        binding.semantic_observation_key
        == selection.semantic_observation_key
        == member.reference.semantic_observation_key
        == expected
    ):
        raise ValueError("retained semantic observation keys do not agree")
    if any(
        semantic_observation_key(candidate) != expected
        for candidate in binding.candidate_records
    ):
        raise ValueError(
            "every retained correction candidate must share one semantic key"
        )


def _validate_proof_integrity(
    entries: tuple,
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> None:
    """Validate complete retained proof state without replaying proof layers."""

    for _group, member, binding, record in entries:
        reference_record_id = _validate_retained_id(
            "binding reference selected_record_id",
            member.reference.selected_record_id,
        )
        selection = binding.correction_selection
        _validate_candidate_universe(binding, selection, record)
        _validate_correction_proof(binding, selection)
        _validate_freshness_proof(member.role, binding, record)
        _validate_semantic_proof(member, binding, record)
        if reference_record_id != record.metadata.record_id:
            raise ValueError("binding reference selected ID does not match record")

    referenced_ids = tuple(id(entry[2]) for entry in entries)
    if len(set(referenced_ids)) != len(referenced_ids):
        raise ValueError("a selected binding must not be consumed more than once")
    if set(referenced_ids) != {id(binding) for binding in bindings}:
        raise ValueError("every selected binding must be referenced exactly once")
    selected_record_ids = tuple(
        _validate_retained_id(
            "consumed selected record_id", entry[3].metadata.record_id
        )
        for entry in entries
    )
    if len(set(selected_record_ids)) != len(selected_record_ids):
        raise ValueError("consumed selected record IDs must be unique")


def _contract_order_key(contract_key: OptionContractKey) -> tuple:
    underlying = contract_key.underlying_key
    return (
        underlying.symbol,
        underlying.listing_mic or "",
        underlying.security_type.value,
        underlying.currency,
        contract_key.expiration,
        contract_key.option_type,
        contract_key.strike,
        contract_key.contract_multiplier,
        contract_key.currency,
        contract_key.deliverable_id or "",
    )


def _matching_leg(
    contract_key: OptionContractKey,
    legs: Tuple[OptionLeg, ...],
) -> OptionLeg:
    matches = tuple(
        leg
        for leg in legs
        if (
            contract_key.underlying_key.symbol == leg.underlying
            and contract_key.option_type == leg.option_type
            and contract_key.expiration == leg.expiration
            and contract_key.strike == decimal.Decimal(str(leg.strike))
            and contract_key.contract_multiplier == leg.contract_multiplier
        )
    )
    if len(matches) != 1:
        raise ValueError("selected contract must match exactly one structure leg")
    return matches[0]


def _match_structure_legs(
    entries: tuple,
    structure: OptionStructure,
) -> tuple:
    grouped = []
    for group in tuple(dict.fromkeys(entry[0].group_id for entry in entries)):
        group_entries = tuple(
            entry for entry in entries if entry[0].group_id == group
        )
        records = {entry[1].role: entry[3] for entry in group_entries}
        bindings = {entry[1].role: entry[2] for entry in group_entries}
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        if type(quote.contract_key) is not OptionContractKey:
            raise TypeError("quote must retain an exact OptionContractKey")
        leg = _matching_leg(quote.contract_key, structure.legs)
        grouped.append((quote.contract_key, leg, bindings, records))
    leg_ids = tuple(id(item[1]) for item in grouped)
    if (
        len(set(leg_ids)) != len(leg_ids)
        or set(leg_ids) != {id(leg) for leg in structure.legs}
    ):
        raise ValueError("activity groups must cover structure legs one-to-one")
    return tuple(grouped)


def _validate_contract_sessions(matched: tuple) -> datetime.date:
    session_dates = set()
    for contract_key, _leg, _bindings, records in matched:
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[MarketDataRelationshipRole.OPTION_OPEN_INTEREST]
        if (
            type(volume.contract_key) is not OptionContractKey
            or type(open_interest.contract_key) is not OptionContractKey
        ):
            raise TypeError("activity records must retain exact OptionContractKey")
        if (
            volume.contract_key != contract_key
            or open_interest.contract_key != contract_key
        ):
            raise ValueError("activity group records must share one contract key")
        if quote.session_date != volume.session_date:
            raise ValueError("quote and volume must share one session date")
        session_dates.add(quote.session_date)
        if quote.session_date > contract_key.expiration:
            raise ValueError("activity session must not follow contract expiration")
    if len(session_dates) != 1:
        raise ValueError("all quote and volume records must share one session date")
    return next(iter(session_dates))


def _validate_required_values(matched: tuple) -> Tuple[int, int]:
    for _contract_key, _leg, _bindings, records in matched:
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[MarketDataRelationshipRole.OPTION_OPEN_INTEREST]
        if volume.is_session_complete is not True:
            raise ValueError("every consumed volume session must be complete")
        if (
            type(quote.bid_premium) is not decimal.Decimal
            or not quote.bid_premium.is_finite()
            or quote.bid_premium < 0
            or type(quote.ask_premium) is not decimal.Decimal
            or not quote.ask_premium.is_finite()
            or quote.ask_premium <= 0
            or type(volume.cumulative_volume) is not int
            or type(volume.cumulative_volume) is bool
            or volume.cumulative_volume < 0
            or type(open_interest.open_interest) is not int
            or type(open_interest.open_interest) is bool
            or open_interest.open_interest < 0
        ):
            raise ValueError("every consumed numerical value must be valid")
    minimum_volume = min(
        item[3][MarketDataRelationshipRole.OPTION_VOLUME].cumulative_volume
        for item in matched
    )
    minimum_open_interest = min(
        item[3][MarketDataRelationshipRole.OPTION_OPEN_INTEREST].open_interest
        for item in matched
    )
    return minimum_volume, minimum_open_interest


def _exact_decimal_precision(terms: tuple) -> int:
    """Return a dynamic bound for exact scaled products and their sum."""

    nonzero_terms = tuple(
        term for term in terms if not term[0].is_zero()
    )
    if not nonzero_terms:
        return 4
    minimum_exponent = min(
        value.as_tuple().exponent for value, _scale in nonzero_terms
    )
    aligned_product_bounds = []
    for value, scale in nonzero_terms:
        coefficient_digits = len(value.as_tuple().digits)
        # One binary bit per decimal digit is a conservative bound and avoids
        # any string conversion (including Python's large-int string limit).
        scale_digits = max(1, scale.bit_length())
        exponent_shift = value.as_tuple().exponent - minimum_exponent
        aligned_product_bounds.append(
            coefficient_digits + scale_digits + exponent_shift
        )
    carry_digits = max(1, len(nonzero_terms).bit_length())
    return max(aligned_product_bounds) + carry_digits + 2


def _integer_decimal_digits(value: int) -> int:
    """Return exact base-10 digit count without converting the integer to text."""

    if value == 0:
        return 1
    estimate = (
        ((value.bit_length() - 1) * 30103) // 100000
    ) + 1
    power = 10 ** (estimate - 1)
    while value < power:
        estimate -= 1
        power //= 10
    while value >= power * 10:
        estimate += 1
        power *= 10
    return estimate


def _exact_product_bounds(
    value: decimal.Decimal,
    scale: int,
) -> Tuple[int, int]:
    decimal_tuple = value.as_tuple()
    coefficient = 0
    for digit in decimal_tuple.digits:
        coefficient = coefficient * 10 + digit
    product_coefficient = coefficient * scale
    exponent = decimal_tuple.exponent
    if product_coefficient == 0:
        return 0, 0
    while product_coefficient % 10 == 0:
        product_coefficient //= 10
        exponent += 1
    adjusted = exponent + _integer_decimal_digits(product_coefficient) - 1
    return exponent, adjusted


def _validate_exact_decimal_range(terms: tuple, precision: int) -> None:
    if precision > decimal.MAX_PREC:
        raise ValueError(
            "exact Decimal aggregation exceeds supported Decimal precision"
        )
    minimum_representable_exponent = decimal.MIN_EMIN - precision + 1
    for value, scale in terms:
        exponent, adjusted = _exact_product_bounds(value, scale)
        if adjusted > decimal.MAX_EMAX:
            raise ValueError(
                "exact Decimal aggregation exceeds supported Decimal exponent "
                "range"
            )
        if exponent < minimum_representable_exponent:
            raise ValueError(
                "exact Decimal aggregation exceeds supported Decimal exponent "
                "range"
            )


def _exact_scaled_sum(terms: tuple) -> decimal.Decimal:
    precision = _exact_decimal_precision(terms)
    _validate_exact_decimal_range(terms, precision)
    try:
        with decimal.localcontext() as context:
            context.prec = precision
            context.rounding = decimal.ROUND_HALF_EVEN
            context.Emax = decimal.MAX_EMAX
            context.Emin = decimal.MIN_EMIN
            context.clamp = 0
            for signal in context.traps:
                context.traps[signal] = False
            context.traps[decimal.InvalidOperation] = True
            context.traps[decimal.Overflow] = True
            context.traps[decimal.Underflow] = True
            context.traps[decimal.Inexact] = True
            context.traps[decimal.Rounded] = True
            context.traps[decimal.Clamped] = True
            products = tuple(
                (
                    decimal.Decimal(0)
                    if value.is_zero()
                    else value * decimal.Decimal(scale)
                )
                for value, scale in terms
            )
            total = products[0]
            for product in products[1:]:
                total += product
            return total
    except decimal.DecimalException as error:
        raise ValueError(
            "exact Decimal aggregation could not be represented"
        ) from error


def _aggregate_decimal_values(matched: tuple) -> Tuple[decimal.Decimal, decimal.Decimal]:
    bid_terms = tuple(
        (
            item[3][MarketDataRelationshipRole.OPTION_QUOTE].bid_premium,
            item[1].quantity * item[1].contract_multiplier,
        )
        for item in matched
    )
    ask_terms = tuple(
        (
            item[3][MarketDataRelationshipRole.OPTION_QUOTE].ask_premium,
            item[1].quantity * item[1].contract_multiplier,
        )
        for item in matched
    )
    return _exact_scaled_sum(bid_terms), _exact_scaled_sum(ask_terms)


def _convert_position_values(
    bid_value: decimal.Decimal,
    ask_value: decimal.Decimal,
) -> Tuple[float, float]:
    try:
        quoted_bid_value = float(bid_value)
        quoted_ask_value = float(ask_value)
    except (OverflowError, ValueError) as error:
        raise ValueError("position values must be finite floats") from error
    if not math.isfinite(quoted_bid_value) or not math.isfinite(quoted_ask_value):
        raise ValueError("position values must be finite floats")
    return quoted_bid_value, quoted_ask_value


def _construct_research_record(
    structure: OptionStructure,
    as_of_date: datetime.date,
    quoted_bid_value: float,
    quoted_ask_value: float,
    minimum_volume: int,
    minimum_open_interest: int,
) -> StructureLiquidity:
    return StructureLiquidity(
        structure=structure,
        as_of_date=as_of_date,
        quoted_bid_value=quoted_bid_value,
        quoted_ask_value=quoted_ask_value,
        minimum_leg_open_interest=minimum_open_interest,
        minimum_leg_daily_volume=minimum_volume,
        quote_methodology=_QUOTE_METHODOLOGY,
    )


def _canonical_consumed(matched: tuple) -> Tuple[tuple, tuple, tuple]:
    canonical = tuple(
        sorted(matched, key=lambda item: _contract_order_key(item[0]))
    )
    records = tuple(
        item[3][role] for item in canonical for role in _REQUIRED_ROLES
    )
    bindings = tuple(
        item[2][role] for item in canonical for role in _REQUIRED_ROLES
    )
    return canonical, records, bindings


def _input_reference(record: object) -> CalculationInputReference:
    metadata = record.metadata
    return CalculationInputReference(
        record_id=metadata.record_id,
        normalized_at=metadata.normalized_at,
        source_ids=tuple(
            source.source_id for source in metadata.source_references
        ),
    )


def _construct_input_references(records: tuple) -> tuple:
    return tuple(_input_reference(record) for record in records)


def _construct_parameters(canonical_matched: tuple) -> str:
    leg_correspondence = []
    for contract_key, leg, _bindings, records in canonical_matched:
        underlying = contract_key.underlying_key
        leg_correspondence.append({
            "underlying": {
                "symbol": underlying.symbol,
                "listing_mic": underlying.listing_mic,
                "security_type": underlying.security_type.value,
                "currency": underlying.currency,
            },
            "option_type": contract_key.option_type,
            "expiration": contract_key.expiration,
            "strike": contract_key.strike,
            "currency": contract_key.currency,
            "deliverable_id": contract_key.deliverable_id,
            "contract_multiplier": contract_key.contract_multiplier,
            "quantity": leg.quantity,
            "quote_record_id": records[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].metadata.record_id,
            "volume_record_id": records[
                MarketDataRelationshipRole.OPTION_VOLUME
            ].metadata.record_id,
            "open_interest_record_id": records[
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST
            ].metadata.record_id,
        })
    return canonicalize_lineage_parameters({
        "activity_count_unit": "contracts",
        "leg_correspondence": leg_correspondence,
        "minimum_leg_rule": "minimum_unscaled_contract_count_across_legs",
        "position_value_rule": (
            "sum(premium_per_underlying_unit*quantity*contract_multiplier)"
        ),
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
    })


def _derive_quality_flags(
    bindings: tuple,
    records: tuple,
) -> Tuple[CalculationQualityFlag, ...]:
    selected = {CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED}
    if any(
        NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags
        for record in records
    ):
        selected.add(CalculationQualityFlag.INTERPOLATED)
    if any(
        binding.correction_selection.reason_codes
        == (
            CorrectionSelectionReasonCode
            .DOMINATING_REVISION_VECTOR_SELECTED,
        )
        for binding in bindings
    ):
        selected.add(CalculationQualityFlag.CORRECTION_SELECTED)
    if any(
        record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE
        for record in records
    ):
        selected.add(CalculationQualityFlag.COMPOSITE_INPUT_USED)
    if any(
        NormalizationQualityFlag.INCOMPLETE in record.metadata.quality_flags
        or any(
            SourceQualityFlag.PARTIAL in source.quality_flags
            for source in record.metadata.source_references
        )
        for record in records
    ):
        selected.add(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def _construct_lineage(
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: tuple,
    parameters_json: str,
    quality_flags: tuple,
) -> CalculationLineage:
    return CalculationLineage(
        calculation_id=calculation_id,
        calculation_type="structure_liquidity",
        methodology_id="exact-structure-liquidity",
        methodology_version="v0.1",
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )


def _construct_result(
    record: StructureLiquidity,
    lineage: CalculationLineage,
) -> StructureLiquidityTransformationResult:
    return StructureLiquidityTransformationResult(record=record, lineage=lineage)


def transform_structure_liquidity(
    calculation_id: object,
    structure: object,
    relationship_selection: object,
    calculated_at: object,
) -> StructureLiquidityTransformationResult:
    """Transform one exact selected option-activity proof into liquidity evidence."""

    normalized_id = _validate_calculation_id(calculation_id)
    exact_structure = _validate_structure(structure)
    selection = _validate_relationship_selection(relationship_selection)
    normalized_at = _normalize_calculated_at(calculated_at)
    _validate_selection_status(selection)
    selected = _resolve_selected_candidate(selection)
    groups, bindings = _validate_selected_shape(selected, exact_structure)
    entries = _resolve_selected_objects(groups, bindings)
    _validate_selected_record_types(entries)
    _validate_proof_integrity(entries, bindings)
    matched = _match_structure_legs(entries, exact_structure)
    as_of_date = _validate_contract_sessions(matched)
    minimum_volume, minimum_open_interest = _validate_required_values(matched)
    bid_decimal, ask_decimal = _aggregate_decimal_values(matched)
    quoted_bid, quoted_ask = _convert_position_values(
        bid_decimal, ask_decimal
    )
    record = _construct_research_record(
        exact_structure,
        as_of_date,
        quoted_bid,
        quoted_ask,
        minimum_volume,
        minimum_open_interest,
    )
    canonical_matched, records, consumed_bindings = _canonical_consumed(matched)
    inputs = _construct_input_references(records)
    parameters_json = _construct_parameters(canonical_matched)
    quality_flags = _derive_quality_flags(consumed_bindings, records)
    lineage = _construct_lineage(
        normalized_id,
        normalized_at,
        inputs,
        parameters_json,
        quality_flags,
    )
    return _construct_result(record, lineage)
