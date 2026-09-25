"""Lumped electro-thermal iteration for LLC devices and magnetics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ..core.operating_point import LLCOperatingPoint
from ..core.spec import LLCDesignSpec
from ..core.tank import TankDesign, design_tank
from .physics_evidence import ModelGrade, physical_sanity_issues
from .primary_bridge import primary_bridge_loss
from .synchronous_rectifier import synchronous_rectifier_loss
from .system import LLCSystemAnalyzer, OperatingPointLoss


@dataclass(frozen=True)
class ThermalNodeResult:
    name: str
    ambient_c: float
    temperature_c: float
    loss_w: float
    rth_k_per_w: float
    grade: ModelGrade


@dataclass(frozen=True)
class ElectroThermalResult:
    converged: bool
    iterations: int
    nodes: tuple[ThermalNodeResult, ...]
    primary_tj_c: float
    sr_tj_c: float
    transformer_c: float
    inductor_c: float
    point: OperatingPointLoss | None
    sanity: tuple[str, ...]
    warnings: tuple[str, ...]


def iterate_electro_thermal(
    spec: LLCDesignSpec,
    op: LLCOperatingPoint,
    *,
    analyzer: LLCSystemAnalyzer | None = None,
    tank: TankDesign | None = None,
    ambient_c: float | None = None,
    primary_rth_k_per_w: float = 2.5,
    sr_rth_k_per_w: float = 3.0,
    max_iterations: int | None = None,
    tolerance_c: float | None = None,
    loss_builder: Callable[[LLCDesignSpec, LLCOperatingPoint], OperatingPointLoss] | None = None,
) -> ElectroThermalResult:
    """T = Ta + P·Rθ until temperatures stabilize; updates device junctions on spec clone."""

    analyzer = analyzer or LLCSystemAnalyzer()
    tank = tank or design_tank(spec)
    ta = float(ambient_c if ambient_c is not None else getattr(spec, "ambient_temperature_c", 40.0))
    n_iter = int(max_iterations or spec.magnetic_thermal_max_iterations)
    tol = float(tolerance_c or spec.magnetic_thermal_tolerance_c)
    devices = analyzer.device_db
    primary = devices.get_primary(spec.primary_device)
    sr = devices.get_sr(spec.sr_device)

    tj_p = float(spec.primary_junction_temperature_c)
    tj_s = float(spec.sr_junction_temperature_c)
    t_tx = ta
    t_lr = ta
    warnings: list[str] = []
    last_point: OperatingPointLoss | None = None
    converged = False
    used = 0

    for used in range(1, n_iter + 1):
        working = spec.clone(
            primary_junction_temperature_c=tj_p,
            sr_junction_temperature_c=tj_s,
        )
        if loss_builder is not None:
            point = loss_builder(working, op)
        else:
            # One-point loss using existing system kernels (FHA path).
            p_primary = primary_bridge_loss(working, tank, op, primary)
            p_sr = synchronous_rectifier_loss(working, op, sr)
            # Magnetics temperatures use previous iterate via Rθ on last losses if available.
            # For first pass use analyzer magnetics at this OP via a tiny multi-point analyze.
            analysis = analyzer.analyze(working, work_points=[(op.vbus_v, op.load_fraction)])
            point = analysis.operating_points[0]
            # Prefer freshly computed semiconductor pieces at updated Tj.
            from .system import OperatingPointLoss as OPL
            point = OPL(
                operating_point=op,
                primary=p_primary,
                synchronous_rectifier=p_sr,
                transformer=point.transformer,
                resonant_inductor=point.resonant_inductor,
                resonant_capacitor=point.resonant_capacitor,
                output_capacitor=point.output_capacitor,
                auxiliary_w=point.auxiliary_w,
                total_loss_w=(
                    p_primary.total_w + p_sr.total_w + point.transformer.total_w
                    + point.resonant_inductor.total_w + point.resonant_capacitor.loss_w
                    + point.output_capacitor.capacitor_loss_w + point.auxiliary_w
                ),
                efficiency=0.0,
            )
            point = replace(
                point,
                efficiency=(
                    op.pout_w / (op.pout_w + point.total_loss_w) if op.pout_w > 0 else 0.0
                ),
            )

        last_point = point
        new_tj_p = ta + point.primary.total_w * primary_rth_k_per_w
        new_tj_s = ta + point.synchronous_rectifier.total_w * sr_rth_k_per_w
        new_t_tx = ta + point.transformer.total_w * spec.transformer_rth_k_per_w
        new_t_lr = ta + point.resonant_inductor.total_w * spec.resonant_inductor_rth_k_per_w
        deltas = (
            abs(new_tj_p - tj_p),
            abs(new_tj_s - tj_s),
            abs(new_t_tx - t_tx),
            abs(new_t_lr - t_lr),
        )
        tj_p, tj_s, t_tx, t_lr = new_tj_p, new_tj_s, new_t_tx, new_t_lr
        if max(deltas) < tol:
            converged = True
            break

    if not converged:
        warnings.append(f"electro-thermal NOT_CONVERGED after {used} iterations (tol={tol} °C)")

    nodes = (
        ThermalNodeResult("primary_mosfet", ta, tj_p, last_point.primary.total_w if last_point else 0.0,
                          primary_rth_k_per_w, ModelGrade.APPROXIMATION),
        ThermalNodeResult("sr_mosfet", ta, tj_s,
                          last_point.synchronous_rectifier.total_w if last_point else 0.0,
                          sr_rth_k_per_w, ModelGrade.APPROXIMATION),
        ThermalNodeResult("transformer", ta, t_tx,
                          last_point.transformer.total_w if last_point else 0.0,
                          spec.transformer_rth_k_per_w, ModelGrade.APPROXIMATION),
        ThermalNodeResult("resonant_inductor", ta, t_lr,
                          last_point.resonant_inductor.total_w if last_point else 0.0,
                          spec.resonant_inductor_rth_k_per_w, ModelGrade.APPROXIMATION),
    )
    sanity = physical_sanity_issues(
        loss_w=last_point.total_loss_w if last_point else None,
        efficiency=last_point.efficiency if last_point else None,
        tj_c=tj_p,
        ta_c=ta,
        dissipating=True,
    )
    return ElectroThermalResult(
        converged=converged,
        iterations=used,
        nodes=nodes,
        primary_tj_c=tj_p,
        sr_tj_c=tj_s,
        transformer_c=t_tx,
        inductor_c=t_lr,
        point=last_point,
        sanity=sanity,
        warnings=tuple(warnings),
    )


__all__ = [
    "ElectroThermalResult",
    "ThermalNodeResult",
    "iterate_electro_thermal",
]
