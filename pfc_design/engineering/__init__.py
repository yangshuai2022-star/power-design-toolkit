"""Engineering-oriented PFC power-stage design kernels.

This package is intentionally separate from the historical two-phase PFC loss
model and from the TTPL control laboratory.  It owns specification-to-hardware
sizing calculations that should remain usable from GUI, CLI, web and Agent
front ends.
"""

from .cap_thermal import (
    CapacitorBankDesignConfig,
    CapacitorBankResult,
    CapacitorUnitSpec,
    TTPLThermalConfig,
    TTPLThermalResult,
    design_bus_capacitor_bank,
    solve_ttpl_semiconductor_thermal,
)
from .device_library import PFCDeviceDatabase, default_user_pfc_device_library_path
from .device_loss import (
    TTPLDeviceComparison,
    TTPLHFDeviceLoss,
    TTPLSlowDeviceLoss,
    compare_ttpl_devices,
    evaluate_hf_device,
    evaluate_slow_device,
)
from .ttpl_design import (
    TTPLDesignResult,
    TTPLDesignSpec,
    TTPLInputWorkPoint,
    TTPLLineTrace,
    analyze_ttpl_design,
)
from .pfc_v3 import (
    ConvergenceStatus,
    PFCLineCycleResult,
    PFTHDResult,
    ZeroCrossAnalysisResult,
    PFCSmartControlV3Result,
    analyze_zero_crossing,
    build_line_cycle_result,
    build_pfc_smart_control_v3,
    compute_pf_thd,
    localize_distortion,
    pf_thd_from_waveforms,
    run_pfc_engineering_v3_core,
)

__all__ = [
    "CapacitorBankDesignConfig",
    "CapacitorBankResult",
    "CapacitorUnitSpec",
    "PFCDeviceDatabase",
    "TTPLDesignResult",
    "TTPLDesignSpec",
    "TTPLDeviceComparison",
    "TTPLHFDeviceLoss",
    "TTPLInputWorkPoint",
    "TTPLLineTrace",
    "TTPLSlowDeviceLoss",
    "TTPLThermalConfig",
    "TTPLThermalResult",
    "analyze_ttpl_design",
    "compare_ttpl_devices",
    "default_user_pfc_device_library_path",
    "design_bus_capacitor_bank",
    "evaluate_hf_device",
    "evaluate_slow_device",
    "solve_ttpl_semiconductor_thermal",
    "ConvergenceStatus",
    "PFCLineCycleResult",
    "PFTHDResult",
    "ZeroCrossAnalysisResult",
    "PFCSmartControlV3Result",
    "analyze_zero_crossing",
    "build_line_cycle_result",
    "build_pfc_smart_control_v3",
    "compute_pf_thd",
    "localize_distortion",
    "pf_thd_from_waveforms",
    "run_pfc_engineering_v3_core",
]
