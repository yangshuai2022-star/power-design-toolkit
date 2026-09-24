"""Shared validation helpers for user-entered devices and magnetics.

Built-in reference libraries remain separate from user overlays.  When a loss or
magnetics calculation needs a field that is missing or non-positive, callers must
prompt the user instead of silently substituting another brand's coefficients.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class MissingParameter:
    name: str
    unit: str
    reason: str


def load_brand_taxonomy(path: Path | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1] / "engineering_data" / "brand_taxonomy.json"
    data = json.loads((path or root).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "brands" not in data:
        raise ValueError("brand taxonomy must contain a brands array")
    return data


def brand_display_names() -> tuple[str, ...]:
    return tuple(str(item["display_name"]) for item in load_brand_taxonomy()["brands"])


def missing_llc_mosfet_loss_parameters(device: Any) -> tuple[MissingParameter, ...]:
    """Fields required by the current LLC single-point MOSFET loss model."""
    required = (
        ("part_number", "", "part identification"),
        ("vds_max_v", "V", "voltage rating"),
        ("id_cont_a", "A", "continuous current rating"),
        ("rds_on_25_ohm", "Ω", "RDS(on) @ 25 °C"),
        ("rds_on_hot_ohm", "Ω", "RDS(on) at hot reference"),
        ("hot_temperature_c", "°C", "hot RDS reference temperature"),
        ("qg_c", "C", "gate charge"),
        ("coss_er_f", "F", "Coss energy-related capacitance"),
        ("eoff_ref_j", "J", "turn-off energy reference"),
        ("eoff_ref_v", "V", "Eoff reference voltage"),
        ("eoff_ref_i", "A", "Eoff reference current"),
        ("gate_voltage_v", "V", "gate drive voltage"),
    )
    missing: list[MissingParameter] = []
    for name, unit, reason in required:
        value = getattr(device, name, None)
        if value is None:
            missing.append(MissingParameter(name, unit, reason))
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(MissingParameter(name, unit, reason))
            continue
        if isinstance(value, (int, float)) and float(value) <= 0.0 and name not in {"body_diode_vf_v"}:
            missing.append(MissingParameter(name, unit, f"{reason} must be > 0"))
    return tuple(missing)


def missing_pfc_mosfet_loss_parameters(device: Any) -> tuple[MissingParameter, ...]:
    required = (
        ("manufacturer", "", "manufacturer / brand"),
        ("part_number", "", "part identification"),
        ("vds_max", "V", "voltage rating"),
        ("id_25c", "A", "current rating @ 25 °C"),
        ("rds_on_25c", "Ω", "RDS(on) @ 25 °C"),
        ("qg_nc", "nC", "gate charge"),
        ("coss_er_pF", "pF", "Coss energy-related"),
        ("vgs", "V", "gate drive voltage"),
    )
    missing: list[MissingParameter] = []
    for name, unit, reason in required:
        value = getattr(device, name, None)
        if value is None or (isinstance(value, str) and not str(value).strip()):
            missing.append(MissingParameter(name, unit, reason))
            continue
        if isinstance(value, (int, float)) and float(value) <= 0.0:
            missing.append(MissingParameter(name, unit, f"{reason} must be > 0"))
    # Switching energy is optional, but if one side is set the reference pair must be complete.
    eon = float(getattr(device, "eon_ref_uj", 0.0) or 0.0)
    eoff = float(getattr(device, "eoff_ref_uj", 0.0) or 0.0)
    if (eon > 0.0) != (eoff > 0.0):
        missing.append(MissingParameter(
            "eon_ref_uj/eoff_ref_uj", "µJ",
            "provide both Eon and Eoff references, or leave both at 0 to use tr/tf fallback",
        ))
    return tuple(missing)


def missing_ferrite_steinmetz_parameters(
    material_name: str,
    steinmetz: Any | None,
) -> tuple[MissingParameter, ...]:
    if steinmetz is None:
        return (
            MissingParameter(
                "steinmetz",
                "k,α,β",
                f"no Steinmetz coefficients for '{material_name}'; cannot borrow another brand's fit",
            ),
        )
    missing: list[MissingParameter] = []
    for name, unit in (("k", "SI"), ("alpha", "-"), ("beta", "-")):
        value = getattr(steinmetz, name, None)
        if value is None or float(value) <= 0.0:
            missing.append(MissingParameter(name, unit, f"Steinmetz {name} required for ferrite loss"))
    return tuple(missing)


def format_missing(items: Iterable[MissingParameter]) -> str:
    lines = [f"- {item.name}" + (f" [{item.unit}]" if item.unit else "") + f": {item.reason}" for item in items]
    return "\n".join(lines) if lines else ""


__all__ = [
    "MissingParameter",
    "brand_display_names",
    "format_missing",
    "load_brand_taxonomy",
    "missing_ferrite_steinmetz_parameters",
    "missing_llc_mosfet_loss_parameters",
    "missing_pfc_mosfet_loss_parameters",
]
