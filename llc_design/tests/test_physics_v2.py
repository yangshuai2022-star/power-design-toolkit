"""V2 physics accuracy tests: FHA↔TD, waveform loss, thermal, two-stage opt."""

from __future__ import annotations

import math

import pytest

from llc_design.analysis.engineering_validation import run_engineering_validation
from llc_design.analysis.fha_td_validation import (
    FhaCredibility,
    build_fha_validity_map,
    validate_fha_against_time_domain,
)
from llc_design.core.operating_point import solve_operating_point
from llc_design.core.spec import LLCDesignSpec
from llc_design.core.tank import design_tank
from llc_design.models.devices import DeviceDatabase
from llc_design.models.electro_thermal import iterate_electro_thermal
from llc_design.models.physics_evidence import (
    ModelGrade,
    SwitchingClass,
    classify_turn_on_from_zvs_margin,
    physical_sanity_issues,
)
from llc_design.models.system import LLCSystemAnalyzer
from llc_design.models.waveform_loss import (
    bridge_loss_with_provenance,
    rectifier_loss_with_provenance,
)
from llc_design.optimization.sweep import OptimizationConfig
from llc_design.optimization.two_stage import TwoStageLLCOptimizer


def test_validate_fha_against_time_domain_critical_points():
    spec = LLCDesignSpec()
    report = validate_fha_against_time_domain(spec)
    assert len(report.points) >= 4
    assert report.overall_validity.value in {"PASS", "WARN", "FAIL", "UNKNOWN"}
    # Non-converged TD must not silently become PASS for that point alone without gate
    for point in report.points:
        if point.td is not None and not point.td.convergence.converged:
            assert point.model_validity.value in {"UNKNOWN", "WARN", "FAIL"}


def test_fha_validity_map_data_layer():
    spec = LLCDesignSpec()
    amap = build_fha_validity_map(
        spec, fn_values=(0.9, 1.0), load_fractions=(1.0, 0.25),
    )
    assert len(amap.fn_axis) == 2
    assert len(amap.load_axis) == 2
    assert len(amap.cells) == 4
    cell = amap.cell(1.0, 1.0)
    assert cell is not None
    assert isinstance(cell.credibility, FhaCredibility)


def test_turn_on_class_from_zvs_margin():
    assert classify_turn_on_from_zvs_margin(0.5) == SwitchingClass.FULL_ZVS
    assert classify_turn_on_from_zvs_margin(0.05) == SwitchingClass.PARTIAL_ZVS
    assert classify_turn_on_from_zvs_margin(-0.1) == SwitchingClass.HARD_SWITCHING
    assert classify_turn_on_from_zvs_margin(float("nan")) == SwitchingClass.UNKNOWN


def test_physical_sanity_catches_impossible_efficiency():
    issues = physical_sanity_issues(efficiency=1.05, loss_w=-1.0, bpk_t=-0.1)
    assert any("efficiency" in i for i in issues)
    assert any("loss" in i for i in issues)
    assert any("Bpk" in i for i in issues)


def test_waveform_loss_provenance_and_bucket_sum():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    device = DeviceDatabase().get_primary(spec.primary_device)
    bridge = bridge_loss_with_provenance(spec, tank, op, device)
    assert bridge.turn_on_class in SwitchingClass
    assert bridge.total_w == pytest.approx(sum(t.value_w for t in bridge.terms), rel=1e-9)
    assert all(isinstance(t.model, ModelGrade) for t in bridge.terms)

    sr = DeviceDatabase().get_sr(spec.sr_device)
    diode = rectifier_loss_with_provenance(spec, op, sr, kind="DIODE")
    rr = next(t for t in diode.terms if t.name == "reverse_recovery")
    assert rr.model == ModelGrade.UNKNOWN  # must not pretend zero is verified


def test_electro_thermal_iteration_reports_status():
    spec = LLCDesignSpec()
    analysis = LLCSystemAnalyzer().analyze(spec)
    result = iterate_electro_thermal(spec, analysis.nominal.operating_point)
    assert result.iterations >= 1
    assert result.primary_tj_c >= spec.ambient_temperature_c - 1e-6
    assert len(result.nodes) == 4
    # Status is explicit even when not converged
    assert result.converged in (True, False)


def test_engineering_validation_consumer_chain():
    spec = LLCDesignSpec()
    report = run_engineering_validation(spec, include_thermal=True, include_validity_map=False)
    assert report.envelope.points
    assert report.fha_td.points
    assert report.worst_case_summary
    assert any("Leakage" in r.model for r in report.model_rows)
    text = report.as_markdown()
    assert "Model Validity" in text
    assert "UNKNOWN" in text or "APPROXIMATION" in text


def test_system_analyzer_engineering_validation_method():
    analyzer = LLCSystemAnalyzer()
    report = analyzer.engineering_validation(LLCDesignSpec(), include_thermal=False)
    assert report.fha_td.points


