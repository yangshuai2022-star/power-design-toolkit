"""FHA ↔ switched time-domain cross-validation on critical LLC points.

Reuses existing ``solve_fha`` / ``solve_time_domain`` kernels. Does not invent
new tank physics. Emits per-metric DeviationResult and an overall
MODEL_VALIDITY of PASS / WARN / FAIL / UNKNOWN.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .fha import solve_fha
from .metrics import relative_error_percent
from .time_domain import TimeDomainConfig, solve_time_domain
from .types import LLCAnalysisRequest, LLCModelResult, ModelMetrics
from ..core.engineering import ConstraintStatus
from ..core.spec import LLCDesignSpec


class ModelValidity(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ValidityThresholds:
    """Relative percent thresholds for FHA vs TD disagreement."""

    warn_percent: float = 8.0
    fail_percent: float = 20.0
    frequency_warn_percent: float = 5.0
    frequency_fail_percent: float = 12.0
    phase_warn_deg: float = 8.0
    phase_fail_deg: float = 20.0

    def validate(self) -> None:
        if not (0.0 < self.warn_percent <= self.fail_percent):
            raise ValueError("warn_percent must be in (0, fail_percent]")
        if not (0.0 < self.frequency_warn_percent <= self.frequency_fail_percent):
            raise ValueError("frequency warn/fail thresholds invalid")
        if not (0.0 < self.phase_warn_deg <= self.phase_fail_deg):
            raise ValueError("phase warn/fail thresholds invalid")


@dataclass(frozen=True)
class DeviationResult:
    metric: str
    fha_value: float
    td_value: float
    deviation_percent: float
    absolute_deviation: float
    status: ConstraintStatus
    units: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, float | str]:
        return {
            "metric": self.metric,
            "fha_value": self.fha_value,
            "td_value": self.td_value,
            "deviation_percent": self.deviation_percent,
            "absolute_deviation": self.absolute_deviation,
            "status": self.status.value,
            "units": self.units,
            "message": self.message,
        }


@dataclass(frozen=True)
class FhaTdPointValidation:
    request: LLCAnalysisRequest
    fha: LLCModelResult | None
    td: LLCModelResult | None
    deviations: tuple[DeviationResult, ...]
    model_validity: ModelValidity
    warnings: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return (
            f"Vin={self.request.bus_voltage_v:.0f}V_"
            f"load={self.request.load_fraction*100:.0f}pct"
        )


@dataclass(frozen=True)
class FhaTdValidationReport:
    points: tuple[FhaTdPointValidation, ...]
    overall_validity: ModelValidity
    thresholds: ValidityThresholds
    warnings: tuple[str, ...] = ()

    def as_summary(self) -> dict[str, str | int]:
        return {
            "MODEL_VALIDITY": self.overall_validity.value,
            "points": len(self.points),
            "pass": sum(1 for p in self.points if p.model_validity == ModelValidity.PASS),
            "warn": sum(1 for p in self.points if p.model_validity == ModelValidity.WARN),
            "fail": sum(1 for p in self.points if p.model_validity == ModelValidity.FAIL),
            "unknown": sum(1 for p in self.points if p.model_validity == ModelValidity.UNKNOWN),
        }


_VALIDITY_RANK = {
    ModelValidity.PASS: 0,
    ModelValidity.UNKNOWN: 1,
    ModelValidity.WARN: 2,
    ModelValidity.FAIL: 3,
}


def _merge_validity(*values: ModelValidity) -> ModelValidity:
    if not values:
        return ModelValidity.UNKNOWN
    return max(values, key=lambda v: _VALIDITY_RANK[v])


def _status_from_percent(
    deviation_percent: float,
    warn: float,
    fail: float,
) -> ConstraintStatus:
    mag = abs(deviation_percent)
    if mag >= fail:
        return ConstraintStatus.FAIL
    if mag >= warn:
        return ConstraintStatus.WARN
    return ConstraintStatus.PASS


def _status_from_abs(
    absolute_deviation: float,
    warn: float,
    fail: float,
) -> ConstraintStatus:
    mag = abs(absolute_deviation)
    if mag >= fail:
        return ConstraintStatus.FAIL
    if mag >= warn:
        return ConstraintStatus.WARN
    return ConstraintStatus.PASS


def _metric_deviation(
    name: str,
    fha: float,
    td: float,
    thresholds: ValidityThresholds,
    *,
    units: str = "",
    mode: str = "percent",
) -> DeviationResult:
    abs_dev = td - fha
    if mode == "phase_deg":
        status = _status_from_abs(abs_dev, thresholds.phase_warn_deg, thresholds.phase_fail_deg)
        pct = relative_error_percent(td, fha) if abs(fha) > 1e-12 else 0.0
    elif name == "switching_frequency_hz":
        pct = relative_error_percent(td, fha)
        status = _status_from_percent(
            pct, thresholds.frequency_warn_percent, thresholds.frequency_fail_percent)
    else:
        pct = relative_error_percent(td, fha)
        status = _status_from_percent(pct, thresholds.warn_percent, thresholds.fail_percent)
    return DeviationResult(
        metric=name,
        fha_value=float(fha),
        td_value=float(td),
        deviation_percent=float(pct),
        absolute_deviation=float(abs_dev),
        status=status,
        units=units,
        message=f"|Δ|={abs(pct):.2f}% ({status.value})",
    )


def compare_fha_td_metrics(
    fha: ModelMetrics,
    td: ModelMetrics,
    thresholds: ValidityThresholds | None = None,
) -> tuple[DeviationResult, ...]:
    """Compare the critical FHA↔TD electrical quantities."""

    thr = thresholds or ValidityThresholds()
    thr.validate()
    return (
        _metric_deviation(
            "switching_frequency_hz",
            fha.switching_frequency_hz, td.switching_frequency_hz, thr, units="Hz"),
        _metric_deviation(
            "normalized_gain",
            fha.normalized_gain, td.normalized_gain, thr),
        _metric_deviation(
            "resonant_current_rms_a",
            fha.resonant_current_rms_a, td.resonant_current_rms_a, thr, units="A"),
        _metric_deviation(
            "resonant_current_peak_a",
            fha.resonant_current_peak_a, td.resonant_current_peak_a, thr, units="A"),
        _metric_deviation(
            "magnetizing_current_peak_a",
            fha.magnetizing_current_peak_a, td.magnetizing_current_peak_a, thr, units="A"),
        _metric_deviation(
            "input_phase_deg",
            fha.input_phase_deg, td.input_phase_deg, thr,
            units="deg", mode="phase_deg"),
    )


def _validity_from_deviations(
    deviations: Sequence[DeviationResult],
    *,
    fha_ok: bool,
    td_ok: bool,
) -> ModelValidity:
    if not fha_ok or not td_ok:
        return ModelValidity.UNKNOWN
    statuses = [d.status for d in deviations]
    if any(s == ConstraintStatus.FAIL for s in statuses):
        return ModelValidity.FAIL
    if any(s == ConstraintStatus.WARN for s in statuses):
        return ModelValidity.WARN
    if any(s == ConstraintStatus.UNKNOWN for s in statuses):
        return ModelValidity.UNKNOWN
    return ModelValidity.PASS


def default_critical_requests(
    spec: LLCDesignSpec,
) -> tuple[LLCAnalysisRequest, ...]:
    """Vin / Pout corners that matter for FHA↔TD credibility."""

    return (
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_nom_v, load_fraction=1.0,
                           samples_per_cycle=512, waveform_cycles=1),
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_nom_v, load_fraction=0.25,
                           samples_per_cycle=512, waveform_cycles=1),
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_min_normal_v, load_fraction=1.0,
                           samples_per_cycle=512, waveform_cycles=1),
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_max_v, load_fraction=1.0,
                           samples_per_cycle=512, waveform_cycles=1),
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_hold_end_v, load_fraction=1.0,
                           samples_per_cycle=512, waveform_cycles=1),
        LLCAnalysisRequest(spec=spec, vbus_v=spec.vbus_nom_v, load_fraction=0.10,
                           samples_per_cycle=512, waveform_cycles=1),
    )


def validate_fha_td_point(
    request: LLCAnalysisRequest,
    *,
    thresholds: ValidityThresholds | None = None,
    time_domain: TimeDomainConfig | None = None,
) -> FhaTdPointValidation:
    """Run FHA and TD on one request and grade MODEL_VALIDITY."""

    thr = thresholds or ValidityThresholds()
    thr.validate()
    warnings: list[str] = []
    fha_result: LLCModelResult | None = None
    td_result: LLCModelResult | None = None

    try:
        fha_result = solve_fha(request)
    except Exception as exc:
        warnings.append(f"FHA failed: {exc}")

    try:
        td_result = solve_time_domain(
            request,
            time_domain or TimeDomainConfig(
                samples_per_cycle=512,
                output_cycles=1,
                frequency_scan_points=7,
            ),
        )
    except Exception as exc:
        warnings.append(f"TD failed: {exc}")

    fha_ok = fha_result is not None and fha_result.convergence.converged
    td_ok = td_result is not None and td_result.convergence.converged
    if fha_result is not None and not fha_result.convergence.converged:
        warnings.append("FHA returned non-converged result")
    if td_result is not None and not td_result.convergence.converged:
        warnings.append(
            f"TD non-converged (residual={td_result.convergence.residual_norm:.3e})"
        )

    if fha_ok and td_ok:
        assert fha_result is not None and td_result is not None
        deviations = compare_fha_td_metrics(fha_result.metrics, td_result.metrics, thr)
        fha_ind = fha_result.metrics.input_phase_deg > 0.0
        td_ind = td_result.metrics.input_phase_deg > 0.0
        if fha_ind != td_ind:
            deviations = deviations + (
                DeviationResult(
                    metric="zvs_region_agreement",
                    fha_value=fha_result.metrics.input_phase_deg,
                    td_value=td_result.metrics.input_phase_deg,
                    deviation_percent=100.0,
                    absolute_deviation=(
                        td_result.metrics.input_phase_deg - fha_result.metrics.input_phase_deg
                    ),
                    status=ConstraintStatus.FAIL,
                    units="deg",
                    message="FHA/TD disagree on inductive vs capacitive region",
                ),
            )
    else:
        deviations = ()

    validity = _validity_from_deviations(deviations, fha_ok=fha_ok, td_ok=td_ok)
    return FhaTdPointValidation(
        request=request,
        fha=fha_result,
        td=td_result,
        deviations=deviations,
        model_validity=validity,
        warnings=tuple(warnings),
    )


def validate_fha_td(
    spec: LLCDesignSpec,
    *,
    requests: Sequence[LLCAnalysisRequest] | None = None,
    thresholds: ValidityThresholds | None = None,
    time_domain: TimeDomainConfig | None = None,
) -> FhaTdValidationReport:
    """Cross-validate FHA against TD on the critical operating set."""

    spec.validate()
    thr = thresholds or ValidityThresholds()
    point_requests = list(requests or default_critical_requests(spec))
    points = [
        validate_fha_td_point(req, thresholds=thr, time_domain=time_domain)
        for req in point_requests
    ]
    overall = _merge_validity(*(p.model_validity for p in points))
    warnings = tuple(dict.fromkeys(w for p in points for w in p.warnings))
    return FhaTdValidationReport(
        points=tuple(points),
        overall_validity=overall,
        thresholds=thr,
        warnings=warnings,
    )


class FhaCredibility(str, Enum):
    """How trustworthy FHA is at one work point relative to TD."""

    FHA_VALID = "FHA_VALID"
    FHA_WARNING = "FHA_WARNING"
    FHA_OUT_OF_RANGE = "FHA_OUT_OF_RANGE"
    UNKNOWN = "UNKNOWN"


def credibility_from_validity(validity: ModelValidity) -> FhaCredibility:
    if validity == ModelValidity.PASS:
        return FhaCredibility.FHA_VALID
    if validity == ModelValidity.WARN:
        return FhaCredibility.FHA_WARNING
    if validity == ModelValidity.FAIL:
        return FhaCredibility.FHA_OUT_OF_RANGE
    return FhaCredibility.UNKNOWN


@dataclass(frozen=True)
class FhaValidityCell:
    normalized_frequency: float
    load_fraction: float
    credibility: FhaCredibility
    model_validity: ModelValidity
    max_relative_error_percent: float
    steady_state_verified: bool


@dataclass(frozen=True)
class FhaValidityMap:
    """Data-layer FHA credibility surface: fn × load (no GUI required)."""

    cells: tuple[FhaValidityCell, ...]
    fn_axis: tuple[float, ...]
    load_axis: tuple[float, ...]

    def cell(self, fn: float, load: float) -> FhaValidityCell | None:
        if not self.cells:
            return None
        return min(
            self.cells,
            key=lambda c: abs(c.normalized_frequency - fn) + abs(c.load_fraction - load),
        )


def _dedupe_requests(requests: Sequence[LLCAnalysisRequest]) -> tuple[LLCAnalysisRequest, ...]:
    seen: set[tuple[float, float]] = set()
    out: list[LLCAnalysisRequest] = []
    for req in requests:
        key = (round(float(req.bus_voltage_v), 3), round(float(req.load_fraction), 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(req)
    return tuple(out)


def critical_requests_from_envelope(
    spec: LLCDesignSpec,
    envelope_eval=None,
) -> tuple[LLCAnalysisRequest, ...]:
    """Nominal + Vin/P extremes + worst envelope corners, de-duplicated."""

    base = list(default_critical_requests(spec))
    if envelope_eval is not None:
        by_id = {
            p.corner_id: p.corner
            for p in getattr(envelope_eval, "points", ())
            if getattr(p, "corner", None) is not None
        }
        for finding in getattr(envelope_eval, "worst_cases", ()):
            corner = by_id.get(getattr(finding, "corner_id", ""))
            if corner is None:
                continue
            base.append(LLCAnalysisRequest(
                spec=spec,
                vbus_v=float(corner.vbus_v),
                load_fraction=max(float(corner.load_fraction), 0.05),
                samples_per_cycle=512,
                waveform_cycles=1,
            ))
    return _dedupe_requests(base)


def validate_fha_against_time_domain(
    spec: LLCDesignSpec,
    *,
    envelope_eval=None,
    requests: Sequence[LLCAnalysisRequest] | None = None,
    thresholds: ValidityThresholds | None = None,
    time_domain: TimeDomainConfig | None = None,
) -> FhaTdValidationReport:
    """P0 entry: only critical points, never the full envelope mesh."""

    selected = requests or critical_requests_from_envelope(spec, envelope_eval)
    return validate_fha_td(
        spec,
        requests=selected,
        thresholds=thresholds,
        time_domain=time_domain,
    )


def build_fha_validity_map(
    spec: LLCDesignSpec,
    *,
    fn_values: Sequence[float] | None = None,
    load_fractions: Sequence[float] | None = None,
    thresholds: ValidityThresholds | None = None,
    time_domain: TimeDomainConfig | None = None,
) -> FhaValidityMap:
    """Sparse fn × load map. Fixed-frequency compare when FN overrides regulate."""

    from ..core.tank import design_tank

    spec.validate()
    thr = thresholds or ValidityThresholds()
    tank = design_tank(spec)
    fn_axis = tuple(fn_values or (0.7, 0.85, 1.0, 1.2, 1.5))
    load_axis = tuple(load_fractions or (1.0, 0.5, 0.25, 0.10))
    cells: list[FhaValidityCell] = []
    td_cfg = time_domain or TimeDomainConfig(
        samples_per_cycle=256,
        output_cycles=1,
        frequency_scan_points=5,
        maximum_settling_cycles=120,
    )
    for load in load_axis:
        for fn in fn_axis:
            freq = float(fn) * tank.fr_hz
            if not (spec.minimum_frequency_hz <= freq <= spec.maximum_frequency_hz):
                cells.append(FhaValidityCell(
                    normalized_frequency=float(fn),
                    load_fraction=float(load),
                    credibility=FhaCredibility.UNKNOWN,
                    model_validity=ModelValidity.UNKNOWN,
                    max_relative_error_percent=float("nan"),
                    steady_state_verified=False,
                ))
                continue
            req = LLCAnalysisRequest(
                spec=spec,
                vbus_v=spec.vbus_nom_v,
                load_fraction=float(load),
                frequency_hz=freq,
                regulate_output=False,
                samples_per_cycle=256,
                waveform_cycles=1,
            )
            point = validate_fha_td_point(req, thresholds=thr, time_domain=td_cfg)
            steady = bool(point.td is not None and point.td.convergence.converged)
            errs = [abs(d.deviation_percent) for d in point.deviations] or [float("nan")]
            cells.append(FhaValidityCell(
                normalized_frequency=float(fn),
                load_fraction=float(load),
                credibility=credibility_from_validity(point.model_validity),
                model_validity=point.model_validity,
                max_relative_error_percent=float(max(errs)),
                steady_state_verified=steady,
            ))
    return FhaValidityMap(cells=tuple(cells), fn_axis=fn_axis, load_axis=load_axis)


__all__ = [
    "DeviationResult",
    "FhaCredibility",
    "FhaTdPointValidation",
    "FhaTdValidationReport",
    "FhaValidityCell",
    "FhaValidityMap",
    "ModelValidity",
    "ValidityThresholds",
    "build_fha_validity_map",
    "compare_fha_td_metrics",
    "credibility_from_validity",
    "critical_requests_from_envelope",
    "default_critical_requests",
    "validate_fha_against_time_domain",
    "validate_fha_td",
    "validate_fha_td_point",
]
