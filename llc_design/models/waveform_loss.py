"""Waveform-aware / provenance-tagged LLC semiconductor loss (V2).

Reuses FHA operating-point scalars when no TD waveform is available, but every
term carries ModelGrade / DataConfidence. Turn-on class is linked to ZVS_MARGIN.
Non-converged TD must not be labeled VERIFIED.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from ..core.operating_point import LLCOperatingPoint
from ..core.spec import LLCDesignSpec, MosfetSpec
from ..core.tank import TankDesign
from ..core.zvs_margin import evaluate_zvs_margin
from ..dynamics.waveforms import WaveformBundle
from .physics_evidence import (
    DataConfidence,
    LossTerm,
    ModelGrade,
    SwitchingClass,
    classify_turn_on_from_zvs_margin,
    physical_sanity_issues,
)
from .primary_bridge import PrimaryBridgeLoss, primary_bridge_loss
from .synchronous_rectifier import SynchronousRectifierLoss, synchronous_rectifier_loss


RectifierKind = Literal["DIODE", "SYNCHRONOUS_RECTIFIER"]


@dataclass(frozen=True)
class ProvenancedBridgeLoss:
    legacy: PrimaryBridgeLoss
    terms: tuple[LossTerm, ...]
    turn_on_class: SwitchingClass
    zvs_margin: float | None
    waveform_source: str
    sanity: tuple[str, ...]

    @property
    def total_w(self) -> float:
        return float(sum(t.value_w for t in self.terms))


@dataclass(frozen=True)
class ProvenancedRectifierLoss:
    kind: RectifierKind
    legacy: SynchronousRectifierLoss | None
    terms: tuple[LossTerm, ...]
    waveform_source: str
    sanity: tuple[str, ...]

    @property
    def total_w(self) -> float:
        return float(sum(t.value_w for t in self.terms if t.model != ModelGrade.NOT_APPLICABLE))


def _rms_from_waveform(bundle: WaveformBundle, key: str) -> float | None:
    try:
        return float(bundle.signal(key).statistics.rms)
    except Exception:
        return None


def bridge_loss_with_provenance(
    spec: LLCDesignSpec,
    tank: TankDesign,
    op: LLCOperatingPoint,
    device: MosfetSpec,
    *,
    waveform: WaveformBundle | None = None,
    td_converged: bool | None = None,
) -> ProvenancedBridgeLoss:
    """Build MOSFET loss terms; waveform path upgrades conduction RMS when available."""

    zvs = evaluate_zvs_margin(spec, tank, op, device=device, level=2)
    turn_on = classify_turn_on_from_zvs_margin(
        None if math.isnan(zvs.zvs_margin) else zvs.zvs_margin
    )
    legacy = primary_bridge_loss(spec, tank, op, device)

    ir_rms = op.resonant_current_rms_a
    source = "FHA_OPERATING_POINT"
    conduction_grade = ModelGrade.APPROXIMATION
    if waveform is not None and td_converged:
        wf_rms = _rms_from_waveform(waveform, "i_resonant")
        if wf_rms is not None and wf_rms > 0.0:
            ir_rms = wf_rms
            source = "TIME_DOMAIN_WAVEFORM"
            conduction_grade = ModelGrade.VERIFIED
    elif waveform is not None and td_converged is False:
        source = "TD_NOT_CONVERGED_FALLBACK_FHA"
        conduction_grade = ModelGrade.UNKNOWN

    npar = spec.primary_parallel_devices
    tj = spec.primary_junction_temperature_c
    rds = device.rds_at(tj) / npar
    p_cond = (ir_rms**2) * spec.bridge_series_devices * rds

    # Turn-on: never silently zero under ZVS; scale residual hard-switching energy.
    eoss = 0.5 * device.coss_er_f * op.vbus_v**2
    if turn_on == SwitchingClass.FULL_ZVS:
        turn_on_w = 0.0
        ton_grade = ModelGrade.APPROXIMATION
        ton_note = "FULL_ZVS: hard turn-on energy suppressed; residual treated as 0 (approx)"
    elif turn_on == SwitchingClass.PARTIAL_ZVS:
        turn_on_w = (
            spec.bridge_device_count * npar * eoss * op.switching_frequency_hz * 0.35
        )
        ton_grade = ModelGrade.APPROXIMATION
        ton_note = "PARTIAL_ZVS: 35% residual Eoss-like turn-on (approx)"
    elif turn_on == SwitchingClass.HARD_SWITCHING:
        turn_on_w = (
            spec.bridge_device_count * npar * eoss * op.switching_frequency_hz
        )
        ton_grade = ModelGrade.APPROXIMATION
        ton_note = "HARD_SWITCHING: full 0.5·Coss·V² proxy for Eon"
    else:
        turn_on_w = legacy.residual_coss_w
        ton_grade = ModelGrade.UNKNOWN
        ton_note = "ZVS class unknown; reuse legacy residual Coss term"

    qoss_source = (
        DataConfidence.DATASHEET if device.qoss_c > 0.0 else DataConfidence.APPROXIMATION
    )
    terms = (
        LossTerm("conduction", p_cond, conduction_grade, DataConfidence.DATASHEET, tj,
                 f"Rds_on({tj:.0f}°C); Ir_rms from {source}"),
        LossTerm("turn_off", legacy.turnoff_w, ModelGrade.APPROXIMATION, DataConfidence.DATASHEET, tj,
                 "Eoff ref scaled by V·I"),
        LossTerm("turn_on", turn_on_w, ton_grade, qoss_source, tj, ton_note),
        LossTerm("gate", legacy.gate_drive_w, ModelGrade.APPROXIMATION, DataConfidence.DATASHEET, tj),
        LossTerm("coss_residual", legacy.residual_coss_w, ModelGrade.APPROXIMATION, qoss_source, tj,
                 "legacy residual after charge/energy margin"),
        LossTerm("deadtime_diode", legacy.deadtime_diode_w, ModelGrade.APPROXIMATION,
                 DataConfidence.DEFAULT, tj, "body-diode Vf default path — not GaN/SiC specific"),
    )
    total = sum(t.value_w for t in terms)
    sanity = physical_sanity_issues(
        loss_w=total,
        q_available=zvs.q_available,
        tj_c=tj,
        ta_c=spec.ambient_temperature_c if hasattr(spec, "ambient_temperature_c") else 40.0,
        dissipating=total > 0.0,
    )
    return ProvenancedBridgeLoss(
        legacy=legacy,
        terms=terms,
        turn_on_class=turn_on,
        zvs_margin=None if math.isnan(zvs.zvs_margin) else zvs.zvs_margin,
        waveform_source=source,
        sanity=sanity,
    )


def rectifier_loss_with_provenance(
    spec: LLCDesignSpec,
    op: LLCOperatingPoint,
    device: MosfetSpec,
    *,
    kind: RectifierKind = "SYNCHRONOUS_RECTIFIER",
    waveform: WaveformBundle | None = None,
    td_converged: bool | None = None,
) -> ProvenancedRectifierLoss:
    tj = spec.sr_junction_temperature_c
    source = "FHA_OPERATING_POINT"
    if waveform is not None and td_converged:
        source = "TIME_DOMAIN_WAVEFORM"
    elif waveform is not None and td_converged is False:
        source = "TD_NOT_CONVERGED_FALLBACK_FHA"

    if kind == "DIODE":
        # Diode path: conduction ≈ 2·Vf·Iavg (full bridge), RR unknown without datasheet.
        i_avg = 2.0 * op.pout_w / max(spec.vout_v, 1e-9) / math.pi
        vf = device.body_diode_vf_v
        p_cond = 2.0 * vf * i_avg
        terms = (
            LossTerm("conduction", p_cond, ModelGrade.APPROXIMATION, DataConfidence.DEFAULT, tj,
                     "full-bridge diode average current approx"),
            LossTerm("switching", 0.0, ModelGrade.NOT_APPLICABLE, DataConfidence.UNKNOWN, tj),
            LossTerm("reverse_recovery", 0.0, ModelGrade.UNKNOWN, DataConfidence.UNKNOWN, tj,
                     "Qrr not supplied — UNKNOWN, not zero"),
            LossTerm("drive", 0.0, ModelGrade.NOT_APPLICABLE, DataConfidence.UNKNOWN, tj),
        )
        return ProvenancedRectifierLoss(
            kind=kind, legacy=None, terms=terms, waveform_source=source,
            sanity=physical_sanity_issues(loss_w=p_cond),
        )

    legacy = synchronous_rectifier_loss(spec, op, device)
    grade = ModelGrade.VERIFIED if source.startswith("TIME_DOMAIN") else ModelGrade.APPROXIMATION
    if "NOT_CONVERGED" in source:
        grade = ModelGrade.UNKNOWN
    terms = (
        LossTerm("conduction", legacy.conduction_w, grade, DataConfidence.DATASHEET, tj),
        LossTerm("switching", legacy.turnoff_w, ModelGrade.APPROXIMATION, DataConfidence.DATASHEET, tj,
                 "SR turn-off advance model"),
        LossTerm("reverse_recovery", 0.0, ModelGrade.NOT_APPLICABLE, DataConfidence.UNKNOWN, tj,
                 "SR channel — RR N/A"),
        LossTerm("drive", legacy.gate_drive_w, ModelGrade.APPROXIMATION, DataConfidence.DATASHEET, tj),
        LossTerm("coss", legacy.coss_w, ModelGrade.APPROXIMATION, DataConfidence.APPROXIMATION, tj),
        LossTerm("deadtime_diode", legacy.deadtime_diode_w, ModelGrade.APPROXIMATION, DataConfidence.DEFAULT, tj),
    )
    return ProvenancedRectifierLoss(
        kind=kind,
        legacy=legacy,
        terms=terms,
        waveform_source=source,
        sanity=physical_sanity_issues(loss_w=legacy.total_w),
    )


__all__ = [
    "ProvenancedBridgeLoss",
    "ProvenancedRectifierLoss",
    "bridge_loss_with_provenance",
    "rectifier_loss_with_provenance",
]
