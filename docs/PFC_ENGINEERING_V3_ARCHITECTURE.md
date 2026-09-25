# PFC Engineering V3 — Architecture

**Date:** 2026-09-26  
**Façade:** `pfc_design/engineering/pfc_v3.py`  
**Math authorities (frozen):** `simulate_pfc_line_cycle`, `build_pfc_control_lab_analysis`, `build_pfc_control_handoff`

---

## Principle

```text
Specification → Unified Line-Cycle → PF/THD → Zero Crossing → Smart Control → Evidence
```

Do **not** invent a fourth current waveform. Sizing (`TTPLLineTrace`) and legacy loss (`LineCycleTrace`) remain for their consumers; closed-loop PF/THD/ZC use **`PFCLineCycleWaveforms` only**.

---

## Data chain (round 1)

```text
PFCControlLabConfig
      ↓
build_line_cycle_result → PFCLineCycleResult + InstantPoint + ConvergenceStatus
      ↓
pf_thd_from_waveforms / compute_pf_thd → PFTHDResult (PF=DPF×Distortion)
      ↓
localize_distortion → DistortionRegionResult[]
      ↓
analyze_zero_crossing → ZeroCrossAnalysisResult
      ↓
build_pfc_smart_control_v3 → LoopSeparation + Ms/Mt + PhaseBudget + Exact H(z)
```

One-shot pack: `run_pfc_engineering_v3_core(config)`.

---

## Convergence honesty

| Status | Meaning |
| --- | --- |
| `LINE_CYCLE_CONVERGED` | Pin cycle-to-cycle + Vbus average within tolerance |
| `NOT_CONVERGED` | Drift / bus error — PF/THD status forced WARN, never VERIFIED |
| `UNKNOWN` | <2 cycles for Pin check |

---

## Smart Control V3 (PFC)

| Loop | Open-loop product | Budget keys |
| --- | --- | --- |
| Current | Ci · InduComp · PWM/ZOH · Gid · Sense | those five |
| Voltage | Cv · AMC/VFF · BusPlant(×Ti) · Sense | those four |

`LoopSeparationResult` reports `Fc_i`, `Fc_v`, ratio, and **2×fline** headroom.

Exact H(z) remains `PFCControlHandoff` — no Kp/Ti rebuild.

---

## Deferred (later phases)

Magnetics L(I,T), waveform-driven MOSFET loss thermal loop, full operating envelope / worst-case engine, FRA plant source, oscilloscope CSV correlation, X-cap / burst modes, TTPL PDF report.
