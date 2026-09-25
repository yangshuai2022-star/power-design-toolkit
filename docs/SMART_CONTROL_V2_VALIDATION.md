# Smart Control V2 — Validation

**Date:** 2026-09-26

---

## Test modules

| File | Covers |
| --- | --- |
| `test_loop_builder.py` | LoopModel chain, PWM update consumer, fixed×C = L |
| `test_timing_model.py` | Ownership, pure-delay −36° @ 20 µs / 5 kHz, zero-wait min |
| `test_phase_budget.py` | Σ phase ≈ open-loop, ADC/delay lag, unwrap-safe residual |
| `test_gain_budget.py` | Σ gain ≈ open-loop near Fc |
| `test_solution_map_v2.py` | Synthesize → metrics; Robust/Balanced/Fast (no score) |
| `test_loop_robustness.py` | Case A/B/C worst PM / delay / Ms selection |
| `test_exact_hz_chain.py` | Map H(z) = installed = C99 literals |
| `test_float32_loop.py` | Double vs float32 H(z); FLOAT32_WARNING path |

---

## Required scenarios ↔ tests

| Scenario | Test |
| --- | --- |
| Zero / known pure delay | `test_timing_model`, `test_pure_delay_phase_*` |
| Sensor / digital LPF phase | `test_sensor_rc_and_digital_filter_appear_in_budget` |
| Multiple crossover flag | `compute_stability_metrics` → `MULTI_CROSSOVER` when lists >1 |
| Near-zero / negative margins | `test_unstable_or_near_zero_pm_marked_warn` |
| Headroom saturation | `compute_headroom` (LoopModel) |
| Vin/load corner selection | `test_robustness_selects_worst_corners_reproducibly` |
| float32 quantization | `test_float32_*` |
| PWM update delay consumer | `test_pwm_update_delay_changes_open_loop_phase` |

---

## Phase budget math

```text
Σ phase(controller, fm_power_stage, sense_analog_calibrated, adc_sampling, delay_nominal)
  ≈ unwrap(angle(open_loop_nominal)) @ Fc
tolerance_deg = 2° (branch-aligned)
```

Falsifier: unwrap ±360° error would fail `consistent`.

---

## Delay math

```text
∠ e^{-j 2π f T} = −360° · f · T
T=20 µs, f=5 kHz → −36°
```

---

## Robustness regression cases

| Case | Intent |
| --- | --- |
| A nominal | Reference stable loop |
| B worst delay | Extra pure delay → worst delay margin |
| C plant shifted | Higher loop gain → competes for worst PM/Ms |

`worst_*` corner IDs must be reproducible across runs.

---

## Capability summary

| Capability | Before | After | Status | Evidence | Remaining risk |
| --- | --- | --- | --- | --- | --- |
| Exact Loop | Plant×C informal | `LoopModel` + FR keys | **ALIVE** | `test_loop_builder` | PFC adapter still Expert-side |
| Timing | total_delay blur; LLC PWM update DEAD | `TimingModel` + `pwm_update_delay_s` | **ALIVE** | `test_timing_model`, PWM falsifier | ISR/shadow still 0 placeholders |
| Phase Budget | Cursor helper only | Σ≈L @ Fc | **ALIVE** | `test_phase_budget` | Fine split of delay_nominal display-only |
| Gain Budget | Missing | Σ≈\|L\| @ Fc | **ALIVE** | `test_gain_budget` | — |
| PM/GM | First critical | All crossovers + MULTI flag | **ALIVE** | margins + metrics | Critical pick heuristic unchanged |
| Ms/Mt | Map only | LoopModel + map V2 | **ALIVE** | stability + map tests | Grid max, not continuous peak |
| Solution Map | Fc×PM PI | + Mt/sampling annotate | **PARTIAL** | `test_solution_map_v2` | PIF/2P2Z map still deferred |
| Robustness | DEAD in SC | Report + worst_* | **PARTIAL** | `test_loop_robustness` | LLC Vin/Lr GUI corners not wired |
| Exact H(z) | Bridge exists | Regression Map→Bode→C99 | **ALIVE** | `test_exact_hz_chain` | Guided Auto without Apply still non-install |
| float32_t | DEAD | verify + WARN | **ALIVE** | `test_float32_loop` | Pole-radius compare coarse |
| FRA | Sibling only | `PlantResponse` API | **PARTIAL** | correlate unit path | Guided MEASURED_FRA consumer DEAD |
| Evidence | Warnings | `LoopEvidenceResult` + GUI tab | **ALIVE** | Loop Chain tab | Per-widget click-through polish |

---

## How to re-run

```bash
.venv/bin/python -m pytest \
  llc_design/tests/test_loop_builder.py \
  llc_design/tests/test_timing_model.py \
  llc_design/tests/test_phase_budget.py \
  llc_design/tests/test_gain_budget.py \
  llc_design/tests/test_solution_map_v2.py \
  llc_design/tests/test_loop_robustness.py \
  llc_design/tests/test_exact_hz_chain.py \
  llc_design/tests/test_float32_loop.py -q
```
