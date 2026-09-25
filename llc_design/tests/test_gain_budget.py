"""Smart Control V2 — gain budget (companion to phase budget)."""

from __future__ import annotations

from functools import lru_cache

import pytest

from llc_design.control.analysis import build_small_signal_analysis
from llc_design.control.digital_loop import (
    CommandTimingConfig,
    PIFControllerConfig,
    build_digital_loop_analysis,
)
from llc_design.control.smart_control import compute_gain_budget
from llc_design.core.spec import LLCDesignSpec
from llc_design.models.system import LLCSystemAnalyzer


@lru_cache(maxsize=1)
def _analysis():
    spec = LLCDesignSpec()
    system = LLCSystemAnalyzer().analyze(spec)
    small = build_small_signal_analysis(spec, system_analysis=system, sample_time_s=20e-6)
    return build_digital_loop_analysis(
        small,
        controller_config=PIFControllerConfig(
            kp=0.002, ti_s=3e-3, lpf_cutoff_hz=3500, sample_time_s=20e-6),
        command_timing=CommandTimingConfig(computation_delay_s=1e-6),
    )


def test_gain_budget_explains_crossover():
    budget = compute_gain_budget(_analysis())
    assert budget is not None
    assert budget.consistent
    total_from_parts = sum(e.gain_db for e in budget.entries)
    assert total_from_parts == pytest.approx(budget.total_gain_db, abs=1e-9)
    assert abs(budget.open_loop_gain_db) < 1.0
