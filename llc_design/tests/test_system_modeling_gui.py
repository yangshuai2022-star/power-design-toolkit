from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qapp(qt_widgets):
    return qt_widgets.QApplication.instance() or qt_widgets.QApplication([])


def test_launcher_exposes_guided_system_design_as_first_class_entry():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from llc_design.gui.launcher import WorkspaceSelectionDialog

    app = _qapp(qt_widgets)
    dialog = WorkspaceSelectionDialog()
    button = dialog.findChild(qt_widgets.QPushButton, "guided_system_design_button")
    assert button is not None
    card = dialog.findChild(qt_widgets.QFrame, "guided_system_design_card")
    assert card is not None
    assert "系统建模与设计" in card.findChildren(qt_widgets.QLabel)[1].text() or any(
        "系统建模与设计" in label.text() for label in card.findChildren(qt_widgets.QLabel)
    )
    dialog.close()
    app.processEvents()


def test_guided_wizard_supports_llc_and_ttpl_and_keeps_future_topologies_disabled():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from llc_design.gui.system_modeling import SystemModelingDesignDialog
    from power_control_tools.system_definition import SystemTopology

    app = _qapp(qt_widgets)
    dialog = SystemModelingDesignDialog()
    assert dialog.vienna_radio.isEnabled() is False
    assert dialog.dc_radio.isEnabled() is False
    assert dialog.generic_radio.isEnabled() is False
    assert dialog.pages.count() == 8

    llc = dialog.build_definition()
    llc.validate()
    assert llc.topology == SystemTopology.LLC
    assert len(llc.sensors) == 1

    dialog.select_topology(SystemTopology.TTPL_PFC)
    app.processEvents()
    ttpl = dialog.build_definition()
    ttpl.validate()
    assert ttpl.topology == SystemTopology.TTPL_PFC
    assert len(ttpl.sensors) == 3
    assert ttpl.ttpl_stage is not None

    dialog.pages.setCurrentIndex(dialog.PAGE_REVIEW)
    app.processEvents()
    assert dialog.finish_button.isEnabled()
    dialog.close()
    app.processEvents()


def test_guided_llc_definition_populates_existing_expert_workspace():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from llc_design.core.spec import LLCDesignSpec
    from llc_design.gui.main_window import LLCMainWindow
    from llc_design.gui.system_modeling import SystemModelingDesignDialog, apply_definition_to_llc_window

    app = _qapp(qt_widgets)
    wizard = SystemModelingDesignDialog()
    wizard.llc_vnom.setValue(390.0)
    wizard.llc_vout.setValue(48.0)
    wizard.llc_sample.setValue(80.0)
    definition = wizard.build_definition()

    window = LLCMainWindow(LLCDesignSpec())
    spec = apply_definition_to_llc_window(window, definition)
    assert spec.vbus_nom_v == pytest.approx(390.0)
    assert spec.vout_v == pytest.approx(48.0)
    assert window.spec.vbus_nom_v == pytest.approx(390.0)
    assert window.digital_loop_view.sample_us.value() == pytest.approx(12.5)
    assert window.digital_loop_view.adc_clock_mhz.value() == pytest.approx(60.0)
    assert window.guided_system_definition is definition
    assert "Guided System Definition" in window.statusBar().currentMessage()

    wizard.close(); window.close(); app.processEvents()


def test_guided_ttpl_definition_populates_workspace_and_preserves_adc_contract():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from llc_design.gui.system_modeling import SystemModelingDesignDialog, apply_definition_to_ttpl_window
    from pfc_design.gui.main_window import PFCMainWindow

    app = _qapp(qt_widgets)
    wizard = SystemModelingDesignDialog()
    wizard.select_topology(
        __import__("power_control_tools.system_definition", fromlist=["SystemTopology"]).SystemTopology.TTPL_PFC
    )
    wizard.ttpl_l.setValue(350.0)
    wizard.ttpl_cbus.setValue(470.0)
    wizard.adc_vref.setValue(3.0)
    wizard.adc_bits.setValue(14)
    wizard.compute_delay.setValue(1.2)
    wizard.pwm_delay.setValue(7.5)
    definition = wizard.build_definition()

    window = PFCMainWindow()
    config = apply_definition_to_ttpl_window(window, definition)
    control = window.control_lab_view.control_lab
    assert control.inductance.value() == pytest.approx(350.0)
    assert control.cbus.value() == pytest.approx(470.0)
    assert config.current_sense.adc_vref_v == pytest.approx(3.0)
    assert config.current_sense.adc_bits == 14
    assert config.firmware.current_computation_delay_s == pytest.approx(1.2e-6)
    assert config.firmware.current_pwm_update_delay_s == pytest.approx(7.5e-6)
    assert window.guided_system_definition is definition

    wizard.close(); window.close(); app.processEvents()


def test_guided_review_blocks_analyze_when_fc_exceeds_nyquist():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from llc_design.gui.system_modeling import SystemModelingDesignDialog

    app = _qapp(qt_widgets)
    dialog = SystemModelingDesignDialog()
    dialog.llc_sample.setValue(10.0)  # 10 kHz → Nyquist 5 kHz
    dialog.target_fc.setValue(8000.0)
    dialog.pages.setCurrentIndex(dialog.PAGE_REVIEW)
    app.processEvents()
    assert dialog.finish_button.isEnabled() is False
    assert "Nyquist" in dialog.review_checks.item(dialog.review_checks.count() - 1).text()
    dialog.close()
    app.processEvents()
