# Smart Control V2 — Architecture

**Date:** 2026-09-26  
**Math authority:** `llc_design/control/digital_loop.py` (`build_digital_loop_analysis`)  
**V2 façade:** `llc_design/control/smart_control.py` (`build_loop_model`)

---

## Principle

```text
System definition → Exact LoopModel → Controller design → Corners → Evidence
```

GUI / Solution Map / C99 must **not** assemble a second open-loop. They consume:

1. `DigitalLoopAnalysis` responses, or  
2. `LoopModel` derived from that analysis.

---

## Exact loop product

```text
L(jω) = C(z) · Kfm·Gvf · Sense_analog · ADC · Delay_nominal
```

Response keys (single authority):

| Key | Role |
| --- | --- |
| `controller` | Exact H(z) |
| `fm_power_stage` | FM gain × plant |
| `sense_analog_calibrated` | Divider / RC (DC-calibrated) |
| `adc_sampling` | SOC aperture + recursive average |
| `delay_nominal` | EOC + compute + `pwm_update_delay_s` + PWM zero-wait + optional ZOH FR |

Phase / gain budgets sum these keys and must match `open_loop_nominal` within tolerance.

---

## Timing ownership (no double count)

| Owner | Owns | Must not also own |
| --- | --- | --- |
| `ADCSamplingConfig` | Acquisition / conversion → `eoc_delay_s` (applied inside delay FR) | Compute / PWM update |
| `CommandTimingConfig` | `computation_delay_s`, `pwm_update_delay_s`, PWM zero-wait envelope | ADC EOC again |
| ZOH | Half-sample + sinc in delay FR when enabled | Extra pure-delay term in totals |

`TimingModel` exposes min/nominal/max pure-delay totals; ZOH half-sample is tracked separately for display.

---

## LoopModel contents

```text
blocks[]          LoopBlock chain (domain, delay, source, status)
timing            TimingModel
stability         Fc, PM, GM, all crossovers, Ms, Mt, poles, MULTI_CROSSOVER
phase_budget      Σ block phase ≈ open-loop phase @ Fc
gain_budget       Σ block gain ≈ open-loop gain @ Fc
headroom          static PCMD range
sampling          Fs/Fc, Fsw/Fc (configurable warn)
evidence[]        metric + assumptions + falsification_condition
```

---

## Solution Map V2

Unchanged mesh API (`build_fc_pm_solution_map`). V2 point path:

```text
Target Fc×PM
  → synthesize Tustin PI Exact H(z)   (b[], a[] direct)
  → L = fixed_loop × C(z)
  → margins + Ms + Mt
  → constraints (Fc err, PM, GM, Ms, Mt, sampling warn)
  → FEASIBLE / WARN-class / INFEASIBLE statuses
```

Candidates: **Robust / Balanced / Fast** — no opaque score; user selects.

---

## Exact H(z) chain

```text
Solution Map / Control Tools H(z)
  → controller_transfer_function=… (no Kp/Ti re-discretize)
  → Bode / closed loop
  → export_controller_c99 (copies b[]/a[])
  → float32 verify (optional FLOAT32_WARNING)
```

---

## FRA / plant source (data layer)

`PlantResponse` + `PlantResponseSource` (`ANALYTICAL` | `TIME_DOMAIN` | `MEASURED_FRA` | `IDENTIFIED_MODEL`).  
`correlate_plant_responses` compares curves — does **not** merge them. Guided FRA plant select remains a follow-on consumer (audit: still DEAD until wired).

---

## GUI surfaces (minimal)

Digital Loop Expert tab **Loop Chain / Evidence** renders `build_loop_model` output.  
Bode cursor phase budget uses `compute_phase_budget` (multiplicative keys).

---

## Explicit non-goals (this release)

Topology sprawl, AI auto-tune, FEM/SPICE transistor, datasheet scraping, second Bode engine in Web/GUI.
