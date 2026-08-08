"""Deterministic verification for one caller-supplied option structure."""

from dataclasses import dataclass as _dataclass

from .evidence import OptionStructure as _OptionStructure
from .market_data_transformations import (
    StructureCostsTransformationResult as _StructureCostsTransformationResult,
    StructureLiquidityTransformationResult as _StructureLiquidityTransformationResult,
)


__all__ = (
    "DirectEntryExactStructureVerification",
    "verify_direct_entry_exact_structure",
)


def _validate_top_level_types(
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
class DirectEntryExactStructureVerification:
    structure: _OptionStructure
    costs_result: _StructureCostsTransformationResult
    liquidity_result: _StructureLiquidityTransformationResult

    def __post_init__(self) -> None:
        _validate_top_level_types(
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


def verify_direct_entry_exact_structure(
    structure: _OptionStructure,
    costs_result: _StructureCostsTransformationResult,
    liquidity_result: _StructureLiquidityTransformationResult,
) -> DirectEntryExactStructureVerification:
    _validate_top_level_types(structure, costs_result, liquidity_result)
    return DirectEntryExactStructureVerification(
        structure,
        costs_result,
        liquidity_result,
    )
