"""PFC Engineering V3 — PF / THD engine regressions."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pfc_design.engineering.pfc_v3 import compute_pf_thd


def _grid(line_hz: float = 50.0, cycles: int = 1, fs: float = 50e3):
    n = int(round(cycles * fs / line_hz))
    t = np.arange(n, dtype=float) / fs
    return t, line_hz


def test_case_a_ideal_sine_in_phase():
    t, fl = _grid()
    vac = 230.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t)
    iac = 10.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t)
    r = compute_pf_thd(t, vac, iac, line_hz=fl, max_harmonic=11)
    assert r.sanity_ok
    assert r.pf == pytest.approx(1.0, abs=2e-3)
    assert r.dpf == pytest.approx(1.0, abs=2e-3)
    assert r.distortion_factor == pytest.approx(1.0, abs=2e-3)
    assert r.thd == pytest.approx(0.0, abs=2e-3)
    assert abs(r.pf - r.dpf * r.distortion_factor) < 5e-3


def test_case_b_phase_shifted_sine():
    t, fl = _grid()
    phi = math.radians(30.0)
    vac = 230.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t)
    iac = 10.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t - phi)
    r = compute_pf_thd(t, vac, iac, line_hz=fl, max_harmonic=11)
    assert r.dpf == pytest.approx(math.cos(phi), abs=5e-3)
    assert r.distortion_factor == pytest.approx(1.0, abs=5e-3)
    assert r.pf == pytest.approx(math.cos(phi), abs=1e-2)
    assert abs(r.pf - r.dpf * r.distortion_factor) < 2e-2


def test_case_c_injected_h3_h5_harmonics():
    t, fl = _grid()
    w = 2 * math.pi * fl
    vac = 230.0 * math.sqrt(2) * np.sin(w * t)
    # Peak amplitudes: H1=10√2, H3=1.0√2, H5=0.5√2 → RMS 10, 1, 0.5
    iac = (
        10.0 * math.sqrt(2) * np.sin(w * t)
        + 1.0 * math.sqrt(2) * np.sin(3 * w * t)
        + 0.5 * math.sqrt(2) * np.sin(5 * w * t)
    )
    r = compute_pf_thd(t, vac, iac, line_hz=fl, max_harmonic=11)
    thd_analytic = math.sqrt(1.0**2 + 0.5**2) / 10.0
    assert r.harmonics_rms_a[3] == pytest.approx(1.0, rel=0.05)
    assert r.harmonics_rms_a[5] == pytest.approx(0.5, rel=0.08)
    assert r.thd == pytest.approx(thd_analytic, rel=0.08)
    assert r.dpf == pytest.approx(1.0, abs=2e-2)
    assert abs(r.pf - r.dpf * r.distortion_factor) < 3e-2


def test_case_d_dc_offset_does_not_claim_perfect_thd_identity_blindly():
    t, fl = _grid()
    vac = 230.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t)
    iac = 10.0 * math.sqrt(2) * np.sin(2 * math.pi * fl * t) + 0.5
    r = compute_pf_thd(t, vac, iac, line_hz=fl, max_harmonic=11)
    assert r.sanity_ok
    assert r.pf <= 1.0 + 1e-6
    # DC is outside odd-harmonic THD convention; residual may grow — engine must stay sane.
    assert r.thd >= 0.0


def test_pf_cannot_exceed_one_silently():
    t, fl = _grid()
    vac = np.sin(2 * math.pi * fl * t)
    iac = 2.0 * np.sin(2 * math.pi * fl * t)
    r = compute_pf_thd(t, vac, iac, line_hz=fl)
    assert r.pf <= 1.0 + 1e-6
    assert r.convention.fundamental_definition == "DFT_H1_RMS"
