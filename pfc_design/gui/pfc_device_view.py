"""PFC MOSFET library editor and TTPL semiconductor loss comparison UI."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pfc_design.core.spec import MosfetSpec
from pfc_design.engineering import (
    PFCDeviceDatabase,
    TTPLDesignResult,
    compare_ttpl_devices,
)
from pfc_design.gui.pfc_loss_summary import PFCDeviceLossRollup
from power_control_tools.part_validation import format_missing, missing_pfc_mosfet_loss_parameters


_NUMERIC_FIELDS = (
    ("vds_max", "VDS max", " V", 1.0, 1.0, 5000.0, 1),
    ("id_25c", "ID @25°C", " A", 1.0, 0.1, 2000.0, 2),
    ("id_100c", "ID @100°C", " A", 1.0, 0.1, 2000.0, 2),
    ("rds_on_25c", "RDS(on) @25°C", " mΩ", 1e3, 0.001, 5000.0, 3),
    ("rds_on_150c", "RDS(on) @150°C", " mΩ", 1e3, 0.001, 10000.0, 3),
    ("rds_alpha", "RDS alpha", " /°C", 1.0, 0.0, 0.1, 6),
    ("qg_nc", "Qg", " nC", 1.0, 0.001, 10000.0, 3),
    ("coss_er_pF", "Coss energy-equivalent", " pF", 1.0, 0.001, 1e7, 3),
    ("tr_ns", "tr", " ns", 1.0, 0.001, 1e5, 3),
    ("tf_ns", "tf", " ns", 1.0, 0.001, 1e5, 3),
    ("vgs", "Gate voltage", " V", 1.0, 0.1, 30.0, 2),
    ("eon_ref_uj", "Eon reference", " µJ", 1.0, 0.0, 1e7, 3),
    ("eoff_ref_uj", "Eoff reference", " µJ", 1.0, 0.0, 1e7, 3),
    ("e_ref_v", "Switch-energy reference V", " V", 1.0, 0.001, 5000.0, 2),
    ("e_ref_i", "Switch-energy reference I", " A", 1.0, 0.001, 2000.0, 2),
    ("price_usd", "Reference price", " USD", 1.0, 0.0, 100000.0, 3),
)


def _new_device_default() -> MosfetSpec:
    return MosfetSpec(
        manufacturer="User",
        part_number="USER_PFC_650V_NEW",
        technology="SiC",
        vds_max=650.0,
        id_25c=50.0,
        id_100c=35.0,
        rds_on_25c=0.045,
        rds_on_150c=0.075,
        rds_alpha=0.0045,
        qg_nc=60.0,
        coss_er_pF=100.0,
        tr_ns=15.0,
        tf_ns=10.0,
        vgs=15.0,
        package="USER",
        eon_ref_uj=70.0,
        eoff_ref_uj=40.0,
        e_ref_v=400.0,
        e_ref_i=20.0,
    )


class PFCDeviceEditDialog(QDialog):
    def __init__(
        self,
        device: MosfetSpec | None = None,
        *,
        lock_part_number: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.original = device or _new_device_default()
        self.setWindowTitle("PFC MOSFET — Device Parameters")
        self.resize(560, 760)
        root = QVBoxLayout(self)

        note = QLabel(
            "Enter values from one controlled datasheet revision and keep the reference conditions consistent. "
            "The current loss model uses single-point RDS/Coss/Eon/Eoff approximations and is not a hardware sign-off model."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()
        self.manufacturer = QLineEdit(self.original.manufacturer)
        self.part_number = QLineEdit(self.original.part_number)
        self.part_number.setReadOnly(lock_part_number)
        self.technology = QLineEdit(self.original.technology)
        self.package = QLineEdit(self.original.package)
        form.addRow("Manufacturer", self.manufacturer)
        form.addRow("Part number", self.part_number)
        form.addRow("Technology", self.technology)
        form.addRow("Package", self.package)
        self.numeric: dict[str, tuple[QDoubleSpinBox, float]] = {}
        for key, label, suffix, scale, lo, hi, decimals in _NUMERIC_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(decimals)
            spin.setSuffix(suffix)
            spin.setKeyboardTracking(False)
            spin.setValue(float(getattr(self.original, key)) * scale)
            self.numeric[key] = (spin, scale)
            form.addRow(label, spin)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_checked(self) -> None:
        if not self.part_number.text().strip():
            QMessageBox.warning(self, "PFC Device Library", "Part number must not be empty.")
            return
        if self.numeric["rds_on_150c"][0].value() < 0.5 * self.numeric["rds_on_25c"][0].value():
            QMessageBox.warning(
                self,
                "PFC Device Library",
                "RDS(on) @150°C is unexpectedly far below the 25°C value; verify the entry.",
            )
            return
        device = self.device()
        missing = missing_pfc_mosfet_loss_parameters(device)
        if missing:
            QMessageBox.warning(
                self,
                "Missing loss parameters",
                "Cannot save until loss-model fields are complete:\n" + format_missing(missing),
            )
            return
        self.accept()

    def device(self) -> MosfetSpec:
        changes = {
            key: spin.value() / scale
            for key, (spin, scale) in self.numeric.items()
        }
        return replace(
            self.original,
            manufacturer=self.manufacturer.text().strip() or "User",
            part_number=self.part_number.text().strip(),
            technology=self.technology.text().strip() or "MOSFET",
            package=self.package.text().strip() or "USER",
            **changes,
        )


class PFCDeviceLibraryDialog(QDialog):
    """Persistent PFC MOSFET library shared by TTPL/Vienna engineering pages."""

    def __init__(self, database: PFCDeviceDatabase, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("PFC Device Library")
        self.resize(1180, 700)
        root = QVBoxLayout(self)

        path = QLabel(f"User library: {database.user_path}")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(path)
        note = QLabel(
            "Built-in PFC part records are read-only and currently classified as unverified engineering data. "
            "Clone a record or create a user record before editing, and verify the source datasheet before hardware release."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Part",
                "Manufacturer",
                "Technology",
                "VDS",
                "RDS 25°C",
                "RDS 150°C",
                "Qg",
                "Coss(eq)",
                "Package",
                "Origin",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._edit_selected)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        for text, callback in (
            ("New", self._new_device),
            ("Edit", self._edit_selected),
            ("Clone", self._clone_selected),
            ("Delete User Device", self._delete_selected),
            ("Import JSON", self._import_json),
            ("Export User JSON", self._export_json),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        self.database.refresh()
        self.table.setRowCount(len(self.database.all))
        for row, device in enumerate(self.database.all):
            values = (
                device.part_number,
                device.manufacturer,
                device.technology,
                f"{device.vds_max:.0f} V",
                f"{device.rds_on_25c*1e3:.3f} mΩ",
                f"{device.rds_on_150c*1e3:.3f} mΩ",
                f"{device.qg_nc:.1f} nC",
                f"{device.coss_er_pF:.1f} pF",
                device.package,
                "User" if self.database.is_user(device.part_number) else "Built-in / unverified",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, device.part_number)
                self.table.setItem(row, col, item)
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _selected(self) -> MosfetSpec | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        part = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            return self.database.get(str(part))
        except KeyError:
            return None

    def _new_device(self) -> None:
        dialog = PFCDeviceEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(dialog.device())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "PFC Device Library", str(exc))

    def _edit_selected(self, *_args) -> None:
        device = self._selected()
        if device is None:
            return
        if not self.database.is_user(device.part_number):
            QMessageBox.information(
                self,
                "PFC Device Library",
                "Built-in records are read-only. Use Clone to create an editable user record.",
            )
            return
        dialog = PFCDeviceEditDialog(device, lock_part_number=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(dialog.device(), overwrite=True)
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "PFC Device Library", str(exc))

    def _clone_selected(self) -> None:
        device = self._selected()
        if device is None:
            return
        clone = replace(device, part_number=f"USER_{device.part_number}")
        dialog = PFCDeviceEditDialog(clone, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(dialog.device())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "PFC Device Library", str(exc))

    def _delete_selected(self) -> None:
        device = self._selected()
        if device is None:
            return
        if not self.database.is_user(device.part_number):
            QMessageBox.information(
                self, "PFC Device Library", "Built-in records cannot be deleted."
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete User Device",
            f"Delete '{device.part_number}' from the persistent PFC user library?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.database.delete_user_device(device.part_number)
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "PFC Device Library", str(exc))

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PFC Device Library", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            count = self.database.import_user_library(path, overwrite=True)
            self.refresh()
            QMessageBox.information(
                self, "PFC Device Library", f"Imported {count} user MOSFET records."
            )
        except Exception as exc:
            QMessageBox.critical(self, "PFC Device Library", str(exc))

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PFC User Device Library",
            "power_design_pfc_devices.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            target = self.database.export_user_library(Path(path))
            QMessageBox.information(
                self, "PFC Device Library", f"Exported user library to:\n{target}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "PFC Device Library", str(exc))


class TTPLDeviceLossView(QWidget):
    """Compare HF-leg and line-frequency-leg MOSFETs at one TTPL work point."""

    def __init__(
        self,
        design: TTPLDesignResult | None = None,
        database: PFCDeviceDatabase | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.database = database or PFCDeviceDatabase()
        self.design = design

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        header = QHBoxLayout()
        title = QLabel("TTPL Devices / Loss Compare")
        title.setStyleSheet("font-size:16px;font-weight:650;")
        header.addWidget(title)
        header.addStretch(1)

        self.workpoint = QComboBox()
        self.workpoint.addItem("Low line", "low")
        self.workpoint.addItem("Nominal", "nominal")
        self.workpoint.addItem("High line", "high")
        self.tj = self._spin(25.0, 150.0, 1, 100.0, " °C")
        self.deadtime = self._spin(0.0, 2000.0, 1, 100.0, " ns")
        self.reverse_drop = self._spin(0.0, 10.0, 3, 2.0, " V")
        self.derating = self._spin(0.10, 1.0, 3, 0.80)
        for label, widget in (
            ("Workpoint", self.workpoint),
            ("Tj", self.tj),
            ("Deadtime", self.deadtime),
            ("Reverse drop", self.reverse_drop),
            ("VDS derating", self.derating),
        ):
            header.addWidget(QLabel(label))
            header.addWidget(widget)
        self.library_button = QPushButton("Device Library…")
        self.refresh_button = QPushButton("Refresh Compare")
        header.addWidget(self.library_button)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        self.note = QLabel(
            "HF comparison assumes the same MOSFET is used for active and synchronous devices in the fast half-bridge. "
            "Built-in part data are screening inputs only; Eon/Eoff are linearly scaled in V/I and Coss may overlap datasheet switching energy."
        )
        self.note.setWordWrap(True)
        root.addWidget(self.note)

        self.summary = QLabel("Run Power Stage / Sizing first.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        pick = QHBoxLayout()
        pick.addWidget(QLabel("HF pick"))
        self.hf_pick = QComboBox()
        pick.addWidget(self.hf_pick, 1)
        pick.addWidget(QLabel("Slow pick"))
        self.slow_pick = QComboBox()
        pick.addWidget(self.slow_pick, 1)
        root.addLayout(pick)
        self.rollup_text = QPlainTextEdit()
        self.rollup_text.setReadOnly(True)
        self.rollup_text.setMaximumHeight(220)
        self.rollup_text.setPlainText("Select HF/Slow devices after comparison to build the loss rollup.")
        root.addWidget(self.rollup_text)

        tabs = QTabWidget()
        self.hf_table = self._table(
            [
                "Device",
                "Origin",
                "Tech",
                "RDS hot",
                "Pactive cond",
                "Pactive sw",
                "PSR cond",
                "PSR sw",
                "Pdead",
                "PCoss",
                "Pgate",
                "Total",
                "VDS",
                "ID",
            ]
        )
        self.slow_table = self._table(
            [
                "Device",
                "Origin",
                "Tech",
                "RDS hot",
                "Pcond",
                "Pgate",
                "Total",
                "VDS",
                "ID",
            ]
        )
        tabs.addTab(self.hf_table, "HF Half-Bridge")
        tabs.addTab(self.slow_table, "Line-Frequency Leg")
        root.addWidget(tabs, 1)

        self.refresh_button.clicked.connect(self.refresh)
        self.library_button.clicked.connect(self._open_library)
        self.workpoint.currentIndexChanged.connect(self.refresh)
        self.tj.valueChanged.connect(self.refresh)
        self.deadtime.valueChanged.connect(self.refresh)
        self.reverse_drop.valueChanged.connect(self.refresh)
        self.derating.valueChanged.connect(self.refresh)
        self.hf_pick.currentIndexChanged.connect(self._update_rollup)
        self.slow_pick.currentIndexChanged.connect(self._update_rollup)
        self._last_comparison = None
        self._inductor_self_loss_w: float | None = None
        if self.design is not None:
            self.refresh()

    @staticmethod
    def _spin(lo: float, hi: float, decimals: int, value: float, suffix: str = "") -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        return spin

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def set_design_result(self, result: TTPLDesignResult) -> None:
        self.design = result
        self.refresh()

    def _open_library(self) -> None:
        dialog = PFCDeviceLibraryDialog(self.database, self)
        dialog.exec()
        self.database.refresh()
        self.refresh()

    def set_inductor_self_loss(self, loss_w: float | None) -> None:
        self._inductor_self_loss_w = None if loss_w is None else float(loss_w)
        self._update_rollup()

    def refresh(self, *_args) -> None:
        if self.design is None:
            self.summary.setText("Run Power Stage / Sizing first.")
            self.hf_table.setRowCount(0)
            self.slow_table.setRowCount(0)
            self.hf_pick.clear()
            self.slow_pick.clear()
            self.rollup_text.setPlainText("Run Power Stage / Sizing first.")
            self._last_comparison = None
            return
        try:
            comparison = compare_ttpl_devices(
                self.design,
                self.database,
                workpoint=str(self.workpoint.currentData()),
                junction_temperature_c=self.tj.value(),
                deadtime_s=self.deadtime.value() * 1e-9,
                reverse_drop_v=self.reverse_drop.value(),
                voltage_derating=self.derating.value(),
            )
        except Exception as exc:
            self.summary.setText(f"Device comparison failed: {exc}")
            return

        self._last_comparison = comparison
        self.summary.setText(
            f"Vin={comparison.vin_rms_v:.2f} Vrms · Vbus={comparison.design.spec.bus_voltage_v:.1f} V · "
            f"Pout={comparison.design.spec.output_power_w/1000:.3f} kW · fs={comparison.design.spec.switching_frequency_hz/1e3:.2f} kHz · "
            f"Tj={comparison.junction_temperature_c:.1f} °C · user library={self.database.user_path}"
        )

        self.hf_table.setRowCount(len(comparison.hf_devices))
        self.hf_pick.blockSignals(True)
        self.hf_pick.clear()
        for row, loss in enumerate(comparison.hf_devices):
            d = loss.device
            values = (
                d.part_number,
                "User" if self.database.is_user(d.part_number) else "Built-in*",
                d.technology,
                f"{loss.rds_hot_ohm*1e3:.2f} mΩ",
                f"{loss.active_conduction_w:.3f}",
                f"{loss.active_switching_w:.3f}",
                f"{loss.sr_conduction_w:.3f}",
                f"{loss.sr_switching_w:.3f}",
                f"{loss.deadtime_reverse_w:.3f}",
                f"{loss.coss_w:.3f}",
                f"{loss.gate_drive_w:.3f}",
                f"{loss.total_w:.3f} W",
                "PASS" if loss.voltage_ok else "FAIL",
                "PASS" if loss.current_ok else "FAIL",
            )
            for col, value in enumerate(values):
                self.hf_table.setItem(row, col, QTableWidgetItem(value))
            self.hf_pick.addItem(f"{d.part_number} · {loss.total_w:.3f} W", loss)
        self.hf_pick.blockSignals(False)

        self.slow_table.setRowCount(len(comparison.slow_devices))
        self.slow_pick.blockSignals(True)
        self.slow_pick.clear()
        for row, loss in enumerate(comparison.slow_devices):
            d = loss.device
            values = (
                d.part_number,
                "User" if self.database.is_user(d.part_number) else "Built-in*",
                d.technology,
                f"{loss.rds_hot_ohm*1e3:.2f} mΩ",
                f"{loss.conduction_w:.3f}",
                f"{loss.gate_drive_w:.6f}",
                f"{loss.total_w:.3f} W",
                "PASS" if loss.voltage_ok else "FAIL",
                "PASS" if loss.current_ok else "FAIL",
            )
            for col, value in enumerate(values):
                self.slow_table.setItem(row, col, QTableWidgetItem(value))
            self.slow_pick.addItem(f"{d.part_number} · {loss.total_w:.3f} W", loss)
        self.slow_pick.blockSignals(False)
        self._update_rollup()

    def _update_rollup(self, *_args) -> None:
        comparison = self._last_comparison
        hf = self.hf_pick.currentData()
        slow = self.slow_pick.currentData()
        if comparison is None or hf is None or slow is None:
            self.rollup_text.setPlainText("Select HF and Slow devices to build the loss rollup.")
            return
        rollup = PFCDeviceLossRollup(
            workpoint=comparison.workpoint,
            vin_rms_v=comparison.vin_rms_v,
            hf=hf,
            slow=slow,
            inductor_self_loss_w=self._inductor_self_loss_w,
        )
        self.rollup_text.setPlainText(rollup.format_text())

__all__ = [
    "PFCDeviceEditDialog",
    "PFCDeviceLibraryDialog",
    "TTPLDeviceLossView",
]
