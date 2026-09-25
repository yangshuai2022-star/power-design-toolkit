# PFC Engineering V3 — Validation (Round 1)

**Date:** 2026-09-26  
**Scope:** Phases 1–4 + 7

---

## Tests

| File | Covers |
| --- | --- |
| `test_pfc_line_cycle_v3.py` | Unified result, InstantPoint, convergence flag |
| `test_pfc_pf_thd_v3.py` | Cases A–D + PF≤1 sanity |
| `test_pfc_zero_cross_v3.py` | Isolated min-pulse / dead-time / offset |
| `test_pfc_smart_control_v3.py` | Separation, Ms/Mt, Exact H(z), localization, pack |

```bash
.venv/bin/python -m pytest \
  pfc_design/tests/test_pfc_line_cycle_v3.py \
  pfc_design/tests/test_pfc_pf_thd_v3.py \
  pfc_design/tests/test_pfc_zero_cross_v3.py \
  pfc_design/tests/test_pfc_smart_control_v3.py -q
```

---

## Capability table (round 1)

| Capability | Before | After | Status | Evidence | Remaining risk |
| --- | --- | --- | --- | --- | --- |
| Line Cycle | 3 forks | Unified `PFCLineCycleResult` on control sim | **ALIVE** | `test_pfc_line_cycle_v3` | Ideal sizing/legacy still separate |
| Convergence | Warning only | Explicit CONVERGED/NOT/UNKNOWN | **ALIVE** | assess + tests | Startup cycles still short runs |
| PF | Metrics ALIVE | Engine + DPF×Distortion identity | **ALIVE** | Cases A/B | DC/window residual |
| THD / Harmonics | Explicit Hn | Same + THDConvention | **ALIVE** | Case C | Non-integer windows |
| Distortion map | DEAD | Region map + gated causes | **PARTIAL** | localize test | Causes often UNKNOWN |
| Zero Crossing | Wave ZX ALIVE | Analyzer + min-I / td / offset | **ALIVE** | ZC tests | No TBCLK compare-count yet |
| Current / Voltage loops | ALIVE | + Ms/Mt + phase budget | **ALIVE** | smart_control tests | Angle-dependent Ci not in V3 pack |
| Loop Separation | DEAD | Fc ratio + 2×fline | **ALIVE** | separation fields | GUI marker deferred |
| Exact H(z) | ALIVE | Consumed by V3 pack | **ALIVE** | handoff assert | — |
| Magnetics | PARTIAL | Deferred | **DEAD** (this round) | — | Phase 5 |
| MOSFET Loss integrate | Fork | Deferred | **DEAD** (this round) | — | Phase 6 |
| Worst Case | PARTIAL | Deferred | **DEAD** (this round) | — | Phase 8 |
| FRA | DEAD | Deferred | **DEAD** | — | Phase 9/10 |
| Evidence | Warnings | `PFCEvidenceResult` | **PARTIAL** | ZC + SC evidence | GUI Evidence view deferred |

---

## Round-1 acceptance

```text
[ALIVE] Line-Cycle → PF/THD → Zero Crossing → Smart Control
Calculation: config → simulate → V3 façades → evidence dicts
Consumer: tests + Agent API (run_pfc_engineering_v3_core)
Exclusions: magnetics/loss/envelope GUI rewrite
Falsify: NOT_CONVERGED labeled VERIFIED; PF identity broken on Case A/B; handoff≠analysis
```
