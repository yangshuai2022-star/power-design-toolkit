# PFC Smart Control V3

**Entry:** `build_pfc_smart_control_v3`  
**Aligned with:** LLC Smart Control V2 (`LoopModel` / phase budget / Ms·Mt / Exact H(z))

---

## Dual-loop chain

```text
Current: Iref → Ci(z) → InduComp → PWM/ZOH/Delay → Gid → Sense → Feedback
Voltage: Vref → Cv(z) → AMC/VFF → BusPlant(×Ti) → Sense → Feedback
```

---

## LoopSeparationResult

```text
Fc_current, Fc_voltage, ratio = Fc_i/Fc_v
2×fline marker (100 Hz @ 50 Hz grid, 120 Hz @ 60 Hz)
voltage_fc_vs_2fline
```

WARN when ratio < 5 or Fc_v approaches 2×fline (bus-ripple / PF risk).

---

## Stability pack (each loop)

```text
Fc, PM, GM, Ms, Mt, delay_margin, MULTI_CROSSOVER, PhaseBudget
```

Σ block phase ≈ open-loop phase (unwrap-safe, 3° tolerance).

---

## Exact H(z)

```text
Analysis controllers → PFCControlHandoff b[]/a[] → Bode / C99 / ngspice
```

`assert_handoff_matches_analysis` is the regression gate.

Falsifier: C99 regenerates coefficients from Kp/Ti.
