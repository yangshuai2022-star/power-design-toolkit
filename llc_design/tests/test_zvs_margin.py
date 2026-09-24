"""ZVS Level-1 / Level-2 charge-balance margin tests."""

from __future__ import annotations

import math

import pytest

from llc_design.core.operating_point import solve_operating_point
from llc_design.core.spec import LLCDesignSpec, MosfetSpec
from llc_design.core.tank import design_tank
from llc_design.core.zvs_margin import (
    evaluate_zvs_margin,
    level1_region,
    q_available_from_commutation,
    resolve_qoss_requirement,
)
from llc_design.models.devices import DeviceDatabase


def _tiny_qoss_device() -> MosfetSpec:
    base = DeviceDatabase().get_primary("REF_650V_SIC_45M")
    return MosfetSpec(
        **{
            **base.__dict__,
            "part_number": "TEST_HUGE_QOSS",
            "qoss_c": 50e-6,  # absurdly large → negative margin
            "coss_er_f": 1e-9,
        }
    )


def test_level1_inductive_vs_capacitive():
    assert level1_region(10.0) == "INDUCTIVE"
    assert level1_region(-10.0) == "CAPACITIVE"
    assert level1_region(0.0) == "BOUNDARY"


def test_level2_charge_balance_formula_and_outputs():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    device = DeviceDatabase().get_primary(spec.primary_device)
    result = evaluate_zvs_margin(spec, tank, op, device=device, level=2)

    q_req = 2.0 * spec.primary_parallel_devices * max(
        device.qoss_c, device.coss_er_f * op.vbus_v)
    q_av = op.commutation_current_a * spec.primary_deadtime_s
    assert result.q_required == pytest.approx(q_req, rel=1e-12)
    assert result.q_available == pytest.approx(q_av, rel=1e-12)
    assert result.zvs_margin == pytest.approx((q_av - q_req) / q_req, rel=1e-12)
    assert result.i_commutation == pytest.approx(op.commutation_current_a)
    assert result.dead_time_s == pytest.approx(spec.primary_deadtime_s)
    assert result.model_source == "DATASHEET_QOSS"
    assert result.zvs_pass is True
    payload = result.as_dict()
    assert payload["ZVS_PASS"] is True
    assert payload["MODEL_SOURCE"] == "DATASHEET_QOSS"
    assert "Q_AVAILABLE" in payload and "Q_REQUIRED" in payload


def test_negative_zvs_margin_with_huge_qoss():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    result = evaluate_zvs_margin(spec, tank, op, device=_tiny_qoss_device(), level=2)
    assert result.zvs_margin < 0.0
    assert result.zvs_pass is False
    assert result.model_source == "DATASHEET_QOSS"


def test_coss_approximation_marked_not_verified():
    q_req, source, warnings = resolve_qoss_requirement(
        vbus_v=400.0, parallel_devices=1, qoss_c=0.0, coss_f=200e-12)
    assert source == "COSS_APPROXIMATION"
    assert q_req == pytest.approx(2.0 * 200e-12 * 400.0)
    assert any("APPROXIMATION" in w for w in warnings)

    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    result = evaluate_zvs_margin(
        spec, tank, op, qoss_c=0.0, coss_f=200e-12, level=2)
    assert result.model_source == "COSS_APPROXIMATION"
    assert result.model_source != "DATASHEET_QOSS"


def test_unknown_without_qoss_or_coss():
    q_req, source, warnings = resolve_qoss_requirement(
        vbus_v=400.0, parallel_devices=1, qoss_c=None, coss_f=None)
    assert q_req == 0.0
    assert source == "UNKNOWN"
    assert warnings


def test_waveform_integral_q_available():
    # Constant 5 A over 200 ns → 1e-6 C
    samples = (5.0, 5.0, 5.0, 5.0, 5.0)
    dt = 50e-9
    q = q_available_from_commutation(
        5.0, 200e-9, current_waveform=samples, sample_period_s=dt)
    assert q == pytest.approx(5.0 * 200e-9, rel=1e-9)


def test_level1_does_not_pretend_charge_precision():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    device = DeviceDatabase().get_primary(spec.primary_device)
    result = evaluate_zvs_margin(spec, tank, op, device=device, level=1)
    assert result.level == 1
    assert result.level1_region == "INDUCTIVE"
    assert result.zvs_pass is True
    assert math.isnan(result.q_available)
    assert result.model_source == "UNKNOWN"
