"""Acceptance tests for V9.3 engineering data / loss / ferrite / Type II-III paths."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from llc_design.models.system import LLCSystemAnalyzer
from llc_design.core.spec import LLCDesignSpec
from pfc_design.engineering import PFCDeviceDatabase, compare_ttpl_devices, analyze_ttpl_design, TTPLDesignSpec
from pfc_design.gui.pfc_loss_summary import PFCDeviceLossRollup
from pfc_design.magnetics import (
    FerriteInductorRequest,
    design_ferrite_pfc_inductor,
    UserCoreLibrary,
)
from pfc_design.magnetics.core_database import CoreDatabase
from pfc_design.magnetics.core_entry import CoreSpec
from pfc_design.magnetics.steinmetz import SteinmetzMaterial
from power_control_tools.controllers import design_controller, _type2_from_rc
from power_control_tools.models import ControllerKind
from power_control_tools.part_validation import (
    brand_display_names,
    load_brand_taxonomy,
    missing_ferrite_steinmetz_parameters,
    missing_llc_mosfet_loss_parameters,
    missing_pfc_mosfet_loss_parameters,
)


def test_brand_taxonomy_lists_domestic_placeholders_without_invented_parts():
    data = load_brand_taxonomy()
    names = brand_display_names()
    assert "铂科 / POCO Magnetic" in names
    assert "东睦科达" in names
    by_id = {b["id"]: b for b in data["brands"]}
    assert by_id["pocc"]["calculable_builtin_parts"] == []
    assert by_id["dongmu-keda"]["status"] == "brand-placeholder"


def test_missing_llc_and_pfc_device_parameters_prompt_fields():
    incomplete = type("D", (), {"part_number": "", "vds_max_v": 0.0})()
    missing = missing_llc_mosfet_loss_parameters(incomplete)
    assert any(item.name == "part_number" for item in missing)
    assert any(item.name == "rds_on_25_ohm" for item in missing)

    pfc_incomplete = type("D", (), {"manufacturer": "", "part_number": "X", "vds_max": 650.0})()
    pfc_missing = missing_pfc_mosfet_loss_parameters(pfc_incomplete)
    assert any(item.name == "manufacturer" for item in pfc_missing)
    assert any(item.name == "rds_on_25c" for item in pfc_missing)


def test_user_core_library_save_load_and_no_steinmetz_borrow(tmp_path: Path):
    lib = UserCoreLibrary(tmp_path / "pfc_cores.json")
    core = CoreSpec(
        manufacturer="铂科 / POCO Magnetic",
        part_number="USER_POCC_TEST_50",
        material="User Ferrite A",
        material_class="Ferrite",
        od_mm=50, id_mm=30, ht_mm=20,
        ae_cm2=1.5, le_cm=12.0, ve_cm3=18.0,
        al_nH_per_t2=120.0, ui=2000.0, bs_T=0.45,
        source_url="datasheet-rev-A",
        dc_bias_coeffs=[100.0, 0.0, 0.0, 0.0, 0.0],
    )
    lib.save_steinmetz(SteinmetzMaterial(name="User Ferrite A", k=0.3, alpha=1.25, beta=2.5))
    lib.save_core(core)

    db = CoreDatabase(user_path=tmp_path / "pfc_cores.json")
    got = db.get_by_part_number("USER_POCC_TEST_50")
    assert got is not None
    assert db.is_user("USER_POCC_TEST_50")
    assert db.get_steinmetz("User Ferrite A") is not None
    assert missing_ferrite_steinmetz_parameters("Unknown Brand X", None)


def test_ferrite_path_refuses_powder_dc_bias_and_sizes_gap(tmp_path: Path):
    db = CoreDatabase(include_user=False)
    ferrite = next(c for c in db.cores if c.material_class.casefold() == "ferrite")
    steinmetz = db.get_steinmetz(ferrite.material)
    assert steinmetz is not None
    result = design_ferrite_pfc_inductor(
        FerriteInductorRequest(
            topology="ttpl",
            input_rms_v=220.0,
            bus_voltage_v=400.0,
            output_power_w=3000.0,
            switching_frequency_hz=65e3,
            target_inductance_h=220e-6,
            efficiency=0.97,
            core=ferrite,
            steinmetz=steinmetz,
            gap_m=0.5e-3,
            n_cores=2,
        )
    )
    assert result.turns >= 1
    assert result.total_inductor_loss_w > 0.0
    assert any("powder dc_bias" in w for w in result.warnings)

    powder = next(c for c in db.cores if c.material_class.casefold() == "highflux")
    with pytest.raises(ValueError, match="ferrite path refused"):
        design_ferrite_pfc_inductor(
            FerriteInductorRequest(
                topology="ttpl",
                input_rms_v=220.0,
                bus_voltage_v=400.0,
                output_power_w=3000.0,
                switching_frequency_hz=65e3,
                target_inductance_h=220e-6,
                efficiency=0.97,
                core=powder,
                steinmetz=steinmetz,
                gap_m=0.5e-3,
            )
        )


def test_llc_loss_buckets_sum_to_total():
    analysis = LLCSystemAnalyzer().analyze(LLCDesignSpec())
    point = analysis.nominal
    bucket_sum = sum(point.breakdown().values())
    assert bucket_sum == pytest.approx(point.total_loss_w, rel=1e-9, abs=1e-9)


def test_pfc_device_loss_rollup_matches_subtotals():
    design = analyze_ttpl_design(TTPLDesignSpec())
    db = PFCDeviceDatabase(include_user=False)
    comparison = compare_ttpl_devices(design, db, workpoint="nominal")
    hf = comparison.hf_devices[0]
    slow = comparison.slow_devices[0]
    rollup = PFCDeviceLossRollup(
        workpoint=comparison.workpoint,
        vin_rms_v=comparison.vin_rms_v,
        hf=hf,
        slow=slow,
        inductor_self_loss_w=12.5,
    )
    ok, d_hf, d_slow = rollup.verify_sums()
    assert ok
    assert d_hf == pytest.approx(0.0, abs=1e-9)
    assert d_slow == pytest.approx(0.0, abs=1e-9)
    assert rollup.system_device_total_w() == pytest.approx(hf.total_w + slow.total_w)
    text = rollup.format_text()
    assert "Inductor-self" in text
    assert "NOT added" in text


def test_type2_type3_rc_impedance_matches_hs():
    r1, r2, c1, c2 = 10e3, 47e3, 10e-9, 0.47e-9
    tf2 = _type2_from_rc(r1, r2, c1, c2)
    wp0 = 1.0 / (r1 * (c1 + c2))
    wz = 1.0 / (r2 * c1)
    wp = (c1 + c2) / (r2 * c1 * c2)
    # Impedance-derived poles/zeros must match H(s) coefficients.
    num = np.asarray(tf2.numerator, dtype=float)
    den = np.asarray(tf2.denominator, dtype=float)
    assert den[0] == pytest.approx(1.0)
    assert den[-1] == pytest.approx(0.0, abs=1e-18)
    # G(s) = -wp0*wp/wz * (s+wz) / [s(s+wp)]
    gain = -wp0 * wp / wz
    assert num[0] == pytest.approx(gain, rel=1e-9)
    assert num[1] / num[0] == pytest.approx(wz, rel=1e-9)
    assert den[1] == pytest.approx(wp, rel=1e-9)

    r3, c3 = 10e3, 1e-9
    tf3 = design_controller(
        ControllerKind.TYPE_III,
        type_input_mode="rc",
        r1_ohm=r1, r2_ohm=r2, r3_ohm=r3,
        c1_f=c1, c2_f=c2, c3_f=c3,
    )
    wz2 = 1.0 / (c3 * (r1 + r3))
    wp2 = 1.0 / (r3 * c3)
    # Evaluate magnitude ratio vs impedance formula at a mid-band frequency.
    w = 2 * np.pi * 2e3
    s = 1j * w
    hs = np.polyval(tf3.numerator, s) / np.polyval(tf3.denominator, s)
    wp0 = 1.0 / (r1 * (c1 + c2))
    wz1 = 1.0 / (r2 * c1)
    wp1 = (c1 + c2) / (r2 * c1 * c2)
    expected = -wp0 * (1 + s / wz1) * (1 + s / wz2) / (s * (1 + s / wp1) * (1 + s / wp2))
    assert abs(hs - expected) / abs(expected) < 1e-9
