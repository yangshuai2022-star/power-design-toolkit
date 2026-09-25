"""V9.3 guided system modeling and design workflow.

Product entry: define the real closed-loop system step by step, then hand the
canonical ``ControlSystemDefinition`` to the existing LLC / TTPL kernels.

    Topology → Power Stage → Sensing → ADC → Modulator → Timing → Controller → Review
"""
from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from llc_design.core.spec import LLCDesignSpec, PrimaryTopology
from llc_design.core.tank import design_tank, equivalent_ac_load_ohm, gain, target_gain
from llc_design.gui import theme
from llc_design.gui.widgets.sense_schematic import AnalogSenseSchematic
from pfc_design.control import (
    ADCTimingConfig,
    DigitalFilterConfig,
    ExternalSenseConfig,
    PFCControlLabConfig,
    PFCFirmwareAlgorithmConfig,
)
from pfc_design.engineering.ttpl_design import TTPLDesignSpec, analyze_ttpl_design
from power_control_tools.system_definition import (
    ADCDefinition,
    ControlArchitecture,
    ControllerIntent,
    ControlSystemDefinition,
    LLCStageDefinition,
    ModulatorDefinition,
    PlantSource,
    SensorDefinition,
    SystemTopology,
    TTPLStageDefinition,
    TimingDefinition,
)

_STEP_NAMES = (
    "Topology",
    "Power Stage",
    "Sensing",
    "ADC",
    "Modulator",
    "Timing",
    "Controller",
    "Review",
)

_LLC_ARCH = (
    "Vref\n"
    "  ↓\n"
    " Σ → Controller → PCMD → FM LUT → TBPRD/PWM → LLC Plant → Vout\n"
    " ↑                                                    │\n"
    " └── ADC ← Analog Sense ←─────────────────────────────┘"
)

_TTPL_ARCH = (
    "                 Voltage Loop\n"
    "Vbus_ref → Σ → Cv(z) → Gcmd\n"
    "                     ↓\n"
    "Vac → VFF / AMC → Iref\n"
    "                     ↓\n"
    "                 Current Loop\n"
    "IL → Sense → Σ → Ci(z) → Duty → PWM → TTPL Plant"
)


def _mono() -> QFont:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def _sense_derived(sensor: SensorDefinition, adc: ADCDefinition, target_fc_hz: float | None) -> str:
    gain = sensor.front_end_gain_v_per_unit * sensor.amplifier_gain
    poles: list[float] = []
    if sensor.amplifier_bandwidth_hz > 0.0:
        poles.append(sensor.amplifier_bandwidth_hz)
    if sensor.adc_series_resistance_ohm > 0.0 and sensor.adc_shunt_capacitance_f > 0.0:
        poles.append(1.0 / (2.0 * math.pi * sensor.adc_series_resistance_ohm * sensor.adc_shunt_capacitance_f))
    if sensor.source_resistance_ohm > 0.0 and sensor.source_capacitance_f > 0.0:
        poles.append(1.0 / (2.0 * math.pi * sensor.source_resistance_ohm * sensor.source_capacitance_f))
    bw = min(poles) if poles else float("inf")
    phase = 0.0
    if target_fc_hz and target_fc_hz > 0.0:
        for pole in poles:
            phase -= math.degrees(math.atan(target_fc_hz / pole))
    lsb = adc.vref_v / (2 ** adc.bits)
    eng_fs = adc.vref_v / max(gain, 1e-30)
    eng_lsb = lsb / max(gain, 1e-30)
    bw_text = "ideal" if not math.isfinite(bw) else f"{bw/1e3:.5g} kHz"
    return (
        f"DC gain             : {gain:.7g} V/unit\n"
        f"-3 dB bandwidth     : {bw_text}\n"
        f"phase @ target Fc   : {phase:.3f} deg\n"
        f"ADC full scale      : {adc.vref_v:.5g} V\n"
        f"engineering FS      : {eng_fs:.6g}\n"
        f"engineering LSB     : {eng_lsb:.6g}"
    )


