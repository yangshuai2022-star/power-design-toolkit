"""FHA ↔ time-domain cross-validation tests."""

from __future__ import annotations

import pytest

from llc_design.analysis import (
    LLCAnalysisRequest,
    ModelValidity,
    TimeDomainConfig,
    ValidityThresholds,
    compare_fha_td_metrics,
    validate_fha_td,
    validate_fha_td_point,
)
from llc_design.analysis.types import ModelMetrics
from llc_design.core.engineering import ConstraintStatus
from llc_design.core.spec import LLCDesignSpec


def _metrics(**overrides: float) -> ModelMetrics:
    base = dict(
        switching_frequency_hz=100_000.0,
        output_voltage_v=53.0,
        output_power_w=3000.0,
        normalized_gain=0.99,
        input_phase_deg=25.0,
        input_power_w=3100.0,
        resonant_current_rms_a=10.0,
        resonant_current_peak_a=14.0,
        magnetizing_current_rms_a=2.0,
        magnetizing_current_peak_a=2.8,
        primary_load_current_rms_a=8.0,
        primary_load_current_peak_a=11.0,
        secondary_current_rms_a=60.0,
        secondary_current_peak_a=85.0,
        rectifier_current_average_a=55.0,
        resonant_capacitor_rms_v=200.0,
        resonant_capacitor_peak_v=280.0,
        output_capacitor_current_rms_a=5.0,
        power_balance_error_w=1.0,
        power_balance_error_percent=0.03,
    )
    base.update(overrides)
    return ModelMetrics(**base)


def test_compare_metrics_pass_within_tolerance():
    fha = _metrics()
    td = _metrics(
        switching_frequency_hz=101_000.0,
        resonant_current_rms_a=10.3,
        magnetizing_current_peak_a=2.85,
        input_phase_deg=26.0,
    )
    deviations = compare_fha_td_metrics(fha, td, ValidityThresholds())
    assert all(d.status == ConstraintStatus.PASS for d in deviations)


def test_compare_metrics_warn_and_fail_thresholds():
    fha = _metrics(resonant_current_rms_a=10.0)
    td_warn = _metrics(resonant_current_rms_a=11.0)  # 10%
    td_fail = _metrics(resonant_current_rms_a=13.0)  # 30%
    thr = ValidityThresholds(warn_percent=8.0, fail_percent=20.0)
    warn_dev = next(
        d for d in compare_fha_td_metrics(fha, td_warn, thr)
        if d.metric == "resonant_current_rms_a"
    )
    fail_dev = next(
        d for d in compare_fha_td_metrics(fha, td_fail, thr)
        if d.metric == "resonant_current_rms_a"
    )
    assert warn_dev.status == ConstraintStatus.WARN
    assert fail_dev.status == ConstraintStatus.FAIL
    assert fail_dev.deviation_percent == pytest.approx(30.0, abs=0.1)


def test_nominal_fha_td_point_has_validity():
    spec = LLCDesignSpec()
    request = LLCAnalysisRequest(
        spec=spec, load_fraction=1.0, samples_per_cycle=512, waveform_cycles=1)
    result = validate_fha_td_point(
        request,
        time_domain=TimeDomainConfig(
            samples_per_cycle=512, output_cycles=1, frequency_scan_points=7),
        thresholds=ValidityThresholds(
            warn_percent=15.0, fail_percent=35.0,
            frequency_warn_percent=10.0, frequency_fail_percent=25.0,
            phase_warn_deg=15.0, phase_fail_deg=40.0,
        ),
    )
    assert result.fha is not None
    assert result.td is not None
    assert result.model_validity in {
        ModelValidity.PASS, ModelValidity.WARN, ModelValidity.FAIL, ModelValidity.UNKNOWN,
    }
    if result.fha.convergence.converged and result.td.convergence.converged:
        assert result.deviations
        names = {d.metric for d in result.deviations}
        assert "switching_frequency_hz" in names
        assert "normalized_gain" in names
        assert "resonant_current_rms_a" in names
        assert "magnetizing_current_peak_a" in names


def test_vin_and_light_load_fha_td_corners():
    spec = LLCDesignSpec()
    report = validate_fha_td(
        spec,
        requests=(
            LLCAnalysisRequest(
                spec=spec, vbus_v=spec.vbus_nom_v, load_fraction=1.0,
                samples_per_cycle=512, waveform_cycles=1),
            LLCAnalysisRequest(
                spec=spec, vbus_v=spec.vbus_min_normal_v, load_fraction=1.0,
                samples_per_cycle=512, waveform_cycles=1),
            LLCAnalysisRequest(
                spec=spec, vbus_v=spec.vbus_nom_v, load_fraction=0.10,
                samples_per_cycle=512, waveform_cycles=1),
        ),
        time_domain=TimeDomainConfig(
            samples_per_cycle=512, output_cycles=1, frequency_scan_points=7),
        thresholds=ValidityThresholds(
            warn_percent=20.0, fail_percent=45.0,
            frequency_warn_percent=15.0, frequency_fail_percent=35.0,
            phase_warn_deg=20.0, phase_fail_deg=50.0,
        ),
    )
    assert len(report.points) == 3
    assert report.overall_validity in {
        ModelValidity.PASS, ModelValidity.WARN, ModelValidity.FAIL, ModelValidity.UNKNOWN,
    }
    summary = report.as_summary()
    assert summary["points"] == 3
    assert "MODEL_VALIDITY" in summary
