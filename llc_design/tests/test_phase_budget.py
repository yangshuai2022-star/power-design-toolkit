"""Smart Control V2 — phase / gain budget consistency."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from llc_design.control.analysis import build_small_signal_analysis
from llc_design.control.digital_loop import (
    CommandTimingConfig,
    PIFControllerConfig,
    build_digital_loop_analysis,
)
from llc_design.control.smart_control import (
    compute_gain_budget,
    compute_phase_budget,
    pure_delay_phase_deg,
)
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
        command_timing=CommandTimingConfig(computation_delay_s=1e-6, pwm_update_delay_s=2e-6),
    )


def test_phase_budget_sums_to_open_loop_phase():
    analysis = _analysis()
    budget = compute_phase_budget(analysis, tolerance_deg=2.0)
    assert budget is not None
    assert budget.consistent, (
        f"residual={budget.residual_deg:.3f}° "
        f"sum={budget.total_phase_deg:.3f} open={budget.open_loop_phase_deg:.3f}"
    )
    assert abs(budget.residual_deg) <= budget.tolerance_deg
    keys = {e.key for e in budget.entries}
    assert "delay_nominal" in keys
    assert "controller" in keys


def test_gain_budget_sums_to_open_loop_gain():
    analysis = _analysis()
    budget = compute_gain_budget(analysis, tolerance_db=0.5)
    assert budget is not None
    assert budget.consistent, f"residual={budget.residual_db:.4f} dB"
    # At Fc, open-loop gain should be near 0 dB.
    assert abs(budget.open_loop_gain_db) < 1.0


def test_known_pure_delay_phase_formula():
    assert pure_delay_phase_deg(20e-6, 5e3) == pytest.approx(-36.0)
    # Sign must be lagging (negative) for positive delay.
    assert pure_delay_phase_deg(10e-6, 10e3) < 0.0


def test_sensor_rc_and_digital_filter_appear_in_budget():
    """At a high enough frequency, analog RC and ADC recursive contribute phase."""
    analysis = _analysis()
    # Divider/RC poles sit ~100–360 kHz; probe well above typical Fc.
    probe_hz = min(20e3, float(analysis.frequencies_hz[-1]) * 0.5)
    budget = compute_phase_budget(analysis, frequency_hz=probe_hz)
    assert budget is not None
    by_key = {e.key: e for e in budget.entries}
    assert "sense_analog_calibrated" in by_key
    assert "adc_sampling" in by_key
    # ADC recursive average is a discrete LPF — phase lag grows with frequency.
    assert by_key["adc_sampling"].phase_deg < -0.5
    # Timing block must contribute lagging phase for positive delay.
    assert by_key["delay_nominal"].phase_deg < -1.0
    assert budget.consistent or abs(budget.residual_deg) <= 5.0