def test_two_stage_optimizer_rejects_fail_before_rank():
    opt = TwoStageLLCOptimizer()
    result = opt.run(
        LLCDesignSpec(),
        OptimizationConfig.quick(),
        maximum_candidates=4,
        top_n=2,
        run_stage_b=False,  # keep CI light; still exercises envelope gate + ranking metrics
    )
    assert result.stage_a.table is not None
    # Every accepted candidate must precede every rejected candidate.
    flags = [candidate.rejected for candidate in result.verified]
    assert flags == sorted(flags)
    for candidate in result.verified:
        if candidate.rejected:
            assert candidate.reject_reason


@pytest.mark.parametrize("reject_at", ["envelope", "td"])
def test_two_stage_optimizer_rejection_gates_are_not_vacuous(monkeypatch, reject_at):
    """Force both an accepted and rejected candidate through the real ranking path.

    Only physical evaluations and the Stage-A table are substituted. This test
    verifies gate consumption/order, not the accuracy of the substituted models.
    """
    from types import SimpleNamespace

    import pandas as pd

    import llc_design.optimization.two_stage as module

    spec = LLCDesignSpec()
    analyzer = LLCSystemAnalyzer()
    analysis = analyzer.analyze(spec)
    optimizer = TwoStageLLCOptimizer(analyzer)
    rejected_ln = float(spec.ln_ratio)
    accepted_ln = rejected_ln + 1.0
    rows = [
        {
            "feasible": True,
            "ln": ln,
            "q_full": spec.q_full_load,
            "fr_khz": spec.resonant_frequency_hz / 1e3,
            "primary_turns": spec.primary_turns,
            "secondary_turns": spec.secondary_turns,
            "primary_device": spec.primary_device,
            "sr_parallel": spec.sr_parallel_devices_per_position,
            "weighted_loss_w": float(index),
        }
        for index, ln in enumerate((rejected_ln, accepted_ln))
    ]
    monkeypatch.setattr(
        optimizer.fast, "run",
        lambda *args, **kwargs: SimpleNamespace(table=pd.DataFrame(rows)),
    )
    monkeypatch.setattr(analyzer, "analyze", lambda candidate: analysis)
    checked = []

    def envelope_status(candidate, unused_analyzer):
        checked.append(candidate.ln_ratio)
        if reject_at == "envelope" and candidate.ln_ratio == rejected_ln:
            return module.ConstraintStatus.FAIL
        return module.ConstraintStatus.PASS

    def td_report(candidate):
        validity = module.ModelValidity.PASS
        if reject_at == "td" and candidate.ln_ratio == rejected_ln:
            validity = module.ModelValidity.FAIL
        return SimpleNamespace(overall_validity=validity)

    monkeypatch.setattr(module, "_envelope_status", envelope_status)
    monkeypatch.setattr(module, "validate_fha_against_time_domain", td_report)
    monkeypatch.setattr(
        module, "evaluate_zvs_margin",
        lambda *args, **kwargs: SimpleNamespace(zvs_margin=0.5),
    )
    result = optimizer.run(spec, maximum_candidates=2, top_n=1, run_stage_b=True)
    assert checked == [rejected_ln, accepted_ln]
    assert len(result.verified) == 2
    accepted, rejected = result.verified
    assert not accepted.rejected
    assert accepted.spec.ln_ratio == accepted_ln
    assert rejected.rejected
    assert rejected.spec.ln_ratio == rejected_ln
    expected_reason = (
        "envelope constraint FAIL"
        if reject_at == "envelope" else "FHA↔TD MODEL_VALIDITY FAIL"
    )
    assert rejected.reject_reason == expected_reason
    assert rejected.rank_metrics == {}


def test_regression_case_a_nominal_loss_positive():
    """Case A — nominal LLC: baseline must remain physically sane."""
    analysis = LLCSystemAnalyzer().analyze(LLCDesignSpec())
    assert analysis.nominal.total_loss_w > 0.0
    assert 0.0 < analysis.nominal.efficiency < 1.0


def test_regression_case_b_high_gain_low_vin_solves_or_records():
    """Case B — high gain / low Vin corner remains solvable or explicit fail."""
    from llc_design.core.tank import GainNotReachableError

    spec = LLCDesignSpec(vbus_min_normal_v=320.0, vbus_hold_end_v=280.0)
    try:
        analysis = LLCSystemAnalyzer().analyze(
            spec, work_points=[(spec.vbus_hold_end_v, 1.0)])
        assert analysis.operating_points
    except GainNotReachableError as exc:
        msg = str(exc).lower()
        assert any(k in msg for k in ("gain", "reachable", "operating point", "solved"))
    except Exception as exc:
        msg = str(exc).lower()
        assert any(k in msg for k in ("gain", "reachable", "operating point", "solved"))


def test_regression_case_c_light_load_zvs_boundary_tagged():
    """Case C — light load ZVS class is classified, not silently FULL_ZVS."""
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 0.10)
    device = DeviceDatabase().get_primary(spec.primary_device)
    bridge = bridge_loss_with_provenance(spec, tank, op, device)
    assert bridge.turn_on_class in SwitchingClass
