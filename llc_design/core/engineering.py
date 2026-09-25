"""Operating envelope, constraints, worst-case identification.

Turns discrete LLC work points into an engineering validation surface:
envelope corners → solve → constraints (PASS/WARN/FAIL/UNKNOWN) →
which corner is worst for each metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import itertools
import math
from typing import Iterable, Sequence

from .operating_point import LLCOperatingPoint, solve_operating_point
from .spec import LLCDesignSpec, TankParameterMode
from .tank import GainNotReachableError, TankDesign, design_tank
from .zvs_margin import ZVSMarginResult, evaluate_zvs_margin


class ConstraintStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


_STATUS_RANK = {
    ConstraintStatus.PASS: 0,
    ConstraintStatus.UNKNOWN: 1,
    ConstraintStatus.WARN: 2,
    ConstraintStatus.FAIL: 3,
}


def merge_status(*statuses: ConstraintStatus) -> ConstraintStatus:
    if not statuses:
        return ConstraintStatus.UNKNOWN
    return max(statuses, key=lambda s: _STATUS_RANK[s])


@dataclass(frozen=True)
class OperatingEnvelope:
    """Design / validation envelope around a base LLC specification.

    Tolerances are relative fractions (0.05 = ±5%). Dead-time and temperature
    are absolute SI / °C values.
    """

    vin_min_v: float
    vin_max_v: float
    vo_min_v: float
    vo_max_v: float
    pout_min_w: float
    pout_max_w: float
    lr_tolerance: float = 0.0
    lm_tolerance: float = 0.0
    cr_tolerance: float = 0.0
    turns_ratio_tolerance: float = 0.0
    dead_time_min_s: float | None = None
    dead_time_max_s: float | None = None
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    load_fractions: tuple[float, ...] = (0.10, 0.25, 0.50, 1.00)
    include_zero_load: bool = False

    @classmethod
    def from_spec(
        cls,
        spec: LLCDesignSpec,
        *,
        lr_tolerance: float = 0.05,
        lm_tolerance: float = 0.05,
        cr_tolerance: float = 0.05,
        turns_ratio_tolerance: float = 0.02,
        load_fractions: tuple[float, ...] = (0.10, 0.25, 0.50, 1.00),
        include_zero_load: bool = False,
    ) -> "OperatingEnvelope":
        return cls(
            vin_min_v=spec.vbus_hold_end_v,
            vin_max_v=spec.vbus_max_v,
            vo_min_v=spec.vout_v,
            vo_max_v=spec.vout_v,
            pout_min_w=spec.pout_w * min(load_fractions),
            pout_max_w=spec.pout_w * max(load_fractions),
            lr_tolerance=lr_tolerance,
            lm_tolerance=lm_tolerance,
            cr_tolerance=cr_tolerance,
            turns_ratio_tolerance=turns_ratio_tolerance,
            dead_time_min_s=spec.primary_deadtime_s,
            dead_time_max_s=spec.primary_deadtime_s,
            temperature_min_c=spec.primary_junction_temperature_c,
            temperature_max_c=spec.primary_junction_temperature_c,
            load_fractions=load_fractions,
            include_zero_load=include_zero_load,
        )

    def validate(self) -> None:
        if not (0.0 < self.vin_min_v <= self.vin_max_v):
            raise ValueError("vin range invalid")
        if not (0.0 < self.vo_min_v <= self.vo_max_v):
            raise ValueError("vo range invalid")
        if not (0.0 < self.pout_min_w <= self.pout_max_w):
            raise ValueError("pout range invalid")
        for name, tol in (
            ("lr_tolerance", self.lr_tolerance),
            ("lm_tolerance", self.lm_tolerance),
            ("cr_tolerance", self.cr_tolerance),
            ("turns_ratio_tolerance", self.turns_ratio_tolerance),
        ):
            if tol < 0.0 or tol >= 1.0:
                raise ValueError(f"{name} must be in [0, 1)")
        if self.dead_time_min_s is not None and self.dead_time_min_s <= 0.0:
            raise ValueError("dead_time_min_s must be positive")
        if (
            self.dead_time_min_s is not None
            and self.dead_time_max_s is not None
            and self.dead_time_min_s > self.dead_time_max_s
        ):
            raise ValueError("dead-time range invalid")
        if any(lf < 0.0 for lf in self.load_fractions):
            raise ValueError("load fractions cannot be negative")
        if any(lf == 0.0 for lf in self.load_fractions) and not self.include_zero_load:
            raise ValueError("zero load fraction requires include_zero_load=True")


@dataclass(frozen=True)
class EnvelopeCorner:
    """One concrete corner of the operating envelope."""

    corner_id: str
    vbus_v: float
    vout_v: float
    pout_w: float
    load_fraction: float
    lr_scale: float = 1.0
    lm_scale: float = 1.0
    cr_scale: float = 1.0
    turns_ratio_scale: float = 1.0
    dead_time_s: float | None = None
    temperature_c: float | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintResult:
    name: str
    status: ConstraintStatus
    value: float | None = None
    limit: float | None = None
    message: str = ""
    units: str = ""

    def as_dict(self) -> dict[str, float | str | None]:
        return {
            "name": self.name,
            "status": self.status.value,
            "value": self.value,
            "limit": self.limit,
            "message": self.message,
            "units": self.units,
        }


@dataclass(frozen=True)
class OperatingPointResult:
    """Unified result for one envelope corner."""

    corner: EnvelopeCorner
    operating_point: LLCOperatingPoint | None
    zvs: ZVSMarginResult | None
    constraints: tuple[ConstraintResult, ...]
    overall_status: ConstraintStatus
    solve_error: str | None = None
    tank: TankDesign | None = None

    @property
    def corner_id(self) -> str:
        return self.corner.corner_id


@dataclass(frozen=True)
class WorstCaseFinding:
    """Identifies which corner is worst for a named metric — not only min/max."""

    metric: str
    corner_id: str
    value: float
    status: ConstraintStatus
    sense: str
    reason: str
    units: str = ""


@dataclass(frozen=True)
class EnvelopeEvaluation:
    envelope: OperatingEnvelope
    base_spec: LLCDesignSpec
    points: tuple[OperatingPointResult, ...]
    worst_cases: tuple[WorstCaseFinding, ...]
    overall_status: ConstraintStatus
    warnings: tuple[str, ...] = ()

    def points_by_status(self, status: ConstraintStatus) -> tuple[OperatingPointResult, ...]:
        return tuple(p for p in self.points if p.overall_status == status)

    def worst(self, metric: str) -> WorstCaseFinding | None:
        for item in self.worst_cases:
            if item.metric == metric:
                return item
        return None


def _unique_sorted(values: Iterable[float], rel: float = 1e-9) -> list[float]:
    ordered = sorted(float(v) for v in values)
    out: list[float] = []
    for value in ordered:
        if not out or abs(value - out[-1]) > max(rel * abs(value), 1e-12):
            out.append(value)
    return out


def enumerate_envelope_corners(
    spec: LLCDesignSpec,
    envelope: OperatingEnvelope,
    *,
    include_tolerance_corners: bool = True,
    include_dead_time_corners: bool = True,
    include_temperature_corners: bool = True,
) -> tuple[EnvelopeCorner, ...]:
    """Build a structured corner set (electrical × load + named tolerance axes)."""

    envelope.validate()
    rated = max(spec.pout_w, 1e-12)
    loads = list(envelope.load_fractions)
    if envelope.include_zero_load and 0.0 not in loads:
        loads = [0.0, *loads]
    loads = _unique_sorted(loads)

    vins = _unique_sorted((envelope.vin_min_v, spec.vbus_nom_v, envelope.vin_max_v))
    vos = _unique_sorted((envelope.vo_min_v, spec.vout_v, envelope.vo_max_v))

    corners: list[EnvelopeCorner] = []
    for vbus, vout, load in itertools.product(vins, vos, loads):
        pout = rated * load if load > 0.0 else 0.0
        tags = ["electrical"]
        if abs(vbus - envelope.vin_min_v) < 1e-9:
            tags.append("vin_min")
        if abs(vbus - envelope.vin_max_v) < 1e-9:
            tags.append("vin_max")
        if load <= 1e-12:
            tags.append("zero_load")
        elif load <= 0.15:
            tags.append("light_load")
        elif load >= 0.999:
            tags.append("full_load")
        corners.append(EnvelopeCorner(
            corner_id=f"vin{vbus:.0f}_vo{vout:.1f}_p{load*100:.0f}",
            vbus_v=vbus,
            vout_v=vout,
            pout_w=pout,
            load_fraction=load,
            dead_time_s=spec.primary_deadtime_s,
            temperature_c=spec.primary_junction_temperature_c,
            tags=tuple(tags),
        ))

    if include_tolerance_corners and any(
        t > 0.0 for t in (
            envelope.lr_tolerance, envelope.lm_tolerance,
            envelope.cr_tolerance, envelope.turns_ratio_tolerance,
        )
    ):
        tol_defs = (
            ("tol_lr_hi", 1.0 + envelope.lr_tolerance, 1.0, 1.0, 1.0),
            ("tol_lr_lo", 1.0 - envelope.lr_tolerance, 1.0, 1.0, 1.0),
            ("tol_lm_hi", 1.0, 1.0 + envelope.lm_tolerance, 1.0, 1.0),
            ("tol_lm_lo", 1.0, 1.0 - envelope.lm_tolerance, 1.0, 1.0),
            ("tol_cr_hi", 1.0, 1.0, 1.0 + envelope.cr_tolerance, 1.0),
            ("tol_cr_lo", 1.0, 1.0, 1.0 - envelope.cr_tolerance, 1.0),
            ("tol_n_hi", 1.0, 1.0, 1.0, 1.0 + envelope.turns_ratio_tolerance),
            ("tol_n_lo", 1.0, 1.0, 1.0, 1.0 - envelope.turns_ratio_tolerance),
            (
                "tol_gain_hard",
                1.0 + envelope.lr_tolerance,
                1.0 - envelope.lm_tolerance,
                1.0 - envelope.cr_tolerance,
                1.0 + envelope.turns_ratio_tolerance,
            ),
            (
                "tol_zvs_hard",
                1.0 - envelope.lr_tolerance,
                1.0 + envelope.lm_tolerance,
                1.0 + envelope.cr_tolerance,
                1.0 - envelope.turns_ratio_tolerance,
            ),
        )
        for name, lr_s, lm_s, cr_s, n_s in tol_defs:
            if all(abs(x - 1.0) < 1e-15 for x in (lr_s, lm_s, cr_s, n_s)):
                continue
            corners.append(EnvelopeCorner(
                corner_id=f"{name}_vin{spec.vbus_nom_v:.0f}_p100",
                vbus_v=spec.vbus_nom_v,
                vout_v=spec.vout_v,
                pout_w=spec.pout_w,
                load_fraction=1.0,
                lr_scale=lr_s,
                lm_scale=lm_s,
                cr_scale=cr_s,
                turns_ratio_scale=n_s,
                dead_time_s=spec.primary_deadtime_s,
                temperature_c=spec.primary_junction_temperature_c,
                tags=("tolerance", name),
            ))

    if include_dead_time_corners:
        dts = []
        if envelope.dead_time_min_s is not None:
            dts.append(envelope.dead_time_min_s)
        if envelope.dead_time_max_s is not None:
            dts.append(envelope.dead_time_max_s)
        for dt in _unique_sorted(dts):
            if abs(dt - spec.primary_deadtime_s) < 1e-15:
                continue
            corners.append(EnvelopeCorner(
                corner_id=f"tdead{dt*1e9:.0f}ns_vin{spec.vbus_nom_v:.0f}_p100",
                vbus_v=spec.vbus_nom_v,
                vout_v=spec.vout_v,
                pout_w=spec.pout_w,
                load_fraction=1.0,
                dead_time_s=dt,
                temperature_c=spec.primary_junction_temperature_c,
                tags=("dead_time",),
            ))

    if include_temperature_corners:
        temps = []
        if envelope.temperature_min_c is not None:
            temps.append(envelope.temperature_min_c)
        if envelope.temperature_max_c is not None:
            temps.append(envelope.temperature_max_c)
        for temp in _unique_sorted(temps):
            if abs(temp - spec.primary_junction_temperature_c) < 1e-9:
                continue
            corners.append(EnvelopeCorner(
                corner_id=f"Tj{temp:.0f}C_vin{spec.vbus_nom_v:.0f}_p100",
                vbus_v=spec.vbus_nom_v,
                vout_v=spec.vout_v,
                pout_w=spec.pout_w,
                load_fraction=1.0,
                dead_time_s=spec.primary_deadtime_s,
                temperature_c=temp,
                tags=("temperature",),
            ))

    seen: set[str] = set()
    unique: list[EnvelopeCorner] = []
    for corner in corners:
        if corner.corner_id in seen:
            continue
        seen.add(corner.corner_id)
        unique.append(corner)
    return tuple(unique)


def _scaled_tank(spec: LLCDesignSpec, corner: EnvelopeCorner) -> TankDesign:
    base = design_tank(spec)
    lr = base.lr_h * corner.lr_scale
    cr = base.cr_f * corner.cr_scale
    lm = base.lm_h * corner.lm_scale
    if lm <= lr:
        lm = lr * (1.0 + 1e-6)
    return design_tank(spec.clone(
        parameter_mode=TankParameterMode.USER_DEFINED,
        user_lr_h=lr,
        user_cr_f=cr,
        user_lm_h=lm,
    ))


def _corner_spec(spec: LLCDesignSpec, corner: EnvelopeCorner) -> LLCDesignSpec:
    secondary = max(1, int(round(spec.secondary_turns)))
    primary = max(1, int(round(spec.primary_turns * corner.turns_ratio_scale)))
    if abs(corner.turns_ratio_scale - 1.0) > 1e-12:
        target_ratio = spec.turns_ratio * corner.turns_ratio_scale
        primary = max(1, int(round(target_ratio * secondary)))
    changes: dict = {
        "vout_v": corner.vout_v,
        "primary_turns": primary,
        "secondary_turns": secondary,
    }
    if corner.dead_time_s is not None:
        changes["primary_deadtime_s"] = corner.dead_time_s
    if corner.temperature_c is not None:
        changes["primary_junction_temperature_c"] = corner.temperature_c
    return spec.clone(**changes)


def evaluate_constraints_for_point(
    spec: LLCDesignSpec,
    op: LLCOperatingPoint | None,
    zvs: ZVSMarginResult | None,
    *,
    solve_error: str | None = None,
    require_inductive_full_load: bool = True,
) -> tuple[ConstraintResult, ...]:
    """Evaluate power-stage constraints for one solved (or failed) point."""

    results: list[ConstraintResult] = []
    if solve_error is not None or op is None:
        results.append(ConstraintResult(
            name="frequency_solve",
            status=ConstraintStatus.FAIL,
            message=solve_error or "operating point not solved",
        ))
        results.append(ConstraintResult(
            name="zvs",
            status=ConstraintStatus.UNKNOWN,
            message="ZVS not evaluated because the operating point failed",
        ))
        return tuple(results)

    results.append(ConstraintResult(
        name="frequency_solve",
        status=ConstraintStatus.PASS,
        value=op.switching_frequency_hz,
        limit=spec.maximum_frequency_hz,
        message="gain reachable inside frequency window",
        units="Hz",
    ))

    if op.switching_frequency_hz < spec.minimum_frequency_hz - 1e-6:
        results.append(ConstraintResult(
            name="frequency_min",
            status=ConstraintStatus.FAIL,
            value=op.switching_frequency_hz,
            limit=spec.minimum_frequency_hz,
            message="switching frequency below minimum",
            units="Hz",
        ))
    elif op.switching_frequency_hz > spec.maximum_frequency_hz + 1e-6:
        results.append(ConstraintResult(
            name="frequency_max",
            status=ConstraintStatus.FAIL,
            value=op.switching_frequency_hz,
            limit=spec.maximum_frequency_hz,
            message="switching frequency above maximum",
            units="Hz",
        ))
    else:
        results.append(ConstraintResult(
            name="frequency_window",
            status=ConstraintStatus.PASS,
            value=op.switching_frequency_hz,
            message="fs inside [fmin, fmax]",
            units="Hz",
        ))

    gain_err = abs(op.achieved_gain - op.required_gain) / max(op.required_gain, 1e-12)
    results.append(ConstraintResult(
        name="gain_match",
        status=ConstraintStatus.PASS if gain_err < 1e-3 else ConstraintStatus.WARN,
        value=op.achieved_gain,
        limit=op.required_gain,
        message=f"relative gain error {gain_err:.3e}",
    ))

    inductive_limit = spec.minimum_inductive_angle_deg
    if op.load_fraction >= 0.999 and require_inductive_full_load:
        if op.input_phase_deg < inductive_limit:
            status = ConstraintStatus.FAIL
            msg = "full-load inductive angle below minimum"
        else:
            status = ConstraintStatus.PASS
            msg = "full-load inductive"
        results.append(ConstraintResult(
            name="inductive_full_load",
            status=status,
            value=op.input_phase_deg,
            limit=inductive_limit,
            message=msg,
            units="deg",
        ))
    else:
        if op.input_phase_deg <= 0.0:
            status = ConstraintStatus.FAIL
            msg = "capacitive input impedance"
        elif op.input_phase_deg < inductive_limit:
            status = ConstraintStatus.WARN
            msg = "inductive but below preferred angle"
        else:
            status = ConstraintStatus.PASS
            msg = "inductive"
        results.append(ConstraintResult(
            name="inductive_region",
            status=status,
            value=op.input_phase_deg,
            limit=inductive_limit,
            message=msg,
            units="deg",
        ))

    if zvs is None:
        results.append(ConstraintResult(
            name="zvs",
            status=ConstraintStatus.UNKNOWN,
            message="ZVS result missing",
        ))
    else:
        preferred = spec.primary_zvs_margin_required
        preferred_surplus = preferred - 1.0
        if not zvs.zvs_pass and zvs.level1_region == "CAPACITIVE":
            zstatus = ConstraintStatus.FAIL
            msg = "capacitive — ZVS not credible"
        elif math.isnan(zvs.zvs_margin):
            zstatus = ConstraintStatus.UNKNOWN
            msg = "ZVS margin unknown"
        elif zvs.zvs_margin < 0.0:
            zstatus = ConstraintStatus.FAIL
            msg = "negative charge-balance margin"
        elif zvs.zvs_margin < preferred_surplus:
            zstatus = ConstraintStatus.WARN
            msg = "margin below preferred surplus"
        else:
            zstatus = ConstraintStatus.PASS
            msg = f"ZVS ok ({zvs.model_source})"
        results.append(ConstraintResult(
            name="zvs_margin",
            status=zstatus,
            value=None if math.isnan(zvs.zvs_margin) else zvs.zvs_margin,
            limit=preferred_surplus,
            message=msg,
        ))
        results.append(ConstraintResult(
            name="zvs_model",
            status=(
                ConstraintStatus.PASS
                if zvs.model_source != "UNKNOWN"
                else ConstraintStatus.UNKNOWN
            ),
            message=zvs.model_source,
        ))

    return tuple(results)


def _identify_worst_cases(
    points: Sequence[OperatingPointResult],
) -> tuple[WorstCaseFinding, ...]:
    findings: list[WorstCaseFinding] = []

    def _pick(metric: str, sense: str, extractor, units: str, reason_fmt: str) -> None:
        scored: list[tuple[OperatingPointResult, float]] = []
        for point in points:
            try:
                value = extractor(point)
            except Exception:
                continue
            if value is None:
                continue
            value_f = float(value)
            if not math.isfinite(value_f):
                continue
            scored.append((point, value_f))
        if not scored:
            return
        winner, value = (
            max(scored, key=lambda item: item[1])
            if sense == "maximum"
            else min(scored, key=lambda item: item[1])
        )
        findings.append(WorstCaseFinding(
            metric=metric,
            corner_id=winner.corner_id,
            value=value,
            status=winner.overall_status,
            sense=sense,
            reason=reason_fmt.format(
                corner=winner.corner_id,
                value=value,
                vin=winner.corner.vbus_v,
                load=winner.corner.load_fraction,
            ),
            units=units,
        ))

    _pick(
        "zvs_margin",
        "minimum",
        lambda p: None if p.zvs is None else p.zvs.zvs_margin,
        "",
        "Lowest ZVS surplus margin at corner {corner} "
        "(Vin={vin:.0f} V, load={load:.0%}): {value:.4f}",
    )
    _pick(
        "resonant_current_rms_a",
        "maximum",
        lambda p: p.operating_point.resonant_current_rms_a if p.operating_point else None,
        "A",
        "Highest Ir_rms at corner {corner} (Vin={vin:.0f} V, load={load:.0%}): {value:.4f} A",
    )
    _pick(
        "resonant_current_peak_a",
        "maximum",
        lambda p: p.operating_point.resonant_current_peak_a if p.operating_point else None,
        "A",
        "Highest Ir_peak at corner {corner}: {value:.4f} A",
    )
    _pick(
        "switching_frequency_hz",
        "maximum",
        lambda p: p.operating_point.switching_frequency_hz if p.operating_point else None,
        "Hz",
        "Highest fs at corner {corner}: {value:.1f} Hz",
    )
    _pick(
        "switching_frequency_hz_min",
        "minimum",
        lambda p: p.operating_point.switching_frequency_hz if p.operating_point else None,
        "Hz",
        "Lowest fs at corner {corner}: {value:.1f} Hz",
    )
    _pick(
        "input_phase_deg",
        "minimum",
        lambda p: p.operating_point.input_phase_deg if p.operating_point else None,
        "deg",
        "Most capacitive / least inductive phase at {corner}: {value:.3f} deg",
    )
    _pick(
        "commutation_current_a",
        "minimum",
        lambda p: p.operating_point.commutation_current_a if p.operating_point else None,
        "A",
        "Lowest commutation current at {corner}: {value:.4f} A",
    )

    failed = [p for p in points if p.overall_status == ConstraintStatus.FAIL]
    if failed:
        pick = failed[0]
        findings.append(WorstCaseFinding(
            metric="constraint_fail",
            corner_id=pick.corner_id,
            value=float(len(failed)),
            status=ConstraintStatus.FAIL,
            sense="maximum",
            reason=(
                f"{len(failed)} corner(s) FAIL; first failure at {pick.corner_id}: "
                + "; ".join(
                    c.message for c in pick.constraints if c.status == ConstraintStatus.FAIL
                )
            ),
        ))
    return tuple(findings)


def evaluate_operating_envelope(
    spec: LLCDesignSpec,
    envelope: OperatingEnvelope | None = None,
    *,
    device_qoss_c: float | None = None,
    device_coss_f: float | None = None,
    corners: Sequence[EnvelopeCorner] | None = None,
    zvs_level: int = 2,
) -> EnvelopeEvaluation:
    """Solve envelope corners, attach ZVS + constraints, identify worst cases."""

    spec.validate()
    env = envelope or OperatingEnvelope.from_spec(spec)
    env.validate()
    corner_list = list(corners or enumerate_envelope_corners(spec, env))
    points: list[OperatingPointResult] = []
    warnings: list[str] = []

    for corner in corner_list:
        corner_spec = _corner_spec(spec, corner)
        try:
            tank = _scaled_tank(corner_spec, corner)
        except Exception as exc:
            points.append(OperatingPointResult(
                corner=corner,
                operating_point=None,
                zvs=None,
                constraints=evaluate_constraints_for_point(
                    corner_spec, None, None, solve_error=str(exc)),
                overall_status=ConstraintStatus.FAIL,
                solve_error=str(exc),
            ))
            continue

        if corner.load_fraction <= 0.0:
            constraints = (
                ConstraintResult(
                    name="frequency_solve",
                    status=ConstraintStatus.UNKNOWN,
                    message="zero-load FHA Rac undefined; burst/skip expected",
                ),
                ConstraintResult(
                    name="zvs",
                    status=ConstraintStatus.UNKNOWN,
                    message="zero-load ZVS requires burst/skip model",
                ),
            )
            points.append(OperatingPointResult(
                corner=corner,
                operating_point=None,
                zvs=None,
                constraints=constraints,
                overall_status=ConstraintStatus.UNKNOWN,
                solve_error="zero-load not solved by FHA Rac model",
                tank=tank,
            ))
            warnings.append(f"{corner.corner_id}: zero-load left UNKNOWN (FHA Rac)")
            continue

        solve_spec = spec.clone(
            vout_v=corner.vout_v,
            primary_turns=corner_spec.primary_turns,
            secondary_turns=corner_spec.secondary_turns,
            primary_deadtime_s=corner_spec.primary_deadtime_s,
            primary_junction_temperature_c=corner_spec.primary_junction_temperature_c,
            parameter_mode=TankParameterMode.USER_DEFINED,
            user_lr_h=tank.lr_h,
            user_cr_f=tank.cr_f,
            user_lm_h=tank.lm_h,
        )
        try:
            op = solve_operating_point(
                solve_spec, tank, corner.vbus_v, corner.load_fraction)
            zvs = evaluate_zvs_margin(
                solve_spec,
                tank,
                op,
                qoss_c=device_qoss_c,
                coss_f=device_coss_f,
                level=zvs_level,
                dead_time_s=corner.dead_time_s,
            )
            constraints = evaluate_constraints_for_point(solve_spec, op, zvs)
            overall = merge_status(*(c.status for c in constraints))
            points.append(OperatingPointResult(
                corner=corner,
                operating_point=op,
                zvs=zvs,
                constraints=constraints,
                overall_status=overall,
                tank=tank,
            ))
        except GainNotReachableError as exc:
            constraints = evaluate_constraints_for_point(
                solve_spec, None, None, solve_error=str(exc))
            points.append(OperatingPointResult(
                corner=corner,
                operating_point=None,
                zvs=None,
                constraints=constraints,
                overall_status=ConstraintStatus.FAIL,
                solve_error=str(exc),
                tank=tank,
            ))
        except Exception as exc:
            constraints = evaluate_constraints_for_point(
                solve_spec, None, None, solve_error=str(exc))
            points.append(OperatingPointResult(
                corner=corner,
                operating_point=None,
                zvs=None,
                constraints=constraints,
                overall_status=ConstraintStatus.FAIL,
                solve_error=str(exc),
                tank=tank,
            ))

    worst = _identify_worst_cases(points)
    overall = (
        merge_status(*(p.overall_status for p in points))
        if points
        else ConstraintStatus.UNKNOWN
    )
    return EnvelopeEvaluation(
        envelope=env,
        base_spec=spec,
        points=tuple(points),
        worst_cases=worst,
        overall_status=overall,
        warnings=tuple(dict.fromkeys(warnings)),
    )


__all__ = [
    "ConstraintResult",
    "ConstraintStatus",
    "EnvelopeCorner",
    "EnvelopeEvaluation",
    "OperatingEnvelope",
    "OperatingPointResult",
    "WorstCaseFinding",
    "enumerate_envelope_corners",
    "evaluate_constraints_for_point",
    "evaluate_operating_envelope",
    "merge_status",
]
