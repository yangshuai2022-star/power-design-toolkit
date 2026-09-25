"""Smart Control V2 — Solution Map V2 + controller candidates."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from llc_design.control.analysis import build_small_signal_analysis
from llc_design.control.digital_loop import (
    CommandTimingConfig,
    PIControllerConfig,
    build_digital_loop_analysis,
)
from llc_design.control.smart_control import (
    evaluate_solution_map_v2_point,
    fixed_loop_without_controller,
    synthesize_controller_candidates,
)
from llc_design.control.solution_map import SolutionStatus
from llc_design.core.spec import LLCDesignSpec
from llc_design.models.system import LLCSystemAnalyzer


@lru_cache(maxsize=1)
def _fixed_loop():
    spec = LLCDesignSpec()
    system = LLCSystemAnalyzer().analyze(spec)
    small = build_small_signal_analysis(spec, system_analysis=system, sample_time_s=20e-6)
    analysis = build_digital_loop_analysis(
        small,
        controller_config=PIControllerConfig(kp=0.002, ti_s=3e-3, sample_time_s=20e-6),
        command_timing=CommandTimingConfig(computation_delay_s=1e-6),
    )
    return analysis, fixed_loop_without_controller(analysis)


def test_solution_map_v2_feasible_point_rebuilds_loop():
    analysis, fixed = _fixed_loop()
    point = evaluate_solution_map_v2_point(
        analysis.frequencies_hz,
        fixed,
        sample_rate_hz=1.0 / analysis.controller.sample_time_s,
        switching_frequency_hz=analysis.small_signal.operating_point.switching_frequency_hz,
        target_crossover_hz=1500.0,
        target_phase_margin_deg=70.0,
        mt_max=5.0,
        sampling_warn_threshold=8.0,
    )
    assert point.status in SolutionStatus
    # Synthesis must produce Exact H(z) coefficients even when constraints fail.
    if point.status != SolutionStatus.PHASE_TARGET_UNREACHABLE:
        assert point.kp is not None and point.ti_s is not None
        assert point.ms is not None and point.mt is not None


def test_controller_candidates_are_named_not_scored():
    analysis, fixed = _fixed_loop()
    # Targets chosen so Tustin PI phase is reachable on this plant.
    candidates = synthesize_controller_candidates(
        analysis.frequencies_hz,
        fixed,
        sample_rate_hz=1.0 / analysis.controller.sample_time_s,
        switching_frequency_hz=analysis.small_signal.operating_point.switching_frequency_hz,
        base_fc_hz=1500.0,
        base_pm_deg=70.0,
    )
    names = {c.name for c in candidates}
    assert names <= {"Robust", "Balanced", "Fast"}
    assert len(candidates) >= 1
    for c in candidates:
        payload = c.as_dict()
        assert "score" not in payload
        assert "ai" not in payload
        assert c.kp > 0.0 and c.ti_s > 0.0
