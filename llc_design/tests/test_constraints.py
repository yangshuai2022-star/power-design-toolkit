"""Constraint engine PASS/WARN/FAIL/UNKNOWN boundary tests."""

from __future__ import annotations

import pytest

from llc_design.core.engineering import (
    ConstraintStatus,
    evaluate_constraints_for_point,
    merge_status,
)
from llc_design.core.operating_point import solve_operating_point
from llc_design.core.spec import LLCDesignSpec
from llc_design.core.tank import design_tank
from llc_design.core.zvs_margin import ZVSMarginResult, evaluate_zvs_margin
from llc_design.models.devices import DeviceDatabase


def test_merge_status_ranks_fail_over_warn_over_unknown():
    assert merge_status(ConstraintStatus.PASS, ConstraintStatus.WARN) == ConstraintStatus.WARN
    assert merge_status(ConstraintStatus.WARN, ConstraintStatus.FAIL) == ConstraintStatus.FAIL
    assert merge_status(ConstraintStatus.PASS, ConstraintStatus.UNKNOWN) == ConstraintStatus.UNKNOWN


def test_unsolved_point_is_fail_with_unknown_zvs():
    spec = LLCDesignSpec()
    constraints = evaluate_constraints_for_point(
        spec, None, None, solve_error="required gain unreachable")
    by_name = {c.name: c for c in constraints}
    assert by_name["frequency_solve"].status == ConstraintStatus.FAIL
    assert by_name["zvs"].status == ConstraintStatus.UNKNOWN


def test_nominal_full_load_constraints_pass_or_warn():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    device = DeviceDatabase().get_primary(spec.primary_device)
    zvs = evaluate_zvs_margin(spec, tank, op, device=device, level=2)
    constraints = evaluate_constraints_for_point(spec, op, zvs)
    statuses = {c.status for c in constraints}
    assert ConstraintStatus.FAIL not in statuses
    assert any(c.name == "zvs_margin" for c in constraints)
    assert any(c.name == "frequency_window" and c.status == ConstraintStatus.PASS for c in constraints)


def test_exact_preferred_zvs_surplus_boundary():
    """At exact preferred surplus threshold the constraint is PASS (not WARN)."""

    spec = LLCDesignSpec(primary_zvs_margin_required=1.20)
    preferred_surplus = spec.primary_zvs_margin_required - 1.0
    zvs = ZVSMarginResult(
        zvs_pass=True,
        zvs_margin=preferred_surplus,
        q_available=1.2e-6,
        q_required=1.0e-6,
        i_commutation=6.0,
        dead_time_s=200e-9,
        model_source="DATASHEET_QOSS",
        level=2,
        level1_region="INDUCTIVE",
        input_phase_deg=20.0,
        charge_ratio=1.20,
    )
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    constraints = evaluate_constraints_for_point(spec, op, zvs)
    zc = next(c for c in constraints if c.name == "zvs_margin")
    assert zc.status == ConstraintStatus.PASS
    assert zc.limit == pytest.approx(preferred_surplus)


def test_negative_zvs_margin_is_fail():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
    zvs = ZVSMarginResult(
        zvs_pass=False,
        zvs_margin=-0.25,
        q_available=0.75e-6,
        q_required=1.0e-6,
        i_commutation=1.0,
        dead_time_s=200e-9,
        model_source="DATASHEET_QOSS",
        level=2,
        level1_region="INDUCTIVE",
        input_phase_deg=10.0,
        charge_ratio=0.75,
    )
    constraints = evaluate_constraints_for_point(spec, op, zvs)
    zc = next(c for c in constraints if c.name == "zvs_margin")
    assert zc.status == ConstraintStatus.FAIL


def test_capacitive_region_fails_inductive_constraint():
    spec = LLCDesignSpec()
    tank = design_tank(spec)
    op = solve_operating_point(spec, tank, spec.vbus_nom_v, 0.25)
    # Force capacitive phase via replace-like reconstruction is hard on frozen OP;
    # use a synthetic constraint call with a shallow copy through object.__new__.
    capacitive = type(op)(**{**op.__dict__, "input_phase_deg": -5.0, "load_fraction": 0.25})
    zvs = ZVSMarginResult(
        zvs_pass=False,
        zvs_margin=-1.0,
        q_available=0.1e-6,
        q_required=1.0e-6,
        i_commutation=0.5,
        dead_time_s=200e-9,
        model_source="DATASHEET_QOSS",
        level=2,
        level1_region="CAPACITIVE",
        input_phase_deg=-5.0,
        charge_ratio=0.1,
    )
    constraints = evaluate_constraints_for_point(spec, capacitive, zvs)
    assert any(
        c.name == "inductive_region" and c.status == ConstraintStatus.FAIL
        for c in constraints
    )
    assert any(
        c.name == "zvs_margin" and c.status == ConstraintStatus.FAIL
        for c in constraints
    )
