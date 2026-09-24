"""Operating-envelope enumeration and evaluation tests."""

from __future__ import annotations

import math

import pytest

from llc_design.core.engineering import (
    ConstraintStatus,
    OperatingEnvelope,
    enumerate_envelope_corners,
    evaluate_operating_envelope,
)
from llc_design.core.spec import LLCDesignSpec
from llc_design.models.devices import DeviceDatabase
from llc_design.models.system import LLCSystemAnalyzer


def test_envelope_from_spec_covers_vin_pout_and_tolerances():
    spec = LLCDesignSpec()
    env = OperatingEnvelope.from_spec(
        spec,
        lr_tolerance=0.05,
        lm_tolerance=0.05,
        cr_tolerance=0.05,
        turns_ratio_tolerance=0.02,
        load_fractions=(0.10, 0.25, 1.00),
    )
    assert env.vin_min_v == pytest.approx(spec.vbus_hold_end_v)
    assert env.vin_max_v == pytest.approx(spec.vbus_max_v)
    assert env.pout_min_w == pytest.approx(0.10 * spec.pout_w)
    assert env.pout_max_w == pytest.approx(spec.pout_w)

    corners = enumerate_envelope_corners(spec, env)
    assert any(c.vbus_v == pytest.approx(spec.vbus_hold_end_v) for c in corners)
    assert any(c.vbus_v == pytest.approx(spec.vbus_max_v) for c in corners)
    assert any(abs(c.load_fraction - 0.10) < 1e-12 for c in corners)
    assert any(abs(c.load_fraction - 1.0) < 1e-12 for c in corners)
    assert any("tol_gain_hard" in c.corner_id for c in corners)
    assert any("tol_zvs_hard" in c.corner_id for c in corners)
    assert any(abs(c.lr_scale - 1.05) < 1e-12 for c in corners)
    assert len({c.corner_id for c in corners}) == len(corners)


def test_envelope_vin_pout_fs_corners_solve_and_identify_worst_zvs():
    spec = LLCDesignSpec()
    device = DeviceDatabase().get_primary(spec.primary_device)
    env = OperatingEnvelope.from_spec(
        spec,
        lr_tolerance=0.0,
        lm_tolerance=0.0,
        cr_tolerance=0.0,
        turns_ratio_tolerance=0.0,
        load_fractions=(0.25, 1.00),
    )
    result = evaluate_operating_envelope(
        spec, env,
        device_qoss_c=device.qoss_c,
        device_coss_f=device.coss_er_f,
    )
    assert result.points
    solved = [p for p in result.points if p.operating_point is not None]
    assert len(solved) >= 4
    for point in solved:
        assert point.operating_point.switching_frequency_hz > 0.0
        assert point.zvs is not None
        assert point.overall_status in {
            ConstraintStatus.PASS, ConstraintStatus.WARN,
            ConstraintStatus.FAIL, ConstraintStatus.UNKNOWN,
        }

    worst = result.worst("zvs_margin")
    assert worst is not None
    assert worst.corner_id
    assert worst.sense == "minimum"
    assert "corner" in worst.reason or "ZVS" in worst.reason


def test_envelope_light_and_zero_load():
    spec = LLCDesignSpec()
    device = DeviceDatabase().get_primary(spec.primary_device)
    env = OperatingEnvelope(
        vin_min_v=spec.vbus_nom_v,
        vin_max_v=spec.vbus_nom_v,
        vo_min_v=spec.vout_v,
        vo_max_v=spec.vout_v,
        pout_min_w=1.0,
        pout_max_w=spec.pout_w,
        load_fractions=(0.10, 1.0),
        include_zero_load=True,
        lr_tolerance=0.0,
        lm_tolerance=0.0,
        cr_tolerance=0.0,
        turns_ratio_tolerance=0.0,
    )
    result = evaluate_operating_envelope(
        spec, env,
        device_qoss_c=device.qoss_c,
        device_coss_f=device.coss_er_f,
    )
    zero = [p for p in result.points if "zero_load" in p.corner.tags]
    assert zero
    assert zero[0].overall_status == ConstraintStatus.UNKNOWN
    light = [p for p in result.points if abs(p.corner.load_fraction - 0.10) < 1e-12]
    assert light
    assert light[0].operating_point is not None


def test_tolerance_corners_change_tank():
    spec = LLCDesignSpec()
    device = DeviceDatabase().get_primary(spec.primary_device)
    env = OperatingEnvelope.from_spec(
        spec, lr_tolerance=0.10, lm_tolerance=0.0, cr_tolerance=0.0,
        turns_ratio_tolerance=0.0, load_fractions=(1.0,),
    )
    result = evaluate_operating_envelope(
        spec, env,
        device_qoss_c=device.qoss_c,
        device_coss_f=device.coss_er_f,
    )
    hi = next(p for p in result.points if "tol_lr_hi" in p.corner_id)
    lo = next(p for p in result.points if "tol_lr_lo" in p.corner_id)
    assert hi.tank is not None and lo.tank is not None
    assert hi.tank.lr_h == pytest.approx(lo.tank.lr_h / 0.9 * 1.1, rel=1e-9)


def test_system_analyzer_evaluate_envelope_wires_device_qoss():
    spec = LLCDesignSpec()
    analysis = LLCSystemAnalyzer().evaluate_envelope(
        spec,
        OperatingEnvelope.from_spec(
            spec, lr_tolerance=0.0, lm_tolerance=0.0, cr_tolerance=0.0,
            turns_ratio_tolerance=0.0, load_fractions=(1.0,),
        ),
    )
    assert analysis.points
    assert analysis.points[0].zvs is not None
    assert analysis.points[0].zvs.model_source == "DATASHEET_QOSS"