class _TopologyCard(QFrame):
    def __init__(self, title: str, subtitle: str, *, enabled: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        palette = theme.active_theme()
        self.setStyleSheet(
            f"QFrame {{background:{palette.surface}; border:2px solid {palette.border_card};"
            f"border-radius:12px;}}"
            f"QFrame[selected='true'] {{border-color:{palette.accent}; background:{palette.checked_bg};}}"
            f"QFrame[enabled='false'] {{background:{palette.surface_alt}; color:{palette.text_muted};}}"
        )
        self.setProperty("selected", False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-size:15px;font-weight:700;border:none;")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"color:{palette.text_muted};border:none;")
        self.select = QPushButton("Select" if enabled else "Coming later")
        self.select.setEnabled(enabled)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addStretch(1)
        layout.addWidget(self.select, alignment=Qt.AlignmentFlag.AlignRight)
        self.setMinimumHeight(130)
        self.setEnabled(enabled)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class SystemModelingDesignDialog(QDialog):
    """Guided V9.3 model-definition wizard for LLC and TTPL PFC."""

    PAGE_TOPOLOGY = 0
    PAGE_STAGE = 1
    PAGE_SENSING = 2
    PAGE_ADC = 3
    PAGE_MODULATOR = 4
    PAGE_TIMING = 5
    PAGE_CONTROLLER = 6
    PAGE_REVIEW = 7

    def __init__(self, parent=None, initial_definition: ControlSystemDefinition | None = None) -> None:
        super().__init__(parent)
        self.definition: ControlSystemDefinition | None = None
        self._selected_topology = SystemTopology.LLC
        self.setWindowTitle("系统建模与设计 / Guided System Design — V9.3")
        self.resize(1280, 860)
        self.setMinimumSize(1080, 720)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setStyleSheet(theme.workspace_stylesheet(theme.active_theme()))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title = QLabel("System Modeling & Design")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:700;padding:4px;")
        root.addWidget(title)
        subtitle = QLabel(
            "Power Stage → Plant → Sensor → Analog Filter → ADC → Sampling → "
            "Controller → PWM/FM → Delay → System Review → Existing analysis engines"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#667085;padding-bottom:6px;")
        root.addWidget(subtitle)

        body = QHBoxLayout()
        self.progress = QVBoxLayout()
        self.progress_labels: list[QLabel] = []
        for index, name in enumerate(_STEP_NAMES, start=1):
            label = QLabel(f"○  {index}  {name}")
            label.setMinimumWidth(168)
            label.setStyleSheet("padding:9px 10px;border-radius:6px;color:#667085;")
            self.progress.addWidget(label)
            self.progress_labels.append(label)
        self.progress.addStretch(1)
        body.addLayout(self.progress)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._topology_page())
        self.pages.addWidget(self._power_stage_page())
        self.pages.addWidget(self._sensing_page())
        self.pages.addWidget(self._adc_page())
        self.pages.addWidget(self._modulator_page())
        self.pages.addWidget(self._timing_page())
        self.pages.addWidget(self._controller_page())
        self.pages.addWidget(self._review_page())
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.finish_button = QPushButton("Analyze Complete System")
        self.finish_button.setEnabled(False)
        footer.addWidget(self.cancel_button)
        footer.addStretch(1)
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)
        footer.addWidget(self.finish_button)
        root.addLayout(footer)

        self.cancel_button.clicked.connect(self.reject)
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        self.finish_button.clicked.connect(self._finish)
        self.pages.currentChanged.connect(self._page_changed)
        self._hook_live_updates()
        if initial_definition is not None:
            self._load_definition(initial_definition)
        self._page_changed(0)
        self._refresh_live_summaries()

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _double(lo: float, hi: float, decimals: int, value: float, suffix: str = "") -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(lo, hi)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSuffix(suffix)
        widget.setKeyboardTracking(False)
        return widget

    @staticmethod
    def _spin(lo: int, hi: int, value: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(lo, hi)
        widget.setValue(value)
        widget.setKeyboardTracking(False)
        return widget

    @staticmethod
    def _summary_box(title: str) -> tuple[QGroupBox, QPlainTextEdit]:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setFont(_mono())
        layout.addWidget(text)
        return box, text

    @staticmethod
    def _advanced_box(title: str = "Advanced") -> tuple[QGroupBox, QFormLayout]:
        box = QGroupBox(title)
        box.setCheckable(True)
        box.setChecked(False)
        form = QFormLayout(box)
        return box, form

    def _is_llc(self) -> bool:
        return self._selected_topology == SystemTopology.LLC

    def select_topology(self, topology: SystemTopology) -> None:
        if topology not in {SystemTopology.LLC, SystemTopology.TTPL_PFC}:
            raise ValueError(f"unsupported guided topology: {topology}")
        self._selected_topology = topology
        self.llc_card.set_selected(topology == SystemTopology.LLC)
        self.ttpl_card.set_selected(topology == SystemTopology.TTPL_PFC)
        # Compatibility shims for existing tests.
        self.llc_radio.setChecked(topology == SystemTopology.LLC)
        self.ttpl_radio.setChecked(topology == SystemTopology.TTPL_PFC)
        self._sync_topology_pages()
        self._refresh_architecture()
        self._refresh_live_summaries()

    # ---- pages -----------------------------------------------------------

    def _topology_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        left = QVBoxLayout()
        intro = QLabel(
            "选择真实闭环系统。V9.3 正式支持 LLC FM 数字电压环与单相 Totem-Pole 双环；"
            "其它拓扑仅作路线图占位，不伪装成已可用。"
        )
        intro.setWordWrap(True)
        left.addWidget(intro)

        cards = QHBoxLayout()
        self.llc_card = _TopologyCard("LLC Resonant Converter", "FM Digital Voltage Loop")
        self.ttpl_card = _TopologyCard("Totem-Pole PFC", "Current Inner + Voltage Outer Loop")
        self.llc_card.select.clicked.connect(lambda: self.select_topology(SystemTopology.LLC))
        self.ttpl_card.select.clicked.connect(lambda: self.select_topology(SystemTopology.TTPL_PFC))
        cards.addWidget(self.llc_card)
        cards.addWidget(self.ttpl_card)
        left.addLayout(cards)

        future = QGroupBox("Coming in later V9.3 / future release")
        future_layout = QVBoxLayout(future)
        self.vienna_radio = QRadioButton("Vienna PFC")
        self.dc_radio = QRadioButton("Buck / Boost / Buck-Boost / Flyback")
        self.generic_radio = QRadioButton("Generic Plant")
        for button in (self.vienna_radio, self.dc_radio, self.generic_radio):
            button.setEnabled(False)
            future_layout.addWidget(button)
        left.addWidget(future)

        # Hidden radios keep older tests/API working.
        self.topology_group = QButtonGroup(self)
        self.llc_radio = QRadioButton("LLC")
        self.ttpl_radio = QRadioButton("TTPL")
        self.llc_radio.hide()
        self.ttpl_radio.hide()
        self.topology_group.addButton(self.llc_radio)
        self.topology_group.addButton(self.ttpl_radio)
        self.llc_radio.setChecked(True)
        left.addWidget(self.llc_radio)
        left.addWidget(self.ttpl_radio)

        plant = QGroupBox("Plant Source")
        plant_form = QFormLayout(plant)
        self.plant_source = QComboBox()
        self.plant_source.addItem("Analytical / topology model", PlantSource.ANALYTICAL)
        for label, value in (
            ("Imported FRA (reserved)", PlantSource.IMPORTED_FRA),
            ("Identified plant (reserved)", PlantSource.IDENTIFIED),
            ("Custom G(s) (reserved)", PlantSource.CUSTOM_GS),
            ("Custom G(z) (reserved)", PlantSource.CUSTOM_GZ),
        ):
            self.plant_source.addItem(label, value)
        for i in range(1, self.plant_source.count()):
            item = self.plant_source.model().item(i)
            if item is not None:
                item.setEnabled(False)
        plant_form.addRow("Source", self.plant_source)
        left.addWidget(plant)
        left.addStretch(1)
        root.addLayout(left, 1)

        arch_box, self.architecture_view = self._summary_box("Control Architecture")
        self.architecture_view.setMinimumWidth(360)
        root.addWidget(arch_box, 1)
        self.select_topology(SystemTopology.LLC)
        return page

    def _power_stage_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        self.stage_stack = QStackedWidget()

        llc = QWidget()
        llc_layout = QVBoxLayout(llc)
        basic = QGroupBox("Electrical Spec / Resonant Tank")
        form = QFormLayout(basic)
        self.llc_vmin = self._double(50, 1000, 2, 360, " V")
        self.llc_vnom = self._double(50, 1000, 2, 400, " V")
        self.llc_vmax = self._double(50, 1000, 2, 420, " V")
        self.llc_vout = self._double(1, 1000, 2, 53, " V")
        self.llc_pout = self._double(1, 200000, 1, 3000, " W")
        self.llc_fr = self._double(1, 1000, 2, 100, " kHz")
        self.llc_fmin = self._double(1, 1000, 2, 60, " kHz")
        self.llc_fmax = self._double(1, 1000, 2, 180, " kHz")
        self.llc_ln = self._double(1.001, 100, 4, 5.0)
        self.llc_q = self._double(0.001, 10, 4, 0.35)
        self.llc_np = self._spin(1, 1000, 30)
        self.llc_ns = self._spin(1, 1000, 4)
        for label, widget in (
            ("Vin min", self.llc_vmin), ("Vin nominal", self.llc_vnom), ("Vin max", self.llc_vmax),
            ("Vout", self.llc_vout), ("Pout", self.llc_pout),
            ("Fr", self.llc_fr), ("Fmin", self.llc_fmin), ("Fmax", self.llc_fmax),
            ("Ln", self.llc_ln), ("Q", self.llc_q), ("Np", self.llc_np), ("Ns", self.llc_ns),
        ):
            form.addRow(label, widget)
        llc_layout.addWidget(basic)
        llc_layout.addStretch(1)
        self.stage_stack.addWidget(llc)

        ttpl = QWidget()
        ttpl_layout = QVBoxLayout(ttpl)
        ac = QGroupBox("AC Input")
        form = QFormLayout(ac)
        self.ttpl_vmin = self._double(20, 400, 2, 176, " Vrms")
        self.ttpl_vnom = self._double(20, 400, 2, 230, " Vrms")
        self.ttpl_vmax = self._double(20, 400, 2, 264, " Vrms")
        self.ttpl_line = self._double(40, 70, 2, 50, " Hz")
        for label, widget in (
            ("Vin min", self.ttpl_vmin), ("Vin nom", self.ttpl_vnom),
            ("Vin max", self.ttpl_vmax), ("Fline", self.ttpl_line),
        ):
            form.addRow(label, widget)
        ttpl_layout.addWidget(ac)
        dc = QGroupBox("DC Output / Power Stage")
        form = QFormLayout(dc)
        self.ttpl_vbus = self._double(100, 1000, 2, 400, " V")
        self.ttpl_pout = self._double(10, 200000, 1, 3300, " W")
        self.ttpl_eff = self._double(0.7, 1.0, 4, 0.97)
        self.ttpl_fsw = self._double(5, 500, 2, 50, " kHz")
        self.ttpl_l = self._double(1, 10000, 2, 220, " µH")
        self.ttpl_dcr = self._double(0, 5000, 3, 55, " mΩ")
        self.ttpl_cbus = self._double(1, 100000, 1, 1320, " µF")
        self.ttpl_cesr = self._double(0, 1000, 3, 35, " mΩ")
        for label, widget in (
            ("Vbus", self.ttpl_vbus), ("Pout", self.ttpl_pout), ("Efficiency", self.ttpl_eff),
            ("Fsw", self.ttpl_fsw), ("Lboost", self.ttpl_l), ("DCR", self.ttpl_dcr),
            ("Cbus", self.ttpl_cbus), ("ESR", self.ttpl_cesr),
        ):
            form.addRow(label, widget)
        ttpl_layout.addWidget(dc)
        ttpl_layout.addStretch(1)
        self.stage_stack.addWidget(ttpl)
        root.addWidget(self.stage_stack, 1)
        stage_box, self.stage_summary = self._summary_box("Live engineering summary")
        root.addWidget(stage_box, 1)
        return page

    def _sensing_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        left = QVBoxLayout()
        self.sense_stack = QStackedWidget()

        llc = QWidget()
        form = QFormLayout(llc)
        self.llc_rup = self._double(0.001, 1e6, 3, 117.0, " kΩ")
        self.llc_rlow = self._double(0.001, 1e6, 3, 1.6, " kΩ")
        self.llc_cdiv = self._double(0, 1e6, 4, 1.0, " nF")
        self.llc_amp_gain = self._double(0.001, 1000, 5, 1.0)
        self.llc_amp_bw = self._double(0, 1e6, 2, 0.0, " kHz")
        self.llc_adc_r = self._double(0, 1e7, 2, 220, " Ω")
        self.llc_adc_c = self._double(0, 1e6, 4, 2.0, " nF")
        self.llc_sample = self._double(1, 1000, 3, 50, " kHz")
        for label, widget in (
            ("Divider Rup", self.llc_rup), ("Divider Rlow", self.llc_rlow),
            ("Rlow shunt C", self.llc_cdiv), ("OpAmp gain", self.llc_amp_gain),
            ("OpAmp BW (0=ideal)", self.llc_amp_bw), ("ADC series R", self.llc_adc_r),
            ("ADC shunt C", self.llc_adc_c), ("Sample rate", self.llc_sample),
        ):
            form.addRow(label, widget)
        adv, adv_form = self._advanced_box()
        adv_form.addRow(QLabel("Divider parasitics and OpAmp BW are already exposed above."))
        llc_page = QWidget()
        llc_root = QVBoxLayout(llc_page)
        llc_root.addWidget(QLabel("Signal chain: Vout → Divider → OpAmp → RC → ADC"))
        llc_root.addWidget(llc)
        llc_root.addWidget(adv)
        llc_root.addStretch(1)
        self.sense_stack.addWidget(llc_page)

        ttpl = QWidget()
        ttpl_layout = QVBoxLayout(ttpl)
        ttpl_layout.addWidget(QLabel("Select a sense path, then edit its front-end parameters."))
        self.sense_path_list = QListWidget()
        for name in ("IL Sense", "VAC Sense", "VBUS Sense"):
            self.sense_path_list.addItem(name)
        self.sense_path_list.setCurrentRow(0)
        self.sense_path_list.currentRowChanged.connect(lambda *_: self._refresh_live_summaries())
        ttpl_layout.addWidget(self.sense_path_list)
        self.current_sense = self._ttpl_sensor_fields(0.03, 2000, 0, 0, 220, 2, 50)
        self.vac_sense = self._ttpl_sensor_fields(1 / 150, 1000, 2000, 1, 220, 2, 50)
        self.vbus_sense = self._ttpl_sensor_fields(
            1600 / (117000 + 1600), 1000, 117000 * 1600 / (117000 + 1600), 1, 220, 2, 10
        )
        self.ttpl_sense_stack = QStackedWidget()
        for fields, title in (
            (self.current_sense, "IL Sense"),
            (self.vac_sense, "VAC Sense"),
            (self.vbus_sense, "VBUS Sense"),
        ):
            box = QGroupBox(title)
            form = QFormLayout(box)
            for label, key in (
                ("Front-end gain", "gain"), ("Amplifier BW", "bw"),
                ("Source R", "source_r"), ("Source C", "source_c"),
                ("ADC R", "out_r"), ("ADC C", "out_c"),
                ("Sample rate", "sample"), ("Digital LPF alpha", "alpha"),
            ):
                form.addRow(label, fields[key])
            self.ttpl_sense_stack.addWidget(box)
        self.sense_path_list.currentRowChanged.connect(self.ttpl_sense_stack.setCurrentIndex)
        ttpl_layout.addWidget(self.ttpl_sense_stack, 1)
        self.sense_stack.addWidget(ttpl)
        left.addWidget(self.sense_stack, 1)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        self.sense_schematic = AnalogSenseSchematic("Analog sensing chain")
        right.addWidget(self.sense_schematic)
        sense_box, self.sense_summary = self._summary_box("Sense derived values")
        right.addWidget(sense_box, 1)
        root.addLayout(right, 1)
        return page

    def _ttpl_sensor_fields(
        self, gain: float, bw_khz: float, source_r: float, source_c_nf: float,
        out_r: float, out_c_nf: float, sample_khz: float,
    ) -> dict[str, QDoubleSpinBox]:
        return {
            "gain": self._double(1e-9, 1000, 9, gain, " V/unit"),
            "bw": self._double(0.1, 100000, 2, bw_khz, " kHz"),
            "source_r": self._double(0, 1e7, 3, source_r, " Ω"),
            "source_c": self._double(0, 1e6, 4, source_c_nf, " nF"),
            "out_r": self._double(0, 1e7, 3, out_r, " Ω"),
            "out_c": self._double(0, 1e6, 4, out_c_nf, " nF"),
            "sample": self._double(0.1, 1000, 3, sample_khz, " kHz"),
            "alpha": self._double(0.000001, 1, 6, 1.0),
        }

    def _adc_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        basic = QGroupBox("ADC")
        form = QFormLayout(basic)
        self.adc_vref = self._double(0.1, 20, 3, 3.3, " V")
        self.adc_bits = self._spin(1, 32, 12)
        self.adc_clock = self._double(1, 1000, 3, 60, " MHz")
        for label, widget in (
            ("Vref", self.adc_vref), ("bits", self.adc_bits), ("clock", self.adc_clock),
        ):
            form.addRow(label, widget)
        adv, adv_form = self._advanced_box()
        self.adc_acq = self._double(0, 100000, 2, 300, " ns")
        self.adc_cycles = self._double(0, 100, 3, 13, " cycles")
        self.adc_soc = self._spin(1, 16, 1)
        self.adc_soc_spacing = self._double(0, 1000, 3, 0, " µs")
        self.adc_prev_weight = self._double(0, 0.999, 6, 0.0)
        for label, widget in (
            ("Acquisition window", self.adc_acq), ("Conversion cycles", self.adc_cycles),
            ("SOC count", self.adc_soc), ("SOC spacing", self.adc_soc_spacing),
            ("Recursive averaging weight", self.adc_prev_weight),
        ):
            adv_form.addRow(label, widget)
        left = QVBoxLayout()
        left.addWidget(basic)
        left.addWidget(adv)
        left.addStretch(1)
        root.addLayout(left, 1)
        right = QVBoxLayout()
        timeline, self.adc_timeline = self._summary_box("ADC timing diagram")
        right.addWidget(timeline)
        summary, self.adc_summary = self._summary_box("ADC derived values")
        right.addWidget(summary)
        root.addLayout(right, 1)
        return page

    def _modulator_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        left = QVBoxLayout()
        basic = QGroupBox("Modulator / PWM / FM")
        form = QFormLayout(basic)
        self.timer_clock = self._double(1, 1000, 3, 120, " MHz")
        self.count_mode = QComboBox()
        self.count_mode.addItem("Up-Down", "up_down")
        self.count_mode.addItem("Up", "up")
        self.duty_min = self._double(0, 0.9, 5, 0.01)
        self.duty_max = self._double(0.01, 1, 5, 0.98)
        form.addRow("TBCLK", self.timer_clock)
        form.addRow("Count mode", self.count_mode)
        form.addRow("Duty min", self.duty_min)
        form.addRow("Duty max", self.duty_max)
        left.addWidget(basic)
        adv, adv_form = self._advanced_box()
        self.min_pulse = self._double(0, 100, 4, 0.0, " µs")
        self.deadtime = self._double(0, 10000, 2, 100, " ns")
        adv_form.addRow("Minimum pulse", self.min_pulse)
        adv_form.addRow("Deadtime", self.deadtime)
        left.addWidget(adv)
        left.addStretch(1)
        root.addLayout(left, 1)
        flow, self.mod_flow = self._summary_box("Modulator signal flow")
        root.addWidget(flow, 1)
        return page

    def _timing_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        basic = QGroupBox("Digital timing")
        form = QFormLayout(basic)
        self.compute_delay = self._double(0, 1000, 4, 1.0, " µs")
        self.pwm_delay = self._double(0, 1000, 4, 10.0, " µs")
        self.include_zoh = QCheckBox("Include Zero-Order Hold")
        self.include_zoh.setChecked(True)
        form.addRow("Computation delay", self.compute_delay)
        form.addRow("PWM / shadow update delay", self.pwm_delay)
        form.addRow(self.include_zoh)
        note = QLabel(
            "ADC EOC delay is owned by the ADC page and is not double-counted here. "
            "Timing semantics follow the frozen sampling / firmware contract."
        )
        note.setWordWrap(True)
        left = QVBoxLayout()
        left.addWidget(basic)
        left.addWidget(note)
        left.addStretch(1)
        root.addLayout(left, 1)
        summary, self.timing_summary = self._summary_box("Timing budget")
        root.addWidget(summary, 1)
        return page

    def _controller_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        note = QLabel(
            "Controller design uses the existing PI / PIF / 2P2Z engines. "
            "Fc × PM Solution Map synthesizes firmware Tustin PI only in this tranche."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        box = QGroupBox("Controller Design")
        form = QFormLayout(box)
        self.controller_structure = QComboBox()
        for item in ("PI", "PIF", "2P2Z"):
            self.controller_structure.addItem(item, item)
        self.design_mode = QComboBox()
        self.design_mode.addItem("Manual", "manual")
        self.design_mode.addItem("Auto Design", "auto")
        self.target_fc = self._double(0, 1e6, 2, 0, " Hz")
        self.target_fc.setSpecialValueText("Use existing / Auto Design")
        self.target_pm = self._double(0, 179, 2, 0, "°")
        self.target_pm.setSpecialValueText("Use existing / Auto Design")
        self.target_gm = self._double(0, 100, 2, 6.0, " dB")
        self.target_ms = self._double(0.1, 100, 3, 2.0)
        self.target_switch = self._double(-200, 100, 2, -20.0, " dB")
        form.addRow("Structure", self.controller_structure)
        form.addRow("Mode", self.design_mode)
        form.addRow("Target Fc", self.target_fc)
        form.addRow("Target PM", self.target_pm)
        form.addRow("Minimum GM", self.target_gm)
        form.addRow("Maximum Ms", self.target_ms)
        form.addRow("|L(Fsw)| max", self.target_switch)
        root.addWidget(box)
        root.addStretch(1)
        return page

    def _review_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        left = QVBoxLayout()
        left.addWidget(QLabel("SYSTEM MODEL REVIEW"))
        self.review_cards = QPlainTextEdit()
        self.review_cards.setReadOnly(True)
        self.review_cards.setFont(_mono())
        self.review_cards.setMaximumHeight(180)
        left.addWidget(self.review_cards)
        self.review_checks = QListWidget()
        self.review_checks.itemClicked.connect(self._jump_from_review)
        left.addWidget(self.review_checks, 1)
        self.review_status = QLabel("")
        self.review_status.setWordWrap(True)
        left.addWidget(self.review_status)
        root.addLayout(left, 1)
        right = QVBoxLayout()
        diagram, self.review_diagram = self._summary_box("Complete system diagram")
        right.addWidget(diagram, 1)
        detail, self.review_detail = self._summary_box("Selected block / definition")
        right.addWidget(detail, 1)
        root.addLayout(right, 1)
        return page

    # ---- navigation / live updates --------------------------------------

    def _hook_live_updates(self) -> None:
        widgets = [
            self.llc_vmin, self.llc_vnom, self.llc_vmax, self.llc_vout, self.llc_pout,
            self.llc_fr, self.llc_fmin, self.llc_fmax, self.llc_ln, self.llc_q,
            self.llc_np, self.llc_ns, self.llc_rup, self.llc_rlow, self.llc_cdiv,
            self.llc_amp_gain, self.llc_amp_bw, self.llc_adc_r, self.llc_adc_c, self.llc_sample,
            self.ttpl_vmin, self.ttpl_vnom, self.ttpl_vmax, self.ttpl_line, self.ttpl_vbus,
            self.ttpl_pout, self.ttpl_eff, self.ttpl_fsw, self.ttpl_l, self.ttpl_dcr,
            self.ttpl_cbus, self.ttpl_cesr, self.adc_vref, self.adc_bits, self.adc_clock,
            self.adc_acq, self.adc_cycles, self.adc_soc, self.adc_soc_spacing, self.adc_prev_weight,
            self.timer_clock, self.duty_min, self.duty_max, self.min_pulse, self.deadtime,
            self.compute_delay, self.pwm_delay, self.target_fc, self.target_pm,
            self.target_gm, self.target_ms, self.target_switch,
        ]
        for fields in (self.current_sense, self.vac_sense, self.vbus_sense):
            widgets.extend(fields.values())
        for widget in widgets:
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(lambda *_: self._refresh_live_summaries())
        self.count_mode.currentIndexChanged.connect(lambda *_: self._refresh_live_summaries())
        self.include_zoh.toggled.connect(lambda *_: self._refresh_live_summaries())
        self.controller_structure.currentIndexChanged.connect(lambda *_: self._refresh_live_summaries())
        self.design_mode.currentIndexChanged.connect(lambda *_: self._refresh_live_summaries())

    def _sync_topology_pages(self) -> None:
        index = 0 if self._is_llc() else 1
        if hasattr(self, "stage_stack"):
            self.stage_stack.setCurrentIndex(index)
        if hasattr(self, "sense_stack"):
            self.sense_stack.setCurrentIndex(index)

    def _refresh_architecture(self) -> None:
        self.architecture_view.setPlainText(_LLC_ARCH if self._is_llc() else _TTPL_ARCH)

    def _page_changed(self, index: int) -> None:
        for i, label in enumerate(self.progress_labels):
            name = _STEP_NAMES[i]
            if i == index:
                label.setText(f"●  {i+1}  {name}")
                label.setStyleSheet(
                    "padding:9px 10px;border-radius:6px;background:#eff8ff;color:#175cd3;font-weight:700;"
                )
            elif i < index:
                label.setText(f"✓  {i+1}  {name}")
                label.setStyleSheet(
                    "padding:9px 10px;border-radius:6px;background:#ecfdf3;color:#067647;"
                )
            else:
                label.setText(f"○  {i+1}  {name}")
                label.setStyleSheet("padding:9px 10px;border-radius:6px;color:#667085;")
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < self.PAGE_REVIEW)
        self.finish_button.setVisible(index == self.PAGE_REVIEW)
        if index == self.PAGE_REVIEW:
            self._refresh_review()
        self._refresh_live_summaries()

    def _next(self) -> None:
        if self.pages.currentIndex() < self.PAGE_REVIEW:
            self.pages.setCurrentIndex(self.pages.currentIndex() + 1)

    def _back(self) -> None:
        if self.pages.currentIndex() > 0:
            self.pages.setCurrentIndex(self.pages.currentIndex() - 1)

    def _jump_from_review(self, item: QListWidgetItem) -> None:
        step = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(step, int) and 0 <= step <= self.PAGE_CONTROLLER:
            self.pages.setCurrentIndex(step)

    def _refresh_live_summaries(self) -> None:
        if not hasattr(self, "stage_summary"):
            return
        try:
            if self._is_llc():
                self._refresh_llc_stage_summary()
            else:
                self._refresh_ttpl_stage_summary()
            self._refresh_sense_summary()
            self._refresh_adc_summary()
            self._refresh_modulator_summary()
            self._refresh_timing_summary()
        except Exception as exc:
            self.stage_summary.setPlainText(f"Live summary unavailable:\n{exc}")

    def _refresh_llc_stage_summary(self) -> None:
        spec = LLCDesignSpec(
            vbus_min_normal_v=self.llc_vmin.value(),
            vbus_nom_v=self.llc_vnom.value(),
            vbus_max_v=self.llc_vmax.value(),
            vout_v=self.llc_vout.value(),
            pout_w=self.llc_pout.value(),
            resonant_frequency_hz=self.llc_fr.value() * 1e3,
            minimum_frequency_hz=self.llc_fmin.value() * 1e3,
            maximum_frequency_hz=self.llc_fmax.value() * 1e3,
            ln_ratio=self.llc_ln.value(),
            q_full_load=self.llc_q.value(),
            primary_turns=self.llc_np.value(),
            secondary_turns=self.llc_ns.value(),
            primary_topology=PrimaryTopology.FULL_BRIDGE,
        )
        tank = design_tank(spec)
        rac = equivalent_ac_load_ohm(spec.turns_ratio, spec.vout_v, spec.pout_w)
        m_req = target_gain(spec, spec.vbus_nom_v)
        m_fr = gain(tank, tank.fr_hz, rac)
        self.stage_summary.setPlainText(
            f"Turns ratio n         : {spec.turns_ratio:.6g}\n"
            f"Required gain @ Vnom  : {m_req:.6g}\n"
            f"Tank gain @ Fr        : {m_fr:.6g}\n"
            f"Lr / Cr / Lm          : {tank.lr_h*1e6:.4g} µH / {tank.cr_f*1e9:.4g} nF / {tank.lm_h*1e6:.4g} µH\n"
            f"Frequency range       : {spec.minimum_frequency_hz/1e3:.4g} … {spec.maximum_frequency_hz/1e3:.4g} kHz\n"
            f"Rac @ full load       : {rac:.5g} Ω"
        )

    def _refresh_ttpl_stage_summary(self) -> None:
        design = analyze_ttpl_design(TTPLDesignSpec(
            vin_min_rms_v=self.ttpl_vmin.value(),
            vin_nom_rms_v=self.ttpl_vnom.value(),
            vin_max_rms_v=self.ttpl_vmax.value(),
            line_frequency_hz=self.ttpl_line.value(),
            bus_voltage_v=self.ttpl_vbus.value(),
            output_power_w=self.ttpl_pout.value(),
            efficiency=self.ttpl_eff.value(),
            switching_frequency_hz=self.ttpl_fsw.value() * 1e3,
            duty_min=self.duty_min.value(),
            duty_max=self.duty_max.value(),
        ))
        nom = design.work_points[1]
        low = design.work_points[0]
        l_h = self.ttpl_l.value() * 1e-6
        vpk = math.sqrt(2.0) * self.ttpl_vnom.value()
        duty = max(0.0, 1.0 - vpk / self.ttpl_vbus.value())
        ripple = (vpk * duty) / max(l_h * self.ttpl_fsw.value() * 1e3, 1e-30)
        self.stage_summary.setPlainText(
            f"Iin RMS (nom/low)     : {nom.input_current_rms_a:.4g} / {low.input_current_rms_a:.4g} A\n"
            f"Iin Peak (nom/low)    : {nom.input_current_peak_a:.4g} / {low.input_current_peak_a:.4g} A\n"
            f"Duty @ line peak      : {nom.duty_at_line_peak:.4g}\n"
            f"Ripple estimate @ nom : {ripple:.4g} App\n"
            f"IL peak (low-line eng): {design.estimated_inductor_peak_a:.4g} A\n"
            f"Boost headroom        : {design.boost_headroom_v:.4g} V\n"
            f"Recommended L / Cbus  : {design.required_inductance_uh:.4g} µH / {design.recommended_bus_capacitance_f*1e6:.4g} µF"
        )

    def _active_sensor_for_summary(self) -> SensorDefinition:
        if self._is_llc():
            rup = self.llc_rup.value() * 1e3
            rlow = self.llc_rlow.value() * 1e3
            return SensorDefinition(
                name="LLC output voltage",
                front_end_gain_v_per_unit=rlow / (rup + rlow),
                amplifier_gain=self.llc_amp_gain.value(),
                amplifier_bandwidth_hz=self.llc_amp_bw.value() * 1e3,
                source_resistance_ohm=(rup * rlow) / (rup + rlow),
                source_capacitance_f=self.llc_cdiv.value() * 1e-9,
                adc_series_resistance_ohm=self.llc_adc_r.value(),
                adc_shunt_capacitance_f=self.llc_adc_c.value() * 1e-9,
                sample_rate_hz=self.llc_sample.value() * 1e3,
                divider_upper_ohm=rup,
                divider_lower_ohm=rlow,
            )
        fields = (self.current_sense, self.vac_sense, self.vbus_sense)[self.sense_path_list.currentRow()]
        names = ("PFC inductor current", "AC input voltage", "PFC bus voltage")
        return self._sensor_from_fields(names[self.sense_path_list.currentRow()], fields)

    def _refresh_sense_summary(self) -> None:
        sensor = self._active_sensor_for_summary()
        adc = ADCDefinition(
            vref_v=self.adc_vref.value(), bits=self.adc_bits.value(),
            clock_hz=self.adc_clock.value() * 1e6,
            acquisition_time_s=self.adc_acq.value() * 1e-9,
            conversion_cycles=self.adc_cycles.value(),
            soc_count=self.adc_soc.value(),
            soc_spacing_s=self.adc_soc_spacing.value() * 1e-6,
            recursive_previous_weight=self.adc_prev_weight.value(),
        )
        target = self.target_fc.value() or None
        self.sense_summary.setPlainText(_sense_derived(sensor, adc, target))
        if self._is_llc():
            self.sense_schematic.set_labels(
                title="LLC Vout sense", source="Vout", front="Divider", amp="OpAmp", rc="RC", adc="ADC"
            )
        else:
            labels = (
                ("IL Sense", "IL", "Shunt/Hall"),
                ("VAC Sense", "Vac", "Divider"),
                ("VBUS Sense", "Vbus", "Divider"),
            )[self.sense_path_list.currentRow()]
            self.sense_schematic.set_labels(
                title=labels[0], source=labels[1], front=labels[2], amp="Amp", rc="RC", adc="ADC"
            )

    def _refresh_adc_summary(self) -> None:
        adc = ADCDefinition(
            vref_v=self.adc_vref.value(), bits=self.adc_bits.value(),
            clock_hz=self.adc_clock.value() * 1e6,
            acquisition_time_s=self.adc_acq.value() * 1e-9,
            conversion_cycles=self.adc_cycles.value(),
            soc_count=self.adc_soc.value(),
            soc_spacing_s=self.adc_soc_spacing.value() * 1e-6,
            recursive_previous_weight=self.adc_prev_weight.value(),
        )
        sample = self.llc_sample.value() * 1e3 if self._is_llc() else self.current_sense["sample"].value() * 1e3
        self.adc_timeline.setPlainText(
            "PWM event\n"
            "   │\n"
            "   ▼\n"
            "  SOC\n"
            "   │ acquisition\n"
            "   ├────────\n"
            "            EOC\n"
            "             │\n"
            "             ▼\n"
            "          ISR / CLA"
        )
        if self._is_llc():
            rates = f"LLC Fs={self.llc_sample.value():.4g} kHz"
        else:
            rates = (
                f"IL={self.current_sense['sample'].value():.4g} kHz | "
                f"VAC={self.vac_sense['sample'].value():.4g} kHz | "
                f"VBUS={self.vbus_sense['sample'].value():.4g} kHz"
            )
        self.adc_summary.setPlainText(
            f"ADC LSB              : {adc.vref_v/(2**adc.bits):.6g} V\n"
            f"Acquisition delay    : {adc.acquisition_time_s*1e9:.4g} ns\n"
            f"Conversion delay     : {adc.conversion_time_s*1e9:.4g} ns\n"
            f"Sequence delay       : {max(adc.soc_count-1,0)*adc.soc_spacing_s*1e6:.4g} µs\n"
            f"Effective ready      : {adc.acquisition_to_ready_s*1e6:.4g} µs\n"
            f"Nyquist              : {0.5*sample/1e3:.4g} kHz\n"
            f"Sample rates         : {rates}"
        )

    def _refresh_modulator_summary(self) -> None:
        tbclk = self.timer_clock.value() * 1e6
        mode = str(self.count_mode.currentData())
        if self._is_llc():
            fsw = self.llc_fr.value() * 1e3
            tbprd = tbclk / (2.0 * fsw) if mode == "up_down" else tbclk / fsw
            flow = (
                "Controller output\n"
                "      ↓\n"
                "    PCMD\n"
                "      ↓\n"
                "   FM LUT\n"
                "      ↓\n"
                "    TBPRD\n"
                "      ↓\n"
                "     Fsw"
            )
            detail = (
                f"Nominal Fsw / Fr     : {fsw/1e3:.5g} kHz\n"
                f"Fmin / Fmax          : {self.llc_fmin.value():.4g} / {self.llc_fmax.value():.4g} kHz\n"
                f"TBPRD @ Fr           : {tbprd:.4g}\n"
                f"Timer resolution     : {1e9/tbclk:.4g} ns\n"
                f"Existing FM LUT      : firmware default path reused after Analyze"
            )
        else:
            fsw = self.ttpl_fsw.value() * 1e3
            tbprd = tbclk / (2.0 * fsw) if mode == "up_down" else tbclk / fsw
            duty_step = 1.0 / (2.0 * tbprd) if mode == "up_down" else 1.0 / tbprd
            flow = (
                "Duty command\n"
                "    ↓\n"
                "   PWM\n"
                "    ↓\n"
                "Shadow Register\n"
                "    ↓\n"
                " Load Event\n"
                "    ↓\n"
                "Power Stage"
            )
            detail = (
                f"Fsw                  : {fsw/1e3:.5g} kHz\n"
                f"TBPRD                : {tbprd:.4g}\n"
                f"PWM resolution       : {duty_step:.6g} duty\n"
                f"Update rate          : {fsw/1e3:.5g} kHz\n"
                f"Deadtime / min pulse : {self.deadtime.value():.4g} ns / {self.min_pulse.value():.4g} µs"
            )
        self.mod_flow.setPlainText(flow + "\n\n" + detail)

    def _refresh_timing_summary(self) -> None:
        adc = ADCDefinition(
            vref_v=self.adc_vref.value(), bits=self.adc_bits.value(),
            clock_hz=self.adc_clock.value() * 1e6,
            acquisition_time_s=self.adc_acq.value() * 1e-9,
            conversion_cycles=self.adc_cycles.value(),
            soc_count=self.adc_soc.value(),
            soc_spacing_s=self.adc_soc_spacing.value() * 1e-6,
        )
        compute = self.compute_delay.value() * 1e-6
        pwm = self.pwm_delay.value() * 1e-6
        total = compute + pwm
        sample = self.llc_sample.value() * 1e3 if self._is_llc() else self.current_sense["sample"].value() * 1e3
        ts = 1.0 / sample
        fc = self.target_fc.value() or 1000.0
        phase = -360.0 * fc * total
        self.timing_summary.setPlainText(
            "Sampling\n"
            "   ↓\n"
            "ADC conversion\n"
            "   ↓\n"
            "ISR / CLA\n"
            "   ↓\n"
            "Controller calculation\n"
            "   ↓\n"
            "PWM register write\n"
            "   ↓\n"
            "Shadow load\n"
            "   ↓\n"
            "Power stage response\n\n"
            f"ADC ready delay      : {adc.acquisition_to_ready_s*1e6:.4g} µs  (ADC page)\n"
            f"Compute delay        : {compute*1e6:.4g} µs\n"
            f"PWM update delay     : {pwm*1e6:.4g} µs\n"
            f"Total command delay  : {total*1e6:.4g} µs\n"
            f"Delay / Ts           : {total/ts:.4g}\n"
            f"Phase loss @ Fc      : {phase:.3f} deg  (Fc={fc:.5g} Hz)\n"
            f"ZOH included         : {self.include_zoh.isChecked()}"
        )

    # ---- definition build / review / load --------------------------------

    @staticmethod
    def _sensor_from_fields(name: str, fields: dict[str, QDoubleSpinBox]) -> SensorDefinition:
        return SensorDefinition(
            name=name,
            front_end_gain_v_per_unit=fields["gain"].value(),
            amplifier_bandwidth_hz=fields["bw"].value() * 1e3,
            source_resistance_ohm=fields["source_r"].value(),
            source_capacitance_f=fields["source_c"].value() * 1e-9,
            adc_series_resistance_ohm=fields["out_r"].value(),
            adc_shunt_capacitance_f=fields["out_c"].value() * 1e-9,
            digital_filter_alpha=fields["alpha"].value(),
            sample_rate_hz=fields["sample"].value() * 1e3,
        )

    def build_definition(self) -> ControlSystemDefinition:
        adc = ADCDefinition(
            vref_v=self.adc_vref.value(), bits=self.adc_bits.value(),
            clock_hz=self.adc_clock.value() * 1e6,
            acquisition_time_s=self.adc_acq.value() * 1e-9,
            conversion_cycles=self.adc_cycles.value(), soc_count=self.adc_soc.value(),
            soc_spacing_s=self.adc_soc_spacing.value() * 1e-6,
            recursive_previous_weight=self.adc_prev_weight.value(),
        )
        timing = TimingDefinition(
            computation_delay_s=self.compute_delay.value() * 1e-6,
            pwm_update_delay_s=self.pwm_delay.value() * 1e-6,
            include_zero_order_hold=self.include_zoh.isChecked(),
        )
        intent = ControllerIntent(
            structure=str(self.controller_structure.currentData()),
            design_mode=str(self.design_mode.currentData()),
            target_crossover_hz=(self.target_fc.value() or None),
            target_phase_margin_deg=(self.target_pm.value() or None),
            minimum_gain_margin_db=self.target_gm.value(),
            maximum_sensitivity=self.target_ms.value(),
            maximum_switching_loop_gain_db=self.target_switch.value(),
            source="guided_system_design",
        )
        if self._is_llc():
            stage = LLCStageDefinition(
                self.llc_vmin.value(), self.llc_vnom.value(), self.llc_vmax.value(),
                self.llc_vout.value(), self.llc_pout.value(),
                self.llc_fr.value() * 1e3, self.llc_fmin.value() * 1e3, self.llc_fmax.value() * 1e3,
                self.llc_ln.value(), self.llc_q.value(), self.llc_np.value(), self.llc_ns.value(),
            )
            sensor = self._active_sensor_for_summary()
            return ControlSystemDefinition(
                topology=SystemTopology.LLC,
                plant_source=self.plant_source.currentData(),
                architecture=ControlArchitecture.LLC_FM_VOLTAGE,
                llc_stage=stage,
                sensors=(sensor,),
                adc=adc,
                modulator=ModulatorDefinition(
                    kind="FM/TBPRD", switching_frequency_hz=stage.resonant_frequency_hz,
                    timer_clock_hz=self.timer_clock.value() * 1e6,
                    count_mode=str(self.count_mode.currentData()),
                    duty_min=self.duty_min.value(), duty_max=self.duty_max.value(),
                    minimum_pulse_s=self.min_pulse.value() * 1e-6,
                    deadtime_s=self.deadtime.value() * 1e-9,
                ),
                timing=timing, controller=intent,
            )

        stage = TTPLStageDefinition(
            self.ttpl_vmin.value(), self.ttpl_vnom.value(), self.ttpl_vmax.value(),
            self.ttpl_line.value(), self.ttpl_vbus.value(), self.ttpl_pout.value(),
            self.ttpl_eff.value(), self.ttpl_fsw.value() * 1e3,
            self.ttpl_l.value() * 1e-6, self.ttpl_dcr.value() * 1e-3,
            self.ttpl_cbus.value() * 1e-6, self.ttpl_cesr.value() * 1e-3,
        )
        sensors = (
            self._sensor_from_fields("PFC inductor current", self.current_sense),
            self._sensor_from_fields("AC input voltage", self.vac_sense),
            self._sensor_from_fields("PFC bus voltage", self.vbus_sense),
        )
        return ControlSystemDefinition(
            topology=SystemTopology.TTPL_PFC,
            plant_source=self.plant_source.currentData(),
            architecture=ControlArchitecture.TTPL_DUAL_LOOP,
            ttpl_stage=stage, sensors=sensors, adc=adc,
            modulator=ModulatorDefinition(
                kind="TTPL PWM", switching_frequency_hz=stage.switching_frequency_hz,
                timer_clock_hz=self.timer_clock.value() * 1e6,
                count_mode=str(self.count_mode.currentData()),
                duty_min=self.duty_min.value(), duty_max=self.duty_max.value(),
                minimum_pulse_s=self.min_pulse.value() * 1e-6,
                deadtime_s=self.deadtime.value() * 1e-9,
            ),
            timing=timing, controller=intent,
        )

    def _refresh_review(self) -> None:
        self.review_checks.clear()
        try:
            definition = self.build_definition()
            checks = definition.engineering_checklist()
            all_ok = all(item.ok for item in checks)
            categories = ("Topology", "Power Stage", "Sensing", "ADC", "PWM / FM", "Timing", "Controller")
            cards = []
            for category in categories:
                rows = [c for c in checks if c.category == category]
                if not rows:
                    cards.append(f"{category:<16} READY")
                    continue
                status = "PASS" if all(r.ok for r in rows) else "FAIL"
                if category == "Controller" and all(r.ok for r in rows):
                    status = "READY"
                cards.append(f"{category:<16} {status}")
            self.review_cards.setPlainText("\n".join(cards))
            for item in checks:
                mark = "✓" if item.ok else "✕"
                row = QListWidgetItem(f"{mark} {item.label} — {item.detail}")
                row.setData(Qt.ItemDataRole.UserRole, item.step)
                self.review_checks.addItem(row)
            self.review_diagram.setPlainText(_LLC_ARCH if definition.topology == SystemTopology.LLC else _TTPL_ARCH)
            self.review_detail.setPlainText(
                f"Topology      : {definition.topology.value}\n"
                f"Architecture  : {definition.architecture.value}\n"
                f"Sensors       : {len(definition.sensors)}\n"
                f"ADC           : {definition.adc.bits}-bit / {definition.adc.vref_v:g} V\n"
                f"Modulator     : {definition.modulator.kind}\n"
                f"Command delay : {definition.timing.total_command_delay_s*1e6:.5g} µs\n"
                f"Controller    : {definition.controller.structure} / {definition.controller.design_mode}\n"
                f"Target Fc/PM  : {definition.controller.target_crossover_hz} / {definition.controller.target_phase_margin_deg}"
            )
            self.definition = definition if all_ok else None
            self.finish_button.setEnabled(all_ok)
            if all_ok:
                self.review_status.setText("全部 mandatory check PASS：可以 Analyze Complete System。")
                self.review_status.setStyleSheet(
                    "padding:7px;background:#ecfdf3;color:#067647;border:1px solid #75e0a7;"
                )
            else:
                self.review_status.setText("存在失败项：点击条目可跳回对应步骤。")
                self.review_status.setStyleSheet(
                    "padding:7px;background:#fef3f2;color:#b42318;border:1px solid #fda29b;"
                )
        except Exception as exc:
            self.definition = None
            self.finish_button.setEnabled(False)
            self.review_cards.setPlainText("SYSTEM DEFINITION INVALID")
            self.review_checks.addItem(f"✕ {exc}")
            self.review_status.setText("请返回对应步骤修正参数。")
            self.review_status.setStyleSheet(
                "padding:7px;background:#fef3f2;color:#b42318;border:1px solid #fda29b;"
            )

    def _finish(self) -> None:
        self._refresh_review()
        if self.definition is not None:
            self.accept()

    def _load_definition(self, definition: ControlSystemDefinition) -> None:
        self.select_topology(definition.topology)
        index = self.plant_source.findData(definition.plant_source)
        if index >= 0:
            self.plant_source.setCurrentIndex(index)
        self.adc_vref.setValue(definition.adc.vref_v)
        self.adc_bits.setValue(definition.adc.bits)
        self.adc_clock.setValue(definition.adc.clock_hz / 1e6)
        self.adc_acq.setValue(definition.adc.acquisition_time_s * 1e9)
        self.adc_cycles.setValue(definition.adc.conversion_cycles)
        self.adc_soc.setValue(definition.adc.soc_count)
        self.adc_soc_spacing.setValue(definition.adc.soc_spacing_s * 1e6)
        self.adc_prev_weight.setValue(definition.adc.recursive_previous_weight)
        self.timer_clock.setValue(definition.modulator.timer_clock_hz / 1e6)
        mode_index = self.count_mode.findData(definition.modulator.count_mode)
        if mode_index >= 0:
            self.count_mode.setCurrentIndex(mode_index)
        self.duty_min.setValue(definition.modulator.duty_min)
        self.duty_max.setValue(definition.modulator.duty_max)
        self.min_pulse.setValue(definition.modulator.minimum_pulse_s * 1e6)
        self.deadtime.setValue(definition.modulator.deadtime_s * 1e9)
        self.compute_delay.setValue(definition.timing.computation_delay_s * 1e6)
        self.pwm_delay.setValue(definition.timing.pwm_update_delay_s * 1e6)
        self.include_zoh.setChecked(definition.timing.include_zero_order_hold)
        structure = self.controller_structure.findData(definition.controller.structure)
        if structure >= 0:
            self.controller_structure.setCurrentIndex(structure)
        mode = self.design_mode.findData(definition.controller.design_mode)
        if mode >= 0:
            self.design_mode.setCurrentIndex(mode)
        if definition.controller.target_crossover_hz:
            self.target_fc.setValue(definition.controller.target_crossover_hz)
        if definition.controller.target_phase_margin_deg:
            self.target_pm.setValue(definition.controller.target_phase_margin_deg)
        if definition.controller.minimum_gain_margin_db is not None:
            self.target_gm.setValue(definition.controller.minimum_gain_margin_db)
        if definition.controller.maximum_sensitivity is not None:
            self.target_ms.setValue(definition.controller.maximum_sensitivity)
        if definition.controller.maximum_switching_loop_gain_db is not None:
            self.target_switch.setValue(definition.controller.maximum_switching_loop_gain_db)

        if definition.topology == SystemTopology.LLC and definition.llc_stage is not None:
            stage = definition.llc_stage
            self.llc_vmin.setValue(stage.vbus_min_v)
            self.llc_vnom.setValue(stage.vbus_nom_v)
            self.llc_vmax.setValue(stage.vbus_max_v)
            self.llc_vout.setValue(stage.vout_v)
            self.llc_pout.setValue(stage.pout_w)
            self.llc_fr.setValue(stage.resonant_frequency_hz / 1e3)
            self.llc_fmin.setValue(stage.minimum_frequency_hz / 1e3)
            self.llc_fmax.setValue(stage.maximum_frequency_hz / 1e3)
            self.llc_ln.setValue(stage.ln_ratio)
            self.llc_q.setValue(stage.q_full_load)
            self.llc_np.setValue(stage.primary_turns)
            self.llc_ns.setValue(stage.secondary_turns)
            sensor = definition.sensors[0]
            if sensor.divider_upper_ohm > 0.0:
                self.llc_rup.setValue(sensor.divider_upper_ohm / 1e3)
            if sensor.divider_lower_ohm > 0.0:
                self.llc_rlow.setValue(sensor.divider_lower_ohm / 1e3)
            self.llc_cdiv.setValue(sensor.source_capacitance_f * 1e9)
            self.llc_amp_gain.setValue(sensor.amplifier_gain)
            self.llc_amp_bw.setValue(sensor.amplifier_bandwidth_hz / 1e3)
            self.llc_adc_r.setValue(sensor.adc_series_resistance_ohm)
            self.llc_adc_c.setValue(sensor.adc_shunt_capacitance_f * 1e9)
            self.llc_sample.setValue(sensor.sample_rate_hz / 1e3)
        elif definition.topology == SystemTopology.TTPL_PFC and definition.ttpl_stage is not None:
            stage = definition.ttpl_stage
            self.ttpl_vmin.setValue(stage.vin_min_rms_v)
            self.ttpl_vnom.setValue(stage.vin_nom_rms_v)
            self.ttpl_vmax.setValue(stage.vin_max_rms_v)
            self.ttpl_line.setValue(stage.line_frequency_hz)
            self.ttpl_vbus.setValue(stage.bus_voltage_v)
            self.ttpl_pout.setValue(stage.output_power_w)
            self.ttpl_eff.setValue(stage.efficiency)
            self.ttpl_fsw.setValue(stage.switching_frequency_hz / 1e3)
            self.ttpl_l.setValue(stage.boost_inductance_h * 1e6)
            self.ttpl_dcr.setValue(stage.inductor_dcr_ohm * 1e3)
            self.ttpl_cbus.setValue(stage.bus_capacitance_f * 1e6)
            self.ttpl_cesr.setValue(stage.bus_cap_esr_ohm * 1e3)
            mapping = {
                "PFC inductor current": self.current_sense,
                "AC input voltage": self.vac_sense,
                "PFC bus voltage": self.vbus_sense,
            }
            for sensor in definition.sensors:
                fields = mapping[sensor.name]
                fields["gain"].setValue(sensor.front_end_gain_v_per_unit)
                fields["bw"].setValue(sensor.amplifier_bandwidth_hz / 1e3)
                fields["source_r"].setValue(sensor.source_resistance_ohm)
                fields["source_c"].setValue(sensor.source_capacitance_f * 1e9)
                fields["out_r"].setValue(sensor.adc_series_resistance_ohm)
                fields["out_c"].setValue(sensor.adc_shunt_capacitance_f * 1e9)
                fields["sample"].setValue(sensor.sample_rate_hz / 1e3)
                fields["alpha"].setValue(sensor.digital_filter_alpha)


def llc_spec_from_system_definition(definition: ControlSystemDefinition, base: LLCDesignSpec) -> LLCDesignSpec:
    definition.validate()
    if definition.topology != SystemTopology.LLC or definition.llc_stage is None:
        raise ValueError("LLC adapter requires an LLC system definition")
    stage = definition.llc_stage
    spec = base.clone(
        vbus_min_normal_v=stage.vbus_min_v,
        vbus_nom_v=stage.vbus_nom_v,
        vbus_max_v=stage.vbus_max_v,
        vbus_hold_end_v=min(base.vbus_hold_end_v, stage.vbus_min_v),
        vout_v=stage.vout_v,
        pout_w=stage.pout_w,
        resonant_frequency_hz=stage.resonant_frequency_hz,
        minimum_frequency_hz=stage.minimum_frequency_hz,
        maximum_frequency_hz=stage.maximum_frequency_hz,
        ln_ratio=stage.ln_ratio,
        q_full_load=stage.q_full_load,
        primary_turns=stage.primary_turns,
        secondary_turns=stage.secondary_turns,
        primary_deadtime_s=definition.modulator.deadtime_s,
    )
    spec.validate()
    return spec


def _sense_from_definition(
    default: ExternalSenseConfig, sensor: SensorDefinition, adc: ADCDefinition,
) -> ExternalSenseConfig:
    timing = ADCTimingConfig(
        sample_rate_hz=sensor.sample_rate_hz,
        adc_clock_hz=adc.clock_hz,
        acquisition_time_s=adc.acquisition_time_s,
        conversion_cycles=adc.conversion_cycles,
        soc_count=adc.soc_count,
        soc_spacing_s=adc.soc_spacing_s,
        recursive_previous_weight=adc.recursive_previous_weight,
        computation_delay_s=0.0,
        pwm_update_delay_s=0.0,
        include_zero_order_hold=default.timing.include_zero_order_hold,
        digital_filter=DigitalFilterConfig(sensor.digital_filter_alpha),
    )
    return replace(
        default,
        front_end_gain_v_per_unit=sensor.front_end_gain_v_per_unit,
        amplifier_gain=sensor.amplifier_gain,
        amplifier_bandwidth_hz=sensor.amplifier_bandwidth_hz,
        source_resistance_ohm=sensor.source_resistance_ohm,
        shunt_capacitance_f=sensor.source_capacitance_f,
        output_resistance_ohm=sensor.adc_series_resistance_ohm,
        adc_capacitance_f=sensor.adc_shunt_capacitance_f,
        adc_vref_v=adc.vref_v,
        adc_bits=adc.bits,
        timing=timing,
    )


def ttpl_config_from_system_definition(
    definition: ControlSystemDefinition, base: PFCControlLabConfig | None = None,
) -> PFCControlLabConfig:
    definition.validate()
    if definition.topology != SystemTopology.TTPL_PFC or definition.ttpl_stage is None:
        raise ValueError("TTPL adapter requires a TTPL system definition")
    base = base or PFCControlLabConfig()
    stage_in = definition.ttpl_stage
    stage = replace(
        base.power_stage,
        vin_rms_v=stage_in.vin_nom_rms_v,
        line_frequency_hz=stage_in.line_frequency_hz,
        bus_voltage_v=stage_in.bus_voltage_v,
        output_power_w=stage_in.output_power_w,
        switching_frequency_hz=stage_in.switching_frequency_hz,
        boost_inductance_h=stage_in.boost_inductance_h,
        equivalent_series_resistance_ohm=stage_in.inductor_dcr_ohm,
        bus_capacitance_f=stage_in.bus_capacitance_f,
        bus_cap_esr_ohm=stage_in.bus_cap_esr_ohm,
        efficiency=stage_in.efficiency,
        duty_min=definition.modulator.duty_min,
        duty_max=definition.modulator.duty_max,
        minimum_effective_pulse_s=definition.modulator.minimum_pulse_s,
        deadtime_s=definition.modulator.deadtime_s,
    )
    sensors = {sensor.name: sensor for sensor in definition.sensors}
    current = sensors["PFC inductor current"]
    vac = sensors["AC input voltage"]
    vbus = sensors["PFC bus voltage"]
    current_rate = current.sample_rate_hz
    voltage_rate = vbus.sample_rate_hz
    firmware = PFCFirmwareAlgorithmConfig(
        current_loop_rate_hz=current_rate,
        amc_rate_hz=min(base.firmware.amc_rate_hz, current_rate),
        voltage_loop_rate_hz=voltage_rate,
        vac_rms_lpf_alpha=base.firmware.vac_rms_lpf_alpha,
        vac_rms_feedforward_gain=base.firmware.vac_rms_feedforward_gain,
        gcmd_max_a_per_v=base.firmware.gcmd_max_a_per_v,
        indu_comp_gain=base.firmware.indu_comp_gain,
        indu_comp_min=base.firmware.indu_comp_min,
        indu_comp_max=base.firmware.indu_comp_max,
        vff_bypass=base.firmware.vff_bypass,
        current_computation_delay_s=definition.timing.computation_delay_s,
        current_pwm_update_delay_s=definition.timing.pwm_update_delay_s,
        amc_update_delay_s=base.firmware.amc_update_delay_s,
        voltage_computation_delay_s=definition.timing.computation_delay_s,
    )
    current_controller = replace(base.current_controller, sample_time_s=1.0 / current_rate)
    voltage_controller = replace(base.voltage_controller, sample_time_s=1.0 / voltage_rate)
    config = replace(
        base,
        power_stage=stage,
        firmware=firmware,
        current_controller=current_controller,
        voltage_controller=voltage_controller,
        current_sense=_sense_from_definition(base.current_sense, current, definition.adc),
        vac_sense=_sense_from_definition(base.vac_sense, vac, definition.adc),
        vbus_sense=_sense_from_definition(base.vbus_sense, vbus, definition.adc),
    )
    config.validate()
    return config


def _set_guided_status(window, definition: ControlSystemDefinition | None) -> None:
    if definition is None:
        return
    message = (
        f"System Source: V9.3 Guided System Definition ({definition.topology.value})  |  "
        "Edit System Definition available in toolbar"
    )
    window.statusBar().showMessage(message, 0)
    action = getattr(window, "_guided_edit_action", None)
    if action is not None:
        action.setEnabled(True)
        action.setVisible(True)


def install_guided_context_actions(window, edit_callback) -> QAction:
    """Expose Edit System Definition on Expert toolbars without losing context."""
    from PySide6.QtWidgets import QToolBar

    action = getattr(window, "_guided_edit_action", None)
    if action is None:
        action = QAction("Edit System Definition", window)
        action.setObjectName("edit_system_definition_action")
        action.setEnabled(False)
        action.setVisible(False)
        action.setToolTip("Re-open Guided System Design with the current ControlSystemDefinition")
        toolbars = window.findChildren(QToolBar)
        if toolbars:
            toolbars[0].addSeparator()
            toolbars[0].addAction(action)
        window._guided_edit_action = action
    try:
        action.triggered.disconnect()
    except Exception:
        pass
    action.triggered.connect(edit_callback)
    return action


def apply_definition_to_llc_window(window, definition: ControlSystemDefinition) -> LLCDesignSpec:
    """Populate the existing LLC expert workspace from the canonical model."""
    spec = llc_spec_from_system_definition(definition, window.spec)
    window.spec = spec
    window._load_spec_to_widgets(spec)
    window.guided_system_definition = definition
    sensor = definition.sensors[0]
    loop = window.digital_loop_view
    loop.sample_us.setValue(1e6 / sensor.sample_rate_hz)
    loop.timer_mhz.setValue(definition.modulator.timer_clock_hz / 1e6)
    for index in range(loop.count_mode.count()):
        data = loop.count_mode.itemData(index)
        value = getattr(data, "value", str(data)).lower()
        if value == definition.modulator.count_mode:
            loop.count_mode.setCurrentIndex(index)
            break
    loop.computation_us.setValue(definition.timing.computation_delay_s * 1e6)
    if hasattr(loop, "pwm_update_us"):
        loop.pwm_update_us.setValue(definition.timing.pwm_update_delay_s * 1e6)
    loop.include_zoh.setChecked(definition.timing.include_zero_order_hold)
    if sensor.divider_upper_ohm > 0.0 and sensor.divider_lower_ohm > 0.0:
        loop.rup_k.setValue(sensor.divider_upper_ohm / 1e3)
        loop.rlow_k.setValue(sensor.divider_lower_ohm / 1e3)
    loop.cdiv_nf.setValue(sensor.source_capacitance_f * 1e9)
    loop.opamp_gain.setValue(sensor.amplifier_gain)
    loop.opamp_bw_khz.setValue(sensor.amplifier_bandwidth_hz / 1e3)
    loop.adc_r.setValue(sensor.adc_series_resistance_ohm)
    loop.adc_c_nf.setValue(sensor.adc_shunt_capacitance_f * 1e9)
    loop.adc_clock_mhz.setValue(definition.adc.clock_hz / 1e6)
    loop.acq_ns.setValue(definition.adc.acquisition_time_s * 1e9)
    loop.conversion_cycles.setValue(definition.adc.conversion_cycles)
    loop.soc_count.setValue(definition.adc.soc_count)
    loop.previous_weight.setValue(definition.adc.recursive_previous_weight)
    _set_guided_status(window, definition)
    return spec


def apply_definition_to_ttpl_window(window, definition: ControlSystemDefinition) -> PFCControlLabConfig:
    """Populate the existing TTPL expert workspace and return the exact run config."""
    config = ttpl_config_from_system_definition(definition)
    window.guided_system_definition = definition
    window.guided_ttpl_config = config
    workbench = window.control_lab_view
    stage = definition.ttpl_stage
    assert stage is not None
    design = workbench.power_stage_view
    design.vin_min.setValue(stage.vin_min_rms_v)
    design.vin_nom.setValue(stage.vin_nom_rms_v)
    design.vin_max.setValue(stage.vin_max_rms_v)
    design.line_hz.setValue(stage.line_frequency_hz)
    design.vbus.setValue(stage.bus_voltage_v)
    design.pout.setValue(stage.output_power_w)
    design.efficiency.setValue(stage.efficiency)
    design.fsw.setValue(stage.switching_frequency_hz / 1e3)

    control = workbench.control_lab
    control.engineering_efficiency = stage.efficiency
    control.vin_rms.setValue(stage.vin_nom_rms_v)
    control.line_hz.setValue(stage.line_frequency_hz)
    control.vbus.setValue(stage.bus_voltage_v)
    control.pout.setValue(stage.output_power_w)
    control.fsw.setValue(stage.switching_frequency_hz / 1e3)
    control.inductance.setValue(stage.boost_inductance_h * 1e6)
    control.dcr.setValue(stage.inductor_dcr_ohm * 1e3)
    control.cbus.setValue(stage.bus_capacitance_f * 1e6)
    control.cbus_esr.setValue(stage.bus_cap_esr_ohm * 1e3)
    control.duty_min.setValue(definition.modulator.duty_min)
    control.duty_max.setValue(definition.modulator.duty_max)
    control.min_pulse_us.setValue(definition.modulator.minimum_pulse_s * 1e6)
    control.deadtime_ns.setValue(definition.modulator.deadtime_s * 1e9)
    control.current_delay_us.setValue(definition.timing.total_command_delay_s * 1e6)
    control.voltage_delay_us.setValue(definition.timing.computation_delay_s * 1e6)

    sensor_widgets = {
        "PFC inductor current": control.current_sense,
        "AC input voltage": control.vac_sense,
        "PFC bus voltage": control.vbus_sense,
    }
    for sensor in definition.sensors:
        fields = sensor_widgets[sensor.name]
        fields["gain"].setValue(sensor.front_end_gain_v_per_unit)
        fields["bw"].setValue(sensor.amplifier_bandwidth_hz / 1e3)
        fields["source_r"].setValue(sensor.source_resistance_ohm)
        fields["source_c"].setValue(sensor.source_capacitance_f * 1e9)
        fields["out_r"].setValue(sensor.adc_series_resistance_ohm)
        fields["out_c"].setValue(sensor.adc_shunt_capacitance_f * 1e9)
        fields["sample"].setValue(sensor.sample_rate_hz / 1e3)
        fields["alpha"].setValue(sensor.digital_filter_alpha)
    _set_guided_status(window, definition)
    return config


__all__ = [
    "SystemModelingDesignDialog",
    "apply_definition_to_llc_window",
    "apply_definition_to_ttpl_window",
    "install_guided_context_actions",
    "llc_spec_from_system_definition",
    "ttpl_config_from_system_definition",
]
