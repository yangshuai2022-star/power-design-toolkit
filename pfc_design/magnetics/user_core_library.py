"""Persistent user overlay for PFC magnetic cores (built-in remains read-only).

Brand taxonomy placeholders such as 铂科 / 东睦科达 may appear here only after the
user supplies geometry and loss evidence.  Built-in calculable catalogs are never
shadowed by user part numbers.
"""
from __future__ import annotations

from dataclasses import asdict, fields
import json
import os
from pathlib import Path
import sys
from typing import Any

from .core_entry import CoreSpec
from .steinmetz import SteinmetzMaterial

USER_CORE_LIBRARY_SCHEMA = "power-design-toolkit-pfc-core-library-v1"


def default_user_core_library_path() -> Path:
    override = os.getenv("POWER_DESIGN_TOOLKIT_PFC_CORE_LIBRARY", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return root / "PowerDesignToolkit" / "pfc_cores.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PowerDesignToolkit" / "pfc_cores.json"
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "power-design-toolkit" / "pfc_cores.json"


def _empty_payload() -> dict[str, Any]:
    return {
        "metadata": {
            "schema": USER_CORE_LIBRARY_SCHEMA,
            "source": "User-maintained PFC magnetic core library",
            "warning": (
                "Do not invent DC-bias or Steinmetz coefficients. "
                "Record manufacturer datasheet revision and validity range."
            ),
        },
        "cores": [],
        "steinmetz_materials": {},
    }


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _core_from_dict(entry: dict, source: Path) -> CoreSpec:
    allowed = {f.name for f in fields(CoreSpec)}
    payload = {k: v for k, v in entry.items() if k in allowed}
    required = (
        "manufacturer", "part_number", "material", "material_class",
        "od_mm", "id_mm", "ht_mm", "ae_cm2", "le_cm", "ve_cm3",
        "al_nH_per_t2", "ui", "bs_T",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"user core missing {missing} in {source}")
    return CoreSpec(**payload)


class UserCoreLibrary:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else default_user_core_library_path()
        self.cores: list[CoreSpec] = []
        self.steinmetz: dict[str, SteinmetzMaterial] = {}
        self.metadata: dict[str, Any] = {}
        self.refresh()

    def refresh(self) -> None:
        if not self.path.exists():
            self.cores = []
            self.steinmetz = {}
            self.metadata = _empty_payload()["metadata"]
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"user core library must be a JSON object: {self.path}")
        self.metadata = dict(data.get("metadata") or {})
        self.cores = [_core_from_dict(entry, self.path) for entry in data.get("cores", [])]
        self.steinmetz = {}
        for name, coeffs in (data.get("steinmetz_materials") or {}).items():
            self.steinmetz[str(name)] = SteinmetzMaterial(
                name=str(name),
                k=float(coeffs["k"]),
                alpha=float(coeffs["alpha"]),
                beta=float(coeffs["beta"]),
                f_min_khz=float(coeffs.get("f_range_kHz", [20, 200])[0]),
                f_max_khz=float(coeffs.get("f_range_kHz", [20, 200])[1]),
            )

    def _payload(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata or _empty_payload()["metadata"],
            "cores": [asdict(core) for core in self.cores],
            "steinmetz_materials": {
                name: {
                    "k": mat.k,
                    "alpha": mat.alpha,
                    "beta": mat.beta,
                    "f_range_kHz": [mat.f_min_khz, mat.f_max_khz],
                }
                for name, mat in self.steinmetz.items()
            },
        }

    def save_core(self, core: CoreSpec, *, overwrite: bool = False) -> None:
        name = core.part_number.strip()
        if not name:
            raise ValueError("part_number must not be empty")
        existing = {c.part_number.casefold(): i for i, c in enumerate(self.cores)}
        folded = name.casefold()
        if folded in existing:
            if not overwrite:
                raise ValueError(f"user core '{name}' already exists; pass overwrite=True")
            self.cores[existing[folded]] = core
        else:
            self.cores.append(core)
        _atomic_write(self.path, self._payload())

    def save_steinmetz(self, material: SteinmetzMaterial) -> None:
        if min(material.k, material.alpha, material.beta) <= 0.0:
            raise ValueError("Steinmetz k/alpha/beta must be > 0")
        self.steinmetz[material.name] = material
        _atomic_write(self.path, self._payload())

    def delete_core(self, part_number: str) -> None:
        folded = part_number.casefold()
        self.cores = [c for c in self.cores if c.part_number.casefold() != folded]
        _atomic_write(self.path, self._payload())


__all__ = [
    "USER_CORE_LIBRARY_SCHEMA",
    "UserCoreLibrary",
    "default_user_core_library_path",
]
