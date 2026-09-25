"""PFC Engineering V3 — zero-crossing analyzer regressions (isolated factors)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pfc_design.control import PFCControlLabConfig
from pfc_design.engineering.pfc_v3 import (
    analyze_zero_crossing,
    build_line_cycle_result,
)


def _fast_cfg(**kwargs):
    base = replace(
        PFCControlLabConfig(),
        waveform_line_cycles=3,
        waveform_integration_rate_hz=250e3,
    )
    return replace(base, **kwargs) if kwargs else base


def test_ideal_pwm_reports_minimum_current_bound():
    cfg = _fast_cfg()
    zc = analyze_zero_crossing(cfg)
    assert zc.minimum_realizable_current_a >= 0.0
    assert zc.effective_duty_deadzone >= cfg.power_stage.duty_min
    assert 1.0 in zc.zooms and 10.0 in zc.zooms
    assert zc.points
    assert zc.evidence


def test_minimum_pulse_increases_deadzone_and_min_current():
    base = _fast_cfg()
    stage0 = replace(base.power_stage, minimum_effective_pulse_s=0.0, duty_min=0.01)
    stage1 = replace(base.power_stage, minimum_effective_pulse_s=2.0e-6, duty_min=0.01)
    z0 = analyze_zero_crossing(replace(base, power_stage=stage0))
    z1 = analyze_zero_crossing(replace(base, power_stage=stage1))
    assert z1.effective_duty_deadzone > z0.effective_duty_deadzone
    assert z1.minimum_realizable_current_a > z0.minimum_realizable_current_a


def test_dead_time_voltage_error_scales_with_td():
    base = _fast_cfg()
    stage0 = replace(base.power_stage, deadtime_s=0.0)
    stage1 = replace(base.power_stage, deadtime_s=200e-9)
    z0 = analyze_zero_crossing(replace(base, power_stage=stage0))
    z1 = analyze_zero_crossing(replace(base, power_stage=stage1))
    assert z0.dead_time_voltage_error_v == pytest.approx(0.0, abs=1e-12)
    assert z1.dead_time_voltage_error_v > z0.dead_time_voltage_error_v
    assert "APPROXIMATION" in z1.evidence[1].status.value or z1.evidence[1].status.value == "APPROXIMATION"


def test_sensor_offset_shifts_iactual_only():
    cfg = _fast_cfg()
    line = build_line_cycle_result(cfg)
    z0 = analyze_zero_crossing(cfg, line=line, sensor_offset_a=0.0)
    z1 = analyze_zero_crossing(cfg, line=line, sensor_offset_a=0.1)
    assert z1.sensor_offset_a == pytest.approx(0.1)
    # Same crossing sample: Iactual differs by the offset (sign convention applied).
    assert abs(z1.points[0].iactual_a - z0.points[0].iactual_a) == pytest.approx(0.1, abs=1e-9)


def test_min_pulse_boundary_marks_pulse_validity():
    cfg = _fast_cfg()
    stage = replace(cfg.power_stage, minimum_effective_pulse_s=5.0e-6, duty_min=0.02)
    zc = analyze_zero_crossing(replace(cfg, power_stage=stage))
    assert zc.effective_duty_deadzone == pytest.approx(
        max(0.02, 5.0e-6 * stage.switching_frequency_hz)
    )
