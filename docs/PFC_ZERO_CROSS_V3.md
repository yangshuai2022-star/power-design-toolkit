# PFC Zero Crossing V3

**Analyzer:** `pfc_design.engineering.pfc_v3.analyze_zero_crossing`

---

## Inputs

Closed-loop `PFCLineCycleResult` (or config → simulate) plus:

```text
minimum_effective_pulse_s, duty_min, fsw, L, Vbus, deadtime_s, sensor_offset_a
```

---

## Outputs

Per crossing / zoom (±1/2/5/10°):

```text
Vac, Iref, Iactual, duty_cmd, duty_effective, pulse_width,
pulse_valid, commutation_state, current_error, distortion_margin
```

Analytical bounds (APPROXIMATION):

```text
effective_duty_deadzone = max(duty_min, t_min_pulse · fsw)
minimum_realizable_current ≈ Dmin · Vbus / (L · fsw)   near Vac≈0
dead_time_voltage_error ≈ Vbus · td · fsw
```

---

## Isolated regressions

| Factor | Test |
| --- | --- |
| Ideal PWM | min-current ≥ 0, zooms present |
| Minimum pulse | raises deadzone & min current |
| Dead time | voltage error scales with td |
| Sensor offset | shifts Iactual by offset only |

Do not mix all factors in one test.

Falsifier: raising `minimum_effective_pulse_s` leaves `minimum_realizable_current_a` unchanged.
