# Smart Control V2 — Consumer-Chain Audit

**Date:** 2026-09-26  
**Scope:** Guided System Design / Smart Control for LLC FM voltage loop + TTPL dual loop  
**Rule:** field exists ≠ consumed ≠ changes Bode/PM/GM ≠ consumed by Solution Map / Exact H(z) / C99

---

## End-to-end chain

```text
Guided Definition (ControlSystemDefinition)
  → Adapter (apply_definition_to_{llc|ttpl}_window)
  → Analytical Plant
  → Sensor / ADC / Filter / Delay / Modulator
  → Expert Controller (defaults until Solution Map Apply)
  → Open / Closed Loop (build_digital_loop_analysis / PFC lab)
  → Metrics (calculate_stability_margins)
  → Fc×PM Solution Map (Tustin PI)
  → Install → Exact H(z) → C99
```

FRA Loop Designer is a **sibling** Expert path, not a Guided plant consumer.

---

## Capability grades

| Link | Status | Evidence | Consumer | Falsification |
| --- | --- | --- | --- | --- |
| Guided Definition | **ALIVE** | `system_modeling.build_definition` + `ControlSystemDefinition.validate` | Adapter | Finish allowed while checklist FAIL |
| Analytical Plant | **ALIVE** | LLC stage → tank/Gvf; TTPL stage → PFC plant | Loop engines | Change Ln/L; Bode unchanged |
| Sensor | **ALIVE** | Divider/RC → analog sense | Bode | Change RC; Fc phase unchanged |
| ADC timing | **PARTIAL** | Clock/acq/SOC/recursive affect Bode; vref/bits display-only | Bode | Change only Vref; PM moves |
| Digital filter | **PARTIAL** | LLC = recursive ADC; TTPL alpha on first run | Bode | LLC “alpha” field without Bode change |
| Delay | **ALIVE** | Compute + ZOH + PWM envelope; guided `pwm_update_delay_s` consumed via `CommandTimingConfig` | Bode / TimingModel | Set PWM delay 0→50 µs; open-loop phase must move (−360·f·ΔT) |
| Modulator | **PARTIAL** | FM LUT / count mode alive; duty/deadtime weak on linear Bode | Bode | Change TBCLK; Fc moves |
| ControllerIntent | **DEAD** until Install | Stored; not written to Kp/Ti on finish | Solution Map / manual | Auto Fc/PM finish; Kp unchanged |
| Open/Closed + Metrics | **ALIVE** | `build_digital_loop_analysis`, multi-crossover lists | GUI / map | Analysis fail with null plant |
| Solution Map | **ALIVE** | `build_fc_pm_solution_map` Tustin PI; fail-closed Apply | Install | Non-feasible Apply changes Bode |
| Exact H(z) | **PARTIAL** LLC / **ALIVE** TTPL | LLC TF in analysis; TTPL `PFCControlHandoff` | C99 | Mutate handoff coeffs; assert fails |
| C99 | **ALIVE** Expert | `generate_llc_control_code` / Exact-H(z) export | Firmware | Export before analysis succeeds |
| Guided ↔ FRA | **DEAD** | PlantSource IMPORTED_FRA reserved | — | Selecting FRA in Guided unused |
| Phase Budget UI helper | **ALIVE** | `compute_phase_budget` + Bode cursor + Loop Chain tab | Digital-loop view | Sum≠open-loop phase at Fc |
| Robustness corners | **PARTIAL** | `build_robustness_report` data layer; Guided map still nominal | API / tests | Vin corner never appears in Guided map UI |
| Ms/Mt | **ALIVE** | LoopModel stability + Solution Map points | Map / Loop Chain | Ms constraint ignored if UI not seeded |
| float32 verification | **ALIVE** | `verify_exact_hz_float32` | Tests | Quantized coeffs; tool silent if GUI never calls verify |
| Loop Evidence / Falsification | **ALIVE** | `LoopEvidenceResult` on LoopModel; GUI Loop Chain tab | Expert digital loop | PM shown without falsification text |

---

## Delay ownership (pre-V2)

| Owner | Owns | Risk |
| --- | --- | --- |
| ADC | `eoc_delay_s` (acq+conversion) | OK |
| CommandTiming | `computation_delay_s` + PWM zero-wait envelope + optional ZOH | OK |
| Guided `pwm_update_delay_s` | Shadow/update lag | **Consumed** by `CommandTimingConfig.pwm_update_delay_s` → delay FR |
| ZOH | Half-sample in timing FR | Must not also be added as pure delay elsewhere |

V2 TimingModel makes ownership explicit and consumes `pwm_update_delay_s` once.

---

## Falsifiers retained for V2 regression

1. LLC guided PWM update delay must change open-loop phase at Fc once TimingModel is ALIVE.  
2. Guided Auto Design without Solution Map Apply must not rewrite Exact H(z).  
3. Solution Map Apply must install the **same** `b[]/a[]` used for Bode and C99.  
4. Σ block phase at Fc ≈ open-loop phase (unwrap-safe).  
5. Pure delay T=20 µs at 5 kHz → phase ≈ −36°.

---

## Verdict

Smart Control V1 was a **real guided handoff into Expert engines** with a **working PI Solution Map**.  
V2 adds Exact `LoopModel`, TimingModel ownership (including LLC `pwm_update_delay_s`), Phase/Gain budgets, Ms/Mt, Solution Map V2 annotations, robustness aggregation, Exact H(z)/float32 proofs, and Evidence — still using **`digital_loop.py` as the only Bode math stack**.

Remaining DEAD/PARTIAL: Guided FRA plant source, Guided Vin/Lr corner mesh UI, ControllerIntent auto-install, PIF/2P2Z map synthesis.
