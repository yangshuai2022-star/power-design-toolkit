"""Application launcher for the independent power-design workspaces."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from llc_design import __version__
from llc_design.core.spec import LLCDesignSpec
from llc_design.gui import theme
from llc_design.gui.help import show_help
from llc_design.i18n import t
from llc_design.gui.main_window import LLCMainWindow
from llc_design.gui.closed_loop_install import install_closed_loop_verification
from llc_design.gui.device_library_install import install_device_library
from llc_design.gui.solution_map_install import install_llc_solution_map
from llc_design.gui.system_modeling import (
    SystemModelingDesignDialog,
    apply_definition_to_llc_window,
    apply_definition_to_ttpl_window,
    install_guided_context_actions,
)
from pfc_design.gui.main_window import PFCMainWindow
from pfc_design.gui.solution_map_install import install_ttpl_solution_map
from power_control_tools.gui.fra_advanced import install_advanced_fra_actions
from power_control_tools.gui.fra_loop_designer import FRALoopDesignerWindow
from power_control_tools.gui.main_window import ControlToolsMainWindow
from power_control_tools.system_definition import SystemTopology


class _LauncherCard(QFrame):
    """CAE-style entry card used by the workspace selector."""

    def __init__(
        self,
        title: str,
        description: str,
        *,
        primary: bool = False,
        badge: str = "",
        cta: str = "",
        object_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        palette = theme.active_theme()
        if object_name:
            self.setObjectName(object_name)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        border = palette.accent if primary else palette.border_card
        border_w = 3 if primary else 1
        self.setStyleSheet(
            f"QFrame#{object_name or 'launcher_card'} {{"
            f"background:{palette.surface}; border:{border_w}px solid {border};"
            f"border-radius:14px;}}"
            f"QFrame#{object_name or 'launcher_card'}:hover {{"
            f"border-color:{palette.accent}; background:{palette.hover};}}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)
        if badge:
            chip = QLabel(badge)
            chip.setStyleSheet(
                f"color:{palette.accent}; font-size:11px; font-weight:700;"
                f"letter-spacing:0.4px; border:none; background:transparent;"
            )
            root.addWidget(chip)
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"font-size:{20 if primary else 16}px; font-weight:700;"
            f"color:{palette.text_strong}; border:none; background:transparent;"
        )
        root.addWidget(title_label)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size:13px; color:{palette.text_muted}; border:none; background:transparent;"
        )
        root.addWidget(desc)
        root.addStretch(1)
        self.button = QPushButton(cta or ("Start" if primary else t("进入")))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setMinimumHeight(36 if primary else 32)
        self.button.setStyleSheet(
            "QPushButton {"
            f"font-size:14px; font-weight:650; border-radius:8px; padding:8px 18px;"
            f"background:{palette.accent if primary else palette.surface_alt};"
            f"color:{'#ffffff' if primary else palette.text_strong};"
            f"border:1px solid {palette.accent if primary else palette.border_input};"
            "}"
            f"QPushButton:hover {{background:{palette.pressed if primary else palette.hover};}}"
        )
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.button)
        root.addLayout(row)
        if primary:
            self.setMinimumHeight(168)
        else:
            self.setMinimumHeight(148)


class WorkspaceSelectionDialog(QDialog):
    """Initial function selector shown before an engineering workspace."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.selected_workspace: str | None = None
        self.setWindowTitle(t("电源设计工具箱 — 选择设计功能"))
        self.setMinimumSize(1180, 820)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setStyleSheet(theme.launcher_stylesheet(theme.active_theme()))

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel(t("请选择进入的设计工作区"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 25px; font-weight: 650; padding: 4px;")
        root.addWidget(title)

        subtitle = QLabel(
            t("V9.3 新增“系统建模与设计”：先逐步定义功率级、采样、ADC/PWM 与数字时序，再进入现有强分析引擎；")
            + t("Expert 用户仍可直接进入 LLC、PFC、Control Tools 或 FRA 工作区。")
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; padding: 0 40px 8px 40px;")
        root.addWidget(subtitle)

        guided = _LauncherCard(
            t("系统建模与设计 / Guided System Design"),
            t("从功率级、采样、ADC、PWM 到完整闭环的逐步建模"),
            primary=True,
            badge=f"V{__version__} PRIMARY ENTRY",
            cta="Start",
            object_name="guided_system_design_button",
        )
        # Keep findChild(QPushButton, ...) working for existing smoke tests.
        guided.button.setObjectName("guided_system_design_button")
        guided.setObjectName("guided_system_design_card")
        guided.button.clicked.connect(lambda: self._select("system_modeling"))
        root.addWidget(guided)

        expert_label = QLabel("Expert Workspaces")
        expert_label.setStyleSheet(
            f"font-size:12px; font-weight:700; letter-spacing:0.6px;"
            f"color:{theme.active_theme().text_muted}; padding-top:6px;"
        )
        root.addWidget(expert_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)

        llc = _LauncherCard(
            t("进入 LLC 设计（Expert）"),
            t("谐振腔、磁性器件、损耗、开关波形、小信号与数字电压环"),
            badge="EXPERT",
            cta=t("进入 LLC"),
            object_name="llc_expert_card",
        )
        pfc = _LauncherCard(
            t("进入 PFC 设计（Expert）"),
            t("单相 TTPL + 三相 Vienna：硬件设计、控制、采样链、Bode、AC/开关波形与 PF/THD"),
            badge="EXPERT",
            cta=t("进入 PFC"),
            object_name="pfc_expert_card",
        )
        control = _LauncherCard(
            t("进入 Control Tools"),
            t("S2Z、数字滤波器、Bode、Step/Impulse、P/Z、SOS 与 C99 float32_t 导出"),
            badge="EXPERT",
            cta=t("进入 Control Tools"),
            object_name="control_tools_card",
        )
        fra = _LauncherCard(
            t("进入 FRA Loop Designer"),
            t("Bode100 / SIMPLIS / Generic：Equivalent Plant、Auto Design、Model ID、稳定性与 C99"),
            badge="EXPERT",
            cta=t("进入 FRA Loop Designer"),
            object_name="fra_designer_card",
        )
        llc.button.clicked.connect(lambda: self._select("llc"))
        pfc.button.clicked.connect(lambda: self._select("pfc"))
        control.button.clicked.connect(lambda: self._select("control"))
        fra.button.clicked.connect(lambda: self._select("fra"))
        grid.addWidget(llc, 0, 0)
        grid.addWidget(pfc, 0, 1)
        grid.addWidget(control, 1, 0)
        grid.addWidget(fra, 1, 1)
        root.addLayout(grid, 1)

        cancel = QPushButton(t("退出"))
        cancel.clicked.connect(self.reject)
        help_button = QPushButton(t("使用说明 / 帮助 (F1)"))
        help_button.setToolTip(t("系统建模向导与四个 Expert 工作区分别做什么、如何选择"))
        help_button.clicked.connect(lambda: show_help(self, "selector"))
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(help_button)
        footer.addWidget(cancel)
        footer.addStretch(1)
        root.addLayout(footer)
        shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents), self)
        shortcut.activated.connect(lambda: show_help(self, "selector"))

    def _select(self, workspace: str) -> None:
        self.selected_workspace = workspace
        self.accept()


class WorkspaceApplicationController:
    """Own top-level windows and switch without destroying user state."""

    def __init__(self, initial_spec: LLCDesignSpec) -> None:
        self.llc_window = LLCMainWindow(initial_spec)
        install_device_library(self.llc_window)
        install_closed_loop_verification(self.llc_window)
        install_llc_solution_map(self.llc_window)
        self.pfc_window = PFCMainWindow()
        install_ttpl_solution_map(self.pfc_window)
        self.control_window = ControlToolsMainWindow()
        self.fra_window = FRALoopDesignerWindow()
        install_advanced_fra_actions(self.fra_window)
        self.active_workspace: str | None = None
        self.llc_window.workspace_switch_requested.connect(self._handle_request)
        self.pfc_window.workspace_switch_requested.connect(self._handle_request)
        self.control_window.workspace_switch_requested.connect(self._handle_request)
        self.fra_window.workspace_switch_requested.connect(self._handle_request)
        self.control_window.digital_design_updated.connect(self.llc_window.set_external_control_design)
        self.control_window.digital_design_updated.connect(
            lambda digital, label="": self.llc_window.refresh_closed_loop_controller()
        )
        install_guided_context_actions(
            self.llc_window,
            lambda: self._edit_guided_definition("llc"),
        )
        install_guided_context_actions(
            self.pfc_window,
            lambda: self._edit_guided_definition("pfc"),
        )

    def start(self) -> bool:
        dialog = WorkspaceSelectionDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        if dialog.selected_workspace is None:
            return False
        if dialog.selected_workspace == "system_modeling":
            return self._run_system_modeling(previous=None)
        self.show_workspace(dialog.selected_workspace)
        return True

    def _hide_all(self) -> None:
        self.llc_window.hide()
        self.pfc_window.hide()
        self.control_window.hide()
        self.fra_window.hide()

    def show_workspace(self, workspace: str) -> None:
        if workspace == "system_modeling":
            self._run_system_modeling(previous=self.active_workspace)
            return
        if workspace not in {"llc", "pfc", "control", "fra"}:
            raise ValueError(f"unsupported workspace: {workspace}")
        self._hide_all()
        target = {
            "llc": self.llc_window,
            "pfc": self.pfc_window,
            "control": self.control_window,
            "fra": self.fra_window,
        }[workspace]
        self.active_workspace = workspace
        target.showMaximized()
        target.raise_()
        target.activateWindow()

    def _run_system_modeling(
        self,
        previous: str | None,
        *,
        seed_definition=None,
    ) -> bool:
        """Run V9.3 guided definition, then hand off to maintained engines."""
        self._hide_all()
        wizard = SystemModelingDesignDialog(initial_definition=seed_definition)
        if wizard.exec() != QDialog.DialogCode.Accepted or wizard.definition is None:
            if previous is not None:
                self.show_workspace(previous)
            return previous is not None

        definition = wizard.definition
        if definition.topology == SystemTopology.LLC:
            apply_definition_to_llc_window(self.llc_window, definition)
            self.show_workspace("llc")
            self.llc_window.run_design()
            return True
        if definition.topology == SystemTopology.TTPL_PFC:
            config = apply_definition_to_ttpl_window(self.pfc_window, definition)
            self.pfc_window.subtabs.setCurrentIndex(0)
            self.show_workspace("pfc")
            self.pfc_window.run_ttpl_analysis(config)
            return True
        raise NotImplementedError(f"unsupported V9.3 guided topology: {definition.topology.value}")

    def _edit_guided_definition(self, workspace: str) -> None:
        window = self.llc_window if workspace == "llc" else self.pfc_window
        seed = getattr(window, "guided_system_definition", None)
        self._run_system_modeling(previous=workspace, seed_definition=seed)

    def _handle_request(self, workspace: str) -> None:
        if workspace == "home":
            self._show_selector_again()
        else:
            self.show_workspace(workspace)

    def _show_selector_again(self) -> None:
        previous = self.active_workspace
        self._hide_all()
        dialog = WorkspaceSelectionDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_workspace:
            if dialog.selected_workspace == "system_modeling":
                self._run_system_modeling(previous=previous)
            else:
                self.show_workspace(dialog.selected_workspace)
        elif previous is not None:
            self.show_workspace(previous)


__all__ = ["WorkspaceApplicationController", "WorkspaceSelectionDialog"]
