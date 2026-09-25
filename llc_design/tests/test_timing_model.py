"""Smart Control V2 — timing / delay ownership."""

from __future__ import annotations

import math

import numpy as np
import pytest

from llc_design.control.digital_loop import (
    ADCSamplingConfig,
    CommandTimingConfig,
    DelayEnvelope,
)
from llc_design.control.smart_control import TimingModel, pure_delay_phase_deg


def test_pure_delay_phase_20us_at_5khz():
    assert pure_delay_phase_deg(20e-6, 5e3) == pytest.approx(-36.0)


def test_timing_model_ownership_no_double_count_adc_in_compute():
    adc = ADCSamplingConfig()
    timing = CommandTimingConfig(computation_delay_s=3e-6, pwm_update_delay_s=5e-6)
    model = TimingModel.from_loop_configs(adc, timing, switching_frequency_hz=100e3)
    assert model.sampling_delay_s == pytest.approx(adc.eoc_delay_s)
    assert model.compute_time_s == pytest.approx(3e-6)
    assert model.pwm_update_delay_s == pytest.approx(5e-6)
    # Application delay = ADC EOC + compute + pwm_update + zero-wait (no ZOH).
    app = timing.application_delay_s(adc, 100e3, DelayEnvelope.NOMINAL)
    assert model.total_nominal_s == pytest.approx(app)
    # ZOH half-sample is tracked separately and must not inflate pure-delay total.
    assert model.zoh_half_sample_s == pytest.approx(0.5 * adc.control_sample_time_s)
    assert model.total_nominal_s == pytest.approx(
        model.sampling_delay_s
        + model.compute_time_s
        + model.pwm_update_delay_s
        + model.pwm_zero_wait_nominal_s
    )


def test_zero_delay_envelope_minimum_has_no_zero_wait():
    adc = ADCSamplingConfig()
    timing = CommandTimingConfig(computation_delay_s=0.0, pwm_update_delay_s=0.0,
                                 include_zero_order_hold=False)
    model = TimingModel.from_loop_configs(adc, timing, 80e3)
    assert model.total_min_s == pytest.approx(adc.eoc_delay_s)
    assert CommandTimingConfig.pwm_zero_wait_s(80e3, DelayEnvelope.MINIMUM) == 0.0
    fr = timing.frequency_response(
        np.asarray([1e3, 5e3]), adc=adc, switching_frequency_hz=80e3,
        envelope=DelayEnvelope.MINIMUM)
    # Pure EOC delay only.
    expected = np.exp(-1j * 2 * math.pi * np.asarray([1e3, 5e3]) * adc.eoc_delay_s)
    assert np.allclose(fr, expected, rtol=1e-9, atol=1e-12)
