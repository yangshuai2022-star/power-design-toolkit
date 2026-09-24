"""Reusable TTPL/Vienna PFC boost-inductor design widgets."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pfc_design.magnetics import (
    HIGH_FLUX_254,
    HIGH_FLUX_254_MATERIALS,
    HighFluxCoreGeometry,
    PFCInductorDesignRequest,
    PFCInductorDesignResult,
    design_pfc_inductor,
    FerriteInductorRequest,
    FerriteInductorResult,
    design_ferrite_pfc_inductor,
)
from pfc_design.magnetics.core_database import CoreDatabase
from pfc_design.magnetics.core_entry import CoreSpec
from pfc_design.magnetics.steinmetz import SteinmetzMaterial
from power_control_tools.part_validation import (
    brand_display_names,
    format_missing,
    load_brand_taxonomy,
    missing_ferrite_steinmetz_parameters,
)
from llc_design.gui import theme
from llc_design.user_messages import show_operation_issue
from llc_design.i18n import t


def _prompt_user_core(parent) -> tuple[CoreSpec, SteinmetzMaterial] | None:
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit

    dialog = QDialog(parent)
    dialog.setWindowTitle("Add user magnetic core")
    dialog.resize(480, 520)
    root = QVBoxLayout(dialog)
    note = QLabel(
        "Enter geometry and AL from one manufacturer datasheet revision. "
        "Brand placeholders such as 铂科 / 东睦科达 stay non-calculable until these fields and Steinmetz data exist. "
        "Do not invent coefficients."
    )
    note.setWordWrap(True)
    root.addWidget(note)
    form = QFormLayout()
    brand = QComboBox()
    for name in brand_display_names():
        brand.addItem(name)
    part = QLineEdit("USER_CORE_NEW")
    material = QLineEdit("Ferrite custom")
    material_class = QComboBox()
    material_class.addItems(["Ferrite", "HighFlux", "Sendust", "MPP", "Amorphous", "Nanocrystalline"])
    source = QLineEdit("")
    od = QDoubleSpinBox(); od.setRange(1, 500); od.setValue(50); od.setSuffix(" mm")
    id_ = QDoubleSpinBox(); id_.setRange(0.1, 499); id_.setValue(30); id_.setSuffix(" mm")
    ht = QDoubleSpinBox(); ht.setRange(0.1, 200); ht.setValue(20); ht.setSuffix(" mm")
    ae = QDoubleSpinBox(); ae.setRange(0.01, 100); ae.setDecimals(4); ae.setValue(1.5); ae.setSuffix(" cm²")
    le = QDoubleSpinBox(); le.setRange(0.1, 100); le.setDecimals(3); le.setValue(12.0); le.setSuffix(" cm")
    ve = QDoubleSpinBox(); ve.setRange(0.01, 1000); ve.setDecimals(3); ve.setValue(18.0); ve.setSuffix(" cm³")
    al = QDoubleSpinBox(); al.setRange(0.01, 10000); al.setDecimals(3); al.setValue(100.0); al.setSuffix(" nH/T²")
    ui = QDoubleSpinBox(); ui.setRange(1, 20000); ui.setValue(2000)
    bs = QDoubleSpinBox(); bs.setRange(0.05, 3); bs.setDecimals(3); bs.setValue(0.45); bs.setSuffix(" T")
    sk = QDoubleSpinBox(); sk.setRange(1e-6, 1e3); sk.setDecimals(6); sk.setValue(0.3)
    sa = QDoubleSpinBox(); sa.setRange(0.1, 5); sa.setDecimals(3); sa.setValue(1.25)
    sb = QDoubleSpinBox(); sb.setRange(0.1, 5); sb.setDecimals(3); sb.setValue(2.50)
    for label, w in (
        ("Brand / manufacturer", brand), ("Part number", part), ("Material name", material),
        ("Material class", material_class), ("Source / revision URL", source),
        ("OD", od), ("ID", id_), ("HT", ht), ("Ae", ae), ("Le", le), ("Ve", ve),
        ("AL", al), ("μi", ui), ("Bs", bs),
        ("Steinmetz k", sk), ("Steinmetz α", sa), ("Steinmetz β", sb),
    ):
        form.addRow(label, w)
    root.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    root.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if not part.text().strip():
        QMessageBox.warning(parent, "User core", "Part number required.")
        return None
    core = CoreSpec(
        manufacturer=brand.currentText().strip(),
        part_number=part.text().strip(),
        material=material.text().strip() or "User material",
        material_class=material_class.currentText(),
        od_mm=od.value(),
        id_mm=id_.value(),
        ht_mm=ht.value(),
        ae_cm2=ae.value(),
        le_cm=le.value(),
        ve_cm3=ve.value(),
        al_nH_per_t2=al.value(),
        ui=ui.value(),
        bs_T=bs.value(),
        source_url=source.text().strip() or None,
        dc_bias_coeffs=[100.0, 0.0, 0.0, 0.0, 0.0],
    )
    steinmetz = SteinmetzMaterial(
        name=core.material, k=sk.value(), alpha=sa.value(), beta=sb.value(),
    )
    return core, steinmetz


class PFCInductorDesignEditor(QWidget):
    """Narrow parameter editor suitable for the PFC left inspector."""

    design_completed = Signal(object)

    def __init__(
        self,
        topology: str,
        context_provider: Callable[[], dict[str, float]],
        apply_callback: Callable[[PFCInductorDesignResult], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.topology = topology
        self.context_provider = context_provider
        self.apply_callback = apply_callback
        self.last_result: PFCInductorDesignResult | FerriteInductorResult | None = None
        self.core_db = CoreDatabase()
        self._taxonomy = load_brand_taxonomy()
        self._rebuild_ferrite_cores()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(7)

        intro = QLabel(
            "PFC 升压电感设计。粉芯路径使用 Magnetics High Flux DC-bias 拟合；"
            "铁氧体路径使用显式气隙 + Steinmetz，不套用粉芯偏磁公式。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{theme.active_theme().text_muted};padding:4px 2px;")
        root.addWidget(intro)

        path_group = QGroupBox("磁芯路径")
        path_form = QFormLayout(path_group)
        self.material_path = QComboBox()
        self.material_path.addItem("Powder — Magnetics High Flux", "high_flux")
        self.material_path.addItem("Ferrite — gapped / Steinmetz", "ferrite")
        path_form.addRow("Model path", self.material_path)
        root.addWidget(path_group)
        self.material_path.currentIndexChanged.connect(self._path_changed)

        op_group = QGroupBox("工作点 / 目标")
        op = QFormLayout(op_group)
        self.context_label = QLabel("尚未同步")
        self.context_label.setWordWrap(True)
        self.target_l = self._spin(1.0, 20000.0, 2, 220.0, " µH")
        self.eff = self._spin(0.80, 1.0, 4, 0.97)
        self.n_cores = QSpinBox(); self.n_cores.setRange(1, 16)
        self.n_cores.setValue(2 if topology == "ttpl" else 5)
        op.addRow("功率级", self.context_label)
        op.addRow("满载目标 L", self.target_l)
        op.addRow("估算效率 η", self.eff)
        op.addRow("叠加磁芯数", self.n_cores)
        root.addWidget(op_group)

        core_group = QGroupBox("磁芯 — Magnetics High Flux 254")
        self.high_flux_group = core_group
        core = QFormLayout(core_group)
        self.perm = QComboBox()
        for mu in sorted(HIGH_FLUX_254_MATERIALS):
            self.perm.addItem(f"{mu} µ", mu)
        self.perm.setCurrentIndex(self.perm.findData(60))
        self.al = self._spin(0.01, 5000.0, 3, 81.0, " nH/T²")
        self.le = self._spin(1.0, 1000.0, 2, HIGH_FLUX_254.le_mm, " mm")
        self.ae = self._spin(0.1, 10000.0, 2, HIGH_FLUX_254.ae_mm2, " mm²")
        self.ve = self._spin(1.0, 1e7, 1, HIGH_FLUX_254.ve_mm3, " mm³")
        self.od = self._spin(1.0, 500.0, 2, HIGH_FLUX_254.od_mm, " mm")
        self.id_ = self._spin(0.1, 499.0, 2, HIGH_FLUX_254.id_mm, " mm")
        self.ht = self._spin(0.1, 200.0, 2, HIGH_FLUX_254.ht_mm, " mm")
        self.bsat = self._spin(0.1, 3.0, 3, HIGH_FLUX_254.bs_t, " T")
        for label, widget in (
            ("材料磁导率", self.perm), ("AL", self.al), ("Le", self.le),
            ("Ae", self.ae), ("Ve", self.ve), ("OD", self.od),
            ("ID", self.id_), ("HT", self.ht), ("Bsat", self.bsat),
        ):
            core.addRow(label, widget)
        root.addWidget(core_group)
        self.perm.currentIndexChanged.connect(self._material_changed)

        ferrite_group = QGroupBox("磁芯 — Ferrite（气隙 + Steinmetz）")
        self.ferrite_group = ferrite_group
        ferrite = QFormLayout(ferrite_group)
        self.brand_filter = QComboBox()
        self.brand_filter.addItem("All brands", "")
        for item in self._taxonomy["brands"]:
            self.brand_filter.addItem(item["display_name"], item["id"])
        self.ferrite_core = QComboBox()
        self.gap_mm = self._spin(0.01, 10.0, 3, 0.50, " mm")
        self.b_limit = self._spin(0.05, 0.80, 3, 0.30, " T")
        self.brand_status = QLabel("")
        self.brand_status.setWordWrap(True)
        add_user = QPushButton("Add user core…")
        ferrite.addRow("Brand filter", self.brand_filter)
        ferrite.addRow("Ferrite core", self.ferrite_core)
        ferrite.addRow("Air gap", self.gap_mm)
        ferrite.addRow("Bpeak limit", self.b_limit)
        ferrite.addRow(self.brand_status)
        ferrite.addRow(add_user)
        ferrite_note = QLabel(
            "Built-in Ferrite records come from pfc_design/data/cores.json. "
            "粉末偏磁多项式不会用于本路径。缺少 Steinmetz 系数时会提示，不会借用其他品牌拟合。"
            " 铂科 / 东睦科达 are brand placeholders until datasheet-backed user cores exist."
        )
        ferrite_note.setWordWrap(True)
        ferrite.addRow(ferrite_note)
        root.addWidget(ferrite_group)
        self.ferrite_group.setVisible(False)
        self.brand_filter.currentIndexChanged.connect(self._rebuild_ferrite_combo)
        add_user.clicked.connect(self._add_user_core)
        self._rebuild_ferrite_combo()

        wire_group = QGroupBox("绕组 — 漆包圆铜线")
        wire = QFormLayout(wire_group)
        self.wire_d = self._spin(0.10, 5.0, 3, 1.00, " mm")
        self.enamel = self._spin(0.0, 0.5, 3, 0.05, " mm/side")
        self.j_target = self._spin(0.5, 20.0, 2, 5.0, " A/mm²")
        self.cu_temp = self._spin(20.0, 180.0, 1, 100.0, " °C")
        self.fill = self._spin(0.10, 0.80, 3, 0.45)
        for label, widget in (
            ("单根铜径", self.wire_d), ("漆膜单边厚度", self.enamel),
            ("目标电流密度", self.j_target), ("铜温", self.cu_temp),
            ("窗口填充上限", self.fill),
        ):
            wire.addRow(label, widget)
        root.addWidget(wire_group)

        buttons = QHBoxLayout()
        self.sync_button = QPushButton("从功率级同步")
        self.run_button = QPushButton("计算电感")
        self.run_button.setDefault(True)
        buttons.addWidget(self.sync_button)
        buttons.addWidget(self.run_button)
        root.addLayout(buttons)
        self.apply_button = QPushButton("应用 L / DCR 到功率级")
        self.apply_button.setEnabled(False)
        root.addWidget(self.apply_button)

        self.status = QLabel("等待计算")
        self.status.setWordWrap(True)
        _t = theme.active_theme()
        self.status.setStyleSheet(
            f"padding:6px;border:1px solid {_t.border_card};border-radius:5px;background:{_t.card_bg};color:{_t.text};"
        )
        root.addWidget(self.status)
        root.addStretch(1)

        self.sync_button.clicked.connect(self.sync_from_stage)
        self.run_button.clicked.connect(self.calculate)
        self.apply_button.clicked.connect(self.apply_to_stage)
        self.sync_from_stage()

    @staticmethod
    def _spin(lo: float, hi: float, dec: int, value: float, suffix: str = "") -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi); w.setDecimals(dec); w.setValue(value); w.setSuffix(suffix)
        w.setKeyboardTracking(False)
        return w

    def _material_changed(self) -> None:
        mu = int(self.perm.currentData())
        self.al.setValue(HIGH_FLUX_254_MATERIALS[mu].al_nh_per_t2)

    def _path_changed(self) -> None:
        ferrite = self.material_path.currentData() == "ferrite"
        self.high_flux_group.setVisible(not ferrite)
        self.ferrite_group.setVisible(ferrite)

    def _rebuild_ferrite_cores(self) -> None:
        self.core_db.refresh_user()
        self._ferrite_cores = [
            c for c in self.core_db.cores if c.material_class.casefold() == "ferrite"
        ]

    def _rebuild_ferrite_combo(self) -> None:
        brand_id = self.brand_filter.currentData() if hasattr(self, "brand_filter") else ""
        brand_entry = None
        if brand_id:
            brand_entry = next((b for b in self._taxonomy["brands"] if b["id"] == brand_id), None)
        aliases = set()
        if brand_entry:
            aliases = {brand_entry["display_name"].casefold(), *(a.casefold() for a in brand_entry.get("aliases", []))}
        self.ferrite_core.blockSignals(True)
        self.ferrite_core.clear()
        for core_spec in self._ferrite_cores:
            if aliases and core_spec.manufacturer.casefold() not in aliases and not any(
                a in core_spec.manufacturer.casefold() for a in aliases
            ):
                continue
            origin = "User" if self.core_db.is_user(core_spec.part_number) else "Built-in"
            label = f"[{origin}] {core_spec.manufacturer} {core_spec.part_number} ({core_spec.material})"
            self.ferrite_core.addItem(label, core_spec.part_number)
        self.ferrite_core.blockSignals(False)
        if brand_entry and brand_entry.get("status") == "brand-placeholder" and self.ferrite_core.count() == 0:
            self.brand_status.setText(
                brand_entry.get("note")
                or "No calculable built-in parts for this brand. Add a user core with datasheet evidence."
            )
        else:
            self.brand_status.setText(
                f"{self.ferrite_core.count()} ferrite core(s) listed for this filter."
            )

    def _add_user_core(self) -> None:
        result = _prompt_user_core(self)
        if result is None:
            return
        core, steinmetz = result
        try:
            lib = self.core_db.user_library
            if lib is None:
                raise RuntimeError("user core library unavailable")
            lib.save_steinmetz(steinmetz)
            lib.save_core(core)
            self._rebuild_ferrite_cores()
            self._rebuild_ferrite_combo()
            idx = self.ferrite_core.findData(core.part_number)
            if idx >= 0:
                self.ferrite_core.setCurrentIndex(idx)
        except Exception as exc:
            show_operation_issue(self, "User core save failed", str(exc), critical=False)

    def sync_from_stage(self) -> None:
        context = self.context_provider()
        self.target_l.setValue(float(context["target_inductance_uh"]))
        if "recommended_core_count" in context:
            self.n_cores.setValue(int(context["recommended_core_count"]))
        label = (
            f"Vin={context['input_rms_v']:.4g} V · Vbus={context['bus_voltage_v']:.4g} V\n"
            f"P={context['output_power_w']:.5g} W · fs={context['switching_frequency_hz']/1e3:.4g} kHz"
        )
        self.context_label.setText(label)

    def _request(self) -> PFCInductorDesignRequest:
        context = self.context_provider()
        mu = int(self.perm.currentData())
        material = replace(HIGH_FLUX_254_MATERIALS[mu], al_nh_per_t2=self.al.value())
        core = HighFluxCoreGeometry(
            core_data="254/custom",
            le_mm=self.le.value(), ae_mm2=self.ae.value(), ve_mm3=self.ve.value(),
            od_mm=self.od.value(), id_mm=self.id_.value(), ht_mm=self.ht.value(),
            bs_t=self.bsat.value(),
        )
        return PFCInductorDesignRequest(
            topology=self.topology,
            input_rms_v=float(context["input_rms_v"]),
            bus_voltage_v=float(context["bus_voltage_v"]),
            output_power_w=float(context["output_power_w"]),
            switching_frequency_hz=float(context["switching_frequency_hz"]),
            target_inductance_uh=self.target_l.value(),
            efficiency=self.eff.value(),
            core=core,
            material=material,
            n_cores=self.n_cores.value(),
            wire_copper_diameter_mm=self.wire_d.value(),
            enamel_build_mm=self.enamel.value(),
            target_current_density_a_mm2=self.j_target.value(),
            copper_temperature_c=self.cu_temp.value(),
            max_fill_factor=self.fill.value(),
        )

    def _ferrite_request(self) -> FerriteInductorRequest:
        context = self.context_provider()
        part = str(self.ferrite_core.currentData())
        core = next(c for c in self._ferrite_cores if c.part_number == part)
        steinmetz = self.core_db.get_steinmetz(core.material)
        if steinmetz is None:
            steinmetz = self.core_db.get_steinmetz(core.material_class)
        missing = missing_ferrite_steinmetz_parameters(core.material, steinmetz)
        if missing:
            raise ValueError("Ferrite Steinmetz data missing:\n" + format_missing(missing))
        return FerriteInductorRequest(
            topology=self.topology,
            input_rms_v=float(context["input_rms_v"]),
            bus_voltage_v=float(context["bus_voltage_v"]),
            output_power_w=float(context["output_power_w"]),
            switching_frequency_hz=float(context["switching_frequency_hz"]),
            target_inductance_h=self.target_l.value() * 1e-6,
            efficiency=self.eff.value(),
            core=core,
            steinmetz=steinmetz,
            gap_m=self.gap_mm.value() * 1e-3,
            n_cores=self.n_cores.value(),
            wire_copper_diameter_mm=self.wire_d.value(),
            enamel_build_mm=self.enamel.value(),
            target_current_density_a_mm2=self.j_target.value(),
            copper_temperature_c=self.cu_temp.value(),
            max_fill_factor=self.fill.value(),
            b_peak_limit_t=self.b_limit.value(),
        )

    def calculate(self) -> None:
        try:
            if self.material_path.currentData() == "ferrite":
                result = design_ferrite_pfc_inductor(self._ferrite_request())
            else:
                result = design_pfc_inductor(self._request())
        except Exception as exc:
            show_operation_issue(self, t("PFC 电感设计失败"), str(exc), critical=False)
            return
        self.last_result = result
        self.apply_button.setEnabled(True)
        if isinstance(result, FerriteInductorResult):
            state = "PASS" if result.b_peak_total_t <= result.request.b_peak_limit_t and result.fill_factor <= result.request.max_fill_factor else "CHECK"
            self.status.setText(
                f"{state} · Ferrite N={result.turns}T · L={result.inductance_h*1e6:.3f}µH · "
                f"Bpk={result.b_peak_total_t:.3f}T · Pind={result.total_inductor_loss_w:.3f}W"
            )
        else:
            state = "PASS" if result.inductance_target_met and result.window_ok else "CHECK"
            self.status.setText(
                f"{state} · N={result.turns}T · {result.parallel_wires}×{result.request.wire_copper_diameter_mm:.3g}mm · "
                f"L(full)={result.l_full_load_peak_uh:.3f}µH · PΣ={result.total_loss_w:.3f}W"
            )
        self.status.setStyleSheet(
            "padding:6px;border:1px solid #75e0a7;border-radius:5px;background:#ecfdf3;color:#067647;"
            if state == "PASS" else
            "padding:6px;border:1px solid #fec84b;border-radius:5px;background:#fffaeb;color:#b54708;"
        )
        self.design_completed.emit(result)

    def apply_to_stage(self) -> None:
        if self.last_result is None:
            return
        self.apply_callback(self.last_result)


class PFCInductorDesignResultView(QWidget):
    """Summary + L(I), line ripple/core-loss and loss-breakdown plots."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(5)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(190)
        self.summary.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.summary.setPlainText("尚未计算电感。左侧进入“电感设计”，然后点击“计算电感”。")
        root.addWidget(self.summary)
        self.figure = Figure(figsize=(11, 7))
        self.canvas = FigureCanvasQTAgg(self.figure)
        root.addWidget(self.canvas, 1)

    def set_result(self, result) -> None:
        if isinstance(result, FerriteInductorResult):
            req = result.request
            warn = "\n".join(f"  - {w}" for w in result.warnings)
            self.summary.setPlainText(
                f"{self.title}\n"
                f"Path      : Ferrite gapped + Steinmetz (powder dc_bias NOT used)\n"
                f"Core      : {req.core.manufacturer} {req.core.part_number} ({req.core.material}), cores={req.n_cores}\n"
                f"Gap / AL  : lg={req.gap_m*1e3:.3f} mm, AL≈{result.al_nH_per_t2:.3f} nH/T², Leff_gap={result.effective_gap_m*1e3:.3f} mm\n"
                f"Winding   : N={result.turns} T, {result.parallel_wires} × Ø{req.wire_copper_diameter_mm:.3f} mm, fill={100*result.fill_factor:.2f}%\n"
                f"Inductance: L={result.inductance_h*1e6:.3f} µH (target {req.target_inductance_h*1e6:.3f} µH)\n"
                f"Current   : Irms={result.phase_current_rms_a:.3f} A, Ipk={result.phase_current_peak_a:.3f} A, ΔIpp={result.ripple_pp_a:.3f} A\n"
                f"Flux      : Bac={result.bac_peak_t:.4f} T, Bdc={result.bdc_t:.4f} T, Bpeak={result.b_peak_total_t:.4f} T (limit {req.b_peak_limit_t:.3f} T)\n"
                f"Inductor loss (component only): Pcore={result.core_loss_w:.3f} W, Pcu={result.copper_loss_w:.3f} W, PΣ={result.total_inductor_loss_w:.3f} W\n"
                f"Note      : inductor-self loss above is NOT the converter system loss\n"
                f"Warnings:\n{warn}"
            )
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            labels = ["Core", "Copper", "Inductor Σ"]
            values = [result.core_loss_w, result.copper_loss_w, result.total_inductor_loss_w]
            ax.bar(labels, values)
            ax.set_title("Ferrite inductor-self loss (not system loss)")
            ax.set_ylabel("Loss (W)")
            ax.grid(True, axis="y", alpha=0.3)
            self.figure.suptitle(self.title)
            self.figure.tight_layout()
            self.canvas.draw_idle()
            return

        req = result.request
        warn = "\n".join(f"  - {w}" for w in result.warnings)
        self.summary.setPlainText(
            f"{self.title}\n"
            f"Core      : Magnetics High Flux 254/custom, μ={req.material.permeability}, AL={req.material.al_nh_per_t2:.3f} nH/T², cores={req.n_cores}\n"
            f"Geometry  : Le={req.core.le_mm:.3f} mm, Ae={req.core.ae_mm2:.3f} mm², Ve={req.core.ve_mm3:.1f} mm³, OD/ID/HT={req.core.od_mm:.2f}/{req.core.id_mm:.2f}/{req.core.ht_mm:.2f} mm\n"
            f"Winding   : N={result.turns} T, {result.parallel_wires} × Ø{req.wire_copper_diameter_mm:.3f} mm enamel Cu, Cu area={result.copper_area_mm2:.3f} mm², fill={100*result.fill_factor:.2f}%\n"
            f"Inductance: L0={result.l_no_bias_uh:.3f} µH, L@full-peak={result.l_full_load_peak_uh:.3f} µH, drop={result.l_drop_percent:.2f}%\n"
            f"Current   : Iphase,rms={result.phase_current_rms_a:.3f} A, Irms+ripple={result.total_current_rms_with_ripple_a:.3f} A, Ipk={result.full_load_peak_with_ripple_a:.3f} A\n"
            f"Bias      : Hpk={result.h_peak_oe:.3f} Oe, μ/μi={result.permeability_at_peak_percent:.2f}%, Bdc≈{result.b_dc_approx_peak_t:.4f} T, Bac,max={result.b_ac_line_max_t:.4f} T\n"
            f"Copper    : R20={1e3*result.rdc_20_ohm:.3f} mΩ, Rhot={1e3*result.rdc_hot_ohm:.3f} mΩ, J={result.current_density_a_mm2:.3f} A/mm², Pcu={result.copper_loss_w:.3f} W\n"
            f"Core loss : {result.core_loss_w:.3f} W (Magnetics High Flux fit, line-cycle average)\n"
            f"Inductor-self total: {result.total_loss_w:.3f} W (not converter system loss)\n"
            f"Warnings:\n{warn}"
        )

        self.figure.clear()
        ax_l = self.figure.add_subplot(221)
        ax_ripple = self.figure.add_subplot(222)
        ax_core = self.figure.add_subplot(223)
        ax_loss = self.figure.add_subplot(224)

        ax_l.plot(result.current_a, result.inductance_uh, linewidth=2.0)
        ax_l.axhline(req.target_inductance_uh, linestyle="--", linewidth=1.0, label="Target L")
        ax_l.scatter([result.full_load_peak_with_ripple_a], [result.l_full_load_peak_uh], s=35, zorder=5, label="Full-load peak")
        ax_l.set_title("Inductance droop vs current")
        ax_l.set_xlabel("Current (A)"); ax_l.set_ylabel("L (µH)"); ax_l.grid(True, alpha=.3); ax_l.legend(fontsize=8)

        ax_ripple.plot(result.line_angle_deg, result.line_ripple_pp_a)
        ax_ripple.set_title("Switching ripple over line cycle")
        ax_ripple.set_xlabel("Line angle (deg)"); ax_ripple.set_ylabel("ΔIpp (A)"); ax_ripple.grid(True, alpha=.3)

        ax_core.plot(result.line_angle_deg, result.line_core_loss_w, label="Core loss")
        ax_core2 = ax_core.twinx()
        ax_core2.plot(result.line_angle_deg, result.line_b_ac_t, linestyle="--", label="Bac")
        ax_core.set_title("Core loss / AC flux over line cycle")
        ax_core.set_xlabel("Line angle (deg)"); ax_core.set_ylabel("Core loss (W)"); ax_core2.set_ylabel("Bac (T)")
        ax_core.grid(True, alpha=.3)

        labels = ["Core", "Copper", "Inductor Σ"]
        values = [result.core_loss_w, result.copper_loss_w, result.total_loss_w]
        ax_loss.bar(labels, values)
        ax_loss.set_title("Inductor-self loss breakdown")
        ax_loss.set_ylabel("Loss (W)"); ax_loss.grid(True, axis="y", alpha=.3)
        for idx, value in enumerate(values):
            ax_loss.text(idx, value, f"{value:.2f}", ha="center", va="bottom", fontsize=8)

        self.figure.suptitle(self.title)
        self.figure.tight_layout()
        self.canvas.draw_idle()


__all__ = ["PFCInductorDesignEditor", "PFCInductorDesignResultView"]
