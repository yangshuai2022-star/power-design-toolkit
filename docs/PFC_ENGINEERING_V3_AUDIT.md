# PFC Engineering V3 — Consumer-Chain Audit

**Date:** 2026-09-26  
**Scope:** TTPL (primary) + legacy interleaved / Vienna (noted)  
**Rule:** field exists ≠ consumed ≠ changes result ≠ enters report

Authority documents already present: `docs/PFC_ENGINEERING_WORKSPACE.md`.

---

## End-to-end chain (TTPL live path)

```text
TTPLDesignSpec
  → analyze_ttpl_design (L / Cbus / workpoints / TTPLLineTrace)
  → Apply → PFCControlLabConfig.power_stage
  → Devices / Loss screen (TTPLLineTrace-based; optional)
  → Cap / Thermal Apply → Cbus / ESR
  → simulate_pfc_line_cycle → PFCLineCycleWaveforms + PFCWaveformMetrics
  → PF / THD GUI (metrics authority)
  → Switching / ZX view (state machine + local PWM)
  → build_pfc_control_lab_analysis (Ci / Cv Bode)
  → build_pfc_control_handoff → Exact H(z) → C99 / ngspice
```

Legacy `DesignSpec` → `SystemAnalyzer` → `LineCycleTrace` → PDF is a **parallel** stack, not the TTPL GUI consumer.

---

## Capability grades

| Link | Status | Evidence | Consumer | Falsification |
| --- | --- | --- | --- | --- |
| Spec (TTPL) | **ALIVE** | `engineering/ttpl_design.TTPLDesignSpec.validate` | Sizing | Finish with Vin_min>Vin_max |
| Spec (legacy) | **PARTIAL** | `core/spec.DesignSpec` | Legacy CLI/PDF | TTPL GUI never reads it |
| Power-stage sizing | **ALIVE** | `analyze_ttpl_design` | Apply→control plant | Change ripple ratio; L unchanged |
| Lboost / Cbus electrical | **ALIVE** | `_required_inductance`, capacitance formulas | Control Lab spinboxes | Apply L; Bode still 220 µH |
| Device selection | **ALIVE** screen / **DEAD→plant** | `compare_ttpl_devices` | Loss UI only | Pick HF part; η/plant ESR unchanged |
| Loss (TTPL) | **ALIVE** fork | `device_loss.evaluate_hf_device` | Device page | Same Vin/P vs legacy `MosfetLoss` disagree undocumented |
| Loss (legacy) | **ALIVE** fork | `models/mosfet` + `LineCycleTrace` | PDF / Mathcad tests | — |
| Line cycle (sizing) | **ALIVE** ideal | `TTPLLineTrace` | Loss screen | Assumes unity-PF sine |
| Line cycle (control) | **ALIVE** | `simulate_pfc_line_cycle` | PF/THD, ZX, switching | Last cycle only; no explicit CONVERGED flag |
| Line cycle (legacy) | **ALIVE** fork | `build_line_cycle_trace` | Inductor/MOSFET loss | Half-cycle midpoint; no closed-loop |
| Convergence | **PARTIAL** | Vbus warn if >5% off | Warnings list | Settled Pin cycle-to-cycle not checked |
| PF | **ALIVE** | `PFCWaveformMetrics.power_factor` + DPF + Distortion | AC view | Change window; PF ≠ P/S |
| THD / harmonics | **ALIVE** | Explicit H1…Hn RSS (not residual) | Harmonic panel | Non-integer cycles → THD jumps |
| Distortion localization | **DEAD** | Only ZC error RMS | — | THD=4.8% with no angle map |
| Distortion cause taxonomy | **DEAD** | Heuristic warnings only | — | Auto-blame without evidence |
| Zero crossing (wave) | **ALIVE** | `_ZeroCrossMachine` + ZX signals | Switching view | Ignore min-pulse; ZC error unchanged |
| Zero crossing (analytical) | **PARTIAL** | Min pulse in duty clamp | Metrics fraction | Offset ±100 mA not modelled in analyzer API |
| Min pulse / PWM clock | **PARTIAL** | `minimum_effective_pulse_s * fsw` | Duty clamp | No TBCLK→compare count chain |
| Dead-time | **PARTIAL** | Switching view uses `deadtime_s` | Local PWM | No ZC current-error API |
| Sensing / ADC | **ALIVE** Bode / **PARTIAL** bits | `sensing.py`, sampled chains | Loops + waveforms | Vref-only change moves Bode |
| Current loop | **ALIVE** | `build_pfc_control_lab_analysis` | Control Lab / map | — |
| Voltage loop | **ALIVE** | Nested with closed current | Control Lab | — |
| Loop separation | **DEAD** | Two Bode plots only | — | Fc_i / Fc_v ratio never shown |
| 2×fline marker | **DEAD** | Not annotated on V Bode | — | Raise Fc_v into 100 Hz silently |
| Phase budget | **DEAD** (PFC) | LLC has V2 helper | — | Σ≠open-loop unchecked |
| Ms/Mt | **DEAD** (PFC Bode path) | Not in `LoopResult` | — | PM-only decisions |
| Exact H(z) | **ALIVE** | `handoff` + assert | C99 / spice | Re-discretize from Kp/Ti |
| C99 | **ALIVE** | `generate_ttpl_control_code_exact` | Firmware | Coeff mismatch vs handoff |
| ngspice | **ALIVE** | `pfc_closed_loop` + runtime | Verify stage | `controller_re_discretized=True` |
| Magnetics physical | **PARTIAL** | Control-lab inductor designer | Side path | L(I,T) not in line-cycle |
| Worst-case envelope | **PARTIAL** | Sizing L/N/H workpoints; autotune envelope | Not unified | Vin×P loss worst not searched |
| FRA plant source | **DEAD** | Reserved elsewhere | — | MEASURED_FRA unused |
| Evidence object | **DEAD** | Warnings strings | — | THD without falsification |
| TTPL engineering report | **DEAD** | PDF expects legacy `SystemAnalyzer` | — | TTPL “report” emits interleaved PDF |

