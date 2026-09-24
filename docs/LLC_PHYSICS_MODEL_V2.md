# LLC Physics Model V2

**Date:** 2026-09-24  
**Goal:** Connect Operating Envelope / Worst-Case / Constraints to more trustworthy physics — without replacing FHA for sweep/optimizer Stage A.

Principle: existence ≠ use. Every capability below states **consumer** and **grade**.

---

## Pipeline

```text
Operating Envelope
  → Worst Critical Points (de-duped)
  → FHA (fast)
  → Time-Domain (critical only, steady-state gated)
  → Waveform / Provenanced Loss
  → Magnetic (existing + provenance tags)
  → Electro-Thermal iteration
  → Constraint re-evaluation / Evidence Report
  → Two-Stage Optimizer (Stage B only on Top-N)
```

Entry points:

| API | Module | Consumer |
| --- | --- | --- |
| `validate_fha_against_time_domain` | `analysis/fha_td_validation.py` | `run_engineering_validation`, Stage B |
| `build_fha_validity_map` | same | Evidence / data layer (no GUI) |
| `bridge_loss_with_provenance` / `rectifier_loss_with_provenance` | `models/waveform_loss.py` | Evidence report; opt-in vs default `analyze()` |
| `iterate_electro_thermal` | `models/electro_thermal.py` | Evidence report |
| `run_engineering_validation` / `LLCSystemAnalyzer.engineering_validation` | `analysis/engineering_validation.py` | Report markdown |
| `TwoStageLLCOptimizer.run` | `optimization/two_stage.py` | Constraint-filtered ranking |

Default `analyze()` path remains FHA scalar loss for speed. Waveform/thermal/evidence are explicit consumers — documented as PARTIAL until GUI/PDF wire them.

---

## 1. FHA ↔ Time-Domain

**ALIVE** for critical-point validation; **PARTIAL** for product path (not every analyze).

- FHA kept for envelope sweep, Stage A, preliminary design.
- TD only on de-duplicated critical set: nominal, Vin min/max × full/light, hold-end, plus envelope `WorstCaseFinding` corners (lookup by `corner_id`).
- Metrics compared via `DeviationResult`: gain, Ir_rms/peak, Im_peak, fs, phase; overall `ModelValidity` PASS/WARN/FAIL/UNKNOWN.
- Non-converged TD → `UNKNOWN` — never VERIFIED loss source.

Falsification: a FAIL validity cell never appears in `EngineeringEvidenceReport.fha_td`.

---

## 2. Steady-state gate

TD solver (`solve_time_domain`) already returns `SolverConvergence.converged`. V2 rule:

```text
STEADY_STATE verified ⇔ TD convergence.converged
else NOT_CONVERGED → ModelGrade.UNKNOWN on waveform-derived loss
```

Forbidden path: N cycles → assume last cycle steady → feed optimizer as verified.

---

## 3. FHA Validity Map (data layer)

`FhaValidityMap`: axes `fn` × `load_fraction`, cells carry `FhaCredibility`:

`FHA_VALID` / `FHA_WARNING` / `FHA_OUT_OF_RANGE` / `UNKNOWN`

Purpose: know where FHA is credible — not to “prove FHA wrong.”

---

## 4. Waveform-driven loss + provenance

`LossTerm`: value, `ModelGrade`, `DataConfidence`, optional Tj, notes.

MOSFET (`bridge_loss_with_provenance`):

- Conduction uses `Rds_on(Tj)` (device `rds_at`).
- Turn-on class from ZVS_MARGIN: FULL / PARTIAL / HARD / UNKNOWN.
- Eoss path prefers device Qoss/Coss engineering terms; grade APPROXIMATION unless datasheet curve consumed.
- Waveform Ir_rms upgrades conduction only when `td_converged=True`.

Rectifier: DIODE vs SYNCHRONOUS_RECTIFIER; reverse_recovery for diode is `UNKNOWN`/`N/A` as appropriate — **not** silently zero.

---

## 5. Magnetic / leakage

Reuses existing magnetics (`transformer_designer`, iGSE, Dowell/Litz). V2 evidence tags:

| Item | Grade |
| --- | --- |
| Core loss (iGSE) | APPROXIMATION |
| Copper AC | PARTIAL |
| Leakage vs Lr target | ESTIMATED — `Lr_target` ≠ `Llk_estimated` ≠ measured |

No FEA / 3D this round.

---

## 6. Electro-thermal

`iterate_electro_thermal`: lumped `T = Ta + P·Rθ`, updates Tj → Rds/Vf/magnetics path until `|ΔT| < tol` or max iters.

Statuses: `CONVERGED` / `NOT_CONVERGED`. Even when converged, model grade remains **APPROXIMATION** (lumped Rθ ≠ verified electro-thermal solution).

---

## 7. Two-stage optimizer

- **Stage A:** existing FHA grid (`LLCOptimizer`).
- **Stage B:** Top-N — envelope status, FHA↔TD, ZVS L2; FAIL rejected before ranking.
- Ranking uses explicit weights (`efficiency`, `total_loss_w`, `zvs_margin_worst`) — no opaque AI score.

---

## 8. Engineering evidence

`EngineeringEvidenceReport.as_markdown()` sections: Model Validity, Worst Case Summary, Uncertainty/Unknown.

`physical_sanity_issues()` runtime checks: loss&lt;0, η&gt;1, Bpk&lt;0, etc.

---

## Explicitly out of scope (this round)

GUI polish, FEM, SPICE transistor-level, PCB parasitics, AI auto-design, cloud datasheet crawl, genetic MOO.
