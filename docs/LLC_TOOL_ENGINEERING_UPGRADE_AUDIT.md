# LLC Tool Engineering Upgrade Audit

**Scope:** Operating Envelope · Constraint Engine · Worst Case · ZVS Margin · FHA↔TD validation  
**Date:** 2026-09-24  
**Branch context:** `feature/v9.3-guided-smart-control-ui` (working tree; unrelated Guided UI / PFC / MCP edits preserved)  
**Principle:** physics → compute → constraints → worst corner → user conclusion

---

## 1. Call chain (current)

```text
User Input (GUI / CLI / Web / MCP)
  → LLCDesignSpec (llc_design/core/spec.py)
  → design_tank() → TankDesign (core/tank.py)          [FHA Lr/Cr/Lm, fr, Ln, Q]
  → solve_frequency() / solve_operating_point()         [Gain → fs → stresses]
  → LLCOperatingPoint                                   [Ir, Im, Icomm, phase, Rac]
  → primary_bridge_loss / SR / magnetics / caps         [models/*]
  → LLCSystemAnalyzer.analyze() → SystemAnalysis        [feasibility + warnings]
  → optional: build_q_zvs_analysis()                    [Q/gain/ZVS maps]
  → optional: LLCGoldenSolver / solve_multifidelity()   [FHA / HB / TD]
  → optional: LLCOptimizer grid sweep                   [Ln,Q,fr,turns,devices]
  → Report (formula_pdf) / GUI widgets / Web API        [consume SystemAnalysis / MultiFidelity]
```

Web/API and GUI must not re-implement tank equations; they call the same Python kernels.

---

## 2. Capability classification

| Capability | Status | Evidence |
| --- | --- | --- |
| FHA | **ALIVE** | `core/tank.py`, `analysis/fha.py`, `operating_point.py` |
| Gain | **ALIVE** | `gain` / `gain_vector` / `target_gain` |
| Frequency Solver | **ALIVE** | `solve_frequency` (brentq roots, inductive preference) |
| Load Sweep | **PARTIAL** | Fixed work-point lists + Q/ZVS + new envelope corners |
| ZVS | **ALIVE** (L1/L2 this round) | `core/zvs_margin.py`; legacy ratio retained in `q_zvs` / `primary_bridge` |
| MOSFET Loss | **ALIVE** | `models/primary_bridge.py` (cond / Eoff / gate / Coss residual / diode) |
| Rectifier Loss | **ALIVE** | `models/synchronous_rectifier.py` |
| Transformer Loss | **ALIVE** | magnetics transformer + Litz/Dowell / iGSE (engineering reference data) |
| Core Loss | **PARTIAL** | iGSE on reconstructed B(t); reference materials, not vendor-qualified |
| Thermal | **PARTIAL** | Rth hotspot estimates; no full thermal network |
| Component Database | **ALIVE** | Device JSON + user library; cores in magnetics DB |
| Worst Case | **ALIVE** (this round) | `WorstCaseFinding` names corners; system still also has loss min/max |
| Optimizer | **PARTIAL** | Discrete grid (`optimization/sweep.py`) + Pareto; no constraint engine |
| Report | **ALIVE** | `report/formula_pdf.py`, multifidelity export |
| Operating Envelope | **ALIVE** (this round) | `core/engineering.py` |
| Constraint Engine | **ALIVE** (this round) | PASS/WARN/FAIL/UNKNOWN in `engineering.py` |
| FHA↔TD Validity Gate | **ALIVE** (this round) | `analysis/fha_td_validation.py` |
| Charge-balance ZVS L2 | **ALIVE** (this round) | `core/zvs_margin.py`; wired into SystemAnalysis warnings |

---

## 3. Module audit table

