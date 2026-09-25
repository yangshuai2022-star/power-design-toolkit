"""Smart Control V2 exact-loop construction, timing, budgets, robustness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .digital_loop import (
    ADCSamplingConfig,
    AnalogSenseConfig,
    CommandTimingConfig,
    DelayEnvelope,
    DigitalLoopAnalysis,
    DigitalTransferFunction,
    StabilityMargins,
    calculate_stability_margins,
)
from .phase_budget import PhaseBudgetEntry, phase_budget
from .solution_map import (
    SolutionMapConstraints,
    SolutionMapPoint,
    SolutionStatus,
    evaluate_solution_point,
    synthesize_tustin_pi_at_target,
)


FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


class LoopDomain(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    DISCRETE = "DISCRETE"
    DELAY = "DELAY"
    STATIC_GAIN = "STATIC_GAIN"
    NONLINEAR = "NONLINEAR"


class PlantResponseSource(str, Enum):
    ANALYTICAL = "ANALYTICAL"
    TIME_DOMAIN = "TIME_DOMAIN"
    MEASURED_FRA = "MEASURED_FRA"
    IDENTIFIED_MODEL = "IDENTIFIED_MODEL"


class MetricStatus(str, Enum):
    VERIFIED = "VERIFIED"
    APPROXIMATION = "APPROXIMATION"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"
    MULTI_CROSSOVER = "MULTI_CROSSOVER"


@dataclass(frozen=True)
class LoopBlock:
    name: str
    domain: LoopDomain
    sample_rate_hz: float | None
    gain: complex | float | None
    delay_s: float | None
    source: str
    status: MetricStatus
    poles: tuple[complex, ...] = ()
    zeros: tuple[complex, ...] = ()
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain.value,
            "sample_rate_hz": self.sample_rate_hz,
            "gain": None if self.gain is None else complex(self.gain),
            "delay_s": self.delay_s,
            "source": self.source,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class TimingModel:
    """Unique delay ownership — ADC vs compute vs PWM update vs ZOH."""

    sampling_delay_s: float
    adc_acquisition_time_s: float
    adc_conversion_time_s: float
    isr_latency_s: float
    compute_time_s: float
    shadow_write_time_s: float
    pwm_update_delay_s: float
    zoh_half_sample_s: float
    pwm_zero_wait_nominal_s: float
    include_zoh: bool

    @property
    def total_nominal_s(self) -> float:
        # ZOH half-sample is modelled in FR, not summed into pure delay total.
        return (
            self.sampling_delay_s
            + self.compute_time_s
            + self.isr_latency_s
            + self.shadow_write_time_s
            + self.pwm_update_delay_s
            + self.pwm_zero_wait_nominal_s
        )

    @property
    def total_min_s(self) -> float:
        return (
            self.sampling_delay_s
            + self.compute_time_s
            + self.isr_latency_s
            + self.shadow_write_time_s
            + self.pwm_update_delay_s
        )

    @property
    def total_max_s(self) -> float:
        return self.total_min_s + 2.0 * self.pwm_zero_wait_nominal_s

    def as_dict(self) -> dict[str, float | bool]:
        return {
            "sampling_delay_s": self.sampling_delay_s,
            "adc_acquisition_time_s": self.adc_acquisition_time_s,
            "adc_conversion_time_s": self.adc_conversion_time_s,
            "isr_latency_s": self.isr_latency_s,
            "compute_time_s": self.compute_time_s,
            "shadow_write_time_s": self.shadow_write_time_s,
            "pwm_update_delay_s": self.pwm_update_delay_s,
            "zoh_half_sample_s": self.zoh_half_sample_s,
            "pwm_zero_wait_nominal_s": self.pwm_zero_wait_nominal_s,
            "include_zoh": self.include_zoh,
            "total_min_s": self.total_min_s,
            "total_nominal_s": self.total_nominal_s,
            "total_max_s": self.total_max_s,
        }

    @staticmethod
    def from_loop_configs(
        adc: ADCSamplingConfig,
        timing: CommandTimingConfig,
        switching_frequency_hz: float,
    ) -> "TimingModel":
        acq = float(adc.acquisition_time_s)
        conv = float(adc.conversion_cycles) / max(float(adc.adc_clock_hz), 1.0)
        zoh = 0.5 * float(adc.control_sample_time_s) if timing.include_zero_order_hold else 0.0
        zero_wait = CommandTimingConfig.pwm_zero_wait_s(
            switching_frequency_hz, DelayEnvelope.NOMINAL)
        return TimingModel(
            sampling_delay_s=float(adc.eoc_delay_s),
            adc_acquisition_time_s=acq,
            adc_conversion_time_s=conv,
            isr_latency_s=0.0,
            compute_time_s=float(timing.computation_delay_s),
            shadow_write_time_s=0.0,
            pwm_update_delay_s=float(timing.pwm_update_delay_s),
            zoh_half_sample_s=zoh,
            pwm_zero_wait_nominal_s=zero_wait,
            include_zoh=bool(timing.include_zero_order_hold),
        )


@dataclass(frozen=True)
class PhaseBudgetResult:
    frequency_hz: float
    entries: tuple[PhaseBudgetEntry, ...]
    total_phase_deg: float
    open_loop_phase_deg: float
    phase_margin_deg: float | None
    residual_deg: float
    consistent: bool
    tolerance_deg: float = 2.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "entries": [
                {"key": e.key, "label": e.label, "gain_db": e.gain_db, "phase_deg": e.phase_deg}
                for e in self.entries
            ],
            "total_phase_deg": self.total_phase_deg,
            "open_loop_phase_deg": self.open_loop_phase_deg,
            "phase_margin_deg": self.phase_margin_deg,
            "residual_deg": self.residual_deg,
            "consistent": self.consistent,
        }


@dataclass(frozen=True)
class GainBudgetResult:
    frequency_hz: float
    entries: tuple[PhaseBudgetEntry, ...]
    total_gain_db: float
    open_loop_gain_db: float
    residual_db: float
    consistent: bool
    tolerance_db: float = 0.5

    def as_dict(self) -> dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "entries": [
                {"key": e.key, "label": e.label, "gain_db": e.gain_db, "phase_deg": e.phase_deg}
                for e in self.entries
            ],
            "total_gain_db": self.total_gain_db,
            "open_loop_gain_db": self.open_loop_gain_db,
            "residual_db": self.residual_db,
            "consistent": self.consistent,
        }


@dataclass(frozen=True)
class StabilityMetricsResult:
    margins: StabilityMargins
    ms: float
    mt: float
    closed_loop_poles: tuple[complex, ...]
    pole_stable: bool
    multi_crossover: bool
    status: MetricStatus

    def as_dict(self) -> dict[str, Any]:
        return {
            "fc_hz": self.margins.critical_gain_crossover_hz,
            "pm_deg": self.margins.phase_margin_deg,
            "gm_db": self.margins.gain_margin_db,
            "delay_margin_s": self.margins.delay_margin_s,
            "all_gain_crossovers_hz": list(self.margins.gain_crossovers_hz),
            "all_phase_crossovers_hz": list(self.margins.phase_crossovers_hz),
            "ms": self.ms,
            "mt": self.mt,
            "pole_stable": self.pole_stable,
            "multi_crossover": self.multi_crossover,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ControllerHeadroomResult:
    command_pu: float
    command_min: float
    command_max: float
    headroom_to_max: float
    headroom_to_min: float
    saturated: bool
    status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_pu": self.command_pu,
            "command_min": self.command_min,
            "command_max": self.command_max,
            "headroom_to_max": self.headroom_to_max,
            "headroom_to_min": self.headroom_to_min,
            "saturated": self.saturated,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SamplingRatioResult:
    fs_control_hz: float
    fc_hz: float | None
    fsw_hz: float
    fs_over_fc: float | None
    fsw_over_fc: float | None
    warn_threshold: float
    status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "fs_control_hz": self.fs_control_hz,
            "fc_hz": self.fc_hz,
            "fsw_hz": self.fsw_hz,
            "fs_over_fc": self.fs_over_fc,
            "fsw_over_fc": self.fsw_over_fc,
            "warn_threshold": self.warn_threshold,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class LoopEvidenceResult:
    metric: str
    value: float | str | None
    source_blocks: tuple[str, ...]
    assumptions: tuple[str, ...]
    status: MetricStatus
    falsification_condition: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "source_blocks": list(self.source_blocks),
            "assumptions": list(self.assumptions),
            "status": self.status.value,
            "falsification_condition": self.falsification_condition,
        }


@dataclass(frozen=True)
class PlantResponse:
    frequencies_hz: FloatArray
    complex_response: ComplexArray
    source: PlantResponseSource
    confidence: MetricStatus
    valid_frequency_range_hz: tuple[float, float]
    notes: str = ""


@dataclass(frozen=True)
class PlantCorrelationResult:
    gain_error_db_rms: float
    phase_error_deg_rms: float
    frequency_band_hz: tuple[float, float]
    confidence: MetricStatus
    notes: str = ""


@dataclass(frozen=True)
class ExactHzChainResult:
    b: tuple[float, ...]
    a: tuple[float, ...]
    sample_rate_hz: float
    float32_b: tuple[float, ...]
    float32_a: tuple[float, ...]
    gain_error_db_at_fc: float | None
    phase_error_deg_at_fc: float | None
    pm_shift_deg: float | None
    status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "b": list(self.b),
            "a": list(self.a),
            "sample_rate_hz": self.sample_rate_hz,
            "float32_b": list(self.float32_b),
            "float32_a": list(self.float32_a),
            "gain_error_db_at_fc": self.gain_error_db_at_fc,
            "phase_error_deg_at_fc": self.phase_error_deg_at_fc,
            "pm_shift_deg": self.pm_shift_deg,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class LoopCornerResult:
    corner_id: str
    fc_hz: float | None
    pm_deg: float | None
    gm_db: float | None
    ms: float
    mt: float
    delay_margin_s: float | None
    pole_stable: bool
    constraint_status: MetricStatus
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "corner_id": self.corner_id,
            "fc_hz": self.fc_hz,
            "pm_deg": self.pm_deg,
            "gm_db": self.gm_db,
            "ms": self.ms,
            "mt": self.mt,
            "delay_margin_s": self.delay_margin_s,
            "pole_stable": self.pole_stable,
            "constraint_status": self.constraint_status.value,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class LoopRobustnessReport:
    corners: tuple[LoopCornerResult, ...]
    worst_pm: LoopCornerResult | None
    worst_gm: LoopCornerResult | None
    worst_ms: LoopCornerResult | None
    worst_mt: LoopCornerResult | None
    worst_delay_margin: LoopCornerResult | None

    def as_dict(self) -> dict[str, Any]:
        def _id(item: LoopCornerResult | None) -> str | None:
            return None if item is None else item.corner_id
        return {
            "corners": [c.as_dict() for c in self.corners],
            "worst_pm_corner": _id(self.worst_pm),
            "worst_gm_corner": _id(self.worst_gm),
            "worst_ms_corner": _id(self.worst_ms),
            "worst_mt_corner": _id(self.worst_mt),
            "worst_delay_margin_corner": _id(self.worst_delay_margin),
        }


@dataclass(frozen=True)
class ControllerCandidate:
    name: str
    kp: float
    ti_s: float
    target_fc_hz: float
    target_pm_deg: float
    nominal: SolutionMapPoint
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kp": self.kp,
            "ti_s": self.ti_s,
            "target_fc_hz": self.target_fc_hz,
            "target_pm_deg": self.target_pm_deg,
            "feasible": self.nominal.feasible,
            "actual_fc_hz": self.nominal.actual_crossover_hz,
            "actual_pm_deg": self.nominal.actual_phase_margin_deg,
            "gm_db": self.nominal.gain_margin_db,
            "ms": self.nominal.ms,
            "mt": self.nominal.mt,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class LoopModel:
    """Exact loop construction wrapping a DigitalLoopAnalysis (single math authority)."""

    analysis: DigitalLoopAnalysis
    blocks: tuple[LoopBlock, ...]
    timing: TimingModel
    stability: StabilityMetricsResult
    phase_budget: PhaseBudgetResult | None
    gain_budget: GainBudgetResult | None
    headroom: ControllerHeadroomResult
    sampling: SamplingRatioResult
    evidence: tuple[LoopEvidenceResult, ...]
    chain_labels: tuple[str, ...]

    @property
    def frequencies_hz(self) -> FloatArray:
        return self.analysis.frequencies_hz

    @property
    def open_loop(self) -> ComplexArray:
        return self.analysis.nominal_open_loop

    @property
    def closed_loop(self) -> ComplexArray:
        return self.analysis.nominal_closed_loop

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain": list(self.chain_labels),
            "blocks": [b.as_dict() for b in self.blocks],
            "timing": self.timing.as_dict(),
            "stability": self.stability.as_dict(),
            "phase_budget": None if self.phase_budget is None else self.phase_budget.as_dict(),
            "gain_budget": None if self.gain_budget is None else self.gain_budget.as_dict(),
            "headroom": self.headroom.as_dict(),
            "sampling": self.sampling.as_dict(),
            "evidence": [e.as_dict() for e in self.evidence],
        }


# Multiplicative FR keys that reconstruct open_loop_nominal (single authority).
# delay_nominal owns eoc+compute+pwm_update+zero_wait (+ ZOH FR); do not
# invent a parallel "command_timing_nominal" response.
_BUDGET_KEYS = (
    "controller",
    "fm_power_stage",
    "sense_analog_calibrated",
    "adc_sampling",
    "delay_nominal",
)
_BUDGET_LABELS = {
    "controller": "Controller",
    "fm_power_stage": "FM × Plant",
    "sense_analog_calibrated": "Sensor / Analog",
    "adc_sampling": "ADC aperture / recursive",
    "delay_nominal": "Timing (EOC+compute+PWM+ZOH)",
}


def _unwrap_phase_at(frequencies: FloatArray, response: ComplexArray, frequency_hz: float) -> float:
    phase = np.unwrap(np.angle(response)) * 180.0 / math.pi
    x = math.log10(max(frequency_hz, float(frequencies[0])))
    return float(np.interp(x, np.log10(frequencies), phase))


def _gain_db_at(frequencies: FloatArray, response: ComplexArray, frequency_hz: float) -> float:
    mag = 20.0 * np.log10(np.maximum(np.abs(response), 1e-300))
    x = math.log10(max(frequency_hz, float(frequencies[0])))
    return float(np.interp(x, np.log10(frequencies), mag))


def compute_stability_metrics(analysis: DigitalLoopAnalysis) -> StabilityMetricsResult:
    open_loop = analysis.nominal_open_loop
    margins = analysis.margins_nominal_delay
    sensitivity = 1.0 / (1.0 + open_loop)
    complementary = open_loop / (1.0 + open_loop)
    ms = float(np.nanmax(np.abs(sensitivity)))
    mt = float(np.nanmax(np.abs(complementary)))
    multi = len(margins.gain_crossovers_hz) > 1 or len(margins.phase_crossovers_hz) > 1
    status = MetricStatus.MULTI_CROSSOVER if multi else MetricStatus.APPROXIMATION
    return StabilityMetricsResult(
        margins=margins,
        ms=ms,
        mt=mt,
        closed_loop_poles=tuple(complex(p) for p in analysis.discrete_approximation.closed_loop_poles),
        pole_stable=bool(analysis.discrete_approximation.stable),
        multi_crossover=multi,
        status=status,
    )


def compute_phase_budget(
    analysis: DigitalLoopAnalysis,
    *,
    frequency_hz: float | None = None,
    tolerance_deg: float = 2.0,
) -> PhaseBudgetResult | None:
    fc = frequency_hz or analysis.margins_nominal_delay.critical_gain_crossover_hz
    if fc is None:
        return None
    keys = [k for k in _BUDGET_KEYS if k in analysis.responses]
    entries = phase_budget(analysis.frequencies_hz, analysis.responses, _BUDGET_LABELS, fc, keys)
    total = float(sum(e.phase_deg for e in entries))
    open_phase = _unwrap_phase_at(analysis.frequencies_hz, analysis.nominal_open_loop, fc)
    # Align total to same 360° branch as open_loop phase near -180.
    while total - open_phase > 180.0:
        total -= 360.0
    while open_phase - total > 180.0:
        total += 360.0
    residual = total - open_phase
    pm = analysis.margins_nominal_delay.phase_margin_deg
    return PhaseBudgetResult(
        frequency_hz=float(fc),
        entries=entries,
        total_phase_deg=total,
        open_loop_phase_deg=open_phase,
        phase_margin_deg=pm,
        residual_deg=residual,
        consistent=abs(residual) <= tolerance_deg,
        tolerance_deg=tolerance_deg,
    )


def compute_gain_budget(
    analysis: DigitalLoopAnalysis,
    *,
    frequency_hz: float | None = None,
    tolerance_db: float = 0.5,
) -> GainBudgetResult | None:
    fc = frequency_hz or analysis.margins_nominal_delay.critical_gain_crossover_hz
    if fc is None:
        return None
    keys = [k for k in _BUDGET_KEYS if k in analysis.responses]
    entries = phase_budget(analysis.frequencies_hz, analysis.responses, _BUDGET_LABELS, fc, keys)
    total = float(sum(e.gain_db for e in entries))
    open_gain = _gain_db_at(analysis.frequencies_hz, analysis.nominal_open_loop, fc)
    residual = total - open_gain
    return GainBudgetResult(
        frequency_hz=float(fc),
        entries=entries,
        total_gain_db=total,
        open_loop_gain_db=open_gain,
        residual_db=residual,
        consistent=abs(residual) <= tolerance_db,
        tolerance_db=tolerance_db,
    )


def compute_headroom(
    analysis: DigitalLoopAnalysis,
    *,
    command_min: float = 0.0,
    command_max: float = 1.0,
) -> ControllerHeadroomResult:
    cmd = float(analysis.fm_operating_point.command_pu)
    sat = cmd <= command_min + 1e-9 or cmd >= command_max - 1e-9
    return ControllerHeadroomResult(
        command_pu=cmd,
        command_min=command_min,
        command_max=command_max,
        headroom_to_max=command_max - cmd,
        headroom_to_min=cmd - command_min,
        saturated=sat,
        status=MetricStatus.WARN if sat else MetricStatus.APPROXIMATION,
        notes="Static PCMD headroom at the analyzed operating point (linear Bode does not include anti-windup).",
    )


def compute_sampling_ratio(
    analysis: DigitalLoopAnalysis,
    *,
    warn_threshold: float = 10.0,
) -> SamplingRatioResult:
    fs = 1.0 / float(analysis.controller.sample_time_s)
    fsw = float(analysis.small_signal.operating_point.switching_frequency_hz)
    fc = analysis.margins_nominal_delay.critical_gain_crossover_hz
    fs_over = None if fc is None or fc <= 0.0 else fs / fc
    fsw_over = None if fc is None or fc <= 0.0 else fsw / fc
    status = MetricStatus.APPROXIMATION
    notes = "Sampling ratio is a configurable warning rule, not a universal 10× guarantee."
    if fs_over is not None and fs_over < warn_threshold:
        status = MetricStatus.WARN
        notes = f"Fs/Fc={fs_over:.2f} below warn_threshold={warn_threshold:g}"
    return SamplingRatioResult(
        fs_control_hz=fs,
        fc_hz=fc,
        fsw_hz=fsw,
        fs_over_fc=fs_over,
        fsw_over_fc=fsw_over,
        warn_threshold=warn_threshold,
        status=status,
        notes=notes,
    )


def build_loop_blocks(analysis: DigitalLoopAnalysis, timing: TimingModel) -> tuple[LoopBlock, ...]:
    fs = 1.0 / float(analysis.controller.sample_time_s)
    return (
        LoopBlock("controller", LoopDomain.DISCRETE, fs, None, None,
                  analysis.controller_source, MetricStatus.VERIFIED,
                  notes=analysis.controller.name),
        LoopBlock("fm_modulator", LoopDomain.STATIC_GAIN, None,
                  complex(analysis.fm_operating_point.gain_hz_per_pu), None,
                  "FrequencyModulatorLUT", MetricStatus.APPROXIMATION,
                  notes="local FM slope at operating PCMD"),
        LoopBlock("plant", LoopDomain.CONTINUOUS, None, None, None,
                  "LLC Gvf(s) small-signal", MetricStatus.APPROXIMATION),
        LoopBlock("sensor_analog", LoopDomain.CONTINUOUS, None, None, None,
                  "AnalogSenseConfig", MetricStatus.APPROXIMATION),
        LoopBlock("adc_digital_filter", LoopDomain.DISCRETE, fs, None,
                  timing.sampling_delay_s, "ADCSamplingConfig", MetricStatus.APPROXIMATION,
                  notes="owns acquisition/conversion; not double-counted in compute"),
        LoopBlock("compute_pwm_timing", LoopDomain.DELAY, fs, None,
                  timing.compute_time_s + timing.pwm_update_delay_s,
                  "CommandTimingConfig", MetricStatus.APPROXIMATION,
                  notes="owns compute + pwm_update; ZOH separate"),
        LoopBlock("zoh", LoopDomain.DELAY if timing.include_zoh else LoopDomain.STATIC_GAIN,
                  fs, 1.0 if not timing.include_zoh else None,
                  timing.zoh_half_sample_s if timing.include_zoh else 0.0,
                  "CommandTimingConfig.ZOH", MetricStatus.APPROXIMATION),
    )


def build_loop_evidence(
    analysis: DigitalLoopAnalysis,
    stability: StabilityMetricsResult,
    timing: TimingModel,
) -> tuple[LoopEvidenceResult, ...]:
    pm = stability.margins.phase_margin_deg
    fc = stability.margins.critical_gain_crossover_hz
    items = [
        LoopEvidenceResult(
            metric="phase_margin_deg",
            value=pm,
            source_blocks=("controller", "fm_power_stage", "sense", "adc", "timing"),
            assumptions=(
                "Linear mixed-domain Bode",
                "Const-current / averaged plant",
                f"Timing total_nominal={timing.total_nominal_s * 1e6:.3f} µs",
            ),
            status=stability.status,
            falsification_condition=(
                f"If measured plant phase at Fc≈{fc} Hz is >10° more lagging than the model, "
                "or ISR/PWM total delay exceeds the TimingModel by >15 µs, this PM is invalid."
            ),
        ),
        LoopEvidenceResult(
            metric="Ms",
            value=stability.ms,
            source_blocks=("open_loop",),
            assumptions=("S=1/(1+L) on the analysis frequency grid",),
            status=MetricStatus.APPROXIMATION,
            falsification_condition="If an unmodelled resonance exists between grid points, Ms may be understated.",
        ),
        LoopEvidenceResult(
            metric="exact_hz_source",
            value=analysis.controller_source,
            source_blocks=("controller",),
            assumptions=("b[]/a[] from controller TF used for Bode and export",),
            status=MetricStatus.VERIFIED if "Control Tools" in analysis.controller_source
            or "local" in analysis.controller_source.lower()
            else MetricStatus.APPROXIMATION,
            falsification_condition="If C99 export re-discretizes from Kp/Ti instead of copying b/a, Exact H(z) chain is broken.",
        ),
    ]
    return tuple(items)


def build_loop_model(analysis: DigitalLoopAnalysis) -> LoopModel:
    """Construct Smart Control V2 LoopModel from an existing DigitalLoopAnalysis."""

    fsw = float(analysis.small_signal.operating_point.switching_frequency_hz)
    timing = TimingModel.from_loop_configs(
        analysis.adc_sampling, analysis.command_timing, fsw)
    stability = compute_stability_metrics(analysis)
    pbudget = compute_phase_budget(analysis)
    gbudget = compute_gain_budget(analysis)
    headroom = compute_headroom(analysis)
    sampling = compute_sampling_ratio(analysis)
    blocks = build_loop_blocks(analysis, timing)
    evidence = build_loop_evidence(analysis, stability, timing)
    chain = (
        "C(z)", "FM Gain", "PWM/ZOH", "Computation+PWM Update",
        "LLC Gvf", "Sensor", "ADC/Digital Filter",
    )
    return LoopModel(
        analysis=analysis,
        blocks=blocks,
        timing=timing,
        stability=stability,
        phase_budget=pbudget,
        gain_budget=gbudget,
        headroom=headroom,
        sampling=sampling,
        evidence=evidence,
        chain_labels=chain,
    )


def pure_delay_phase_deg(delay_s: float, frequency_hz: float) -> float:
    return -360.0 * float(delay_s) * float(frequency_hz)


def evaluate_solution_map_v2_point(
    frequencies_hz: Sequence[float] | FloatArray,
    fixed_loop_response: Sequence[complex] | ComplexArray,
    *,
    sample_rate_hz: float,
    switching_frequency_hz: float,
    target_crossover_hz: float,
    target_phase_margin_deg: float,
    constraints: SolutionMapConstraints | None = None,
    mt_max: float | None = None,
    sampling_warn_threshold: float = 10.0,
) -> SolutionMapPoint:
    """Solution Map V2: synthesize → rebuild loop → full metrics → classify."""

    point = evaluate_solution_point(
        frequencies_hz,
        fixed_loop_response,
        sample_rate_hz=sample_rate_hz,
        switching_frequency_hz=switching_frequency_hz,
        target_crossover_hz=target_crossover_hz,
        target_phase_margin_deg=target_phase_margin_deg,
        constraints=constraints,
    )
    if not point.feasible:
        return point
    # Extra V2 gates: Mt and sampling ratio.
    messages = []
    status = point.status
    if mt_max is not None and point.mt is not None and point.mt > mt_max:
        status = SolutionStatus.MS_CONSTRAINT_FAIL
        messages.append(f"Mt={point.mt:.3f} exceeds Mt_max={mt_max:g}")
    if point.actual_crossover_hz and point.actual_crossover_hz > 0.0:
        ratio = sample_rate_hz / point.actual_crossover_hz
        if ratio < sampling_warn_threshold:
            messages.append(f"Fs/Fc={ratio:.2f} below warn threshold {sampling_warn_threshold:g}")
            # Warn does not flip FEASIBLE → keep FEASIBLE but annotate.
    note = point.message
    if messages:
        note = (note + "; " if note else "") + "; ".join(messages)
    if status == point.status and note == point.message:
        return point
    return SolutionMapPoint(
        target_crossover_hz=point.target_crossover_hz,
        target_phase_margin_deg=point.target_phase_margin_deg,
        status=status,
        kp=point.kp,
        ti_s=point.ti_s,
        actual_crossover_hz=point.actual_crossover_hz,
        actual_phase_margin_deg=point.actual_phase_margin_deg,
        gain_margin_db=point.gain_margin_db,
        ms=point.ms,
        mt=point.mt,
        switching_loop_gain_db=point.switching_loop_gain_db,
        controller_phase_deg=point.controller_phase_deg,
        message=note,
    )


def synthesize_controller_candidates(
    frequencies_hz: Sequence[float] | FloatArray,
    fixed_loop_response: Sequence[complex] | ComplexArray,
    *,
    sample_rate_hz: float,
    switching_frequency_hz: float,
    base_fc_hz: float,
    base_pm_deg: float,
    constraints: SolutionMapConstraints | None = None,
) -> tuple[ControllerCandidate, ...]:
    """Robust / Balanced / Fast PI candidates — user chooses, no opaque score."""

    specs = (
        ("Robust", base_fc_hz * 0.75, min(base_pm_deg + 10.0, 75.0)),
        ("Balanced", base_fc_hz, base_pm_deg),
        ("Fast", base_fc_hz * 1.25, max(base_pm_deg - 8.0, 35.0)),
    )
    out: list[ControllerCandidate] = []
    for name, fc, pm in specs:
        point = evaluate_solution_map_v2_point(
            frequencies_hz,
            fixed_loop_response,
            sample_rate_hz=sample_rate_hz,
            switching_frequency_hz=switching_frequency_hz,
            target_crossover_hz=fc,
            target_phase_margin_deg=pm,
            constraints=constraints,
        )
        if point.kp is None or point.ti_s is None:
            continue
        out.append(ControllerCandidate(
            name=name, kp=point.kp, ti_s=point.ti_s,
            target_fc_hz=fc, target_pm_deg=pm, nominal=point,
            notes="Tustin PI Exact H(z); compare worst-corner metrics before install",
        ))
    return tuple(out)


def build_robustness_report(
    corner_loops: Mapping[str, tuple[FloatArray, ComplexArray]],
    *,
    discrete_stable: Mapping[str, bool] | None = None,
) -> LoopRobustnessReport:
    """Aggregate per-corner open-loop responses into a robustness report."""

    corners: list[LoopCornerResult] = []
    for corner_id, (freq, open_loop) in corner_loops.items():
        margins = calculate_stability_margins(freq, open_loop)
        sens = 1.0 / (1.0 + open_loop)
        comp = open_loop / (1.0 + open_loop)
        ms = float(np.nanmax(np.abs(sens)))
        mt = float(np.nanmax(np.abs(comp)))
        pole_ok = True if discrete_stable is None else bool(discrete_stable.get(corner_id, True))
        pm = margins.phase_margin_deg
        gm = margins.gain_margin_db
        status = MetricStatus.APPROXIMATION
        if pm is None or pm <= 0.0 or (gm is not None and gm <= 0.0) or not pole_ok:
            status = MetricStatus.WARN
        corners.append(LoopCornerResult(
            corner_id=corner_id,
            fc_hz=margins.critical_gain_crossover_hz,
            pm_deg=pm,
            gm_db=gm,
            ms=ms,
            mt=mt,
            delay_margin_s=margins.delay_margin_s,
            pole_stable=pole_ok,
            constraint_status=status,
        ))

    def _worst(key, prefer_min: bool = True):
        scored = []
        for c in corners:
            value = getattr(c, key)
            if value is None:
                continue
            scored.append((c, float(value)))
        if not scored:
            return None
        return (min if prefer_min else max)(scored, key=lambda item: item[1])[0]

    return LoopRobustnessReport(
        corners=tuple(corners),
        worst_pm=_worst("pm_deg", True),
        worst_gm=_worst("gm_db", True),
        worst_ms=_worst("ms", False),
        worst_mt=_worst("mt", False),
        worst_delay_margin=_worst("delay_margin_s", True),
    )


def verify_exact_hz_float32(
    controller: DigitalTransferFunction,
    fixed_loop: ComplexArray,
    frequencies_hz: FloatArray,
    *,
    fc_hz: float | None,
    pm_tol_deg: float = 1.0,
    gain_tol_db: float = 0.25,
) -> ExactHzChainResult:
    """Compare double-precision H(z) vs float32 quantized coefficients on the same fixed loop."""

    b = np.asarray(controller.numerator, dtype=float)
    a = np.asarray(controller.denominator, dtype=float)
    b32 = b.astype(np.float32).astype(float)
    a32 = a.astype(np.float32).astype(float)
    ctrl32 = DigitalTransferFunction(
        b32, a32, controller.sample_time_s, name=controller.name + "/float32")
    loop64 = fixed_loop * controller.frequency_response(frequencies_hz)
    loop32 = fixed_loop * ctrl32.frequency_response(frequencies_hz)
    m64 = calculate_stability_margins(frequencies_hz, loop64)
    m32 = calculate_stability_margins(frequencies_hz, loop32)
    gain_err = None
    phase_err = None
    if fc_hz is not None:
        gain_err = abs(_gain_db_at(frequencies_hz, loop32, fc_hz) - _gain_db_at(frequencies_hz, loop64, fc_hz))
        phase_err = abs(
            _unwrap_phase_at(frequencies_hz, loop32, fc_hz)
            - _unwrap_phase_at(frequencies_hz, loop64, fc_hz)
        )
    pm_shift = None
    if m64.phase_margin_deg is not None and m32.phase_margin_deg is not None:
        pm_shift = abs(m32.phase_margin_deg - m64.phase_margin_deg)
    status = MetricStatus.VERIFIED
    notes = "float32 uses IEEE-754 single round-trip on exact b/a"
    if (
        (gain_err is not None and gain_err > gain_tol_db)
        or (phase_err is not None and phase_err > pm_tol_deg)
        or (pm_shift is not None and pm_shift > pm_tol_deg)
    ):
        status = MetricStatus.WARN
        notes = "FLOAT32_WARNING: quantized H(z) shifts Fc/PM beyond tolerance"
    return ExactHzChainResult(
        b=tuple(float(x) for x in b),
        a=tuple(float(x) for x in a),
        sample_rate_hz=1.0 / float(controller.sample_time_s),
        float32_b=tuple(float(x) for x in b32),
        float32_a=tuple(float(x) for x in a32),
        gain_error_db_at_fc=gain_err,
        phase_error_deg_at_fc=phase_err,
        pm_shift_deg=pm_shift,
        status=status,
        notes=notes,
    )


def _complex_log_interp(
    frequencies_hz: FloatArray,
    response: ComplexArray,
    targets_hz: FloatArray,
) -> ComplexArray:
    x = np.log(np.asarray(frequencies_hz, dtype=float))
    mag = np.log(np.maximum(np.abs(response), 1e-300))
    phase = np.unwrap(np.angle(response))
    out = []
    for t in targets_hz:
        xt = math.log(float(t))
        out.append(
            math.exp(float(np.interp(xt, x, mag)))
            * np.exp(1j * float(np.interp(xt, x, phase)))
        )
    return np.asarray(out, dtype=complex)


def correlate_plant_responses(
    analytical: PlantResponse,
    measured: PlantResponse,
) -> PlantCorrelationResult:
    f0 = max(analytical.valid_frequency_range_hz[0], measured.valid_frequency_range_hz[0])
    f1 = min(analytical.valid_frequency_range_hz[1], measured.valid_frequency_range_hz[1])
    if f1 <= f0:
        return PlantCorrelationResult(
            float("nan"), float("nan"), (f0, f1), MetricStatus.UNKNOWN,
            notes="No overlapping valid frequency band",
        )
    grid = np.geomspace(f0, f1, 64)
    a_resp = _complex_log_interp(analytical.frequencies_hz, analytical.complex_response, grid)
    m_resp = _complex_log_interp(measured.frequencies_hz, measured.complex_response, grid)
    gain_err = 20.0 * np.log10(np.maximum(np.abs(a_resp), 1e-300)) - 20.0 * np.log10(
        np.maximum(np.abs(m_resp), 1e-300))
    phase_err = (np.unwrap(np.angle(a_resp)) - np.unwrap(np.angle(m_resp))) * 180.0 / math.pi
    return PlantCorrelationResult(
        gain_error_db_rms=float(np.sqrt(np.mean(gain_err ** 2))),
        phase_error_deg_rms=float(np.sqrt(np.mean(phase_err ** 2))),
        frequency_band_hz=(float(f0), float(f1)),
        confidence=MetricStatus.APPROXIMATION,
        notes="Analytical vs measured kept as separate curves; correlation does not merge them.",
    )


@dataclass(frozen=True)
class NoiseRiskResult:
    controller_hf_gain_db: float
    complementary_hf_mt: float
    status: MetricStatus
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "controller_hf_gain_db": self.controller_hf_gain_db,
            "complementary_hf_mt": self.complementary_hf_mt,
            "status": self.status.value,
            "notes": self.notes,
        }


def assess_noise_risk(
    analysis: DigitalLoopAnalysis,
    *,
    hf_fraction_of_nyquist: float = 0.4,
    controller_gain_warn_db: float = 20.0,
) -> NoiseRiskResult:
    """Basic high-frequency noise risk — not a full PSD analysis."""

    fs = 1.0 / float(analysis.controller.sample_time_s)
    f_hf = hf_fraction_of_nyquist * 0.5 * fs
    f_hf = float(np.clip(f_hf, analysis.frequencies_hz[0], analysis.frequencies_hz[-1]))
    c_gain = _gain_db_at(analysis.frequencies_hz, analysis.responses["controller"], f_hf)
    t_resp = analysis.nominal_closed_loop
    mt_hf = float(np.abs(
        _complex_log_interp(
            analysis.frequencies_hz, t_resp, np.asarray([f_hf], dtype=float)
        )[0]
    ))
    status = MetricStatus.APPROXIMATION
    notes = f"|C| and |T| sampled near {f_hf:.4g} Hz"
    if c_gain > controller_gain_warn_db:
        status = MetricStatus.WARN
        notes = f"controller high-frequency gain {c_gain:.2f} dB exceeds warn {controller_gain_warn_db:g} dB"
    return NoiseRiskResult(
        controller_hf_gain_db=c_gain,
        complementary_hf_mt=mt_hf,
        status=status,
        notes=notes,
    )


def fixed_loop_without_controller(analysis: DigitalLoopAnalysis) -> ComplexArray:
    """Plant×FM×sense×delay — Solution Map / Exact H(z) rebuild input."""

    ctrl = analysis.responses["controller"]
    open_loop = analysis.nominal_open_loop
    with np.errstate(divide="ignore", invalid="ignore"):
        fixed = np.where(np.abs(ctrl) > 1e-30, open_loop / ctrl, 0.0 + 0.0j)
    return np.asarray(fixed, dtype=complex)


__all__ = [
    "ControllerCandidate",
    "ControllerHeadroomResult",
    "ExactHzChainResult",
    "GainBudgetResult",
    "LoopBlock",
    "LoopCornerResult",
    "LoopDomain",
    "LoopEvidenceResult",
    "LoopModel",
    "LoopRobustnessReport",
    "MetricStatus",
    "NoiseRiskResult",
    "PhaseBudgetResult",
    "PlantCorrelationResult",
    "PlantResponse",
    "PlantResponseSource",
    "SamplingRatioResult",
    "StabilityMetricsResult",
    "TimingModel",
    "assess_noise_risk",
    "build_loop_model",
    "build_robustness_report",
    "compute_gain_budget",
    "compute_phase_budget",
    "compute_stability_metrics",
    "correlate_plant_responses",
    "evaluate_solution_map_v2_point",
    "fixed_loop_without_controller",
    "pure_delay_phase_deg",
    "synthesize_controller_candidates",
    "verify_exact_hz_float32",
]
