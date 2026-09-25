"""PFC Engineering V3 façade — Line-Cycle → PF/THD → Zero Crossing → Smart Control.

Math authorities (do not fork):
- Closed-loop AC: ``simulate_pfc_line_cycle`` / ``PFCLineCycleWaveforms``
- Dual-loop Bode / Exact H(z): ``build_pfc_control_lab_analysis`` / handoff
- Ideal sizing trace: ``TTPLLineTrace`` (sizing/loss screen only)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from llc_design.control.phase_budget import phase_budget
from llc_design.control.smart_control import MetricStatus, PhaseBudgetResult

from ..control.analysis import LoopResult, PFCControlLabAnalysis, build_pfc_control_lab_analysis
from ..control.config import PFCControlLabConfig
from ..control.handoff import PFCControlHandoff, build_pfc_control_handoff
from ..control.waveforms import PFCLineCycleWaveforms, simulate_pfc_line_cycle


FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


class ConvergenceStatus(str, Enum):
    LINE_CYCLE_CONVERGED = "LINE_CYCLE_CONVERGED"
    NOT_CONVERGED = "NOT_CONVERGED"
    UNKNOWN = "UNKNOWN"


class DistortionCause(str, Enum):
    ZERO_CROSS = "ZERO_CROSS"
    MIN_PULSE = "MIN_PULSE"
    DEAD_TIME = "DEAD_TIME"
    CURRENT_LOOP = "CURRENT_LOOP"
    CURRENT_SENSOR = "CURRENT_SENSOR"
    DIGITAL_DELAY = "DIGITAL_DELAY"
    DUTY_SATURATION = "DUTY_SATURATION"
    BUS_RIPPLE = "BUS_RIPPLE"
    X_CAP = "X_CAP"
    LIGHT_LOAD_MODE = "LIGHT_LOAD_MODE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class THDConvention:
    fundamental_definition: str = "DFT_H1_RMS"
    included_harmonics: tuple[int, ...] = tuple(range(2, 26))
    window: str = "rectangular_integer_line_cycles"
    cycles: int = 1
    sampling_note: str = "Settled final AC period of multi-rate line-cycle simulation"

    def as_dict(self) -> dict[str, Any]:
        return {
            "fundamental_definition": self.fundamental_definition,
            "included_harmonics": list(self.included_harmonics),
            "window": self.window,
            "cycles": self.cycles,
            "sampling_note": self.sampling_note,
        }


@dataclass(frozen=True)
class PFCEvidenceResult:
    metric: str
    value: float | str | None
    unit: str
    model: str
    source: str
    status: MetricStatus
    assumptions: tuple[str, ...]
    corner: str
    falsification_condition: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "model": self.model,
            "source": self.source,
            "status": self.status.value,
            "assumptions": list(self.assumptions),
            "corner": self.corner,
            "falsification_condition": self.falsification_condition,
        }


@dataclass(frozen=True)
class PFCInstantPoint:
    theta_deg: float
    vac_v: float
    vbus_v: float
    pout_w: float
    duty: float
    fsw_hz: float
    il_avg_a: float
    il_peak_a: float
    il_valley_a: float
    il_ripple_pp_a: float
    switch_state: int
    line_polarity: int
    mode: str = "CCM_AVERAGED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "theta_deg": self.theta_deg,
            "Vac": self.vac_v,
            "Vbus": self.vbus_v,
            "Pout": self.pout_w,
            "D": self.duty,
            "Fsw": self.fsw_hz,
            "IL_avg": self.il_avg_a,
            "IL_peak": self.il_peak_a,
            "IL_valley": self.il_valley_a,
            "IL_ripple": self.il_ripple_pp_a,
            "switch_state": self.switch_state,
            "line_polarity": self.line_polarity,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class LineCycleConvergenceResult:
    status: ConvergenceStatus
    pin_cycle_relative_error: float | None
    vbus_average_v: float
    vbus_command_v: float
    vbus_relative_error: float
    vbus_ripple_pp_v: float
    iac_rms_a: float
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "pin_cycle_relative_error": self.pin_cycle_relative_error,
            "vbus_average_v": self.vbus_average_v,
            "vbus_command_v": self.vbus_command_v,
            "vbus_relative_error": self.vbus_relative_error,
            "vbus_ripple_pp_v": self.vbus_ripple_pp_v,
            "iac_rms_a": self.iac_rms_a,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PFCLineCycleResult:
    """Unified closed-loop line-cycle view wrapping PFCLineCycleWaveforms."""

    waveforms: PFCLineCycleWaveforms
    theta_deg: FloatArray
    time_s: FloatArray
    vac_v: FloatArray
    vac_abs_v: FloatArray
    iac_a: FloatArray
    iac_ref_a: FloatArray
    vbus_v: FloatArray
    duty: FloatArray
    il_avg_a: FloatArray
    il_ripple_pp_a: FloatArray
    il_peak_a: FloatArray
    il_valley_a: FloatArray
    fsw_hz: float
    pin_inst_w: FloatArray
    pout_inst_w: FloatArray
    inductor_current_a: FloatArray
    capacitor_current_a: FloatArray
    hf_leg_current_a: FloatArray
    lf_leg_current_a: FloatArray
    convergence: LineCycleConvergenceResult
    settled_slice: slice

    def instant_point(self, theta_deg: float, *, pout_w: float) -> PFCInstantPoint:
        ang = np.asarray(self.theta_deg, dtype=float)
        delta = np.abs(((ang - theta_deg + 180.0) % 360.0) - 180.0)
        idx = int(np.argmin(delta))
        polarity = 1 if self.vac_v[idx] >= 0.0 else -1
        return PFCInstantPoint(
            theta_deg=float(self.theta_deg[idx]),
            vac_v=float(self.vac_v[idx]),
            vbus_v=float(self.vbus_v[idx]),
            pout_w=float(pout_w),
            duty=float(self.duty[idx]),
            fsw_hz=float(self.fsw_hz),
            il_avg_a=float(self.il_avg_a[idx]),
            il_peak_a=float(self.il_peak_a[idx]),
            il_valley_a=float(self.il_valley_a[idx]),
            il_ripple_pp_a=float(self.il_ripple_pp_a[idx]),
            switch_state=int(round(float(
                self.waveforms.signals["pwm_state_code"][self.settled_slice][idx]))),
            line_polarity=polarity,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "fsw_hz": self.fsw_hz,
            "convergence": self.convergence.as_dict(),
            "n_samples": int(len(self.time_s)),
            "metrics": {
                "pf": self.waveforms.metrics.power_factor,
                "thd_percent": self.waveforms.metrics.current_thd_percent,
                "vbus_avg": self.waveforms.metrics.bus_voltage_average_v,
            },
        }


@dataclass(frozen=True)
class PFTHDResult:
    vac_rms_v: float
    iac_rms_a: float
    pin_w: float
    pout_w: float | None
    pf: float
    dpf: float
    distortion_factor: float
    thd: float
    thd_percent: float
    h1_rms_a: float
    harmonics_rms_a: Mapping[int, float]
    convention: THDConvention
    pf_identity_residual: float
    status: MetricStatus
    sanity_ok: bool
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "Vac_rms": self.vac_rms_v,
            "Iac_rms": self.iac_rms_a,
            "Pin": self.pin_w,
            "Pout": self.pout_w,
            "PF": self.pf,
            "DPF": self.dpf,
            "DistortionFactor": self.distortion_factor,
            "THD": self.thd,
            "THD_percent": self.thd_percent,
            "H1": self.h1_rms_a,
            "harmonics": {str(k): v for k, v in self.harmonics_rms_a.items()},
            "convention": self.convention.as_dict(),
            "pf_identity_residual": self.pf_identity_residual,
            "status": self.status.value,
            "sanity_ok": self.sanity_ok,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class DistortionRegionResult:
    angle_start_deg: float
    angle_end_deg: float
    current_error_rms_a: float
    relative_error: float
    harmonic_contribution_estimate: float
    dominant_cause: DistortionCause
    status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "region_deg": [self.angle_start_deg, self.angle_end_deg],
            "current_error_rms_a": self.current_error_rms_a,
            "relative_error": self.relative_error,
            "harmonic_contribution_estimate": self.harmonic_contribution_estimate,
            "dominant_cause": self.dominant_cause.value,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ZeroCrossPointResult:
    theta_deg: float
    vac_v: float
    iref_a: float
    iactual_a: float
    duty_cmd: float
    duty_effective: float
    pulse_width_s: float
    pulse_valid: bool
    commutation_state: int
    current_error_a: float
    distortion_margin_a: float
    constraint_status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "theta_deg": self.theta_deg,
            "Vac": self.vac_v,
            "Iref": self.iref_a,
            "Iactual": self.iactual_a,
            "duty_cmd": self.duty_cmd,
            "duty_effective": self.duty_effective,
            "pulse_width_s": self.pulse_width_s,
            "pulse_valid": self.pulse_valid,
            "commutation_state": self.commutation_state,
            "current_error": self.current_error_a,
            "distortion_margin": self.distortion_margin_a,
            "constraint_status": self.constraint_status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ZeroCrossAnalysisResult:
    points: tuple[ZeroCrossPointResult, ...]
    zooms: Mapping[float, tuple[ZeroCrossPointResult, ...]]
    minimum_realizable_current_a: float
    effective_duty_deadzone: float
    dead_time_voltage_error_v: float
    sensor_offset_a: float
    status: MetricStatus
    evidence: tuple[PFCEvidenceResult, ...]
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "points": [p.as_dict() for p in self.points],
            "zooms": {str(k): [p.as_dict() for p in v] for k, v in self.zooms.items()},
            "minimum_realizable_current_a": self.minimum_realizable_current_a,
            "effective_duty_deadzone": self.effective_duty_deadzone,
            "dead_time_voltage_error_v": self.dead_time_voltage_error_v,
            "sensor_offset_a": self.sensor_offset_a,
            "status": self.status.value,
            "evidence": [e.as_dict() for e in self.evidence],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class LoopSeparationResult:
    fc_current_hz: float | None
    fc_voltage_hz: float | None
    ratio: float | None
    line_2x_hz: float
    voltage_fc_vs_2fline: float | None
    status: MetricStatus
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "Fc_current": self.fc_current_hz,
            "Fc_voltage": self.fc_voltage_hz,
            "ratio": self.ratio,
            "2x_line_hz": self.line_2x_hz,
            "voltage_fc_vs_2fline": self.voltage_fc_vs_2fline,
            "status": self.status.value,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PFCLoopStabilityV3:
    name: str
    fc_hz: float | None
    pm_deg: float | None
    gm_db: float | None
    ms: float
    mt: float
    delay_margin_s: float | None
    multi_crossover: bool
    phase_budget: PhaseBudgetResult | None
    status: MetricStatus

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "Fc": self.fc_hz,
            "PM": self.pm_deg,
            "GM": self.gm_db,
            "Ms": self.ms,
            "Mt": self.mt,
            "delay_margin_s": self.delay_margin_s,
            "multi_crossover": self.multi_crossover,
            "phase_budget": None if self.phase_budget is None else self.phase_budget.as_dict(),
            "status": self.status.value,
        }


@dataclass(frozen=True)
class PFCSmartControlV3Result:
    analysis: PFCControlLabAnalysis
    handoff: PFCControlHandoff
    separation: LoopSeparationResult
    current: PFCLoopStabilityV3
    voltage: PFCLoopStabilityV3
    evidence: tuple[PFCEvidenceResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "separation": self.separation.as_dict(),
            "current": self.current.as_dict(),
            "voltage": self.voltage.as_dict(),
            "exact_hz_current_b": list(self.handoff.current.b),
            "exact_hz_current_a": list(self.handoff.current.a),
            "exact_hz_voltage_b": list(self.handoff.voltage.b),
            "exact_hz_voltage_a": list(self.handoff.voltage.a),
            "evidence": [e.as_dict() for e in self.evidence],
        }


def _last_cycle_slice(time_s: FloatArray, line_hz: float) -> slice:
    dt = float(np.mean(np.diff(time_s))) if len(time_s) > 1 else 1e-6
    count = max(int(round((1.0 / line_hz) / max(dt, 1e-12))), 4)
    return slice(max(len(time_s) - count, 0), len(time_s))


def _cycle_slices(time_s: FloatArray, line_hz: float, n_cycles: int) -> list[slice]:
    dt = float(np.mean(np.diff(time_s))) if len(time_s) > 1 else 1e-6
    samples = max(int(round((1.0 / line_hz) / max(dt, 1e-12))), 4)
    out: list[slice] = []
    end = len(time_s)
    for _ in range(max(n_cycles, 1)):
        start = max(end - samples, 0)
        if start >= end:
            break
        out.append(slice(start, end))
        end = start
        if end <= 0:
            break
    out.reverse()
    return out


def assess_line_cycle_convergence(
    waveforms: PFCLineCycleWaveforms,
    *,
    line_hz: float,
    vbus_command_v: float,
    pin_tolerance: float = 0.02,
    vbus_tolerance: float = 0.05,
) -> LineCycleConvergenceResult:
    time = np.asarray(waveforms.time_s, dtype=float)
    pin = np.asarray(waveforms.signals["input_power"], dtype=float)
    vbus = np.asarray(waveforms.signals["vbus"], dtype=float)
    iac = np.asarray(waveforms.signals["i_input_signed"], dtype=float)
    slices = _cycle_slices(time, line_hz, 2)
    notes: list[str] = []
    pin_err = None
    if len(slices) >= 2:
        pin0 = float(np.mean(pin[slices[-2]]))
        pin1 = float(np.mean(pin[slices[-1]]))
        pin_err = abs(pin1 - pin0) / max(abs(pin1), 1e-9)
    sl = slices[-1] if slices else _last_cycle_slice(time, line_hz)
    vbus_avg = float(np.mean(vbus[sl]))
    vbus_err = abs(vbus_avg - vbus_command_v) / max(abs(vbus_command_v), 1e-9)
    ripple = float(np.ptp(vbus[sl]))
    iac_rms = float(np.sqrt(np.mean(iac[sl] ** 2)))
    status = ConvergenceStatus.LINE_CYCLE_CONVERGED
    if pin_err is None:
        status = ConvergenceStatus.UNKNOWN
        notes.append("Fewer than two full cycles available for Pin drift check")
    if pin_err is not None and pin_err > pin_tolerance:
        status = ConvergenceStatus.NOT_CONVERGED
        notes.append(f"Pin cycle-to-cycle relative error {pin_err:.4g} > {pin_tolerance:g}")
    if vbus_err > vbus_tolerance:
        status = ConvergenceStatus.NOT_CONVERGED
        notes.append(f"Vbus average error {vbus_err:.4g} > {vbus_tolerance:g}")
    return LineCycleConvergenceResult(
        status=status,
        pin_cycle_relative_error=pin_err,
        vbus_average_v=vbus_avg,
        vbus_command_v=vbus_command_v,
        vbus_relative_error=vbus_err,
        vbus_ripple_pp_v=ripple,
        iac_rms_a=iac_rms,
        notes=tuple(notes),
    )


def build_line_cycle_result(config: PFCControlLabConfig) -> PFCLineCycleResult:
    """Run the authoritative closed-loop line-cycle and expose a unified result."""

    config.validate()
    waveforms = simulate_pfc_line_cycle(config)
    stage = config.power_stage
    time = np.asarray(waveforms.time_s, dtype=float)
    sl = _last_cycle_slice(time, stage.line_frequency_hz)
    s = waveforms.signals
    vac = np.asarray(s["vac"][sl], dtype=float)
    vac_abs = np.abs(vac)
    il = np.asarray(s["i_inductor"][sl], dtype=float)
    duty = np.asarray(s["duty_total"][sl], dtype=float)
    vbus = np.asarray(s["vbus"][sl], dtype=float)
    fsw = float(stage.switching_frequency_hz)
    ripple = vac_abs * duty / max(stage.boost_inductance_h * fsw, 1e-18)
    peak = il + 0.5 * ripple
    valley = np.maximum(il - 0.5 * ripple, 0.0)
    iac = np.asarray(s["i_input_signed"][sl], dtype=float)
    conv = assess_line_cycle_convergence(
        waveforms,
        line_hz=stage.line_frequency_hz,
        vbus_command_v=stage.bus_voltage_v,
    )
    return PFCLineCycleResult(
        waveforms=waveforms,
        theta_deg=np.asarray(s["line_angle_deg"][sl], dtype=float),
        time_s=time[sl],
        vac_v=vac,
        vac_abs_v=vac_abs,
        iac_a=iac,
        iac_ref_a=np.asarray(s["i_ref"][sl], dtype=float),
        vbus_v=vbus,
        duty=duty,
        il_avg_a=il,
        il_ripple_pp_a=ripple,
        il_peak_a=peak,
        il_valley_a=valley,
        fsw_hz=fsw,
        pin_inst_w=np.asarray(s["input_power"][sl], dtype=float),
        pout_inst_w=np.asarray(s["load_current"][sl], dtype=float) * vbus,
        inductor_current_a=il,
        capacitor_current_a=np.asarray(s["bus_cap_current"][sl], dtype=float),
        hf_leg_current_a=il.copy(),
        lf_leg_current_a=np.abs(iac),
        convergence=conv,
        settled_slice=sl,
    )


def compute_pf_thd(
    time_s: Sequence[float] | FloatArray,
    vac_v: Sequence[float] | FloatArray,
    iac_a: Sequence[float] | FloatArray,
    *,
    line_hz: float,
    max_harmonic: int = 25,
    pout_w: float | None = None,
    convention: THDConvention | None = None,
    status_if_ok: MetricStatus = MetricStatus.APPROXIMATION,
) -> PFTHDResult:
    """Unified PF/THD engine. PF = P/S; identity PF ≈ DPF × DistortionFactor."""

    t = np.asarray(time_s, dtype=float)
    v = np.asarray(vac_v, dtype=float)
    i = np.asarray(iac_a, dtype=float)
    if t.ndim != 1 or v.shape != t.shape or i.shape != t.shape or len(t) < 8:
        raise ValueError("PF/THD requires equal-length 1-D waveforms")
    if line_hz <= 0.0 or max_harmonic < 1:
        raise ValueError("line frequency / max_harmonic invalid")

    n = len(t)
    theta = 2.0 * math.pi * line_hz * (t - t[0])

    def phasor(x: FloatArray, harmonic: int) -> complex:
        a = 2.0 / n * float(np.sum(x * np.cos(harmonic * theta)))
        b = 2.0 / n * float(np.sum(x * np.sin(harmonic * theta)))
        return complex(a, -b) / math.sqrt(2.0)

    v1 = phasor(v, 1)
    i1 = phasor(i, 1)
    v_rms = float(np.sqrt(np.mean(v ** 2)))
    i_rms = float(np.sqrt(np.mean(i ** 2)))
    pin = float(np.mean(v * i))
    s_app = v_rms * i_rms
    pf = pin / max(s_app, 1e-12)
    dpf = float(math.cos(np.angle(v1) - np.angle(i1)))
    h1 = abs(i1)
    harmonics = {h: float(abs(phasor(i, h))) for h in range(1, max_harmonic + 1)}
    rss = math.sqrt(sum(harmonics[h] ** 2 for h in range(2, max_harmonic + 1)))
    thd = rss / max(h1, 1e-12)
    distortion = h1 / max(math.sqrt(h1 * h1 + rss * rss), 1e-12)
    identity = abs(pf - dpf * distortion)
    conv = convention or THDConvention(included_harmonics=tuple(range(2, max_harmonic + 1)))
    notes: list[str] = []
    sanity = True
    if pf > 1.0 + 1e-6 or thd < -1e-12 or i_rms < 0.0:
        sanity = False
        notes.append("INVALID: PF>1 or THD<0 or negative RMS")
    status = status_if_ok if sanity else MetricStatus.WARN
    if identity > 0.05:
        notes.append(f"PF vs DPF×Distortion residual={identity:.4g} (window/DC effects)")
    return PFTHDResult(
        vac_rms_v=v_rms,
        iac_rms_a=i_rms,
        pin_w=pin,
        pout_w=pout_w,
        pf=pf,
        dpf=dpf,
        distortion_factor=distortion,
        thd=thd,
        thd_percent=100.0 * thd,
        h1_rms_a=h1,
        harmonics_rms_a=harmonics,
        convention=conv,
        pf_identity_residual=identity,
        status=status,
        sanity_ok=sanity,
        notes=tuple(notes),
    )


def pf_thd_from_waveforms(
    waveforms: PFCLineCycleWaveforms,
    *,
    line_hz: float,
    pout_w: float | None = None,
    max_harmonic: int = 25,
    convergence: LineCycleConvergenceResult | None = None,
) -> PFTHDResult:
    sl = _last_cycle_slice(np.asarray(waveforms.time_s, dtype=float), line_hz)
    status = MetricStatus.APPROXIMATION
    if convergence is not None:
        if convergence.status == ConvergenceStatus.LINE_CYCLE_CONVERGED:
            status = MetricStatus.VERIFIED
        elif convergence.status == ConvergenceStatus.NOT_CONVERGED:
            status = MetricStatus.WARN
    return compute_pf_thd(
        waveforms.time_s[sl],
        waveforms.signals["vac"][sl],
        waveforms.signals["i_input_signed"][sl],
        line_hz=line_hz,
        max_harmonic=max_harmonic,
        pout_w=pout_w,
        status_if_ok=status,
    )


_DEFAULT_REGIONS = (
    (0.0, 10.0),
    (10.0, 30.0),
    (30.0, 150.0),
    (150.0, 170.0),
    (170.0, 180.0),
)


def localize_distortion(
    line: PFCLineCycleResult,
    *,
    regions: Sequence[tuple[float, float]] = _DEFAULT_REGIONS,
) -> tuple[DistortionRegionResult, ...]:
    """Angle-local current-error map. Causes are evidence-gated, else UNKNOWN."""

    theta = np.asarray(line.theta_deg, dtype=float)
    half = theta % 180.0
    err = np.asarray(line.waveforms.signals["current_error"][line.settled_slice], dtype=float)
    iref = np.abs(np.asarray(line.iac_ref_a, dtype=float))
    zc = np.asarray(line.waveforms.signals["zero_cross_active"][line.settled_slice], dtype=float)
    min_pulse = np.asarray(line.waveforms.signals["minimum_pulse_active"][line.settled_slice], dtype=float)
    duty = np.asarray(line.duty, dtype=float)
    total_err_energy = float(np.sum(err ** 2)) + 1e-18
    out: list[DistortionRegionResult] = []
    for a0, a1 in regions:
        mask = (half >= a0) & (half < a1)
        if not np.any(mask):
            out.append(DistortionRegionResult(
                a0, a1, 0.0, 0.0, 0.0, DistortionCause.UNKNOWN, MetricStatus.UNKNOWN,
                notes="no samples in region",
            ))
            continue
        e_rms = float(np.sqrt(np.mean(err[mask] ** 2)))
        ref_rms = float(np.sqrt(np.mean(iref[mask] ** 2)))
        rel = e_rms / max(ref_rms, 1e-6)
        contrib = float(np.sum(err[mask] ** 2) / total_err_energy)
        cause = DistortionCause.UNKNOWN
        status = MetricStatus.UNKNOWN
        note = "insufficient separation — marked UNKNOWN"
        zc_frac = float(np.mean(zc[mask] > 0.5))
        mp_frac = float(np.mean(min_pulse[mask] > 0.5))
        sat_frac = float(np.mean((duty[mask] <= 0.02) | (duty[mask] >= 0.98)))
        if zc_frac > 0.5 and e_rms > 0.0:
            cause, status, note = DistortionCause.ZERO_CROSS, MetricStatus.APPROXIMATION, "ZC active dominates region"
        elif mp_frac > 0.4 and e_rms > 0.0:
            cause, status, note = DistortionCause.MIN_PULSE, MetricStatus.APPROXIMATION, "minimum-pulse active dominates"
        elif sat_frac > 0.4:
            cause, status, note = DistortionCause.DUTY_SATURATION, MetricStatus.APPROXIMATION, "duty near limits"
        elif a0 >= 30.0 and a1 <= 150.0 and rel > 0.05:
            cause, status, note = DistortionCause.CURRENT_LOOP, MetricStatus.APPROXIMATION, "mid-angle tracking error"
        out.append(DistortionRegionResult(
            a0, a1, e_rms, rel, contrib, cause, status, notes=note,
        ))
    return tuple(out)


def _pulse_width_s(duty: float, fsw_hz: float) -> float:
    return float(np.clip(duty, 0.0, 1.0) / max(fsw_hz, 1e-12))


def analyze_zero_crossing(
    config: PFCControlLabConfig,
    *,
    line: PFCLineCycleResult | None = None,
    sensor_offset_a: float = 0.0,
    zoom_windows_deg: Sequence[float] = (1.0, 2.0, 5.0, 10.0),
) -> ZeroCrossAnalysisResult:
    """Zero-crossing analyzer — waveform evidence + analytical min-pulse bound."""

    config.validate()
    stage = config.power_stage
    if line is None:
        line = build_line_cycle_result(config)
    fsw = stage.switching_frequency_hz
    period = 1.0 / fsw
    duty_min = max(stage.duty_min, stage.minimum_effective_pulse_s * fsw)
    dead_time = float(getattr(stage, "deadtime_s", 0.0) or 0.0)
    dead_v_err = stage.bus_voltage_v * dead_time * fsw
    min_current = duty_min * stage.bus_voltage_v / max(stage.boost_inductance_h * fsw, 1e-18)

    s = line.waveforms.signals
    sl = line.settled_slice
    theta = np.asarray(line.theta_deg, dtype=float)
    targets = (0.0, 180.0, 360.0)
    points: list[ZeroCrossPointResult] = []
    for target in targets:
        delta = np.abs(((theta - target + 180.0) % 360.0) - 180.0)
        idx = int(np.argmin(delta))
        vac = float(line.vac_v[idx])
        iref = float(line.iac_ref_a[idx])
        iact = float(line.iac_a[idx]) - sensor_offset_a
        duty_cmd = float(s["duty_unclamped"][sl][idx])
        duty_eff = float(line.duty[idx])
        pw = _pulse_width_s(duty_eff, fsw)
        pulse_valid = pw + 1e-15 >= stage.minimum_effective_pulse_s and duty_eff >= duty_min - 1e-12
        state = int(round(float(s["pwm_state_code"][sl][idx])))
        err = iref - iact
        margin = abs(iref) - min_current
        status = MetricStatus.APPROXIMATION
        notes: list[str] = []
        if not pulse_valid:
            status = MetricStatus.WARN
            notes.append("pulse below minimum / duty dead-zone")
        if abs(sensor_offset_a) > 1e-9:
            notes.append(f"sensor_offset={sensor_offset_a:.4g} A applied to Iactual")
        if dead_time > 0.0:
            notes.append("dead-time voltage error is APPROXIMATION")
        points.append(ZeroCrossPointResult(
            theta_deg=float(theta[idx]),
            vac_v=vac,
            iref_a=iref,
            iactual_a=iact,
            duty_cmd=duty_cmd,
            duty_effective=duty_eff,
            pulse_width_s=pw,
            pulse_valid=pulse_valid,
            commutation_state=state,
            current_error_a=float(err),
            distortion_margin_a=float(margin),
            constraint_status=status,
            notes="; ".join(notes),
        ))

    zooms: dict[float, tuple[ZeroCrossPointResult, ...]] = {}
    for window in zoom_windows_deg:
        w = float(window)
        mask = (theta % 180.0 <= w) | (theta % 180.0 >= (180.0 - w))
        idxs = np.nonzero(mask)[0]
        if idxs.size == 0:
            zooms[w] = ()
            continue
        step = max(int(len(idxs) / 41), 1)
        zoom_pts: list[ZeroCrossPointResult] = []
        for idx in idxs[::step]:
            vac = float(line.vac_v[idx])
            iref = float(line.iac_ref_a[idx])
            iact = float(line.iac_a[idx]) - sensor_offset_a
            duty_eff = float(line.duty[idx])
            pw = _pulse_width_s(duty_eff, fsw)
            zoom_pts.append(ZeroCrossPointResult(
                theta_deg=float(theta[idx]),
                vac_v=vac,
                iref_a=iref,
                iactual_a=iact,
                duty_cmd=float(s["duty_unclamped"][sl][idx]),
                duty_effective=duty_eff,
                pulse_width_s=pw,
                pulse_valid=pw >= stage.minimum_effective_pulse_s,
                commutation_state=int(round(float(s["pwm_state_code"][sl][idx]))),
                current_error_a=float(iref - iact),
                distortion_margin_a=float(abs(iref) - min_current),
                constraint_status=MetricStatus.APPROXIMATION,
            ))
        zooms[w] = tuple(zoom_pts)

    evidence = (
        PFCEvidenceResult(
            metric="minimum_realizable_current_a",
            value=min_current,
            unit="A",
            model="Dmin*Vbus/(L*fsw) near Vac≈0",
            source="PFCPowerStageConfig",
            status=MetricStatus.APPROXIMATION,
            assumptions=("Averaged CCM volt-second", "Vac≈0 at crossing"),
            corner="zero_cross",
            falsification_condition=(
                "If PWM TBCLK/compare resolution cannot realize Dmin, or DCM occurs, "
                "recompute with measured minimum pulse."
            ),
        ),
        PFCEvidenceResult(
            metric="dead_time_voltage_error_v",
            value=dead_v_err,
            unit="V",
            model="Vbus*td*fsw (pair-averaged)",
            source="power_stage.deadtime_s",
            status=MetricStatus.APPROXIMATION,
            assumptions=("Ideal switch edges", "no transistor-level recovery"),
            corner="zero_cross",
            falsification_condition="If measured volt-second error differs by >20%, mark model invalid.",
        ),
    )
    notes_t = (
        f"effective_duty_min={duty_min:.6g}",
        f"pwm_period={period:.6g}s",
        "Analytical dead-time and min-current are APPROXIMATION — not SPICE-level.",
    )
    return ZeroCrossAnalysisResult(
        points=tuple(points),
        zooms=zooms,
        minimum_realizable_current_a=float(min_current),
        effective_duty_deadzone=float(duty_min),
        dead_time_voltage_error_v=float(dead_v_err),
        sensor_offset_a=float(sensor_offset_a),
        status=MetricStatus.APPROXIMATION,
        evidence=evidence,
        notes=notes_t,
    )


def _stability_from_loop(
    name: str,
    loop: LoopResult,
    frequencies: FloatArray,
    open_key: str,
    budget_keys: Sequence[str],
    budget_labels: Mapping[str, str],
) -> PFCLoopStabilityV3:
    open_loop = loop.responses[open_key]
    margins = loop.margins
    sens = 1.0 / (1.0 + open_loop)
    comp = open_loop / (1.0 + open_loop)
    ms = float(np.nanmax(np.abs(sens)))
    mt = float(np.nanmax(np.abs(comp)))
    multi = len(margins.gain_crossovers_hz) > 1 or len(margins.phase_crossovers_hz) > 1
    status = MetricStatus.MULTI_CROSSOVER if multi else MetricStatus.APPROXIMATION
    fc = margins.critical_gain_crossover_hz
    pbudget = None
    if fc is not None:
        keys = [k for k in budget_keys if k in loop.responses]
        entries = phase_budget(frequencies, loop.responses, budget_labels, fc, keys)
        total = float(sum(e.phase_deg for e in entries))
        phase = np.unwrap(np.angle(open_loop)) * 180.0 / math.pi
        open_phase = float(np.interp(math.log10(fc), np.log10(frequencies), phase))
        while total - open_phase > 180.0:
            total -= 360.0
        while open_phase - total > 180.0:
            total += 360.0
        residual = total - open_phase
        pbudget = PhaseBudgetResult(
            frequency_hz=float(fc),
            entries=entries,
            total_phase_deg=total,
            open_loop_phase_deg=open_phase,
            phase_margin_deg=margins.phase_margin_deg,
            residual_deg=residual,
            consistent=abs(residual) <= 3.0,
            tolerance_deg=3.0,
        )
    return PFCLoopStabilityV3(
        name=name,
        fc_hz=fc,
        pm_deg=margins.phase_margin_deg,
        gm_db=margins.gain_margin_db,
        ms=ms,
        mt=mt,
        delay_margin_s=margins.delay_margin_s,
        multi_crossover=multi,
        phase_budget=pbudget,
        status=status,
    )


def build_loop_separation(analysis: PFCControlLabAnalysis) -> LoopSeparationResult:
    fc_i = analysis.current_loop.margins.critical_gain_crossover_hz
    fc_v = analysis.voltage_loop.margins.critical_gain_crossover_hz
    line_2x = 2.0 * analysis.config.power_stage.line_frequency_hz
    ratio = None if fc_i is None or fc_v is None or fc_v <= 0.0 else fc_i / fc_v
    vs = None if fc_v is None else fc_v / line_2x
    notes = [
        f"2×fline={line_2x:.6g} Hz must stay well above voltage-loop Fc to limit bus-ripple amplification.",
        "Current loop must remain faster than voltage loop (typical ratio ≫ 1).",
    ]
    status = MetricStatus.APPROXIMATION
    if ratio is not None and ratio < 5.0:
        status = MetricStatus.WARN
        notes.append(f"Fc_i/Fc_v={ratio:.3g} is low — outer/inner interaction risk")
    if vs is not None and vs > 0.3:
        status = MetricStatus.WARN
        notes.append(f"Fc_v is {vs:.3g}× of 2×fline — ripple rejection / PF risk")
    return LoopSeparationResult(
        fc_current_hz=fc_i,
        fc_voltage_hz=fc_v,
        ratio=ratio,
        line_2x_hz=line_2x,
        voltage_fc_vs_2fline=vs,
        status=status,
        notes=tuple(notes),
    )


def build_pfc_smart_control_v3(
    config: PFCControlLabConfig,
    *,
    analysis: PFCControlLabAnalysis | None = None,
) -> PFCSmartControlV3Result:
    """Dual-loop Smart Control V3: separation, Ms/Mt, phase budgets, Exact H(z)."""

    analysis = analysis or build_pfc_control_lab_analysis(config)
    handoff = build_pfc_control_handoff(analysis)
    separation = build_loop_separation(analysis)
    current = _stability_from_loop(
        "current",
        analysis.current_loop,
        analysis.frequencies_hz,
        "open_current",
        ("controller_ci", "indu_comp_gain", "pwm_zoh", "plant_gid", "sense_hi"),
        {
            "controller_ci": "Controller Ci(z)",
            "indu_comp_gain": "InduComp",
            "pwm_zoh": "PWM/ZOH/Delay",
            "plant_gid": "Current plant",
            "sense_hi": "Current sense",
        },
    )
    voltage = _stability_from_loop(
        "voltage",
        analysis.voltage_loop,
        analysis.frequencies_hz,
        "open_voltage",
        # bus_plant_gvg already embeds closed current dynamics — do not also budget Ti.
        ("controller_cv", "amc_vff", "bus_plant_gvg", "sense_hv"),
        {
            "controller_cv": "Controller Cv(z)",
            "amc_vff": "AMC/VFF",
            "bus_plant_gvg": "Bus plant × Ti",
            "sense_hv": "Vbus sense",
        },
    )
    evidence = (
        PFCEvidenceResult(
            metric="exact_hz_current",
            value=f"{handoff.current.loop_name}:{handoff.current.kind}",
            unit="",
            model="PFCControlHandoff frozen b[]/a[]",
            source="build_pfc_control_handoff",
            status=MetricStatus.VERIFIED,
            assumptions=("No Kp/Ti re-discretize on export",),
            corner="nominal",
            falsification_condition="If C99 regenerates coefficients from Kp/Ti, Exact H(z) chain is broken.",
        ),
        PFCEvidenceResult(
            metric="loop_separation_ratio",
            value=separation.ratio,
            unit="",
            model="Fc_current / Fc_voltage",
            source="PFCControlLabAnalysis margins",
            status=separation.status,
            assumptions=("Linear small-signal Bode",),
            corner="nominal OP",
            falsification_condition="If FRA shows current closed-loop peaking near Fc_v, separation claim is invalid.",
        ),
        PFCEvidenceResult(
            metric="2x_line_marker_hz",
            value=separation.line_2x_hz,
            unit="Hz",
            model="2 * fline",
            source="power_stage.line_frequency_hz",
            status=MetricStatus.VERIFIED,
            assumptions=("Grid frequency known",),
            corner="nominal",
            falsification_condition="If line frequency drifts beyond design band, recompute voltage-loop headroom.",
        ),
    )
    return PFCSmartControlV3Result(
        analysis=analysis,
        handoff=handoff,
        separation=separation,
        current=current,
        voltage=voltage,
        evidence=evidence,
    )


def run_pfc_engineering_v3_core(config: PFCControlLabConfig) -> dict[str, Any]:
    """One-shot Phase 2–4 + 7 pack for tests / Agent consumers."""

    line = build_line_cycle_result(config)
    pfthd = pf_thd_from_waveforms(
        line.waveforms,
        line_hz=config.power_stage.line_frequency_hz,
        pout_w=config.power_stage.output_power_w,
        convergence=line.convergence,
    )
    regions = localize_distortion(line)
    zc = analyze_zero_crossing(config, line=line)
    smart = build_pfc_smart_control_v3(config)
    if not pfthd.sanity_ok:
        raise ValueError(f"PF/THD sanity failed: {pfthd.notes}")
    return {
        "line_cycle": line.as_dict(),
        "pf_thd": pfthd.as_dict(),
        "distortion_regions": [r.as_dict() for r in regions],
        "zero_crossing": zc.as_dict(),
        "smart_control": smart.as_dict(),
        "instant_90deg": line.instant_point(90.0, pout_w=config.power_stage.output_power_w).as_dict(),
    }


__all__ = [
    "ConvergenceStatus",
    "DistortionCause",
    "DistortionRegionResult",
    "LineCycleConvergenceResult",
    "LoopSeparationResult",
    "PFCEvidenceResult",
    "PFCInstantPoint",
    "PFCLineCycleResult",
    "PFCLoopStabilityV3",
    "PFTHDResult",
    "PFCSmartControlV3Result",
    "THDConvention",
    "ZeroCrossAnalysisResult",
    "ZeroCrossPointResult",
    "analyze_zero_crossing",
    "assess_line_cycle_convergence",
    "build_line_cycle_result",
    "build_loop_separation",
    "build_pfc_smart_control_v3",
    "compute_pf_thd",
    "localize_distortion",
    "pf_thd_from_waveforms",
    "run_pfc_engineering_v3_core",
]