| Module | Current capability | Model | Inputs | Outputs | Callers | Assumptions | Limits | Suggested enhancements |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `core/spec.py` | Full design input | Spec dataclass | Vin/Vo/P, fr/Ln/Q or Lr/Cr/Lm, devices, T, deadtime | `LLCDesignSpec` | All | FB/HB LLC, FB-SR | No envelope/tolerance fields | Envelope as separate object; keep spec stable |
| `core/tank.py` | FHA tank + fs solve | FHA phasor | Spec, Rac, f | TankDesign, FrequencySolution | OP, FHA, Q/ZVS, system | Ideal L/C, FHA Rac | No ESR in gain path for design | Keep formulas; do not rewrite |
| `core/operating_point.py` | One regulated OP | FHA | Spec, tank, Vbus, load | `LLCOperatingPoint` | System, loss, ZVS | min load clamp 10% | No constraint status | Wrap into OperatingPointResult |
| `core/q_zvs.py` | Q/gain/ZVS maps | FHA + device Qoss/Coss | Spec, loads, Vbus | Map + workpoints | GUI Q/ZVS view | Constant Icomm·tdead | Margin = ratio not surplus | Call `zvs_margin` Level 1/2 |
| `analysis/fha.py` | FHA waveforms | FHA | LLCAnalysisRequest | LLCModelResult | Golden | Sinusoidal states | No device Coss dynamics | Reference for FHA↔TD |
| `analysis/harmonic_balance.py` | Multi-harmonic HB | Nonlinear HB | Request + config | LLCModelResult | Golden | Odd harmonics | Light-load fallback | Out of scope this round |
| `analysis/time_domain.py` | Switched PSS | Piecewise TD | Request + config | LLCModelResult | Golden | Ideal switches | Not vendor Coss | Reuse for FHA↔TD |
| `analysis/golden.py` | Multi-fidelity compare | Orchestration | Request | MultiFidelityAnalysis | GUI, tests | Best converged ref | % errors only | Feed DeviationResult / validity |
| `models/primary_bridge.py` | MOSFET loss + ZVS ratio | Semi-empirical | OP + MosfetSpec | PrimaryBridgeLoss | System | Single-point Qoss/Coss | APPROX not labeled | Use shared zvs_margin |
| `models/synchronous_rectifier.py` | SR loss/timing | Engineering | OP + device | SR loss | System | Timing params | — | Defer rewrite |
| `models/system.py` | End-to-end analysis | Aggregation | Spec, work points | SystemAnalysis | Optimizer, GUI, PDF | Fixed default corners | Feasibility as string list | Attach EnvelopeEvaluation |
| `magnetics/*` | Tx / Lr design + loss | Area-product, Litz, iGSE | Spec, OP set | Designs + loss | System | Reference cores | Leakage not FEA | Document next phase |
| `optimization/sweep.py` | Grid search | Discrete | OptimizationConfig | DataFrame + Pareto | CLI/GUI | Feasible flag | No envelope corners | Wire constraints later |
| `report/formula_pdf.py` | Formula dump | Text | Spec/OP/loss | PDF | GUI | Mirrors V1 equations | — | Emit ZVS_MARGIN fields |
| `control/solution_map.py` | Control Fc/PM map | Small-signal | Gvf, constraints | Solution map | GUI | Control only | Not power-stage | Do not conflate |
| Web / MCP | Front ends | API | Spec JSON | Analysis JSON | Users | Shared kernels | — | Consume new results |

---

## 4. Explicit answers (Phase 1)

### Where FHA is used
Tank synthesis, gain-frequency solve, operating-point currents, Q/ZVS maps, primary/SR/magnetic loss drivers, optimizer candidates, FHA fidelity in Golden solver, formula PDF.

### Where time-domain exists
`analysis/time_domain.py` → `dynamics/switched.py` periodic shooting; also complementarity TD and multiphase star TD. ngspice is a separate switching-correlation path (not LLC FHA kernel).

### ZVS criterion (today)
1. Theoretical: `input_phase_deg > 0` (Im{Zin} > 0).  
2. Engineering: `I_comm * t_dead / Q_required` and energy ratio vs `0.5·Coss·V²`; fail if min ratio &lt; 1.0; warn if &lt; `primary_zvs_margin_required`.  
`I_comm = max(0.75·Im_peak, |Ir_peak·sin(φ)|)`.

### MOSFET / rectifier loss
Primary: conduction (series Rds), Eoff ∝ Icomm, gate, residual Coss when ZVS incomplete, body-diode deadtime.  
SR: conduction, deadtime diode, turn-off, Coss fraction, gate (`synchronous_rectifier.py`).

### Magnetics depth
Transformer + resonant inductor synthesis, Litz/foil copper, temperature iGSE core loss, gap fringing term for Lr. Evidence: reference materials — not hardware-qualified.

### Optimizer
Variables: Ln, Q, fr, Np, Ns, primary device, SR parallel. Objective: Pareto on efficiency / size / stress proxies. Constraints: feasibility from SystemAnalysis strings.

### Sweep dimensions
Same as optimizer grid; Q/ZVS uses load × frequency mesh at fixed Vbus_nom (plus discrete Vbus workpoints).

### PDF / Excel / Web consume
PDF: formula + OP numbers from SystemAnalysis. Multifidelity export: CSV/MD metrics. Web/backend: shared analyzers (control export present; LLC web mirrors kernels). Excel path via web optional openpyxl — no duplicate equations intended.

---

## 5. Frozen architecture rules (this upgrade)

- Do not delete verified FHA formulas in `tank.py` / `operating_point.py`.
- No large aesthetic GUI/CSS refactors.
- Public APIs of existing dataclasses stay; new types are additive.
- New models compatible with `LLCOperatingPoint` / `LLCAnalysisRequest` / `MosfetSpec`.
- Existing tests must keep PASS; new physics get unit tests.
- Prefer Core → Service → API; Web must not duplicate equations.

---

## 6. This-round implementation targets

| Item | Action |
| --- | --- |
| OperatingEnvelope | First-class ranges + tolerance corners |
| OperatingPointResult + ConstraintResult | PASS/WARN/FAIL/UNKNOWN |
| WorstCaseFinding | Identify which corner is worst per metric |
| ZVS Level 1 / 2 | Inductive + sign; charge-balance margin + MODEL_SOURCE |
| FHA↔TD | DeviationResult + MODEL_VALIDITY on critical points |
| Magnetics / Loss / Optimizer / Report | Wire only if low-risk; else next phase |

---

## 7. Next-phase suggestions (deferred)

- Full magnetic redesign / leakage FEA precision claims  
- Full loss-engine rewrite with nonlinear Coss(V) curves  
- Optimizer AI / multi-objective continuous search  
- Big GUI for envelope visualization  
- Thermal network + derating automation  
- Marking APPROXIMATION results as VERIFIED (forbidden)