---

## Calculation / consumer forks (must not invent a fourth)

| Kernel | Purpose | V3 rule |
| --- | --- | --- |
| `TTPLLineTrace` | Ideal CCM sizing / device screen | Keep for sizing & loss screen |
| `LineCycleTrace` | Legacy loss / magnetics | Keep for legacy tests; do not feed TTPL PF |
| `PFCLineCycleWaveforms` | Closed-loop AC / PF / ZX | **Authority for V3 PF/THD/ZC** |

---

## Delay / sensing ownership (control)

| Owner | Owns | Risk |
| --- | --- | --- |
| Sampling block | ADC / SOC / recursive | Documented not double-counted with firmware |
| Firmware block | Compute + PWM update | Must stay exclusive |
| ZOH | In PWM FR | Not also as pure delay |

---

## Falsifiers retained for V3 regression

1. Settled-cycle PF must equal `mean(v·i)/(Vrms·Irms)` within tolerance.  
2. `PF ≈ DPF × DistortionFactor` within tolerance.  
3. Ideal in-phase sine → THD≈0, PF≈1, DPF≈1.  
4. Phase-shifted sine → DPF≈cos(φ), Distortion≈1.  
5. H3/H5 injection → THD matches analytic RSS.  
6. Raising `minimum_effective_pulse_s` increases ZC current error / min-pulse fraction.  
7. Current-sensor offset biases ZC polarity / error (when analyzer consumes offset).  
8. Exact H(z) handoff coefficients identical in Bode and C99.  
9. Unconverged Vbus (>5% or cycle Pin drift) must not be labeled VERIFIED.

---

## Verdict

TTPL V2 already has a **real** Spec→Sizing→Control→Waveform→H(z) path. Gaps for V3 are unification and honesty: **shared InstantPoint / convergence status**, **PF=DPF×Distortion + THDConvention**, **distortion localization + cause taxonomy**, **analytical Zero-Cross analyzer**, **loop separation / phase budget / MsMt**, and **evidence objects** — without rewriting the averaged plant or Exact H(z) stack.

First implementation round: Phases **1–4 + 7** only (Line-Cycle → PF/THD → Zero Crossing → Smart Control). Magnetics / waveform loss / full worst-case deferred.
