"""Smart Control V2 — Exact H(z) single source of truth."""

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
    export_controller_c99,
)
from llc_design.control.smart_control import (
    fixed_loop_without_controller,
    verify_exact_hz_float32,
)
from llc_design.control.solution_map import synthesize_tustin_pi_at_target
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


def test_solution_map_hz_matches_installed_controller_coefficients():
    analysis = _analysis()
    fixed = fixed_loop_without_controller(analysis)
    from llc_design.control.solution_map import _interp_complex_log_frequency
    target_fc = 1500.0
    fixed_fc = _interp_complex_log_frequency(analysis.frequencies_hz, fixed, target_fc)
    synth = synthesize_tustin_pi_at_target(
        fixed_fc,
        target_crossover_hz=target_fc,
        target_phase_margin_deg=70.0,
        sample_rate_hz=1.0 / analysis.controller.sample_time_s,
    )
    if synth is None:
        pytest.skip("PI phase unreachable at this operating point")
    cfg, _ = synth
    hz = cfg.transfer_function()
    installed = build_digital_loop_analysis(
        analysis.small_signal,
        controller_transfer_function=hz,
        controller_source="Solution Map Exact H(z)",
        fm_lut=analysis.fm_lut,
        analog_sense=analysis.analog_sense,
        adc_sampling=analysis.adc_sampling,
        command_timing=analysis.command_timing,
        frequencies_hz=analysis.frequencies_hz,
    )
    assert installed.controller.numerator == pytest.approx(hz.numerator)
    assert installed.controller.denominator == pytest.approx(hz.denominator)
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = export_controller_c99(installed.controller, Path(tmp) / "c99.c")
        text = path.read_text(encoding="utf-8")
        assert "llc_ctrl_b" in text and "llc_ctrl_a" in text
        for value in list(hz.numerator) + list(hz.denominator[1:]):
            literal = f"{float(value):.9g}"
            if "e" not in literal.lower() and "." not in literal:
                literal += ".0"
            assert literal + "f" in text


def test_control_tools_bridge_does_not_rediscretize():
    analysis = _analysis()
    b = np.asarray([0.01, -0.008], dtype=float)
    a = np.asarray([1.0, -1.0], dtype=float)
    hz = DigitalTransferFunction(b, a, analysis.controller.sample_time_s, name="Exact")
    result = build_digital_loop_analysis(
        analysis.small_signal,
        controller_transfer_function=hz,
        controller_source="Control Tools Exact H(z)",
        command_timing=analysis.command_timing,
        frequencies_hz=analysis.frequencies_hz,
    )
    assert result.controller.numerator == pytest.approx(b)
    assert result.controller.denominator == pytest.approx(a)
    assert "Exact" in result.controller.name or "Control Tools" in result.controller_source
