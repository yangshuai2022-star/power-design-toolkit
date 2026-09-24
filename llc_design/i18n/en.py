"""English catalogue.

Policy: strings that are already English in the source have no entry here —
they are returned unchanged by :func:`llc_design.i18n.t`.
"""

CATALOGUE: dict[str, str] = {
    # ------------------------------------------------------------------ shell
    "电源设计工具箱 — 选择设计功能": "Power Design Toolkit — Choose a Workspace",
    "请选择进入的设计工作区": "Choose the workspace to enter",
    "LLC、PFC、数字控制工具与 FRA Loop Designer 使用独立工作区；": "LLC, PFC, Digital Control Tools and the FRA Loop Designer are separate workspaces;",
    "FRA 工作区支持控制器剥离、实时整定、目标 Fc/PM 自动设计与低阶模型辨识。": "the FRA workspace supports controller de-embedding, live tuning, Auto Design to a target Fc/PM and low-order model identification.",
    "进入 LLC 设计": "Enter LLC Design",
    "谐振腔、磁性器件、损耗、开关波形、小信号与数字电压环": "Resonant tank, magnetics, losses, switching waveforms, small-signal and the digital voltage loop",
    "进入 PFC 设计": "Enter PFC Design",
    "单相 TTPL + 三相 Vienna：控制、采样链、Bode、AC 周期、开关波形与 PF/THD": "Single-phase TTPL + three-phase Vienna: control, sensing chain, Bode, AC line cycle, switching waveforms and PF/THD",
    "进入 Control Tools": "Enter Control Tools",
    "S2Z、数字滤波器、Bode、Step/Impulse、P/Z、SOS 与 C99 float32_t 导出": "S2Z, digital filters, Bode, Step/Impulse, P/Z, SOS and single-file C99 float32_t export",
    "进入 FRA Loop Designer": "Enter FRA Loop Designer",
    "Bode100 / SIMPLIS / Generic：Equivalent Plant、Auto Design、Model ID、稳定性与 C99": "Bode100 / SIMPLIS / generic: Equivalent Plant, Auto Design, Model ID, margins and C99",
    "退出": "Quit",
    "使用说明 / 帮助 (F1)": "Help (F1)",
    "四个工作区分别做什么、如何选择、通用操作与快捷键": "What each workspace does, how to choose, general operation and shortcuts",
    # ---------------------------------------------------------------- toolbar
    "电源设计工具箱 — LLC Design / Waveform / Control": "Power Design Toolkit — LLC Design / Waveform / Control",
    "电源设计工具箱 — PFC Design: TTPL / Vienna": "Power Design Toolkit — PFC Design: TTPL / Vienna",
    "电源设计工具箱 — Digital Control Tools": "Power Design Toolkit — Digital Control Tools",
    "电源设计工具箱 — FRA Loop Designer": "Power Design Toolkit — FRA Loop Designer",
    "工程": "Project",
    "加载 JSON": "Load JSON",
    "保存工程 JSON": "Save project JSON",
    "导出公式 PDF": "Export formula PDF",
    "输出目录": "Output folder",
    "切换到 PFC": "Switch to PFC",
    "切换到 LLC": "Switch to LLC",
    "功能选择": "Workspace",
    "帮助": "Help",
    "语言 / Language": "Language / 语言",
    "检查更新": "Check for updates",
    "隐藏设计参数": "Hide design parameters",
    "显示设计参数": "Show design parameters",
    "显示/隐藏 LLC 全局设计参数（F4）": "Show or hide the global LLC design parameters (F4)",
    "运行日志": "Run log",
    "专注模式": "Focus mode",
    "运行当前": "Run current page",
    "运行当前页面对应的分析（Ctrl+R）": "Run the analysis for the current page (Ctrl+R)",
    "关于": "About",
    "关于 PFC": "About PFC",
    "PFC 工作区": "PFC workspace",
    "运行当前 PFC 分析": "Run current PFC analysis",
    "重新计算": "Recompute",
    "导出单文件 C99": "Export single-file C99",
    "导入 FRA": "Import FRA",
    "导出 C99": "Export C99",
    "PFC 工作区就绪": "PFC workspace ready",
    "就绪": "Ready",
    "专注模式：已隐藏全局参数与运行日志": "Focus mode: global parameters and run log hidden",
    # ----------------------------------------------------------------- updater
    "点击发送邮件：maileyang@qq.com\n": "Click to send an e-mail: maileyang@qq.com\n",
    "有不懂的地方、或结果与实测不符，欢迎直接发邮件讨论（帮助 F1 → 联系方式与支持）": "If anything is unclear, or a result disagrees with measurement, feel free to e-mail me (Help F1 → Contact & Support)",
    "微信: maileyang": "WeChat: maileyang",
    "微信号: maileyang\n": "WeChat ID: maileyang\n",
    "公众号 / 技术博客: 开关电源仿真与实用设计（帮助 F1 → 联系方式与支持 内有二维码）": "Official account / blog: 开关电源仿真与实用设计 (QR code under Help F1 → Contact & Support)",
    "(该版本未附带发布说明)": "(this release has no notes attached)",
    "发现新版本": "New version available",
    "打开下载页": "Open download page",
    "知道了": "Close",
    "当前已是最新版本 {APP_VERSION}。": "Already up to date ({APP_VERSION}).",
    "检查更新失败": "Update check failed",
    "无法连接到 GitHub,请检查网络后重试。\n": "Could not reach GitHub. Check your network and try again.\n",
    # -------------------------------------------------------------- help title
    "LLC Design 工作区 — 使用说明": "LLC Design workspace — User guide",
    "PFC Design 工作区 — 使用说明": "PFC Design workspace — User guide",
    "Digital Control Tools 工作区 — 使用说明": "Digital Control Tools workspace — User guide",
    "FRA Loop Designer 工作区 — 使用说明": "FRA Loop Designer workspace — User guide",
    "功能选择 — 该进哪个工作区": "Workspace selection — which one do I need?",
    "工具箱按工程任务分成四个独立工作区，各自保持状态，可用工具栏随时切换。": "The toolkit is split into four independent workspaces, each keeping its own state; the toolbar switches between them at any time.",
    # ------------------------------------------------------------ help sections
    "快速上手": "Quick start",
    "页面说明": "Page reference",
    "页面与参数说明": "Page and parameter reference",
    "模型边界与已知限制": "Model boundary and known limits",
    "快捷键与操作": "Shortcuts and operation",
    "联系方式与支持": "Contact and support",
    "实现说明 — FHA / HB / TD 三种模型怎么算的": "Implementation — how FHA / HB / TD are computed",
    "实现说明 — 数字环与延时怎么建模的": "Implementation — how the digital loop and delays are modelled",
    "实现说明 — 采样链与延迟拆分（最容易出错的地方）": "Implementation — sampling chain and delay split (the easiest place to get wrong)",
    "实现说明 — 控制结构与求解器": "Implementation — control structure and solvers",
    "电感设计": "Inductor design",
    "控制器类型一览": "Controller catalogue",
    "实现说明 — 系数约定与离散化": "Implementation — coefficient convention and discretization",
    "实现说明 — C99 导出结构": "Implementation — C99 export structure",
    "实现说明 — 稳定性判定": "Implementation — stability classification",
    "测量语义：TS 类型不能猜": "Measurement semantics: the TS type must not be guessed",
    "控制器输入与整定": "Controller input and tuning",
    "实现说明 — 频响求值与裕度判据": "Implementation — frequency response and margin criteria",
    "实现说明 — 剥离、重建与辨识算法": "Implementation — de-embedding, reconstruction and identification",
    "实现说明 — 辨识模型 × 控制器与 Step": "Implementation — identified model × controller and the step gate",
    "实现说明 — Auto Design 怎么综合的": "Implementation — how Auto Design synthesises",
    "假设与已知限制": "Assumptions and known limits",
    "四个工作区": "The four workspaces",
    "怎么选": "How to choose",
    "每个工作区的帮助里有什么": "What each workspace's help contains",
    "通用提示": "General notes",
    "此章节暂无当前语言的正文译文，以下显示原文。": "This section has no translation in the active language yet; the original text is shown below.",
    # ------------------------------------------------------------- help bodies
    "helpbody.common.shortcuts": """F1            Open help for the active workspace (any workspace)
F4            LLC: show/hide the design parameter panel
F8            LLC: show/hide the run log
F9            LLC: focus mode (hides parameters and run log)
Ctrl+R        LLC: run the analysis for the current page
Toolbar       Top of each workspace: switch workspace, run/recompute, export,
              help, contact, update check
""",
    "helpbody.common.contact": """E-mail    maileyang@qq.com
WeChat    maileyang
Official account / blog  开关电源仿真与实用设计 (scan the QR code below)

If something is unclear, if you are unsure about a trade-off, or if a result
disagrees with measurement or theory, please just e-mail me. Engineering
questions usually need the actual topology, operating point and waveforms to
answer, so a discussion is often faster than reading documentation — and I do
want to know where these tools get stuck on real projects.

When you write, it helps to include:

  1. workspace and version (Help -> About, or the version next to
     "Check for updates" in the toolbar)
  2. the key input parameters (a screenshot of the parameter panel is fine)
  3. the symptom: expected result vs actual result, ideally with a screenshot
     or the exported CSV/JSON
  4. for measurement-related questions (especially FRA): how you measured,
     where you injected, and whether the data already contains the current
     controller

Many "this looks wrong" cases are actually documented model boundaries rather
than defects — for example FHA far from resonance, sampled Ms/Mt falling between
sweep points, or a Complete Loop record without the real C_old. Each workspace's
"Model boundary and known limits" section covers these.
""",
    "helpbody.common.about": """Power Design Toolkit V{version}
Author: Yang Shuaiguo (杨帅锅)
E-mail    maileyang@qq.com
WeChat    maileyang
Official account / blog  开关电源仿真与实用设计

LLC / PFC / Vienna design, digital control tools and FRA loop design.
License: GNU GPL v3.

This is an engineering design aid. Every result rests on the models and
assumptions written down in each workspace's "Model boundary and known limits";
anything sent to hardware must still go through your project's measurement
verification. Questions are welcome by e-mail.
""",
    "helpbody.selector.workspaces": """LLC Design          Resonant tank design, multi-fidelity electrical analysis,
                    magnetics and losses, SR, interleaving, waveforms,
                    small-signal and the digital voltage loop. Start here for a
                    complete converter design from a specification.
PFC Design          Single-phase TTPL and three-phase Vienna: firmware-shaped
                    dual-loop control, sensing chain, Bode, full AC line cycle,
                    switching waveforms, PF/THD and inductor design.
Control Tools       Standalone digital controller/filter design: choose a
                    structure, watch H(s)/H(z), inspect Bode/Step/Impulse/
                    pole-zero/group delay, export single-file C99.
FRA Loop Designer   Controller tuning from measured frequency response
                    (Bode100/SIMPLIS/generic), Auto Design to a target Fc/PM,
                    low-order model identification, and closed-loop analysis of
                    an identified model with any controller.
""",
    "helpbody.selector.how_to_choose": """* Specification only, designing from scratch -> LLC Design or PFC Design.
* Power stage already exists, design or review controller coefficients ->
  Control Tools.
* You have a machine and a frequency sweep and want to know how much margin the
  current loop has and how to change the controller -> FRA Loop Designer; do
  Model ID first and hand the model back if you also want a time-domain
  prediction.
* Once FRA produced a controller you can re-check the coefficients and the
  export format in Control Tools, or export the C99 directly from the FRA
  workspace.
""",
    "helpbody.selector.what_help_contains": """Every workspace's help contains: quick start, page and parameter reference,
**implementation notes** (how the algorithms and coefficient conventions
actually work), model boundary and known limits, shortcuts, and contact
information.

If a step is unclear, or a result disagrees with measurement or theory, read the
implementation notes first and then check the model boundary to confirm whether
the conclusion is even inside what the model can claim.
""",
    "helpbody.selector.general_tips": """* Every workspace toolbar has 帮助 (F1), contact information and an update
  check on the right.
* The update check runs once silently after start-up and only prompts when a
  newer release exists; a version can be dismissed and remembered.
* "Workspace" returns to the selector at any time; switching workspaces does not
  lose the state of the other windows.
* Engineering questions are welcome by e-mail (see "Contact and support").
""",
    "helpbody.fra.ts_semantics": """Plant TS           The data is already the plant, without the controller:
                   L_new = G_plant * C_new
Complete Loop TS   The data is the closed-loop loop gain / return ratio and does
                   contain the current controller:
                   G_eq = H_scan / C_old

In Complete Loop mode, PWM, ADC, sensing/filtering and real delays are NOT added
again, because they are already inside the measured data. The tool immediately
reconstructs H_scan algebraically and reports the reconstruction error.

Important: the reconstruction check only verifies the complex division and
multiplication and its numerical implementation. If C_old is entered wrongly,
the wrong controller is divided out and multiplied back in, and the
reconstruction still "passes". Hardware controller provenance has to come from
the user.

If the imported file is the ordinary closed-loop reference-to-output transfer T
rather than a loop gain, it cannot be de-embedded directly; convert it first
with L = T/(1-T) (unity feedback case).
""",
    "helpbody.control.controller_catalogue": """Integrator            gain
PI                    Kp, Ti
PIF                   Kp, Ti, LPF pole
PID                   Kp, Ti, Td
PIDF                  Kp, Ti, Td, LPF pole
Analog Type-II        fp0, fz1, fp1   or R1/R2/C1/C2
Analog Type-III       fp0, fz1, fz2, fp1, fp2   or R1/R2/R3/C1/C2/C3
Modified PI           gain, fz1, fp1
Lead / Lag / 1P1Z     gain, fz1, fp1
2P2Z / 3P3Z           equal-order finite pole/zero (gain + N zeros + N poles)
General H(s)          explicit numerator / denominator coefficients

The Filter Designer tab additionally offers IIR (Butterworth / Bessel /
Chebyshev I / II / Elliptic), FIR window, moving average and a DC blocker.

Note: the manual 2P2Z / 3P3Z entry is the equal-order finite pole/zero form,
while FRA Auto Design uses power-compensator templates with an integrator pole.
The two are different, so Auto Design results are written back as exact H(z).
""",
    "helpbody.llc.limits": """* FHA keeps the fundamental only; it must not be used to claim ZVS margin.
* HB is a self-consistent solution of the selected odd harmonics together with
  the rectifier commutation state, not a linear superposition; near light load
  and the discontinuous topology transition it may only return a regularised
  projection with a warning.
* TD uses ideal switches and a piecewise-linear model: no parasitics, dead-time
  detail or device nonlinearity.
* The "engineering ZVS" boundary in the Q/ZVS view is an engineering criterion,
  not a device-level dead-time/junction-capacitance simulation.
* The small-signal and digital-loop models are averaged models: no switching
  ripple, sampling jitter or quantisation noise. FM LUT segment gain and
  comparator quantisation are not part of the linear model.
* Exported C99 contains the controller coefficients and the documented timing
  convention only; the actual sampling instant, update instant and
  saturation/anti-windup still have to be aligned on the project side.
""",
    "helpbody.control.limits": """* What is exported is the controller **mathematics**; sampling instant, update
  instant, saturation and anti-windup and the state reset policy have to be
  implemented in firmware according to the project convention.
* Filters are ideal-coefficient designs without a fixed-point quantisation error
  budget.
* Bode is the discrete-system response; the analog H(s) curve is a reference
  only, and the two must separate near Nyquist.
* Group delay is computed in samples and converted to seconds on the page.
""",
    "helpbody.fra.assumptions": """1. A measured file does not itself contain the firmware controller parameters;
   without a real C_old a Complete Loop record can only be used as a numerical
   stress case for import/margins/fitting, and cannot produce a physically valid
   plant.
2. PM / GM / Ms / Mt are frequency-domain robustness evidence that holds under
   the usual power-converter assumption that the plant contains no unaccounted
   right-half-plane poles. They are not a topology-independent proof of
   closed-loop stability; a frequency response cannot reveal the open-loop RHP
   pole count P.
3. Ms / Mt are low-confidence between sweep points: a resonance narrower than
   the sweep spacing can fall between samples, so the sampled value is not a
   mathematical upper bound.
4. The rational fitter is constrained to the stable half-plane, so it cannot
   identify a genuinely unstable open-loop plant.
5. Auto Design currently synthesises PI / PIF / PID / Power 2P2Z / Power 3P3Z;
   the other structures are available for manual design and through the exact
   H(z) entry.
""",
    # help dialog chrome
    '关闭': 'Close',
    '本地未包含 {name}（打包版本不携带 Markdown 源文件），已尝试在浏览器打开 GitHub 上的同名文档。': 'The packaged build does not ship {name} (Markdown sources are not bundled); tried to open the same document on GitHub instead.',
    # workspace chrome harvested from the built windows
    '设计总览': 'Overview',
    '增益 / 工作区': 'Gain / operating region',
    '变压器': 'Transformer',
    '波形': 'Waveforms',
    '小信号': 'Small-signal',
    '小信号 G(s) / G(z)': 'Small-signal G(s) / G(z)',
    '数字控制': 'Digital control',
    '多负载 Gain / Q': 'Multi-load Gain / Q',
    '工作点': 'Operating point',
    '工作点表': 'Operating point table',
    '损耗分解': 'Loss breakdown',
    '损耗汇总': 'Loss summary',
    '局部开关周期': 'Local switching period',
    '完整 AC 周期': 'Full AC line cycle',
    '详细开关波形': 'Detailed switching waveform',
    '详细分段波形': 'Detailed piecewise waveform',
    '快速波形': 'Quick waveform',
    '快速 EDF 波形': 'Quick EDF waveform',
    '多谐波 HB 波形': 'Multi-harmonic HB waveform',
    '横轴使用 Fn=Fsw/Fr': 'X axis uses Fn = Fsw/Fr',
    '适应': 'Fit',
    '全屏': 'Full screen',
    '全屏框图': 'Full-screen diagram',
    '全部关闭': 'Collapse all',
    '全部显示': 'Show all',
    '隐藏参数': 'Hide parameters',
    '隐藏框图': 'Hide block diagram',
    '隐藏环节参数': 'Hide stage parameters',
    '传递函数 ▸': 'Transfer functions ▸',
    '仅开环': 'Open loop only',
    'LLC 设计参数': 'LLC design parameters',
    '自动设计变压器': 'Auto-design transformer',
    '计算 SR Timing / Loss': 'Compute SR Timing / Loss',
    '计算 Interleaved LLC': 'Compute interleaved LLC',
    '计算电感': 'Compute inductor',
    '重新计算 Q / ZVS': 'Recompute Q / ZVS',
    '运行 LLC 完整计算': 'Run full LLC computation',
    '运行 FHA / HB / TD 对比': 'Run FHA / HB / TD comparison',
    '运行分段时域参考': 'Run piecewise time-domain reference',
    '应用匝数到 LLC 主设计': 'Apply turns to the LLC main design',
    '应用 L / DCR 到功率级': 'Apply L / DCR to the power stage',
    '导出设计结果': 'Export design result',
    '设计结果 / 绕组': 'Design result / windings',
    '复制 Auto Tank → User Defined': 'Copy Auto Tank → User Defined',
    '启用 R·I + L·dI/dt 电感压降前馈': 'Enable R·I + L·dI/dt inductor drop feed-forward',
    '建立 / 更新完整数字电压环': 'Build / update the full digital voltage loop',
    '建立小信号对象': 'Build the small-signal object',
    '使用 Control Tools 当前 H(z)': 'Use the current Control Tools H(z)',
    '由功率级工作频率反求 PCMD': 'Solve PCMD from the power-stage operating frequency',
    '生成 C99': 'Generate C99',
    '生成 C99 控制代码': 'Generate C99 control code',
    '运行分析': 'Run analysis',
    '分析摘要': 'Analysis summary',
    '功率级': 'Power stage',
    '功率级/波形': 'Power stage / waveform',
    '双环控制器': 'Dual-loop controller',
    '双环 / Balance': 'Dual loop / Balance',
    '外置滤波/ADC': 'External filter / ADC',
    '8 路采样链': '8-channel sensing chain',
    '电流环 Bode': 'Current loop Bode',
    '电压环 Bode': 'Voltage loop Bode',
    '采样链 Bode': 'Sensing chain Bode',
    'AC 控制细节': 'AC control details',
    'Bode / 稳定性': 'Bode / stability',
    '锁定 ABC 三相参数（硬件滤波共用；关闭后启用增益/偏置失配诊断）': 'Lock ABC three-phase parameters (shared hardware filter; disabling enables gain/offset mismatch diagnostics)',
    '启用 Third-Harmonic / common-mode injection': 'Enable Third-Harmonic / common-mode injection',
    '一键稳定整定并应用': 'One-click stable tuning and apply',
    '一键导出单文件 C99 float32_t / DF2T': 'One-click single-file C99 float32_t / DF2T export',
    '从功率级同步': 'Sync from power stage',
    '包含 Zero-Order Hold': 'Include Zero-Order Hold',
    '导出最终 H(z) — C99 float32_t': 'Export final H(z) — C99 float32_t',
    '当前 PI → New Structure': 'Current PI → New Structure',
    '恢复固件原始 PI': 'Restore firmware original PI',
    '整定参数复位': 'Reset tuning parameters',
    '计算闭环 Step': 'Compute closed-loop step',
    '清除辨识模型': 'Clear identified model',
    '选择并导入 FRA 文件': 'Choose and import an FRA file',
    '打开文档': 'Open document',
    '实现说明（算法与系数约定）': 'Implementation notes (algorithms and coefficient conventions)',
    'FRA Loop Designer V1 契约': 'FRA Loop Designer V1 contract',
    'V1.5 / V2 契约': 'V1.5 / V2 contract',
    'FRA 深度审计': 'FRA deep audit',
    '审计附加说明': 'Audit addendum',
    'V8 实现说明': 'V8 implementation notes',
    'V9 数字控制基线': 'V9 digital control baseline',
    'V9.2.1 发布说明': 'V9.2.1 release notes',
    'PFC 控制台变更': 'PFC control lab changelog',
    '详细结果 / 差分方程': 'Detailed result / difference equation',
    'helpbody.common.language': 'UI language   简体中文 / English / 日本語 / 한국어\nWhere         Right-hand end of any workspace toolbar: "语言 / Language".\n              The choice applies immediately, is remembered, and is reused at\n              the next start.\n\nNotes\n* Wording that is already English in the source (Bode, H(z), C99, Kp, PM, FRA,\n  Summary, ...) is deliberately left as written. Consistent terminology matters\n  more here than translating every word.\n* Help bodies are translated per section. A section that has no body\n  translation yet shows the original text and says so above the body.\n* Switching language changes interface text only; no result, coefficient or\n  exported file is affected.\n* The font stack follows the language (Meiryo / Yu Gothic for Japanese,\n  Malgun Gothic for Korean, Microsoft YaHei / Source Han for Chinese) so shared\n  Han characters are not rendered with Chinese glyph shapes.\n',
    'helpbody.llc.quick_start': '1. Fill in the specification in the left "Design parameters" panel (F4 shows/hides it):\n   bus input, output voltage/current, switching-frequency range, tank parameter mode\n   (auto / user-defined Lr-Cr-Lm). After changing the specification press Ctrl+R or the\n   toolbar "Run current page".\n2. "Overview" gives the operating point, required gain and key stresses. Confirm in\n   "Gain / operating region" that the required gain is reachable over the whole frequency\n   range (both light and full load curves must cover it).\n3. "Q / ZVS" checks the tank Q and the theoretical/engineering ZVS boundary; operating\n   points outside the engineering boundary should be avoided by design.\n4. When a more accurate electrical result is needed, use "FHA / HB / TD" to compare the\n   three fidelities.\n5. Compute the magnetics page by page ("Transformer", "SR Timing / Loss"), or drive the\n   design directly from a transformer specification sheet (TDK PQ presets, integer-turn\n   search, Litz selection).\n6. For the loop, go to "Small-signal" for Gvf(s)/Gvf(z), then to "Digital control" to\n   assemble controller + sampling/ADC + FM LUT/TBPRD modulator + PWM delay into a full\n   L(z) and export C99.\n\nToolbar: F4 design parameters, F8 run log, F9 focus mode, Ctrl+R run current page.\n',
    'helpbody.llc.pages': 'Overview             Specification -> operating point, required gain, primary/secondary\n                     current and capacitor stress, in one summary.\nGain / operating region  Family of normalized gain curves versus frequency with the\n                     real operating points; confirms the target gain is reachable.\nQ / ZVS              Tank Q sweep plus theoretical/engineering ZVS boundaries.\nFHA / HB / TD        The same electrical contract at three fidelities; the comparison\n                     reports convergence, frequency, gain, RMS/peak currents, resonant\n                     capacitor stress and the error against the highest fidelity.\nTransformer          AP/window/winding scheme, turns, current density, Dowell AC copper\n                     loss, core loss.\nSR Timing / Loss     Synchronous-rectifier Qrr, third-quadrant conduction, timing, LUT\n                     and loss accounting.\n2P / 3P Interleaved  Fixed 90 degree two-phase and fixed 120 degree three-phase\n                     interleaved LLC engines.\nWaveforms            Switching-period waveforms for the operating point plus dynamic\n                     phasor waveform reconstruction.\nSmall-signal         LLC power-stage small-signal Gvf(s) and the discretized Gvf(z).\nDigital control      Controller + sampling/ADC + modulator + PWM delay in one closed\n                     loop, with Bode, PM/GM, closed-loop poles and single-file C99.\n',
    'helpbody.llc.impl_models': 'FHA (fundamental approximation)\n  Only the fundamental of the bridge output voltage is kept: 4/pi*Vbus for a full bridge,\n  2/pi*Vbus for a half bridge. The secondary rectifier plus load is reflected as an\n  equivalent AC load Rac (8n^2/pi^2 magnitude, including the SR drop), the tank is solved\n  as an Lr-Cr-Lm series divider, and the operating-point equation is a one-dimensional\n  scalar root solve. Because only the fundamental is kept, the error is largest at light\n  load and away from the resonant frequency.\n\nHB (self-consistent nonlinear multi-harmonic balance)\n  This is NOT independent FHA circuits per harmonic added together. The solver iterates\n  the full-wave rectifier clamp together with all selected odd harmonic currents, for each\n  odd harmonic h:\n      Ir_h    = (Vbridge_h - Vprimary_h) / Zseries(h*ws)\n      Im_h    = Vprimary_h / Zm(h*ws)\n      Iload_h = Ir_h - Im_h\n  Vprimary(t) is generated from the polarity of the reconstructed load current, so the\n  commutation instants and the harmonic coefficients are mutually self-consistent; the\n  output side then enforces average rectified current balance for the specified resistive\n  load. The default harmonic sequence is adaptive: H1 -> H1/H3/H5 -> H1/H3/H5/H7.\n  Near light load and the discontinuous topology transition it may return a regularised\n  projection with a warning instead of an exact solution.\n\nTD (piecewise time domain)\n  Nonlinear piecewise-linear switching-period steady-state solver: the state equations\n  are built per topology segment and the periodic fixed point (steady state) is solved,\n  with ideal switches.\n\nSmall-signal (dynamics/plant.py)\n  Dynamic-phasor model: linearise the fundamental envelope to obtain Gvf, then discretize\n  to Gvf(z) for the digital-loop page.\n',
    'helpbody.llc.impl_digital_loop': 'The frequency domain is evaluated in a MIXED domain (control/digital_loop.py):\ncontinuous power-stage and analog blocks at s = jw, digital blocks at z = exp(jwTs).\nCascade order:\n\n    analog divider/filter -> ADC multi-SOC recursive average -> PI/PIF/2P2Z -> PCMD\n    -> piecewise FM LUT -> PWM/ZOH -> Gvf(s)\n\nAn additional all-discrete approximation is built specifically for the z-plane pole check.\n\nDelay: the "sample to actuation" delay is formed as application_delay minus the ADC\neffective sample offset, then split into an integer number of samples plus a first-order\nThiran fractional delay. The margins are reported for MIN / NOMINAL / MAX delay envelopes\nso the effect of firmware timing jitter on phase margin is visible.\n\nSaturation, burst mode, soft start, current-limit selection and the protection state\nmachines are nonlinear, so they are reported as validity conditions rather than being\nincluded in the linear Bode model.\n',
    'helpbody.pfc.quick_start': '1. Pick the topology in the sub-tabs at the top: Single-Phase TTPL PFC or\n   Three-Phase Vienna PFC.\n2. Fill the input tabs on the left in order: "Power stage", "Dual-loop controller",\n   "External filter / ADC" (Vienna: "Power stage", "Dual loop / Balance",\n   "8-channel sensing chain").\n3. Inductor values can be typed directly, or computed from core and winding on the\n   "Inductor design" page and written back with one click.\n4. Press the toolbar "Run current PFC analysis"; the result pages give current-loop,\n   voltage-loop and sensing-chain Bode, the full AC line cycle, switching-workpoint\n   waveforms and PF/THD.\n5. For production code use the `power_codegen` CLI to generate the C99 float32 controller.\n\nTTPL result pages: current loop Bode, voltage loop Bode, sensing chain Bode,\ninductor design, analysis summary.\nVienna result pages: Current Bode, Vdc Bode, Balance Bode, Sampling Bode,\ninductor design, Summary.\n',
    'helpbody.pfc.impl_sampling_chain': "Every loop's sampling chain is modelled explicitly and contains:\n\n      soc_count / soc_spacing   multi-SOC sampling sequence\n      computation_delay_s       computation delay\n      pwm_update_delay_s        PWM update delay\n      multi_soc_recursive       multi-SOC recursive average\n\nEngineering convention (it MUST match the firmware):\n\n      delay caused by ADC / SOC        belongs to the SAMPLING block\n      delay caused by computation and\n      PWM update                       belongs to the FIRMWARE block\n\nThe two blocks are NOT double counted. An earlier version counted both, which cost extra\nphase in the Bode and made the margins pessimistic; that is fixed.\n\nThe current loop uses current_computation_delay_s; the voltage loop uses\namc_update_delay_s + voltage_computation_delay_s. The multi_soc_recursive average lives in\nthe sampling block, so it appears in both the current and the voltage Bode - changing the\nsampling chain therefore moves every loop at once.\n",
    'helpbody.pfc.impl_control_structure': 'TTPL (single phase)\n  Firmware-shaped dual loop: current inner loop + voltage outer loop; the three sensing\n  chains (inductor current, input voltage, output voltage) are modelled separately.\n  The open-loop Bode plots open-loop responses only by default, and each transfer\n  function can be shown or hidden individually, which makes it possible to see which\n  block contributes the phase loss.\n  The switched-current reconstruction integrates CONTINUOUSLY ACROSS the PWM period\n  instead of resetting to a triangular ripple template every period (that reset used to\n  put an artificial discontinuity on the reconstructed current).\n  The full AC-cycle solver advances time over a complete line cycle until settled; the\n  zero-crossing analyser and the switching-workpoint waveforms are derived from it.\n  PF/THD/harmonics are computed from the whole-cycle result, not from a single point.\n\nVienna (three phase)\n  DC-voltage outer loop + three ABC stationary-frame current inner loops + a split-DC-bus\n  midpoint balance loop; three-level modulation supports common-mode / third-harmonic\n  injection. Each phase has its own current loop and sensing chain, and the balance loop\n  has its own Bode and midpoint-voltage response.\n',
    'helpbody.pfc.inductor': '* Core data comes from the Magnetics High Flux Core Data 254 set, including the\n  permeability roll-off under DC bias and the core-loss fit, so the L(I) curve shown is\n  the inductance after full-load roll-off.\n* Copper loss uses the hot-state DC resistance of enamelled copper wire for the DC I^2R\n  part; AC winding loss follows the project\'s existing model.\n* "Apply back" writes the inductance and turns into the power-stage parameters. After\n  applying, run the analysis again and confirm that current ripple, loop gain and THD are\n  still within the design targets.\n',
    'helpbody.pfc.limits': "* The control models are averaged models: no switching ripple, dead time, device\n  nonlinearity or digital quantisation noise.\n* The sampling-chain delay is a decisive assumption. If the firmware's actual sampling or\n  update instant differs from the page, the Bode phase margin shifts accordingly, so it\n  must be checked against the real firmware.\n* The AC line-cycle solver assumes an ideal sinusoidal, balanced grid; unbalanced or\n  harmonically distorted grids need separate verification.\n* PF/THD are model results and do not replace EMI pre-compliance or a calibrated power\n  meter measurement.\n* The midpoint balance loop and the dead-time / minimum-pulse constraints of three-level\n  modulation are not inside the averaged model.\n",
    'helpbody.control.quick_start': '1. Set the sample rate Fs and the S->Z discretization method in the top panel\n   (tustin / prewarp_tustin / backward_euler). Prewarped Tustin needs a prewarp frequency.\n2. On the "Controller" page choose the controller type; the panel then shows only the\n   parameters that structure actually needs.\n3. The "Live transfer function" box below the panel shows H(s) and H(z) immediately and\n   follows the sliders.\n4. Right-hand tabs: Bode / Step / Impulse / Pole-Zero / Group Delay /\n   Coefficients and SOS / Transfer Function / single-file C99.\n5. Export: fill in the Symbol Prefix, then toolbar "Export single-file C99".\n',
    'helpbody.control.impl_discretization': 'Coefficient convention (uniform across the toolkit):\n\n      H(z) = (b0 + b1 z^-1 + b2 z^-2 + ...) / (1 + a1 z^-1 + a2 z^-2 + ...)\n      y[n] = sum b[k]*x[n-k] - sum a[k]*y[n-k]\n\nEvery digital transfer function is normalized by a0 internally, so the a0 shown on the page\nis always 1.\n\nDiscretization (power_control_tools/discretize.py) does NOT use scipy.cont2discrete; it\nperforms the binomial expansion mapping itself:\n\n      Tustin (bilinear)   s = 2*Fs*(1 - q)/(1 + q),  q = z^-1\n      Prewarped Tustin    same, but k = wp / tan(wp/(2*Fs))\n                          (wp = 2*pi*prewarp frequency), which makes H(z) agree exactly\n                          with H(s) at that frequency\n      Backward Euler      s = Fs*(1 - q)\n\nThe reason for implementing it directly: an ideal PID is improper (numerator degree >\ndenominator degree), cont2discrete rejects it, while the term-by-term binomial mapping\nproduces a causal z-domain form for any structure. The prewarp frequency must lie strictly\nbetween 0 and Nyquist or the tool raises an error.\n',
    'helpbody.control.impl_c99_export': 'Single header-only file, typedef float float32_t; second-order sections in cascade\n(SOS) with DF2T (Direct Form II Transposed):\n\n      y  = b0*x + d1\n      d1 = b1*x - a1*y + d2\n      d2 = b2*x - a2*y\n\n  * the coefficient signs match the displayed H(z) exactly; nothing is sign-flipped\n    implicitly;\n  * each section keeps only d1/d2 as state, which minimises the state count and the\n    numerical dynamic range and suits float32;\n  * order three and above is split into cascaded second-order sections automatically,\n    avoiding the numerical sensitivity of a high-order direct form;\n  * Reset() clears every d1/d2; Run() cascades the sections;\n  * after exporting, the tool compiles the generated code with the local C compiler and\n    compares impulse and step responses point by point against the Python reference.\n    If no C compiler is on PATH the verification reports `C compiler not found` - that is\n    an environment limitation, it does not mean the generated code is wrong, and it never\n    pretends to have passed.\n',
    'helpbody.control.impl_stability': 'Poles are classified by radius (power_control_tools/models.py):\n\n      |p| > 1 + 1e-9     ->  UNSTABLE, export is refused\n      |p| >= 1 - 1e-9    ->  MARGINAL (an integrator / PI pole at z = 1 lands here)\n      otherwise          ->  STABLE\n\nAn ideal integrator and a PI controller are MARGINAL, which is legal for a controller\nbuilding block, so the export gate only rejects UNSTABLE; the panel still tells you the\nclosed loop has to be checked separately.\n\nTwo further engineering hints are shown:\n\n      pole radius > 0.995     the float32 implementation and transient robustness need review\n      critical frequency > 0.2*Fs   frequency warping deserves attention; consider prewarped Tustin\n',
    'helpbody.fra.quick_start': '1. In "1. FRA / Bode data" choose the source format and the TS type, then import.\n   If the data is a complete closed-loop loop gain (containing the current controller) you\n   MUST select Complete Loop TS and fill in the current controller truthfully in section 2,\n   otherwise the de-embedded plant is wrong.\n2. Complete Loop + Quick Tune: drag the gain/coefficient scales and watch the margins;\n   unity scales reproduce the measured loop exactly. Use New Structure for Plant TS or to\n   change structure.\n3. On the right: "Loop Bode" for the open loops, "S / T" for sensitivity and complementary\n   sensitivity, "Closed-Loop Step" for the model-derived step (tick the box to compute it),\n   and "Analysis Details" for every crossing and every withholding reason.\n4. Toolbar "Auto Design" synthesises to a target Fc/PM; "Model ID / Fit" identifies a plant\n   model that can be handed back as the plant source.\n5. Export the final H(z): fill the Symbol Prefix in section 5, then "Export final H(z) -\n   C99 float32_t".\n',
    'helpbody.fra.controller_tuning': '* The current controller is best entered as exact B/A coefficients. Both the canonical\n  convention y = sum(bx) - sum(ay) and the firmware convention y = sum(bx) + sum(Ay) are\n  supported (the tool converts a = -A and never guesses the feedback sign). A PI Kp+Ti\n  plus Fs and the discretization method is also accepted.\n* Quick Tune on an exact-coefficient controller is a coefficient-domain scale change:\n  global gain Kx, per-numerator scales b0x...b3x, per-feedback scales a1x...a3x\n  (supported up to order three / 3P3Z). For a PI Kp+Ti current controller only the Kp and\n  Ti scales are exposed, and the sample rate and discretization method are kept.\n* New Structure offers the same controller library as Control Tools (14 structures\n  including the Type-II/III R/C input mode) plus a Custom H(z) exact-coefficient entry.\n',
    'helpbody.fra.impl_frequency_margins': 'H(z) is evaluated directly from the z^-1 definition at any frequency (no\ninterpolation, no fitting):\n\n      q = exp(-j*2*pi*f / Fs)\n      H = sum b[k]*q^k / sum a[k]*q^k\n\nThe phase is unwrapped with np.unwrap first and the phase margin is then taken as the\nsigned distance to the NEAREST odd multiple of 180 degrees:\n\n      PM = ((phase + 180) mod 360) - 180\n\nThat gives a correct signed margin for multi-turn phase (for example -313 deg or -407 deg)\ninstead of applying 180 + phase, which is only valid near -180 deg. Phase-crossing search\nwalks every -180 + 360*k branch, so repeated crossings and multi-turn cases are all listed\nand the gain margin is the worst of them; more than one 0-dB crossing raises an explicit\nwarning.\n\nThe analysis limit is 0.49*Fs (using min(new controller Fs, old controller Fs)); data above\nthe limit is still displayed as measurement context but never enters the margin\ncomputation. Bode100 data keeps its raw phase and gets a default -180 deg loop-injection\ncorrection which the user can override.\n\nIf the finite sweep never reaches an odd multiple of 180 degrees, the gain margin is\nreported as NOT PROVEN rather than silently satisfied.\n',
    'helpbody.fra.impl_deembed_fitting': 'De-embedding and reconstruction (analysis.py)\n      G_eq = H_scan / C_old\n      H_rebuild = G_eq * C_old\nThe maximum magnitude/phase reconstruction error is reported immediately (default\nthresholds 1e-9 dB / 1e-8 deg). This is an implementation self-check of the complex\ndivision and multiplication, not proof of where C_old came from.\n\nRational identification (fitting.py) - variable projection:\n  1. parametrise the poles first: some real pole frequencies plus some complex-conjugate\n     pairs (natural frequency fn, damping zeta);\n  2. with the poles fixed the denominator is known, so the numerator coefficients are\n     solved in ONE linear least-squares step;\n  3. an outer least_squares(soft_l1) searches the poles, damping and pure delay;\n  4. the polynomial variable is normalised to x = s/w_ref (w_ref = geometric centre of the\n     fit band), which markedly improves the conditioning of high-order polynomials;\n  5. orders 1..5 are tried in turn with both real and complex-conjugate pole structures;\n     candidates are ranked by RMS magnitude error + 0.2*RMS phase error with control-band\n     weighting;\n  6. pure delay is explicit in the frequency domain as exp(-j*w*Td); it is converted to a\n     first-order Pade approximation only for step/pole calculations;\n  7. a delay contributing less than 0.1 deg of phase at the highest fitted frequency is\n     zeroed, so optimizer noise cannot manufacture a fake high-frequency pole pair.\n\n  THIS IS NOT VECTOR FITTING. It is a constrained nonlinear variable-projection rational\n  approximation; the poles and zeros are an engineering approximation of the measured\n  complex response, not physical component identification. The fitter constrains poles to\n  the stable half-plane, so it cannot identify a genuinely unstable open-loop plant.\n',
    'helpbody.fra.impl_plant_link_step': 'Frequency domain: L(jw) = G_fit(jw) * H_ctrl(e^{jwT}), judged by the same margin engine\nas raw FRA.\n\nTime domain: G_fit is first sampled with a zero-order hold at the controller sample rate,\nthen closed with the EXACT discrete controller:\n\n      T(z) = L(z) / (1 + L(z))      then dstep for the step response\n\nImplementation detail: the project stores coefficients as ascending powers of z^-1 while\nthe scipy time-domain routines want descending positive powers of z, so the numerator\nneeds (n-m) TRAILING zeros to keep the sample alignment. Getting this wrong shifts the\nwhole curve by one sample, so it is cross-checked against an independent z^-1 difference\nequation (a direct lfilter recursion); the two agree to 1e-14.\n\nThe step authorisation chain is evaluated in order, first hit wins:\n\n      fit confidence -> plant stability -> loop margins -> bandwidth coverage -> closed-loop stability\n\n      fit confidence LOW                          WITHHELD_LOW_FIT_CONFIDENCE\n      identified plant has RHP poles               WITHHELD_PLANT_MODEL_NOT_STABLE\n      linked open loop fails its margin check      WITHHELD_LOOP_MARGIN_FAIL\n      band fails Fc/Fmin >= 10 or Fmax/Fc >= 5      WITHHELD_INSUFFICIENT_STEP_BANDWIDTH\n      discrete closed loop unstable                WITHHELD_CLOSED_LOOP_UNSTABLE\n\nThe bandwidth-coverage thresholds share one constant definition with the fitted-loop path,\nso the two step paths cannot drift apart. When the step is withheld, Fc/PM are still\nreported: a narrow local fit can explain loop shape but does not authorise a time-domain\nprediction.\n',
    'helpbody.fra.impl_auto_design': '1. At the current trial frequency Fc, derive the controller phase required by the\n   target phase margin:\n\n         desired_loop_phase = -180 deg + target PM\n         required controller phase = desired_loop_phase - plant phase at Fc\n\n2. For the selected structure, a one-dimensional bounded search (minimize_scalar,\n   bounded) finds a parameter that is still free (for example the PI/PIF zero frequency, or\n   the zero base frequency of Power 2P2Z / 3P3Z) such that the discretized controller phase\n   at Fc equals the required value. If the phase error exceeds the allowance, the structure\n   is declared infeasible.\n3. One analytic gain solve then makes |L(Fc)| = 1 (evaluated in the z domain, including the\n   discretization effect).\n4. Every 0-dB crossing, PM, GM, Ms and Mt are computed on the RAW MEASURED POINTS over the\n   whole band and scored: multiple 0-dB crossings, unobserved GM and excessive Ms all lose\n   significant points, so the optimiser cannot win by only matching the target point.\n5. When the target point fails any constraint, the crossover frequency is reduced along a\n   geometric sequence and retried. Only when every constraint holds on the measured points\n   is the result marked PASS; otherwise it comes back as REVIEW for human judgement.\n\nPower 2P2Z / 3P3Z use power-compensator templates with an integrator pole:\n      K*(s+wz1)*(s+wz2) / [s*(s+wp1)]\n      K*(s+wz1)*(s+wz2)*(s+wz3) / [s*(s+wp1)*(s+wp2)]\nThis differs from the equal-order finite pole/zero semantics of the manual entry, so such\nresults are written back as exact H(z) coefficients.\n',
    # runtime dialogs, status and log messages
    'Auto Design 失败': 'Auto Design failed',
    'Auto Design 未通过': 'Auto Design did not pass',
    '当前结果没有满足完整的 Fc/PM/GM/Ms 约束，禁止一键应用。': 'The current result does not satisfy all of the Fc/PM/GM/Ms constraints, so one-click apply is refused.',
    'Auto Design 已应用': 'Auto Design applied',
    '严格 PASS 的自动设计参数已回写，可继续 Slider 微调并导出 C99。': 'The strictly PASSing auto-design parameters have been written back; you can keep fine-tuning with the sliders and export C99.',
    '当前工作区不支持': 'Not supported in this workspace',
    '宿主窗口没有辨识模型回传接口。': 'The host window has no identified-model hand-off interface.',
    '回传失败': 'Hand-off failed',
    'Model Fit 失败': 'Model fit failed',
    '未回传辨识模型：Advanced → Model ID / Fit 完成后点击“用于环路设计”。': 'No identified model has been handed over yet: finish Advanced -> Model ID / Fit and click "use for loop design".',
    'FRA 导入失败': 'FRA import failed',
    '仅 PI 可直接复制': 'Only PI can be copied directly',
    '请先选择 Complete Loop TS，并使用 PI Kp+Ti 作为当前控制器输入。': 'Select Complete Loop TS first and use PI Kp+Ti as the current controller input.',
    '没有可导出的控制器': 'No controller to export',
    '请先导入 FRA 并完成一次有效计算。': 'Import FRA data and complete one valid computation first.',
    '控制器不可导出': 'Controller cannot be exported',
    '当前 H(z) 含单位圆外极点。请先恢复控制器稳定性。': 'The current H(z) has poles outside the unit circle. Restore controller stability first.',
    'C99 导出失败': 'C99 export failed',
    'C99 导出完成': 'C99 export complete',
    '尚未运行分析。': 'No analysis has been run yet.',
    '当前全部关闭。勾选任意传递函数后显示。': 'Everything is currently hidden. Tick any transfer function to show it.',
    '自动整定失败：{exc}': 'Auto tuning failed: {exc}',
    'C99 代码生成': 'C99 code generation',
    '请先运行 PFC 完整分析；建议先执行一键稳定整定。': 'Run the full PFC analysis first; running the one-click stable tuning beforehand is recommended.',
    'C99 代码生成失败': 'C99 code generation failed',
    'PFC Control Lab 参数错误': 'PFC Control Lab parameter error',
    'PFC 电感设计失败': 'PFC inductor design failed',
    '关于 PFC Design': 'About PFC Design',
    '请先运行 Vienna 完整分析。': 'Run the full Vienna analysis first.',
    'Vienna 参数错误': 'Vienna parameter error',
    '已选择功率级组件：{key}': 'Selected power-stage component: {key}',
    '无法复制参数': 'Cannot copy parameters',
    '请输入正的 Lr / Cr / Lm': 'Enter positive Lr / Cr / Lm',
    '加载失败': 'Load failed',
    '保存失败': 'Save failed',
    '输出目录：{path}': 'Output folder: {path}',
    '参数错误': 'Parameter error',
    '公式计算书已导出：{path}': 'Formula report exported: {path}',
    '计算失败': 'Computation failed',
    '变压器设计已导出到：{out}': 'Transformer design exported to: {out}',
    '显示环节参数': 'Show stage parameters',
    '请先建立 / 更新完整数字电压环。': 'Build / update the full digital voltage loop first.',
    'C99 代码生成完成': 'C99 code generation complete',
    '数字环路参数错误': 'Digital loop parameter error',
    '传递函数 ▾': 'Transfer functions ▾',
    '显示框图': 'Show block diagram',
    '显示参数': 'Show parameters',
}

CATALOGUE.update({'设计提醒：': 'Design notes:', '可继续查看和导出已有结果；未满足项与未求解工况仍需复核。': 'Available results can still be viewed and exported; unmet constraints and unsolved operating points need review.'})
