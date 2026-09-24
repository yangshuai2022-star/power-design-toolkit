"""LLC system loss summary panel built from OperatingPointLoss.breakdown()."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from llc_design.models.system import OperatingPointLoss, SystemAnalysis


_LABELS = {
    "primary_conduction_w": "Primary conduction",
    "primary_turnoff_w": "Primary turn-off",
    "primary_gate_w": "Primary gate drive",
    "primary_coss_w": "Primary Coss residual",
    "primary_deadtime_w": "Primary deadtime diode",
    "sr_conduction_w": "SR conduction",
    "sr_deadtime_w": "SR deadtime diode",
    "sr_turnoff_w": "SR turn-off",
    "sr_coss_w": "SR Coss",
    "sr_gate_w": "SR gate drive",
    "transformer_core_w": "Transformer core",
    "transformer_primary_copper_w": "Transformer Cu primary",
    "transformer_secondary_copper_w": "Transformer Cu secondary",
    "resonant_inductor_core_w": "Lr core",
    "resonant_inductor_copper_w": "Lr copper",
    "resonant_capacitor_w": "Cr ESR",
    "output_capacitor_w": "Cout ESR",
    "auxiliary_w": "Auxiliary",
}


class LossSummaryView(QWidget):
    """Show non-overlapping LLC loss buckets and verify they sum to total_loss_w."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Work point"))
        self.point = QComboBox()
        header.addWidget(self.point, 1)
        root.addLayout(header)
        note = QLabel(
            "Buckets come from OperatingPointLoss.breakdown() and are non-overlapping. "
            "Transformer/Lr rows are component magnetics losses inside the converter total — "
            "not a separate “system = inductor-only” total."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        root.addWidget(self.text, 1)
        self._analysis: SystemAnalysis | None = None
        self.point.currentIndexChanged.connect(self._render)

    def set_analysis(self, analysis: SystemAnalysis) -> None:
        self._analysis = analysis
        self.point.blockSignals(True)
        self.point.clear()
        for item in analysis.operating_points:
            op = item.operating_point
            self.point.addItem(
                f"{op.vbus_v:.0f} V / {op.load_fraction*100:.0f}%",
                item,
            )
        # Prefer nominal.
        nominal = analysis.nominal
        for i in range(self.point.count()):
            if self.point.itemData(i) is nominal:
                self.point.setCurrentIndex(i)
                break
        self.point.blockSignals(False)
        self._render()

    def _render(self) -> None:
        item = self.point.currentData()
        if item is None:
            self.text.setPlainText("Run LLC design first.")
            return
        assert isinstance(item, OperatingPointLoss)
        breakdown = item.breakdown()
        lines = [
            "LLC SYSTEM LOSS SUMMARY",
            "=" * 72,
            f"Work point : {item.label}",
            f"fs         : {item.operating_point.switching_frequency_hz/1e3:.5g} kHz",
            "",
            f"{'Bucket':<36} {'Loss (W)':>12}",
            "-" * 50,
        ]
        for key, value in breakdown.items():
            lines.append(f"{_LABELS.get(key, key):<36} {value:12.5f}")
        bucket_sum = sum(breakdown.values())
        lines.extend([
            "-" * 50,
            f"{'Sum of buckets':<36} {bucket_sum:12.5f}",
            f"{'Reported total_loss_w':<36} {item.total_loss_w:12.5f}",
            f"{'Δ (sum - total)':<36} {bucket_sum - item.total_loss_w:12.5e}",
            f"{'Efficiency':<36} {item.efficiency*100:11.4f}%",
            "",
            "Primary device total = "
            f"{item.primary.total_w:.5f} W | SR device total = {item.synchronous_rectifier.total_w:.5f} W",
            "Transformer total = "
            f"{item.transformer.total_w:.5f} W | Lr total = {item.resonant_inductor.total_w:.5f} W",
        ])
        if abs(bucket_sum - item.total_loss_w) > 1e-6 * max(1.0, abs(item.total_loss_w)):
            lines.append("WARNING: bucket sum does not match total_loss_w — investigate counting.")
        self.text.setPlainText("\n".join(lines))


__all__ = ["LossSummaryView"]
