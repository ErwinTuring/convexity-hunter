"""Deterministic Direct Entry contract and research-readiness verification."""

import decimal as _decimal
from dataclasses import dataclass as _dataclass
from typing import Tuple as _Tuple

from .evidence import OptionLeg as _OptionLeg
from .evidence import OptionStructure as _OptionStructure
from .market_data import (
    DataOrigin as _DataOrigin,
    NormalizationMetadata as _NormalizationMetadata,
    OptionContractKey as _OptionContractKey,
    OptionContractReference as _OptionContractReference,
    SourceReference as _SourceReference,
    UnderlyingKey as _UnderlyingKey,
)
from .market_data_transformations import (
    StructureCostsTransformationResult as _StructureCostsTransformationResult,
    StructureLiquidityTransformationResult as _StructureLiquidityTransformationResult,
)


__all__ = (
    "DirectEntryExactContractVerification",
    "verify_direct_entry_exact_contracts",
    "DirectEntryResearchReadinessVerification",
    "verify_direct_entry_research_readiness",
)


def _validate_exact_contract_top_level_types(
    structure: object,
    contract_references: object,
) -> None:
    if type(structure) is not _OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    if type(contract_references) is not tuple:
        raise TypeError("contract_references must have exact type tuple")
    if any(
        type(reference) is not _OptionContractReference
        for reference in contract_references
    ):
        raise TypeError(
            "every contract reference must have exact type OptionContractReference"
        )


def _verify_structure(structure: _OptionStructure) -> None:
    try:
        if type(structure.legs) is not tuple:
            raise TypeError
        rebuilt_legs = []
        for leg in structure.legs:
            if type(leg) is not _OptionLeg:
                raise TypeError
            rebuilt_leg = _OptionLeg(
                leg.underlying,
                leg.option_type,
                leg.strike,
                leg.expiration,
                leg.quantity,
                leg.contract_multiplier,
            )
            if rebuilt_leg != leg:
                raise ValueError
            rebuilt_legs.append(rebuilt_leg)
        rebuilt_structure = _OptionStructure(
            tuple(rebuilt_legs),
            structure.assumed_portfolio_value,
            structure.expected_holding_days,
        )
        if rebuilt_structure != structure:
            raise ValueError
    except Exception:
        raise ValueError("structure is intrinsically invalid") from None


def _verify_contract_reference(
    leg: object,
    reference: _OptionContractReference,
) -> None:
    try:
        key = reference.contract_key
        if type(key) is not _OptionContractKey:
            raise TypeError
        underlying = key.underlying_key
        if type(underlying) is not _UnderlyingKey:
            raise TypeError
        rebuilt_underlying = _UnderlyingKey(
            underlying.symbol,
            underlying.listing_mic,
            underlying.security_type,
            underlying.currency,
        )
        if rebuilt_underlying != underlying:
            raise ValueError
        rebuilt_key = _OptionContractKey(
            rebuilt_underlying,
            key.expiration,
            key.option_type,
            key.strike,
            key.contract_multiplier,
            key.currency,
            key.deliverable_id,
        )
        if rebuilt_key != key:
            raise ValueError

        metadata = reference.metadata
        if type(metadata) is not _NormalizationMetadata:
            raise TypeError
        if type(metadata.source_references) is not tuple:
            raise TypeError
        rebuilt_sources = []
        for source in metadata.source_references:
            if type(source) is not _SourceReference:
                raise TypeError
            rebuilt_source = _SourceReference(
                source.source_id,
                source.provider_name,
                source.dataset_name,
                source.provider_record_id,
                source.provider_request_id,
                source.source_symbol,
                source.source_uri,
                source.observed_at,
                source.retrieved_at,
                source.provider_timezone,
                source.timestamp_methodology,
                source.origin,
                source.is_delayed,
                source.declared_delay_seconds,
                source.payload_sha256,
                source.revision_number,
                source.provider_correction_id,
                source.quality_flags,
            )
            if rebuilt_source != source:
                raise ValueError
            rebuilt_sources.append(rebuilt_source)
        rebuilt_metadata = _NormalizationMetadata(
            metadata.record_id,
            tuple(rebuilt_sources),
            metadata.effective_observed_at,
            metadata.normalized_at,
            metadata.record_origin,
            metadata.normalization_methodology,
            metadata.unit_convention,
            metadata.normalization_version,
            metadata.quality_flags,
        )
        if rebuilt_metadata != metadata:
            raise ValueError
        rebuilt_reference = _OptionContractReference(
            rebuilt_key,
            reference.listing_date,
            reference.last_trade_date,
            reference.exercise_style,
            reference.settlement_type,
            rebuilt_metadata,
        )
        if rebuilt_reference != reference:
            raise ValueError
    except Exception:
        raise ValueError("contract reference is intrinsically invalid") from None
    metadata = reference.metadata
    if metadata.record_origin not in {
        _DataOrigin.PROVIDER_REFERENCE,
        _DataOrigin.SYSTEM_COMPOSITE,
    }:
        raise ValueError("contract reference must be source-backed reference evidence")
    if not metadata.source_references:
        raise ValueError("contract reference must retain source evidence")
    if not any(
        source.origin is _DataOrigin.PROVIDER_REFERENCE
        for source in metadata.source_references
    ):
        raise ValueError("contract reference must retain provider reference evidence")

    expected_strike = _decimal.Decimal(str(leg.strike))
    if (
        key.underlying_key.symbol != leg.underlying
        or key.expiration != leg.expiration
        or key.option_type != leg.option_type
        or key.strike != expected_strike
        or key.contract_multiplier != leg.contract_multiplier
    ):
        raise ValueError("contract reference does not match structure leg")


