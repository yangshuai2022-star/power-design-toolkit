"""PyInstaller entry point; --self-test exercises the actual frozen GUI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


def _run_packaged_self_test() -> int:
    """Exercise all workspaces and emit evidence only after successful completion."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from llc_design import __version__
    from llc_design.core.spec import LLCDesignSpec
    from llc_design.gui import theme
    from llc_design.gui.launcher import WorkspaceApplicationController, WorkspaceSelectionDialog
    from llc_design.gui.system_modeling import SystemModelingDesignDialog
    from llc_design.validation.provenance import validate_bundled_data
    from power_control_tools import part_validation

    app = QApplication.instance() or QApplication(["PowerDesignTool", "--self-test"])
    app.setApplicationName("Power Design Toolkit")
    theme.apply_app_theme(app)
    controller = WorkspaceApplicationController(LLCDesignSpec())
    selector = WorkspaceSelectionDialog()
    selector.close()
    guided = SystemModelingDesignDialog()
    guided.close()
    report = validate_bundled_data()
    if not report.valid:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        for window in (controller.llc_window, controller.pfc_window,
                       controller.control_window, controller.fra_window):
            window.close()
        return 2

    for workspace in ("llc", "pfc", "control", "fra"):
        controller.show_workspace(workspace)
        app.processEvents()
    for window in (controller.llc_window, controller.pfc_window,
                   controller.control_window, controller.fra_window):
        window.hide()
        window.close()
    app.processEvents()

    # This path is inside the frozen bundle, not relative to the source/CWD.
    taxonomy = Path(part_validation.__file__).resolve().parents[1] / "engineering_data/brand_taxonomy.json"
    part_validation.load_brand_taxonomy()
    proof = {
        "success": True, "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)), "platform": sys.platform,
        "workspaces": ["llc", "pfc", "control", "fra"], "guided_design": True,
        "brand_taxonomy_sha256": hashlib.sha256(taxonomy.read_bytes()).hexdigest(),
    }
    destination = os.environ.get("PDT_SELF_TEST_REPORT")
    if destination:
        Path(destination).write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print("Power Design Toolkit packaged self-test: OK")
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _run_packaged_self_test()
    from llc_design.gui.app import run_gui
    return int(run_gui())


if __name__ == "__main__":
    sys.exit(main())
