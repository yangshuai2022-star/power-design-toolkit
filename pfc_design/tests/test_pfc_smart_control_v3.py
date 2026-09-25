"""PFC Engineering V3 — Smart Control dual-loop separation / Exact H(z)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pfc_design.control import PFCControlLabConfig, build_pfc_control_lab_analysis
from pfc_design.control.handoff import assert_handoff_matches_analysis
from pfc_design.engineering.pfc_v3 import (
    build_pfc_smart_control_v3,
    localize_distortion,
    build_line_cycle_result,
    run_pfc_engineering_v3_core,
)


def test_smart_control_exposes_separation_ms_mt_and_2fline():
    cfg = PFCControlLabConfig()
    smart = build_pfc_smart_control_v3(cfg)
    assert smart.separation.line_2x_hz == pytest.approx(
        2.0 * cfg.power_stage.line_frequency_hz
    )
    assert smart.current.ms >= 1.0
    assert smart.voltage.ms >= 1.0
    assert smart.current.mt >= 0.0
    if smart.current.phase_budget is not None:
        assert abs(smart.current.phase_budget.residual_deg) <= 5.0 or not smart.current.phase_budget.consistent
    assert smart.handoff.current.b
    assert smart.handoff.voltage.a[0] == pytest.approx(1.0)
    assert_handoff_matches_analysis(smart.analysis, smart.handoff)


def test_exact_hz_matches_analysis_controllers():
    analysis = build_pfc_control_lab_analysis(PFCControlLabConfig())
    smart = build_pfc_smart_control_v3(PFCControlLabConfig(), analysis=analysis)
    assert np.allclose(smart.handoff.current.b, analysis.current_loop.controller.numerator)
    assert np.allclose(smart.handoff.current.a, analysis.current_loop.controller.denominator)


def test_distortion_localization_returns_regions():
    cfg = replace(
        PFCControlLabConfig(),
        waveform_line_cycles=3,
        waveform_integration_rate_hz=250e3,
    )
    line = build_line_cycle_result(cfg)
    regions = localize_distortion(line)
    assert len(regions) == 5
    assert regions[0].angle_start_deg == 0.0
    assert sum(r.harmonic_contribution_estimate for r in regions) == pytest.approx(1.0, abs=0.05)


def test_core_pack_runs_end_to_end():
    cfg = replace(
        PFCControlLabConfig(),
        waveform_line_cycles=3,
        waveform_integration_rate_hz=250e3,
    )
    pack = run_pfc_engineering_v3_core(cfg)
    assert pack["pf_thd"]["PF"] <= 1.01
    assert pack["pf_thd"]["THD"] >= 0.0
    assert "zero_crossing" in pack
    assert "smart_control" in pack
    assert pack["smart_control"]["separation"]["2x_line_hz"] == pytest.approx(100.0)
