# Changelog

This file keeps the **maintained product history**. Detailed debugging notes, one-off migration instructions, CI result snapshots and binary release artifacts are intentionally kept out of the source documentation tree; Git history, Pull Requests, Actions and Releases provide that archive.

## 9.4.2 — 2026-09-25

### Fixed — Windows release-test encoding

- writes the release-test CHANGELOG fixture explicitly as UTF-8, correcting the Windows CP1252 / UTF-8 mismatch that blocked v9.4.1 before Windows packaging;
- adds regression coverage for both CP1252 and UTF-8 default text encodings without weakening archive, runtime, or release checks;
- aligns package/runtime/version-test/README metadata to 9.4.2; existing tags are preserved;
- retains the complete V9.4 Smart Control feature set: eight-step Guided System Design, Fc–PM Solution Map integration, LLC envelope/constraint/ZVS/FHA–TD foundations, loss summaries and PFC magnetic tooling;
- retains the v9.4.1 packaging corrections: shared engineering data, verified frozen startup outside the source tree, fresh platform evidence, and both-platform draft-before-publication gates;
- no power-stage or control algorithms are changed in this patch. Full Windows/macOS CI and packaged self-tests remain required before publication.

### Engineering boundary

Software test success, packaged startup, model correlation and hardware validation remain distinct. Existing PARTIAL / APPROXIMATION / UNKNOWN model limitations are unchanged. The incomplete v9.4.0 release and failed v9.4.1 attempt are not recommended downloads; use the newest complete release.

## 9.4.1 — 2026-09-25

### Fixed — Complete and verified Smart Control desktop release

- includes shared `engineering_data` in both PyInstaller bundles, fixing the missing `brand_taxonomy.json` startup failure observed in the v9.4.0 macOS executable;
- replaces launch-only self-test invocation with a cross-platform subprocess verifier that waits, checks the exit code and requires a fresh version/platform/resource-hash report;
- extends the frozen self-test to construct Guided System Design in addition to all four Expert workspaces;
- retains the outer macOS `.app` directory in the ZIP;
- prevents partial public releases: both platform jobs must succeed, both archives and taxonomy contents are verified, and all assets are uploaded to a draft before remote sizes/digests are checked and publication is enabled;
- publishes machine-readable platform evidence and `SHA256SUMS.txt` with the two packages;
- adds negative regressions for failed/hung children, absent or incorrect reports, missing platforms and wrong bundled data;
- retains all V9.4 Smart Control and LLC engineering changes; no power-stage or control algorithms are changed in this packaging correction;
- preserves existing tags and marks the incomplete v9.4.0 release as superseded after the correction is published.

### Engineering boundary

These changes validate software packaging and startup, not hardware performance or the accuracy of every model. The PARTIAL / APPROXIMATION / UNKNOWN boundaries documented for V9.4 remain unchanged.

## 9.4.0 — 2026-09-25

### Added / integrated — Smart Control and engineering workflow

- integrates the previously unmerged `feature/v9.3-guided-smart-control-ui` work, including original feature head `ae58161b11c4246e7a81e25b25a9260ec065030d`;
- expands Guided System Design into eight explicit steps: topology, power stage, sensing, ADC, modulator, timing, controller and review, while retaining the Expert workspaces;
- adds live engineering summaries, explicit sensing/timing views, guided-definition re-entry and Solution Map interaction improvements;
- adds LLC operating-envelope, constraint and worst-case engines, plus charge-balance ZVS margin evaluation;
- adds critical-point FHA/time-domain comparison, convergence-aware evidence, waveform-loss provenance, lumped electro-thermal iteration and two-stage optimization foundations;
- adds LLC/PFC loss-summary views, component validation/brand taxonomy, PFC ferrite-inductor design and a persistent user-core library;
- includes the four LLC engineering audit/model-validation documents and associated regression tests;
- fixes the source launcher filenames/behavior, restores the explicit FRA Loop Designer button, and derives the launcher version badge from the runtime version.

### Release validation hardening

- removes an always-true optimizer ordering assertion and adds deterministic envelope/TD rejection-consumer tests;
- synchronizes package/runtime/version regression/README to 9.4.0;
- adds mandatory release-scope preflight documentation: identify intended branches/commits, verify merged ancestry and inspect the final release diff before tagging;
- retains the existing full-test, real-ngspice, version-contract and packaged-application verification paths; published 9.3.x tags are not moved.

### Engineering boundary

