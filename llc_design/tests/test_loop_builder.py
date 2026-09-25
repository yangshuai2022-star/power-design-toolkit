"""Smart Control V2 — exact loop construction."""

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
    LoopDomain,
    MetricStatus,
    build_loop_model,
    fixed_loop_without_controller,
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
        command_timing=CommandTimingConfig(
            computation_delay_s=1e-6, pwm_update_delay_s=2e-6),
    )


def test_build_loop_model_exposes_chain_and_blocks():
    model = build_loop_model(_analysis())
    assert "C(z)" in model.chain_labels
    assert "LLC Gvf" in model.chain_labels
    names = {b.name for b in model.blocks}
    assert {"controller", "fm_modulator", "plant", "sensor_analog",
            "adc_digital_filter", "compute_pwm_timing", "zoh"} <= names
    assert any(b.domain == LoopDomain.DISCRETE for b in model.blocks)
    assert model.stability.ms >= 1.0
    assert model.stability.mt >= 0.0
    assert model.timing.pwm_update_delay_s == pytest.approx(2e-6)
    assert model.open_loop is model.analysis.nominal_open_loop


def test_pwm_update_delay_changes_open_loop_phase():
    """Falsifier: guided PWM update delay must be consumed by Bode."""
    base = _analysis()
    delayed = build_digital_loop_analysis(
        base.small_signal,
        controller_config=base.controller_config,
        fm_lut=base.fm_lut,
        analog_sense=base.analog_sense,
        adc_sampling=base.adc_sampling,
        command_timing=CommandTimingConfig(
            computation_delay_s=1e-6, pwm_update_delay_s=50e-6),
        frequencies_hz=base.frequencies_hz,
    )
    f = 2e3
    idx = int(np.argmin(np.abs(base.frequencies_hz - f)))
    phase0 = np.angle(base.nominal_open_loop[idx], deg=True)
    phase1 = np.angle(delayed.nominal_open_loop[idx], deg=True)
    expected = -360.0 * 48e-6 * f
    assert phase1 - phase0 == pytest.approx(expected, abs=2.0)


def test_fixed_loop_times_controller_recovers_open_loop():
    analysis = _analysis()
    fixed = fixed_loop_without_controller(analysis)
    rebuilt = fixed * analysis.responses["controller"]
    assert np.allclose(rebuilt, analysis.nominal_open_loop, rtol=1e-9, atol=1e-12)


def test_loop_model_evidence_has_falsification():
    model = build_loop_model(_analysis())
    assert model.evidence
    pm_ev = next(e for e in model.evidence if e.metric == "phase_margin_deg")
    assert "falsif" in pm_ev.falsification_condition.lower() or "If" in pm_ev.falsification_condition
    assert pm_ev.status in MetricStatus
