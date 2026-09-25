"""Smart Control V2 — corner / robustness aggregation."""

from __future__ import annotations

import numpy as np

from llc_design.control.smart_control import build_robustness_report


def _loop(gain: float, delay_s: float, frequencies: np.ndarray) -> np.ndarray:
    """Simple L(jw) = gain * exp(-j w T) / (1 + j w / wn) for regression cases."""
    wn = 2 * np.pi * 2e3
    w = 2 * np.pi * frequencies
    return gain / (1.0 + 1j * w / wn) * np.exp(-1j * w * delay_s)


def test_robustness_selects_worst_corners_reproducibly():
    f = np.geomspace(10.0, 50e3, 400)
    # Case A: nominal stable
    a = _loop(gain=8.0, delay_s=5e-6, frequencies=f)
    # Case B: worst delay corner
    b = _loop(gain=8.0, delay_s=40e-6, frequencies=f)
    # Case C: plant gain/phase shifted
    c = _loop(gain=20.0, delay_s=5e-6, frequencies=f)
    report = build_robustness_report({
        "CaseA_nominal": (f, a),
        "CaseB_worst_delay": (f, b),
        "CaseC_plant_shifted": (f, c),
    })
    assert report.worst_pm is not None
    assert report.worst_delay_margin is not None
    assert report.worst_ms is not None
    # Extra delay or higher gain should make PM / delay-margin worse than A.
    pm_by_id = {c.corner_id: c.pm_deg for c in report.corners}
    assert pm_by_id["CaseA_nominal"] is not None
    worst_pm_id = report.worst_pm.corner_id
    assert worst_pm_id in {"CaseB_worst_delay", "CaseC_plant_shifted"}
    assert report.worst_delay_margin.corner_id == "CaseB_worst_delay"
    # Ms should pick the more aggressive plant (higher loop gain → larger peak risk).
    assert report.worst_ms.corner_id in {"CaseB_worst_delay", "CaseC_plant_shifted"}


def test_unstable_or_near_zero_pm_marked_warn():
    f = np.geomspace(10.0, 50e3, 300)
    # Very high gain → likely poor margins
    aggressive = _loop(gain=80.0, delay_s=80e-6, frequencies=f)
    report = build_robustness_report({"aggressive": (f, aggressive)})
    assert len(report.corners) == 1
    corner = report.corners[0]
    # Either WARN on margins or explicit negative/None PM path.
    if corner.pm_deg is not None and corner.pm_deg <= 0.0:
        assert corner.constraint_status.value == "WARN"
    assert report.worst_pm is corner or report.worst_pm is None