Smart Control is the guided system-definition workflow, not an unrestricted drag-and-drop simulator or AI hardware sign-off. Guided adapters currently support LLC FM voltage control and single-phase Totem-Pole PFC; other topology/plant-source placeholders remain reserved. Fc × PM Solution Map synthesis currently targets Tustin PI, not every controller family.

Several new physics capabilities are API/opt-in foundations: the default analysis and some GUI/PDF/Web consumers remain FHA-centric. Constant-current ZVS commutation, nonlinear device curves, winding AC loss, leakage and lumped thermal models retain their documented PARTIAL / APPROXIMATION / UNKNOWN / ESTIMATED status. A converged simulation or passing software regression does not establish hardware validation. See [LLC model validation](docs/LLC_MODEL_VALIDATION_REPORT.md).

## 9.3.1 — 2026-09-24

### Changed — Release packaging and documentation

- synchronized package metadata, runtime version, README badge and version regression to **9.3.1**;
- repackages the current `main` branch through the maintained Windows x64 / macOS Apple Silicon release workflow;
- carries the maintained GitHub Releases download path and the documented version-bump → CI tag → packaging process added after v9.3.0.

### Engineering boundary

This patch does not claim additional hardware validation or new power-stage algorithms beyond the current `main` branch. It publishes the current maintained source state with release/version metadata aligned.

## 9.3.0 — 2026-09-24

### Added — Guided System Design

- launcher entry **系统建模与设计 / Guided System Design** for LLC FM voltage-loop and single-phase Totem-Pole PFC;
- canonical guided control-system definition shared by GUI handoff and downstream engines;
- interactive **Fc–PM Solution Map** with constraint filtering before install into LLC / TTPL workspaces;
- automatic LLC full digital-loop build after guided design when applicable;
- localized Guided System Design strings (zh / en / ja / ko).

### Documentation / release

- README version badge aligned to **9.3.0**;
- binary download section pointing at GitHub Releases;
- maintained **[docs/RELEASE.md](docs/RELEASE.md)** describing the only supported publish path: bump `pyproject.toml` on `main` → CI creates `vX.Y.Z` → package → GitHub Release.

### Engineering boundary

Guided Design reuses existing LLC/PFC kernels; Solution Map install is fail-closed when constraints are not met. Topology placeholders outside LLC/TTPL remain roadmap-only.

## 9.2.3 — 2026-09-16

### Added — PFC Engineering Workspace V2

- explicit eight-stage single-phase TTPL engineering workflow from power-stage sizing through closed-loop verification;
- specification-driven `Lboost` and `Cbus` sizing, hold-up/ripple constraints and downstream parameter handoff;
- persistent PFC MOSFET user library with JSON import/export plus HF/slow-leg device/loss comparison;
- DC-bus capacitor-bank sizing, ESR/lifetime screening and semiconductor loss↔junction-temperature iteration;
- standalone AC Line / PF / THD and Switching / Zero Crossing engineering views consuming the maintained time-domain solver;
- frozen `PFCControlHandoff` exact-H(z) contract for current/voltage loops with no downstream Kp/Ti re-discretization;
- audited TTPL C99 export artifacts carrying the same normalized `b[]/a[]` coefficients used by analysis;
- four-switch TTPL shared-libngspice closed-loop co-simulation with line-polarity-aware gate scheduling;
- firmware-correlated float32 controller runtime including configured sensing poles, ADC quantization, digital filtering, timing, PI/PIF anti-windup and the eight-state TTPL zero-cross machine.

### Added — LLC / platform infrastructure

- LLC Primary/SR user MOSFET library with persistent JSON records and device comparison;
- evidence-driven `reference_designs/` contract and first `LLC_400V_53V_3kW` machine-readable evidence matrix;
- common project/provenance JSON schema plus executable provenance validator and regression tests;
- cross-workspace engineering-data catalog and device/magnetics evidence policy;
- MCP v2 Agent foundation (`power-design-mcp`) that wraps shared deterministic engineering kernels rather than duplicating equations;
- reproducible real Qt launcher screenshot capture script and CI screenshot artifact;
- packaged application `--self-test` that constructs all four workspaces offscreen and validates bundled-data provenance;
- release tag/package-version contract and dynamic release metadata;
- shared-ngspice circuit-simulation foundation for LLC and TTPL closed-loop verification;
- backend-neutral Circuit IR and deterministic netlist generation;
- batch ngspice ASCII RAW execution/parser;
- shared `libngspice` binding with external source callbacks and control/PWM event synchronization;
- standard waveform adapters for SPICE power/control traces;
- real-ngspice CI smoke workflow.

### Changed

