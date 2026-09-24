# LLC V1 Integration Audit

**Date:** 2026-09-24  
**Scope:** Operating Envelope · Constraint · Worst-Case · ZVS Margin · FHA↔TD — *consumer* truth, not class existence  
**Branch:** working tree on `feature/v9.3-guided-smart-control-ui`

Principle: `model implemented ≠ model used ≠ result consumed by Optimizer/Report/Web`.

---

## 1. End-to-end consumer chain

```text
Input (LLCDesignSpec)
  → OperatingEnvelope (core/engineering.py)          [API: evaluate_operating_envelope]
  → OperatingPointResult + ConstraintResult
  → WorstCaseFinding
  → ZVS L1/L2 (core/zvs_margin.py)
  → LLCSystemAnalyzer.analyze() warnings             [partial wire]
  → API / Report / Web / Optimizer                   [mostly NOT consuming envelope JSON yet]
```

| Link | Status | Evidence | Consumer | Falsification |
| --- | --- | --- | --- | --- |
| Spec → Envelope | **ALIVE** | `evaluate_operating_envelope`, tests | Analyzer.`evaluate_envelope`, unit tests | Envelope corners that never call `solve_operating_point` |
| Envelope → Constraints | **ALIVE** | PASS/WARN/FAIL/UNKNOWN per point | EnvelopeEvaluation | Constraints that do not affect `feasible` |
| Envelope → WorstCase | **ALIVE** | `WorstCaseFinding` names corner | EnvelopeEvaluation | Metric worst corner that is not among evaluated points |
| ZVS → analyze() | **PARTIAL** | Worst ZVS charge-balance appended to `warnings` | GUI/PDF only via warning strings | Warning absent while L2 margin fails |
| ZVS → Constraint Engine | **ALIVE** | Envelope constraints include ZVS surplus | EnvelopeEvaluation | Envelope PASS while `ZVS_MARGIN < 0` |
| ZVS → primary_bridge_loss | **PARTIAL** | Loss still uses *ratio* `I·td/Q`; L2 surplus is parallel | Loss totals | Loss ZVS residual disagrees with L2 PASS |
| FHA↔TD → system path | **PARTIAL** | `validate_fha_against_time_domain` + `engineering_validation()` / Stage B | Evidence report, two-stage opt | Validity FAIL never appears in evidence report |
| Envelope → Optimizer | **PARTIAL** | `TwoStageLLCOptimizer` rejects envelope FAIL before rank | Stage B verified list | FAIL candidate ranked above accepted |
| Envelope → Web/PDF structured fields | **DEAD** | No envelope JSON section in export | Web `reporting.py` still uses ratio ZVS | UI shows PASS while envelope FAIL |
| Waveform → Loss | **PARTIAL** | `waveform_loss` provenance path; default `analyze()` still FHA scalars | Evidence / opt-in | Waveform Ir_rms change without provenanced loss change |

---

## 2. Capability grades (consumer-aware)

| Capability | Grade | Note |
| --- | --- | --- |
| Operating Envelope | **PARTIAL** | Engine ALIVE; default design path does not run it |
| Constraint Engine | **PARTIAL** | ALIVE in envelope API; not filtering optimizer |
| Worst Case | **PARTIAL** | Named corners ALIVE; loss worst-case still separate min/max |
| ZVS L1/L2 | **PARTIAL** | L2 ALIVE; analyze() warning only; loss/Q-map still ratio |
| FHA↔TD Validation | **PARTIAL** | Module ALIVE; **no production consumer** → treat as DEAD for V1 “done” claim |
| MOSFET Loss | **ALIVE** (FHA-based) | Provenance/APPROX tags largely missing |
| Rectifier Loss | **ALIVE** (FHA-based) | Same |
| Magnetic | **ALIVE** (eng.) | iGSE + Dowell/Litz; leakage not FEA |
| Thermal | **PARTIAL** | Hotspot Rθ estimates; no electro-thermal iteration |
| Optimizer | **PARTIAL** | Grid + Pareto; no Stage-B TD verification |

---

## 3. Dead / weak paths fixed or deferred in V2

| Issue | V2 action |
| --- | --- |
| FHA↔TD not consumed | Add `validate_fha_against_time_domain` critical-point driver + optional `engineering_validation()` on analyzer; evidence report |
| Optimizer ignores envelope | Two-stage optimizer: Stage A FHA+envelope constraints; Stage B TD verification on Top-N |
| Loss ignores waveforms / ZVS class | Waveform-aware loss path with FULL/PARTIAL/HARD/UNKNOWN turn-on class linked to ZVS_MARGIN |
| No electro-thermal loop | Add lumped Rθ iteration with CONVERGED / NOT_CONVERGED |
| FHA validity map missing | Data-layer `FhaValidityMap` over fn × load |
| TD non-convergence used as verified | Gate: non-converged TD → UNKNOWN, never VERIFIED loss source |

---

## 4. Evidence format used going forward

```text
[ALIVE | PARTIAL | DEAD | UNKNOWN]
Calculation Chain → Evidence Chain → Consumer Chain → Exclusions → Falsification
```

V1 claim “framework complete” is **PARTIAL**: physics objects exist; product path still mostly FHA analyze → loss → PDF.
