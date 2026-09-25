"""ZVS Level-1 / Level-2 engineering margin for LLC primary bridges.

Level 1 (fast sweeps): inductive vs capacitive region from Im{Zin}, plus
commutation-current sign / magnitude used for turn-off and dead-time screening.

Level 2 (charge balance):
  Q_available ≈ ∫ i_commutation dt  ≈ I_commutation * t_dead   (FHA const-current)
  Q_required  = Qoss_hs + Qoss_ls   (= 2 * Nparallel * Qoss_device for a leg)
  ZVS_margin  = (Q_available - Q_required) / Q_required

MODEL_SOURCE is DATASHEET_QOSS when a positive Qoss is supplied, otherwise
COSS_APPROXIMATION (Q ≈ Coss * Vbus) or UNKNOWN. Approximations are never
labeled as verified high precision.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from .operating_point import LLCOperatingPoint
from .spec import LLCDesignSpec, MosfetSpec
from .tank import TankDesign, bridge_fundamental_rms_v, tank_state

ModelSource = Literal["DATASHEET_QOSS", "COSS_APPROXIMATION", "UNKNOWN"]
ZVSRegion = Literal["INDUCTIVE", "CAPACITIVE", "BOUNDARY"]


@dataclass(frozen=True)
class ZVSMarginResult:
    zvs_pass: bool
    zvs_margin: float
    q_available: float
    q_required: float
    i_commutation: float
    dead_time_s: float
    model_source: ModelSource
    level: int
    level1_region: ZVSRegion
    input_phase_deg: float
    charge_ratio: float
    energy_margin: float | None = None
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, float | bool | str | None]:
        return {
            "ZVS_PASS": self.zvs_pass,
            "ZVS_MARGIN": self.zvs_margin,
            "Q_AVAILABLE": self.q_available,
            "Q_REQUIRED": self.q_required,
            "I_COMMUTATION": self.i_commutation,
            "DEAD_TIME": self.dead_time_s,
            "MODEL_SOURCE": self.model_source,
            "LEVEL": float(self.level),
            "LEVEL1_REGION": self.level1_region,
            "INPUT_PHASE_DEG": self.input_phase_deg,
            "CHARGE_RATIO": self.charge_ratio,
            "ENERGY_MARGIN": self.energy_margin,
        }


def commutation_current_a(
    resonant_current_peak_a: float,
    magnetizing_current_peak_a: float,
    input_phase_deg: float,
) -> float:
    """Shared I_comm estimate used by OP solve, loss and ZVS Level 1/2."""

    phase_rad = math.radians(input_phase_deg)
    transition = abs(resonant_current_peak_a * math.sin(phase_rad))
    return max(0.75 * magnetizing_current_peak_a, transition)


def level1_region(input_phase_deg: float, *, boundary_deg: float = 0.5) -> ZVSRegion:
    if input_phase_deg > boundary_deg:
        return "INDUCTIVE"
    if input_phase_deg < -boundary_deg:
        return "CAPACITIVE"
    return "BOUNDARY"


def resolve_qoss_requirement(
    *,
    vbus_v: float,
    parallel_devices: int,
    qoss_c: float | None,
    coss_f: float | None,
) -> tuple[float, ModelSource, tuple[str, ...]]:
    """Return Q_required for one commutating bridge leg (HS+LS)."""

    npar = max(int(parallel_devices), 1)
    warnings: list[str] = []
    q_device: float | None = None
    source: ModelSource = "UNKNOWN"

    if qoss_c is not None and qoss_c > 0.0:
        q_device = float(qoss_c)
        source = "DATASHEET_QOSS"
    elif coss_f is not None and coss_f > 0.0 and vbus_v > 0.0:
        q_device = float(coss_f) * float(vbus_v)
        source = "COSS_APPROXIMATION"
        warnings.append(
            "Qoss unavailable; Q_required uses Coss*Vbus approximation "
            "(MODEL_SOURCE=COSS_APPROXIMATION)"
        )
    elif qoss_c is not None and coss_f is not None:
        # Non-positive Qoss with a usable Coss still approximates.
        if coss_f > 0.0 and vbus_v > 0.0:
            q_device = float(coss_f) * float(vbus_v)
            source = "COSS_APPROXIMATION"
            warnings.append(
                "Qoss <= 0; falling back to Coss*Vbus approximation"
            )

    if q_device is None:
        return 0.0, "UNKNOWN", (
            "No Qoss or Coss data — Q_required unknown; ZVS margin not credible",
        )

    # Prefer datasheet Qoss but never understate vs linear Coss*V when both exist.
    if source == "DATASHEET_QOSS" and coss_f is not None and coss_f > 0.0:
        q_device = max(q_device, float(coss_f) * float(vbus_v))

    q_required = 2.0 * npar * q_device
    return q_required, source, tuple(warnings)


def q_available_from_commutation(
    i_commutation_a: float,
    dead_time_s: float,
    *,
    current_waveform: tuple[float, ...] | None = None,
    sample_period_s: float | None = None,
) -> float:
    """Charge available during dead time.

    Prefer trapezoidal/const-current I*tdead for FHA sweeps. When a commutation
    window waveform is supplied, integrate it (Level-2 waveform path).
    """

    if current_waveform is not None and sample_period_s is not None and sample_period_s > 0.0:
        if len(current_waveform) < 2:
            return max(i_commutation_a, 0.0) * max(dead_time_s, 0.0)
        # ∫|i| dt over the provided window (absolute charge delivered).
        values = [abs(float(v)) for v in current_waveform]
        integral = 0.0
        dt = float(sample_period_s)
        for i0, i1 in zip(values[:-1], values[1:]):
            integral += 0.5 * (i0 + i1) * dt
        return integral
    return max(i_commutation_a, 0.0) * max(dead_time_s, 0.0)


def evaluate_zvs_margin(
    spec: LLCDesignSpec,
    tank: TankDesign,
    op: LLCOperatingPoint,
    *,
    qoss_c: float | None = None,
    coss_f: float | None = None,
    device: MosfetSpec | None = None,
    level: int = 2,
    dead_time_s: float | None = None,
    current_waveform: tuple[float, ...] | None = None,
    sample_period_s: float | None = None,
    pass_margin_min: float = 0.0,
) -> ZVSMarginResult:
    """Compute Level-1 region and Level-2 charge-balance ZVS margin."""

    if level not in (1, 2):
        raise ValueError("ZVS level must be 1 or 2")

    if device is not None:
        if qoss_c is None:
            qoss_c = device.qoss_c
        if coss_f is None:
            coss_f = device.coss_er_f

    dead = float(spec.primary_deadtime_s if dead_time_s is None else dead_time_s)
    if dead <= 0.0:
        raise ValueError("dead time must be positive")

    i_comm = float(op.commutation_current_a)
    region = level1_region(op.input_phase_deg)
    warnings: list[str] = []

    # Level 1: sign / region. Capacitive means commutation current does not
    # assist ZVS in the intended direction for a lagging tank.
    if region == "CAPACITIVE":
        warnings.append("Level-1 capacitive: Im{Zin} < 0")
    elif region == "BOUNDARY":
        warnings.append("Level-1 boundary: near-zero input phase")

    if i_comm <= 0.0:
        warnings.append("commutation current <= 0 — no charge available")

    if level == 1:
        # Fast sweep: pass if inductive and I_comm > 0 (no charge numbers yet).
        zvs_pass = region == "INDUCTIVE" and i_comm > 0.0
        return ZVSMarginResult(
            zvs_pass=zvs_pass,
            zvs_margin=float("nan") if not zvs_pass else float("inf"),
            q_available=float("nan"),
            q_required=float("nan"),
            i_commutation=i_comm,
            dead_time_s=dead,
            model_source="UNKNOWN",
            level=1,
            level1_region=region,
            input_phase_deg=op.input_phase_deg,
            charge_ratio=float("nan"),
            energy_margin=None,
            warnings=tuple(warnings),
        )

    q_required, source, q_warnings = resolve_qoss_requirement(
        vbus_v=op.vbus_v,
        parallel_devices=spec.primary_parallel_devices,
        qoss_c=qoss_c,
        coss_f=coss_f,
    )
    warnings.extend(q_warnings)

    q_available = q_available_from_commutation(
        i_comm, dead,
        current_waveform=current_waveform,
        sample_period_s=sample_period_s,
    )

    if source == "UNKNOWN" or q_required <= 0.0:
        return ZVSMarginResult(
            zvs_pass=False,
            zvs_margin=float("nan"),
            q_available=q_available,
            q_required=q_required,
            i_commutation=i_comm,
            dead_time_s=dead,
            model_source=source,
            level=2,
            level1_region=region,
            input_phase_deg=op.input_phase_deg,
            charge_ratio=float("nan"),
            energy_margin=None,
            warnings=tuple(warnings),
        )

    charge_ratio = q_available / q_required
    zvs_margin = (q_available - q_required) / q_required

    energy_margin = None
    if coss_f is not None and coss_f > 0.0:
        e_required = 2.0 * spec.primary_parallel_devices * 0.5 * coss_f * op.vbus_v**2
        e_available = 0.5 * (tank.lr_h + tank.lm_h) * i_comm**2
        energy_margin = e_available / max(e_required, 1e-15)

    zvs_pass = (
        region == "INDUCTIVE"
        and i_comm > 0.0
        and zvs_margin >= pass_margin_min
    )
    if region != "INDUCTIVE":
        zvs_pass = False

    return ZVSMarginResult(
        zvs_pass=zvs_pass,
        zvs_margin=zvs_margin,
        q_available=q_available,
        q_required=q_required,
        i_commutation=i_comm,
        dead_time_s=dead,
        model_source=source,
        level=2,
        level1_region=region,
        input_phase_deg=op.input_phase_deg,
        charge_ratio=charge_ratio,
        energy_margin=energy_margin,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def evaluate_zvs_at_frequency(
    spec: LLCDesignSpec,
    tank: TankDesign,
    *,
    frequency_hz: float,
    rac_ohm: float,
    vbus_v: float,
    qoss_c: float | None = None,
    coss_f: float | None = None,
    device: MosfetSpec | None = None,
    level: int = 2,
    dead_time_s: float | None = None,
) -> ZVSMarginResult:
    """ZVS evaluation on a fixed (f, Rac) mesh point without full OP solve."""

    state = tank_state(tank, frequency_hz, rac_ohm)
    v_bridge = bridge_fundamental_rms_v(spec, vbus_v)
    i_res = v_bridge / state.z_input_ohm
    v_parallel = i_res * state.z_parallel_ohm
    i_mag = v_parallel / (1j * 2.0 * math.pi * frequency_hz * tank.lm_h)
    i_res_peak = math.sqrt(2.0) * abs(i_res)
    i_mag_peak = math.sqrt(2.0) * abs(i_mag)
    i_comm = commutation_current_a(i_res_peak, i_mag_peak, state.input_phase_deg)

    # Minimal OP-like shim for evaluate_zvs_margin.
    op = LLCOperatingPoint(
        vbus_v=vbus_v,
        load_fraction=1.0,
        pout_w=spec.pout_w,
        output_current_a=spec.output_current_a,
        rac_ohm=rac_ohm,
        q_effective=tank.zr_ohm / rac_ohm,
        required_gain=state.gain,
        switching_frequency_hz=frequency_hz,
        normalized_frequency=frequency_hz / tank.fr_hz,
        achieved_gain=state.gain,
        branch="map",
        input_impedance_ohm=state.z_input_ohm,
        input_phase_deg=state.input_phase_deg,
        bridge_fundamental_rms_v=v_bridge,
        transformer_fundamental_rms_v=abs(v_parallel),
        transformer_square_equivalent_v=abs(v_parallel),
        resonant_current_rms_a=abs(i_res),
        resonant_current_peak_a=i_res_peak,
        magnetizing_current_rms_a=abs(i_mag),
        magnetizing_current_peak_a=i_mag_peak,
        reflected_load_current_rms_a=0.0,
        secondary_current_rms_a=0.0,
        secondary_current_peak_a=0.0,
        commutation_current_a=i_comm,
        estimated_input_power_w=0.0,
        available_gain_min=state.gain,
        available_gain_max=state.gain,
    )
    return evaluate_zvs_margin(
        spec, tank, op,
        qoss_c=qoss_c, coss_f=coss_f, device=device,
        level=level, dead_time_s=dead_time_s,
    )


__all__ = [
    "ModelSource",
    "ZVSMarginResult",
    "ZVSRegion",
    "commutation_current_a",
    "evaluate_zvs_at_frequency",
    "evaluate_zvs_margin",
    "level1_region",
    "q_available_from_commutation",
    "resolve_qoss_requirement",
]
