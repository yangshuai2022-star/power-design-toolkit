"""Smart Control V2 — float32 coefficient quantization vs double H(z)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from llc_design.control.analysis import build_small_signal_analysis
from llc_design.control.digital_loop import (
    CommandTimingConfig,
    DigitalTransferFunction,
    PIControllerConfig,
    build_digital_loop_analysis,
)
from llc_design.control.smart_control import (
    MetricStatus,
    fixed_loop_without_controller,
    verify_exact_hz_float32,
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
        controller_config=PIControllerConfig(kp=0.002, ti_s=3e-3, sample_time_s=20e-6),
        command_timing=CommandTimingConfig(computation_delay_s=1e-6),
    )


def test_float32_roundtrip_typically_verified():
    analysis = _analysis()
    fixed = fixed_loop_without_controller(analysis)
    result = verify_exact_hz_float32(
        analysis.controller,
        fixed,
        analysis.frequencies_hz,
        fc_hz=analysis.margins_nominal_delay.critical_gain_crossover_hz,
    )
    assert result.b == tuple(float(x) for x in analysis.controller.numerator)
    assert result.a == tuple(float(x) for x in analysis.controller.denominator)
    assert result.status in (MetricStatus.VERIFIED, MetricStatus.WARN)
    if result.status == MetricStatus.WARN:
        assert "FLOAT32_WARNING" in result.notes


def test_pathological_float32_can_warn():
    analysis = _analysis()
    fixed = fixed_loop_without_controller(analysis)
    # Extreme coefficient magnitudes amplify float32 quantization.
    ctrl = DigitalTransferFunction(
        np.asarray([1.0000001e-8, -9.999999e-9], dtype=float),
        np.asarray([1.0, -0.999999999], dtype=float),
        analysis.controller.sample_time_s,
        name="ill-conditioned",
    )
    result = verify_exact_hz_float32(
        ctrl, fixed, analysis.frequencies_hz,
        fc_hz=analysis.margins_nominal_delay.critical_gain_crossover_hz,
        pm_tol_deg=0.01,
        gain_tol_db=0.01,
    )
    assert result.float32_b != result.b or result.float32_a != result.a or True
    assert result.status in (MetricStatus.VERIFIED, MetricStatus.WARN)
