"""Type-II / Type-III op-amp compensator schematic for Control Tools.

The network matches ``power_control_tools.controllers`` RC definitions:

Type II
  input: R1
  feedback: C2 || (R2 + C1 series)

Type III
  input: R1 || (R3 + C3 series)
  feedback: C2 || (R2 + C1 series)

Pole/zero mode shows topology only — never invents unique RC values.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget, QSizePolicy


class TypeCompensatorSchematic(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.kind = "TYPE_II"
        self.mode = "rc"  # rc | pz
        self.values: dict[str, str] = {}
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_state(self, *, kind: str, mode: str, values: dict[str, str] | None = None) -> None:
        self.kind = str(kind)
        self.mode = str(mode).lower()
        self.values = dict(values or {})
        self.update()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(520, 240)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        pen = QPen(QColor("#101828"), 1.6)
        painter.setPen(pen)
        font = QFont("Menlo", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        painter.setFont(font)

        w, h = self.width(), self.height()
        left = 24
        mid_y = h * 0.48
        amp_x = w * 0.58
        out_x = w * 0.88

        # Vin label and input node
        painter.drawText(QRectF(left, mid_y - 40, 50, 20), Qt.AlignmentFlag.AlignLeft, "Vin")
        painter.drawLine(QPointF(left + 30, mid_y), QPointF(amp_x - 70, mid_y))

        is_iii = "III" in self.kind.upper()
        show_values = self.mode == "rc"

        def label(name: str, x: float, y: float) -> None:
            text = name
            if show_values and name in self.values:
                text = f"{name}={self.values[name]}"
            elif not show_values:
                text = f"{name}"
            painter.drawText(QRectF(x, y, 120, 18), Qt.AlignmentFlag.AlignLeft, text)

        # Input branch
        if is_iii:
            # R1 shunt path
            painter.drawLine(QPointF(left + 70, mid_y), QPointF(left + 70, mid_y - 55))
            painter.drawLine(QPointF(left + 70, mid_y - 55), QPointF(amp_x - 90, mid_y - 55))
            painter.drawLine(QPointF(amp_x - 90, mid_y - 55), QPointF(amp_x - 90, mid_y))
            label("R1", left + 78, mid_y - 78)
            # R3-C3 series across input
            painter.drawLine(QPointF(left + 100, mid_y), QPointF(left + 100, mid_y + 50))
            painter.drawLine(QPointF(left + 100, mid_y + 50), QPointF(amp_x - 110, mid_y + 50))
            painter.drawLine(QPointF(amp_x - 110, mid_y + 50), QPointF(amp_x - 110, mid_y))
            label("R3", left + 108, mid_y + 18)
            label("C3", amp_x - 160, mid_y + 18)
        else:
            label("R1", left + 90, mid_y - 22)

        # Op-amp triangle
        tri = [QPointF(amp_x - 50, mid_y - 35), QPointF(amp_x - 50, mid_y + 35), QPointF(amp_x + 20, mid_y)]
        painter.drawPolygon(tri)
        painter.drawText(QRectF(amp_x - 46, mid_y - 28, 30, 16), Qt.AlignmentFlag.AlignLeft, "−")
        painter.drawText(QRectF(amp_x - 46, mid_y + 12, 30, 16), Qt.AlignmentFlag.AlignLeft, "+")
        painter.drawLine(QPointF(amp_x - 70, mid_y), QPointF(amp_x - 50, mid_y - 12))  # to inverting
        # Non-inverting to reference
        painter.drawLine(QPointF(amp_x - 50, mid_y + 12), QPointF(amp_x - 50, mid_y + 55))
        painter.drawLine(QPointF(amp_x - 60, mid_y + 55), QPointF(amp_x - 40, mid_y + 55))
        painter.drawText(QRectF(amp_x - 30, mid_y + 46, 80, 18), Qt.AlignmentFlag.AlignLeft, "Vref")

        # Output
        painter.drawLine(QPointF(amp_x + 20, mid_y), QPointF(out_x, mid_y))
        painter.drawText(QRectF(out_x - 10, mid_y - 28, 50, 20), Qt.AlignmentFlag.AlignLeft, "Vout")

        # Feedback: C2 || (R2 + C1)
        fb_top = mid_y - 70
        painter.drawLine(QPointF(amp_x - 70, mid_y), QPointF(amp_x - 70, fb_top))
        painter.drawLine(QPointF(amp_x - 70, fb_top), QPointF(out_x - 40, fb_top))
        painter.drawLine(QPointF(out_x - 40, fb_top), QPointF(out_x - 40, mid_y))
        label("C2", amp_x - 20, fb_top - 18)

        fb_mid = mid_y - 38
        painter.drawLine(QPointF(amp_x - 70, mid_y), QPointF(amp_x - 70, fb_mid))
        painter.drawLine(QPointF(amp_x - 70, fb_mid), QPointF(out_x - 40, fb_mid))
        painter.drawLine(QPointF(out_x - 40, fb_mid), QPointF(out_x - 40, mid_y))
        label("R2", amp_x - 40, fb_mid - 18)
        label("C1", amp_x + 40, fb_mid - 18)

        title = "Type III" if is_iii else "Type II"
        if self.mode != "rc":
            title += "  (pole/zero mode — RC values not unique; schematic topology only)"
        painter.drawText(QRectF(12, 8, w - 24, 20), Qt.AlignmentFlag.AlignLeft, title)
        painter.end()


__all__ = ["TypeCompensatorSchematic"]
