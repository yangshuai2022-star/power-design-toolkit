"""LLC MOSFET library editor and fast device-comparison dialogs."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.operating_point import solve_operating_point
from ..core.spec import LLCDesignSpec, MosfetSpec
from ..core.tank import design_tank
from ..models.devices import DeviceDatabase, DeviceRole
from ..models.primary_bridge import primary_bridge_loss
from ..models.synchronous_rectifier import synchronous_rectifier_loss
from power_control_tools.part_validation import format_missing, missing_llc_mosfet_loss_parameters


_DEVICE_NUMERIC_FIELDS = (
    ("vds_max_v", "VDS max", " V", 1.0, 1.0, 5000.0, 2),
    ("id_cont_a", "ID continuous", " A", 1.0, 0.1, 2000.0, 2),
    ("rds_on_25_ohm", "RDS(on) @25°C", " mΩ", 1e3, 0.001, 5000.0, 4),
    ("rds_on_hot_ohm", "RDS(on) @hot", " mΩ", 1e3, 0.001, 10000.0, 4),
    ("hot_temperature_c", "Hot temperature", " °C", 1.0, 25.0, 250.0, 1),
    ("qg_c", "Qg", " nC", 1e9, 0.001, 10000.0, 3),
    ("coss_er_f", "Coss effective", " pF", 1e12, 0.001, 1e7, 3),
    ("qoss_c", "Qoss", " nC", 1e9, 0.001, 1e6, 3),
    ("eoff_ref_j", "Eoff reference", " µJ", 1e6, 0.0, 1e7, 3),
    ("eoff_ref_v", "Eoff reference VDS", " V", 1.0, 0.001, 5000.0, 2),
    ("eoff_ref_i", "Eoff reference ID", " A", 1.0, 0.001, 2000.0, 2),
    ("gate_voltage_v", "Gate voltage", " V", 1.0, 0.1, 30.0, 2),
    ("body_diode_vf_v", "Body-diode / 3rd-Q Vf", " V", 1.0, 0.0, 10.0, 3),
    ("qrr_c", "Qrr", " nC", 1e9, 0.0, 1e6, 3),
    ("trr_s", "trr", " ns", 1e9, 0.0, 1e6, 3),
    ("qrr_ref_i_a", "Qrr reference current", " A", 1.0, 0.001, 2000.0, 2),
    ("third_quadrant_rds_factor", "3rd-Q RDS factor", "", 1.0, 0.1, 10.0, 4),
    ("third_quadrant_v_offset_v", "3rd-Q voltage offset", " V", 1.0, 0.0, 10.0, 4),
    ("price_usd", "Reference price", " USD", 1.0, 0.0, 100000.0, 3),
)


def _generic_default(role: DeviceRole) -> MosfetSpec:
    if role == "primary":
        return MosfetSpec(
            part_number="USER_PRIMARY_NEW",
            technology="User 650 V MOSFET",
            vds_max_v=650.0,
            id_cont_a=40.0,
            rds_on_25_ohm=0.05,
            rds_on_hot_ohm=0.09,
            hot_temperature_c=150.0,
            qg_c=80e-9,
            coss_er_f=150e-12,
            qoss_c=100e-9,
            eoff_ref_j=80e-6,
            eoff_ref_v=400.0,
            eoff_ref_i=20.0,
            gate_voltage_v=15.0,
            body_diode_vf_v=1.5,
            package="USER",
        )
    return MosfetSpec(
        part_number="USER_SR_NEW",
        technology="User low-voltage SR MOSFET",
        vds_max_v=100.0,
        id_cont_a=150.0,
        rds_on_25_ohm=0.0025,
        rds_on_hot_ohm=0.0045,
        hot_temperature_c=125.0,
        qg_c=90e-9,
        coss_er_f=2e-9,
        qoss_c=250e-9,
        eoff_ref_j=7e-6,
        eoff_ref_v=53.0,
        eoff_ref_i=50.0,
        gate_voltage_v=10.0,
        body_diode_vf_v=0.8,
        qrr_c=130e-9,
        trr_s=50e-9,
        qrr_ref_i_a=50.0,
        third_quadrant_rds_factor=1.18,
        third_quadrant_v_offset_v=0.03,
        package="USER",
    )


class DeviceEditDialog(QDialog):
    def __init__(self, role: DeviceRole, device: MosfetSpec | None = None,
                 *, lock_part_number: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.role = role
        self.original = device or _generic_default(role)
        self.setWindowTitle(f"{'Primary' if role == 'primary' else 'SR'} MOSFET — Device Parameters")
        self.resize(540, 760)
        root = QVBoxLayout(self)
        note = QLabel(
            "Enter datasheet values at the same reference conditions used by the source. "
            "Single-point Coss/Qoss/Eoff values remain an engineering approximation; verify curves before hardware release."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()
        self.part_number = QLineEdit(self.original.part_number)
        self.part_number.setReadOnly(lock_part_number)
        self.technology = QLineEdit(self.original.technology)
        self.package = QLineEdit(self.original.package)
        form.addRow("Part number", self.part_number)
        form.addRow("Technology / description", self.technology)
        form.addRow("Package", self.package)
        self.numeric: dict[str, tuple[QDoubleSpinBox, float]] = {}
        for key, label, suffix, scale, minimum, maximum, decimals in _DEVICE_NUMERIC_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(decimals)
            spin.setSuffix(suffix)
            spin.setKeyboardTracking(False)
            spin.setValue(float(getattr(self.original, key)) * scale)
            self.numeric[key] = (spin, scale)
            form.addRow(label, spin)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_checked(self) -> None:
        if not self.part_number.text().strip():
            QMessageBox.warning(self, "Device Parameters", "Part number must not be empty.")
            return
        if self.numeric["rds_on_hot_ohm"][0].value() < self.numeric["rds_on_25_ohm"][0].value() * 0.5:
            QMessageBox.warning(self, "Device Parameters", "Hot RDS(on) is unexpectedly below the 25°C value; verify the datasheet entry.")
            return
        device = self.device()
        missing = missing_llc_mosfet_loss_parameters(device)
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
            part_number=self.part_number.text().strip(),
            technology=self.technology.text().strip() or "User MOSFET",
            package=self.package.text().strip() or "USER",
            **changes,
        )


class DeviceLibraryDialog(QDialog):
    def __init__(self, database: DeviceDatabase, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("LLC Device Library")
        self.resize(1120, 680)
        root = QVBoxLayout(self)
        path_label = QLabel(f"User library: {database.user_path}")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(path_label)
        note = QLabel(
            "Built-in devices are generic engineering references and are read-only. "
            "Clone one or create a new user record for a selected real MOSFET."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.tabs = QTabWidget()
        self.tables: dict[DeviceRole, QTableWidget] = {}
        for role, title in (("primary", "Primary MOSFET"), ("sr", "SR MOSFET")):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            table = QTableWidget(0, 8)
            table.setHorizontalHeaderLabels([
                "Part", "Technology", "VDS", "RDS 25°C", "RDS hot", "Qg", "Qoss", "Origin"
            ])
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
            table.doubleClicked.connect(self._edit_selected)
            self.tables[role] = table
            page_layout.addWidget(table)
            self.tabs.addTab(page, title)
        root.addWidget(self.tabs, 1)

        row = QHBoxLayout()
        for label, callback in (
            ("New", self._new_device),
            ("Edit", self._edit_selected),
            ("Clone", self._clone_selected),
            ("Delete User Device", self._delete_selected),
            ("Import JSON", self._import_json),
            ("Export User JSON", self._export_json),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)
        self.refresh()

    def current_role(self) -> DeviceRole:
        return "primary" if self.tabs.currentIndex() == 0 else "sr"

    def _records(self, role: DeviceRole) -> list[MosfetSpec]:
        return self.database.primary if role == "primary" else self.database.sr

    def refresh(self) -> None:
        self.database.refresh()
        for role, table in self.tables.items():
            records = self._records(role)
            table.setRowCount(len(records))
            for row, device in enumerate(records):
                values = (
                    device.part_number,
                    device.technology,
                    f"{device.vds_max_v:.0f} V",
                    f"{device.rds_on_25_ohm*1e3:.3f} mΩ",
                    f"{device.rds_on_hot_ohm*1e3:.3f} mΩ",
                    f"{device.qg_c*1e9:.1f} nC",
                    f"{device.qoss_c*1e9:.1f} nC",
                    "User" if self.database.is_user(role, device.part_number) else "Built-in reference",
                )
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, device.part_number)
                    table.setItem(row, col, item)
            if records and table.currentRow() < 0:
                table.selectRow(0)

    def _selected(self, role: DeviceRole | None = None) -> MosfetSpec | None:
        role = role or self.current_role()
        table = self.tables[role]
        row = table.currentRow()
        if row < 0:
            return None
        part = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            return self.database.get_primary(part) if role == "primary" else self.database.get_sr(part)
        except KeyError:
            return None

    def _new_device(self) -> None:
        role = self.current_role()
        dialog = DeviceEditDialog(role, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(role, dialog.device())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Device Library", str(exc))

    def _edit_selected(self, *_args) -> None:
        role = self.current_role()
        device = self._selected(role)
        if device is None:
            return
        if not self.database.is_user(role, device.part_number):
            QMessageBox.information(self, "Device Library", "Built-in references are read-only. Use Clone to create an editable user record.")
            return
        dialog = DeviceEditDialog(role, device, lock_part_number=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(role, dialog.device(), overwrite=True)
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Device Library", str(exc))

    def _clone_selected(self) -> None:
        role = self.current_role()
        device = self._selected(role)
        if device is None:
            return
        clone = replace(device, part_number=f"USER_{device.part_number}")
        dialog = DeviceEditDialog(role, clone, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.save_user_device(role, dialog.device())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Device Library", str(exc))

    def _delete_selected(self) -> None:
        role = self.current_role()
        device = self._selected(role)
        if device is None:
            return
        if not self.database.is_user(role, device.part_number):
            QMessageBox.information(self, "Device Library", "Built-in reference devices cannot be deleted.")
            return
        answer = QMessageBox.question(
            self, "Delete User Device", f"Delete '{device.part_number}' from the user library?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.database.delete_user_device(role, device.part_number)
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Device Library", str(exc))

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Device Library", "", "JSON (*.json)")
        if not path:
            return
        try:
            primary_count, sr_count = self.database.import_user_library(path, overwrite=True)
            self.refresh()
            QMessageBox.information(self, "Device Library", f"Imported {primary_count} primary and {sr_count} SR user records.")
        except Exception as exc:
            QMessageBox.critical(self, "Device Library", str(exc))

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export User Device Library", "power_design_devices.json", "JSON (*.json)")
        if not path:
            return
        try:
            target = self.database.export_user_library(Path(path))
            QMessageBox.information(self, "Device Library", f"Exported user library to:\n{target}")
        except Exception as exc:
            QMessageBox.critical(self, "Device Library", str(exc))


class DeviceCompareDialog(QDialog):
    """Compare all built-in/user devices at the current nominal LLC workpoint."""

    def __init__(self, spec: LLCDesignSpec, database: DeviceDatabase, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LLC Device Compare — nominal full load")
        self.resize(1250, 700)
        root = QVBoxLayout(self)
        tank = design_tank(spec)
        op = solve_operating_point(spec, tank, spec.vbus_nom_v, 1.0)
        note = QLabel(
            f"Comparison workpoint: Vbus={spec.vbus_nom_v:.1f} V, load=100%, fs={op.switching_frequency_hz/1e3:.3f} kHz. "
            "Losses use the current single-point engineering model; use real datasheet curves/hardware data for release decisions."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        tabs = QTabWidget()
        tabs.addTab(self._primary_table(spec, tank, op, database), "Primary MOSFET")
        tabs.addTab(self._sr_table(spec, op, database), "SR MOSFET")
        root.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _primary_table(self, spec, tank, op, database: DeviceDatabase) -> QTableWidget:
        table = self._table([
            "Device", "Origin", "RDS hot", "Pcond", "Poff", "Pgate", "PCoss", "Pdead", "Total", "ZVS Q", "ZVS E", "VDS OK"
        ])
        table.setRowCount(len(database.primary))
        for row, device in enumerate(database.primary):
            loss = primary_bridge_loss(spec, tank, op, device)
            voltage_ok = loss.voltage_stress_v <= device.vds_max_v * spec.primary_voltage_derating
            values = (
                device.part_number,
                "User" if database.is_user("primary", device.part_number) else "Built-in",
                f"{device.rds_at(spec.primary_junction_temperature_c)*1e3:.3f} mΩ",
                f"{loss.conduction_w:.3f} W",
                f"{loss.turnoff_w:.3f} W",
                f"{loss.gate_drive_w:.3f} W",
                f"{loss.residual_coss_w:.3f} W",
                f"{loss.deadtime_diode_w:.3f} W",
                f"{loss.total_w:.3f} W",
                f"{loss.zvs_charge_margin:.3f}",
                f"{loss.zvs_energy_margin:.3f}",
                "PASS" if voltage_ok else "FAIL",
            )
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        table.sortItems(8, Qt.SortOrder.AscendingOrder)
        return table

    def _sr_table(self, spec, op, database: DeviceDatabase) -> QTableWidget:
        table = self._table([
            "Device", "Origin", "RDS hot", "Pcond", "Pdead", "Poff", "PCoss", "Pgate", "Total", "VDS OK"
        ])
        table.setRowCount(len(database.sr))
        for row, device in enumerate(database.sr):
            loss = synchronous_rectifier_loss(spec, op, device)
            voltage_ok = loss.voltage_stress_v <= device.vds_max_v * spec.sr_voltage_derating
            values = (
                device.part_number,
                "User" if database.is_user("sr", device.part_number) else "Built-in",
                f"{device.rds_at(spec.sr_junction_temperature_c)*1e3:.3f} mΩ",
                f"{loss.conduction_w:.3f} W",
                f"{loss.deadtime_diode_w:.3f} W",
                f"{loss.turnoff_w:.3f} W",
                f"{loss.coss_w:.3f} W",
                f"{loss.gate_drive_w:.3f} W",
                f"{loss.total_w:.3f} W",
                "PASS" if voltage_ok else "FAIL",
            )
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        table.sortItems(8, Qt.SortOrder.AscendingOrder)
        return table


__all__ = ["DeviceCompareDialog", "DeviceEditDialog", "DeviceLibraryDialog"]
