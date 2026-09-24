# LLC Model Validation Report (V2)

**Date:** 2026-09-24  
**Suite:** `llc_design/tests/test_physics_v2.py` (+ envelope / ZVS / fha_td unit tests)  
**Honesty rule:** UNKNOWN / APPROXIMATION / NOT VALIDATED stay labeled — never renamed PASS to close the task.

---

## Capability matrix

| Capability | Status | Evidence | Accuracy Limitation | Next Validation |
| --- | --- | --- | --- | --- |
| FHA | **ALIVE** | `solve_fha`; Stage A / envelope | Fundamental harmonic; softens light-load / DCM error | QSpice gain/Ir at fn×Q map |
| Time Domain | **PARTIAL** | `solve_time_domain` + convergence gate | Resonant tank large-signal; not MOSFET transient SPICE | Measured Ir waveform vs TD |
| FHA↔TD | **ALIVE** (API) / **PARTIAL** (product) | `validate_fha_against_time_domain`; `engineering_validation` | Critical points only; thresholds heuristic | Expand map + lab corners |
| ZVS | **PARTIAL** | L2 charge-balance + turn-on class | Const-I deadtime; Coss(V) curves unused | Scope Vds commutation |
| MOSFET Loss | **PARTIAL** | Provenanced terms + Rds(Tj) | Waveform path opt-in; Eoss single-point | Digitised Eoss(V) + calorimeter |
| Rectifier Loss | **PARTIAL** | DIODE/SR terms; RR not fake-zero | Qrr / 3rd-quadrant still eng. | SR timing bench |
| Core Loss | **APPROXIMATION** | iGSE / Steinmetz materials | Ref fits; range not always flagged MODEL_OUT_OF_RANGE | Vendor Pv tables @ T |
| Copper Loss | **PARTIAL** | Dowell/Litz when geometry known | Without winding detail → incomplete AC story | Impedance analyser |
| Leakage | **ESTIMATED** | 1-D stack energy vs Lr target | Not FEA; not measured | LCR + shorted-sec |
| Thermal | **APPROXIMATION** | Rθ iteration CONVERGED/NOT | Lumped; runaway corners incomplete in WorstCase | IR + RθJC datasheet |
| Optimizer | **PARTIAL** | `TwoStageLLCOptimizer` envelope gate | Stage B optional; default GUI still Stage-A-ish | Force Stage B in CI fixture |
| Envelope / Constraints / WorstCase | **ALIVE** engine | `evaluate_operating_envelope` | Web/PDF structured export still weak | Export JSON section |

---

## Regression cases

| Case | Intent | Guard |
| --- | --- | --- |
| A Nominal | `LLCDesignSpec()` analyze | `total_loss_w > 0`, `0 < η < 1` |
| B High gain / low Vin | hold-end Vin full load | Solves **or** explicit `GainNotReachableError` |
| C Light load ZVS boundary | 10% load provenance loss | `turn_on_class ∈ SwitchingClass` (not silent FULL_ZVS) |

---

## Completion questions (spec §26)

| # | Question | Answerable today? | How |
| --- | --- | --- | --- |
| 1 | FHA credible at this point? | **Yes** (API) | FHA↔TD / validity map |
| 2 | TD resonant current? | **Yes** if converged | TD metrics / waveform |
| 3 | Worst current corner? | **Yes** | Envelope WorstCase |
| 4 | Hardest ZVS corner? | **Yes** | Worst ZVS + margin |
| 5 | MOSFET loss sources? | **Partial** | Provenanced terms (opt-in) |
| 6 | Tx Cu / core loss? | **Yes** (eng.) | Magnetics path |
| 7 | Hottest device? | **Partial** | Electro-thermal nodes |
| 8 | Temp → loss feedback? | **Partial** | Iteration status |
| 9 | True bottleneck? | **Partial** | WorstCase + evidence |
| 10 | Why this design ranked? | **Partial** | Explicit weights + reject reasons |
| 11 | What is VERIFIED? | **Yes** | Evidence rows — few items VERIFIED |
| 12 | What is APPROX / UNKNOWN? | **Yes** | Listed below — not hidden |

V2 is **not** claimed complete for product UX (GUI/PDF still FHA-centric). Physics **accuracy scaffolding** is in place.

---

## UNKNOWN / APPROXIMATION / NOT VALIDATED (must remain)

```text
UNKNOWN
  - Nonlinear Coss(V) / Qoss(V) / Eoss(V) curves not consumed
  - Diode reverse-recovery as verified quantity
  - Default analyze() waveform-driven loss (still FHA scalars)
  - Non-converged TD results used as design truth (gated — must stay UNKNOWN)

APPROXIMATION
  - ZVS charge-balance (const-I deadtime)
  - MOSFET Eon/Eoff / single-point Coss
  - Core loss iGSE reference materials
  - Lumped Rθ electro-thermal (even when CONVERGED)
  - FHA outside validated fn×load cells

PARTIAL
  - Copper AC (Dowell/Litz; geometry-dependent)
  - Two-stage optimizer product integration
  - Envelope → structured Report/Web export

ESTIMATED / NOT VALIDATED
  - Leakage inductance vs Lr target (no FEA / no measurement closed loop)
  - AC winding loss vs bench
  - Thermal vs IR / calorimeter
  - FHA↔TD thresholds vs production fleet statistics
```

---

## Test evidence (this delivery)

```text
pytest llc_design/tests/test_physics_v2.py
→ 12 passed (after Case B GainNotReachable message fix)
```

Related: `test_fha_td_validation`, `test_operating_envelope`, `test_zvs_margin`.

---

## Next phase (out of this round)

`TOOL Prediction → QSpice / measured → Error → Calibration → Regression` — model that knows where it is wrong.
