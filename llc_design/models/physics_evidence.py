"""Provenance tags and physical sanity checks for LLC engineering results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DataConfidence(str, Enum):
    DATASHEET = "DATASHEET"
    DIGITIZED_CURVE = "DIGITIZED_CURVE"
    MEASURED = "MEASURED"
    USER_INPUT = "USER_INPUT"
    ESTIMATED = "ESTIMATED"
    DEFAULT = "DEFAULT"
    APPROXIMATION = "APPROXIMATION"
    UNKNOWN = "UNKNOWN"


class ModelGrade(str, Enum):
    VERIFIED = "VERIFIED"
    APPROXIMATION = "APPROXIMATION"
    PARTIAL = "PARTIAL"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "N/A"


class SwitchingClass(str, Enum):
    FULL_ZVS = "FULL_ZVS"
    PARTIAL_ZVS = "PARTIAL_ZVS"
    HARD_SWITCHING = "HARD_SWITCHING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class LossTerm:
    name: str
    value_w: float
    model: ModelGrade
    source: DataConfidence
    temperature_c: float | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value_w": self.value_w,
            "model": self.model.value,
            "source": self.source.value,
            "temperature_c": self.temperature_c,
            "notes": self.notes,
        }


def classify_turn_on_from_zvs_margin(zvs_margin: float | None) -> SwitchingClass:
    if zvs_margin is None or zvs_margin != zvs_margin:  # NaN
        return SwitchingClass.UNKNOWN
    if zvs_margin >= 0.20:
        return SwitchingClass.FULL_ZVS
    if zvs_margin >= 0.0:
        return SwitchingClass.PARTIAL_ZVS
    return SwitchingClass.HARD_SWITCHING


def physical_sanity_issues(
    *,
    loss_w: float | None = None,
    efficiency: float | None = None,
    bpk_t: float | None = None,
    energy_j: float | None = None,
    tj_c: float | None = None,
    ta_c: float | None = None,
    dissipating: bool = False,
    q_available: float | None = None,
) -> tuple[str, ...]:
    issues: list[str] = []
    if loss_w is not None and loss_w < -1e-9:
        issues.append("loss < 0 is physically impossible")
    if efficiency is not None and efficiency > 1.0 + 1e-6:
        issues.append("efficiency > 1 is physically impossible")
    if efficiency is not None and efficiency < -1e-9:
        issues.append("efficiency < 0 is physically impossible")
    if bpk_t is not None and bpk_t < -1e-12:
        issues.append("Bpk < 0 is physically impossible")
    if energy_j is not None and energy_j < -1e-12:
        issues.append("energy < 0 is physically impossible")
    if (
        dissipating
        and tj_c is not None
        and ta_c is not None
        and tj_c + 0.05 < ta_c
        and (loss_w or 0.0) > 1e-3
    ):
        issues.append("Tj < Ta while dissipating power is suspicious")
    if q_available is not None and q_available < -1e-15:
        issues.append("Q_available < 0 — inspect commutation sign convention")
    return tuple(issues)


__all__ = [
    "DataConfidence",
    "LossTerm",
    "ModelGrade",
    "SwitchingClass",
    "classify_turn_on_from_zvs_margin",
    "physical_sanity_issues",
]
