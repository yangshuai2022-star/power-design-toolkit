# PFC PF / THD V3

**Engine:** `pfc_design.engineering.pfc_v3.compute_pf_thd`  
**Closed-loop consumer:** `pf_thd_from_waveforms` (settled final AC period)

---

## Definitions

```text
S     = Vrms · Irms
PF    = Pin / S
DPF   = cos(∠V1 − ∠I1)
THD   = RSS(H2…Hn) / |I1|
DistortionFactor = |I1| / sqrt(|I1|² + RSS(H2…Hn)²)
```

Identity (within window/DC tolerance):

```text
PF ≈ DPF × DistortionFactor
```

`cos(φ)` alone is **DPF**, never total PF.

---

## THDConvention

| Field | Default |
| --- | --- |
| fundamental | DFT H1 RMS (phasor /√2) |
| harmonics | configurable, default 2…25 |
| window | rectangular, integer line cycles |
| cycles | 1 (settled) |

Residual `√(Irms²−I1²)` is **not** used (window sensitivity).

---

## Distortion localization

`localize_distortion` maps half-cycle regions:

```text
0–10° / 10–30° / 30–150° / 150–170° / 170–180°
```

Causes are evidence-gated (`ZERO_CROSS`, `MIN_PULSE`, …); otherwise **UNKNOWN**.

---

## Regression cases

| Case | Expectation |
| --- | --- |
| A Ideal in-phase sine | PF≈1, DPF≈1, THD≈0 |
| B Phase-shifted sine | DPF≈cos(φ), Distortion≈1 |
| C H3/H5 injection | THD ≈ analytic RSS |
| D DC offset | Sanity holds; no silent PF>1 |

Falsifier: GUI THD ≠ `PFTHDResult.thd_percent` on the same settled cycle.