@_dataclass(frozen=True)
class DirectEntryExactContractVerification:
    """Source-backed exact listed-contract identity for every structure leg."""

    structure: _OptionStructure
    contract_references: _Tuple[_OptionContractReference, ...]

    def __post_init__(self) -> None:
        _validate_exact_contract_top_level_types(
            self.structure,
            self.contract_references,
        )
        _verify_structure(self.structure)
        if len(self.contract_references) != len(self.structure.legs):
            raise ValueError("contract_references must correspond one-to-one with legs")
        for leg, reference in zip(self.structure.legs, self.contract_references):
            _verify_contract_reference(leg, reference)
        record_ids = tuple(
            reference.metadata.record_id for reference in self.contract_references
        )
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("contract reference record IDs must be pairwise distinct")


def verify_direct_entry_exact_contracts(
    structure: _OptionStructure,
    contract_references: _Tuple[_OptionContractReference, ...],
) -> DirectEntryExactContractVerification:
    """Verify source-backed exact contract identity without claiming readiness."""

    _validate_exact_contract_top_level_types(structure, contract_references)
    return DirectEntryExactContractVerification(structure, contract_references)


def _validate_research_readiness_top_level_types(
    structure: object,
    costs_result: object,
    liquidity_result: object,
) -> None:
    if type(structure) is not _OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    if type(costs_result) is not _StructureCostsTransformationResult:
        raise TypeError(
            "costs_result must have exact type "
            "StructureCostsTransformationResult"
        )
    if type(liquidity_result) is not _StructureLiquidityTransformationResult:
        raise TypeError(
            "liquidity_result must have exact type "
            "StructureLiquidityTransformationResult"
        )


@_dataclass(frozen=True)
class DirectEntryResearchReadinessVerification:
    """Authentic reviewed cost and liquidity readiness for one structure."""

    structure: _OptionStructure
    costs_result: _StructureCostsTransformationResult
    liquidity_result: _StructureLiquidityTransformationResult

    def __post_init__(self) -> None:
        _validate_research_readiness_top_level_types(
            self.structure,
            self.costs_result,
            self.liquidity_result,
        )

        _StructureCostsTransformationResult(
            self.costs_result.record,
            self.costs_result.lineage,
        )
        _StructureLiquidityTransformationResult(
            self.liquidity_result.record,
            self.liquidity_result.lineage,
        )

        if self.structure != self.costs_result.record.structure:
            raise ValueError("structure does not match costs_result.record.structure")
        if self.structure != self.liquidity_result.record.structure:
            raise ValueError(
                "structure does not match liquidity_result.record.structure"
            )
        if (
            self.costs_result.record.as_of_date
            != self.liquidity_result.record.as_of_date
        ):
            raise ValueError("costs and liquidity records must share as_of_date")


def verify_direct_entry_research_readiness(
    structure: _OptionStructure,
    costs_result: _StructureCostsTransformationResult,
    liquidity_result: _StructureLiquidityTransformationResult,
) -> DirectEntryResearchReadinessVerification:
    """Verify complete reviewed cost and liquidity evidence."""

    _validate_research_readiness_top_level_types(
        structure,
        costs_result,
        liquidity_result,
    )
    return DirectEntryResearchReadinessVerification(
        structure,
        costs_result,
        liquidity_result,
    )
