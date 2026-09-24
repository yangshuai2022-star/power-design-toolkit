"""Gapped / explicit-AL ferrite boost-inductor sizing for PFC.

Powder-core High Flux design remains in ``pfc_inductor_designer``.  This module
intentionally does **not** consume powder ``dc_bias_coeffs``.  Ferrite cores
need an explicit air gap (or a manufacturer AL that already includes the gap)
plus Steinmetz coefficients for the selected material.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from .core_entry import CoreSpec
from .steinmetz import SteinmetzMaterial
from power_control_tools.part_validation import (
    format_missing,
    missing_ferrite_steinmetz_parameters,
)

TopologyKind = Literal["ttpl", "vienna"]
MU0 = 4.0e-7 * math.pi
RHO_CU_20 = 1.724e-8
CU_TEMP_COEFF = 0.00393


@dataclass(frozen=True)
class FerriteInductorRequest:
    topology: TopologyKind
    input_rms_v: float
    bus_voltage_v: float
    output_power_w: float
    switching_frequency_hz: float
    target_inductance_h: float
    efficiency: float
    core: CoreSpec
    steinmetz: SteinmetzMaterial
    gap_m: float
    n_cores: int = 1
    wire_copper_diameter_mm: float = 1.0
    enamel_build_mm: float = 0.05
    target_current_density_a_mm2: float = 5.0
    copper_temperature_c: float = 100.0
    max_fill_factor: float = 0.45
    b_peak_limit_t: float = 0.30

    def validate(self) -> None:
        if self.topology not in {"ttpl", "vienna"}:
            raise ValueError("topology must be 'ttpl' or 'vienna'")
        if self.core.material_class.casefold() != "ferrite":
            raise ValueError(
                f"ferrite path refused material_class={self.core.material_class!r}; "
                "use High Flux / powder designer for powder cores"
            )
        missing = missing_ferrite_steinmetz_parameters(self.core.material, self.steinmetz)
        if missing:
            raise ValueError("Ferrite loss model incomplete:\n" + format_missing(missing))
        if self.gap_m < 0.0:
            raise ValueError("gap_m cannot be negative")
        if self.gap_m <= 0.0 and self.core.ui >= 200.0:
            raise ValueError(
                "ungapped high-μ ferrite is not accepted for PFC boost inductors; "
                "enter a positive air-gap length (m) or select a gapped AL core"
            )
        for name, value in (
            ("input_rms_v", self.input_rms_v),
            ("bus_voltage_v", self.bus_voltage_v),
            ("output_power_w", self.output_power_w),
            ("switching_frequency_hz", self.switching_frequency_hz),
            ("target_inductance_h", self.target_inductance_h),
            ("efficiency", self.efficiency),
            ("wire_copper_diameter_mm", self.wire_copper_diameter_mm),
            ("target_current_density_a_mm2", self.target_current_density_a_mm2),
            ("b_peak_limit_t", self.b_peak_limit_t),
        ):
            if value <= 0.0:
                raise ValueError(f"{name} must be > 0")
        if self.n_cores < 1:
            raise ValueError("n_cores must be >= 1")


@dataclass(frozen=True)
class FerriteInductorResult:
    request: FerriteInductorRequest
    turns: int
    parallel_wires: int
    inductance_h: float
    effective_gap_m: float
    al_nH_per_t2: float
    phase_current_rms_a: float
    phase_current_peak_a: float
    ripple_pp_a: float
    bac_peak_t: float
    bdc_t: float
    b_peak_total_t: float
    core_loss_w: float
    copper_loss_w: float
    total_inductor_loss_w: float
    fill_factor: float
    current_density_a_mm2: float
    warnings: tuple[str, ...]


def _effective_reluctance(core: CoreSpec, gap_m: float, n_cores: int) -> float:
    ae = core.ae_cm2 * 1e-4 * n_cores
    le = core.le_cm * 1e-2
    mu_r = max(float(core.ui), 1.0)
    return gap_m / (MU0 * ae) + le / (MU0 * mu_r * ae)


def design_ferrite_pfc_inductor(request: FerriteInductorRequest) -> FerriteInductorResult:
    """Size turns from target L using explicit gap + μi, then check Bac/Bdc and losses."""
    request.validate()
    core = request.core
    n_cores = request.n_cores
    ae_m2 = core.ae_cm2 * 1e-4 * n_cores
    ve_m3 = core.ve_cm3 * 1e-6 * n_cores

    i_rms = request.output_power_w / (request.efficiency * request.input_rms_v)
    if request.topology == "vienna":
        # Three-phase Vienna shares current across legs; keep conservative single-phase peak.
        i_rms = i_rms / math.sqrt(3.0)
    i_peak_avg = math.sqrt(2.0) * i_rms
    v_pk = math.sqrt(2.0) * request.input_rms_v
    duty_peak = max(0.0, min(0.98, 1.0 - v_pk / request.bus_voltage_v))
    ripple = (v_pk * duty_peak) / max(request.target_inductance_h * request.switching_frequency_hz, 1e-30)
    i_peak = i_peak_avg + 0.5 * ripple

    reluctance = _effective_reluctance(core, request.gap_m, n_cores)
    # N² / R = L  →  N = sqrt(L * R)
    turns = max(1, int(math.ceil(math.sqrt(request.target_inductance_h * reluctance))))
    inductance = turns * turns / reluctance
    al_nh = inductance / (turns * turns) * 1e9

    # AC flux from volt-second on the boost inductor at line peak.
    bac = (v_pk * duty_peak) / max(turns * ae_m2 * request.switching_frequency_hz, 1e-30)
    # DC flux for gapped ferrite: Bdc ≈ μ0 * N * I / gap_eff.
    gap_eff = request.gap_m + (core.le_cm * 1e-2) / max(float(core.ui), 1.0)
    bdc = MU0 * turns * i_peak / max(gap_eff, 1e-9) / n_cores
    b_total = bdc + bac

    copper_d = request.wire_copper_diameter_mm * 1e-3
    copper_area = math.pi * (0.5 * copper_d) ** 2
    parallel = max(1, int(math.ceil(i_rms / max(request.target_current_density_a_mm2 * copper_area * 1e6, 1e-12))))
    j = i_rms / max(parallel * copper_area * 1e6, 1e-12)
    mlt_m = core.mlt_cm * 1e-2
    wire_length = turns * mlt_m * 1.10
    rho = RHO_CU_20 * (1.0 + CU_TEMP_COEFF * (request.copper_temperature_c - 20.0))
    r_hot = rho * wire_length / max(parallel * copper_area, 1e-16)
    copper_loss = i_rms * i_rms * r_hot

    # Core loss uses AC flux only (Steinmetz / iGSE). Never powder DC-bias polynomials.
    core_loss = float(
        request.steinmetz.core_loss(
            request.switching_frequency_hz,
            bac,
            ve_m3,
            method="igse",
            duty=max(duty_peak, 0.05),
        )
    )

    coated_d = (request.wire_copper_diameter_mm + 2.0 * request.enamel_build_mm) * 1e-3
    fill = turns * parallel * math.pi * (0.5 * coated_d) ** 2 / max(core.aw_cm2 * 1e-4, 1e-16)

    warnings: list[str] = []
    if b_total > request.b_peak_limit_t:
        warnings.append(
            f"Bpeak={b_total:.3f} T exceeds limit {request.b_peak_limit_t:.3f} T; increase gap/Ae or reduce L target"
        )
    if b_total > core.bs_T * 0.75:
        warnings.append(f"Bpeak={b_total:.3f} T is close to Bs={core.bs_T:.3f} T")
    if fill > request.max_fill_factor:
        warnings.append(f"fill={fill:.3f} exceeds max_fill_factor={request.max_fill_factor:.3f}")
    warnings.append(
        "Ferrite path uses explicit gap + Steinmetz AC loss; powder dc_bias_coeffs are not applied."
    )

    return FerriteInductorResult(
        request=request,
        turns=turns,
        parallel_wires=parallel,
        inductance_h=inductance,
        effective_gap_m=gap_eff,
        al_nH_per_t2=al_nh,
        phase_current_rms_a=i_rms,
        phase_current_peak_a=i_peak,
        ripple_pp_a=ripple,
        bac_peak_t=bac,
        bdc_t=bdc,
        b_peak_total_t=b_total,
        core_loss_w=core_loss,
        copper_loss_w=copper_loss,
        total_inductor_loss_w=core_loss + copper_loss,
        fill_factor=fill,
        current_density_a_mm2=j,
        warnings=tuple(warnings),
    )


__all__ = [
    "FerriteInductorRequest",
    "FerriteInductorResult",
    "design_ferrite_pfc_inductor",
]