- README/product positioning now presents Power Design Toolkit as an evidence-driven power-electronics CAE + digital-control platform rather than a single LLC calculator;
- PFC documentation now reflects the same engineering-workflow depth as the implemented TTPL code path;
- ngspice documentation now covers both LLC and TTPL shared-library closed-loop architectures;
- release CI runs the packaged executable instead of treating directory existence as a smoke test;
- repository-level target name/description/topics are source-controlled in `.github/REPOSITORY_SETTINGS.md` for application through GitHub repository settings.

### Fixed / validated

- exact-H(z) C99 export regression now uses a stable tuned PFC baseline without weakening the production stability gate;
- sampled-sense regression now respects finite analog front-end settling at the initial ADC instant;
- README Mermaid workflow syntax is GitHub-renderer compatible;
- full regression and real `libngspice` smoke paths are required before the release tag is created.

### Engineering boundary

The shared-ngspice power stages are switching-correlation models, not vendor semiconductor sign-off models. TTPL firmware execution is **firmware-correlated**, not C2000 instruction/register-level bit identity. Board-specific ADC rails/offsets, vendor nonlinear Coss/Qrr/Eon/Eoff surfaces, layout parasitics, complete startup/protection state machines and hardware validation remain separate evidence layers.

## 9.2.2 — 2026-09-15

### Added

- Simplified Chinese / English / Japanese / Korean desktop UI;
- localized in-application help and runtime UI strings;
- language-dependent CJK font stacks;
- i18n regression coverage for workspace UI/help strings and language persistence.

## 9.2.1 — 2026-09-15

### Added

- application-wide Help/F1 system for all four workspaces;
- implementation notes, model boundaries and known-limit sections inside the application;
- contact/support information and documentation links.

### Documentation

- formalized descriptions of FHA/HB/TD, mixed-domain digital loop analysis, sampling/timing separation, discretization, C99 DF2T/SOS, FRA de-embedding/model fitting and Auto Design.

## 9.2.0 — 2026-09-15

### Added — FRA Loop Designer

- Bode100 CSV, SIMPLIS TXT and Generic frequency/gain/phase import;
- explicit Plant TS vs Complete Loop TS semantics;
- existing-controller de-embedding and Equivalent Plant reconstruction;
- Quick Tune and New Structure controller workflows;
- target-Fc/PM Auto Design with robustness checks/fallback;
- low-order rational model identification with fit confidence;
- identified-plant × controller loop analysis;
- Bode, all-crossover PM/GM, S/T, Ms/Mt and model-derived step gating;
- exact H(z) / C99 export;
- shared controller catalogue alignment with Control Tools.

### Fixed / validated

- str-Enum GUI data handling in Complete Loop import;
- LEAD/LAG/1P1Z/Modified-PI parameter mapping;
- Type-II/III pole mapping;
- unified step authorization based on model confidence, loop status and measurement-band coverage;
- deeper FRA regression for multiple phase turns/crossovers and real Bode100-format fixtures.

## 9.1.0 — 2026-09-09

### Added

- LLC formula PDF worksheet with formulas, substituted numbers, units and model boundaries;
- versioned engineering project JSON with input and result/source metadata;
- improved SemVer update checking;
- report/project/GUI regression coverage.

## 9.0 — Digital control baseline

### Architecture

- promoted Control Tools exact H(z) to a first-class controller source;
- linked exact discrete coefficients into LLC loop analysis without PI/PID re-fit;
- consolidated sensing/ADC, FM/PWM, timing, stability and C99 coefficient semantics.

## 8.x — LLC multi-fidelity architecture

### Added

- common LLC analysis request/result contracts;
- FHA / nonlinear multi-harmonic HB / switched time-domain comparison;
- Golden/reference waveform and diagnostics structure;
- DCM/rectifier/SR timing/loss extensions;
- 2-phase and 3-phase interleaved LLC analysis;
- expanded magnetic/device loss and parasitic modelling.

## 7.x — Workspaces, PFC/Vienna and code generation

### Added

- independent LLC/PFC workspaces and later shared Control Tools workflow;
- three-phase Vienna PFC analysis;
- detailed TTPL/Vienna sensing/Bode/AC-cycle/switching views;
- PFC inductor design;
- LLC transformer design workflow;
- portable C99 `float32_t` controller generation;
- desktop UI restructuring, theme/update mechanisms and engineering waveform tools.

## Earlier history

Earlier iterations established the original LLC design workflow, Bode cursors, basic digital-control visualization and desktop packaging. Exact per-commit history remains available in Git.
