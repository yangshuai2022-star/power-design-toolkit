"""Engineering validation façade: envelope + FHA↔TD + evidence summary."""

from __future__ import annotations

from dataclasses import dataclass

from ..analysis.fha_td_validation import (
    FhaTdValidationReport,
    FhaValidityMap,
    ModelValidity,
    build_fha_validity_map,
    credibility_from_validity,
    validate_fha_against_time_domain,
)
from ..core.engineering import EnvelopeEvaluation
from ..core.spec import LLCDesignSpec
from ..models.electro_thermal import ElectroThermalResult, iterate_electro_thermal
from ..models.physics_evidence import ModelGrade
from ..models.system import LLCSystemAnalyzer
from ..models.waveform_loss import bridge_loss_with_provenance


@dataclass(frozen=True)
class ModelValidityRow:
    model: str
    status: str
    notes: str = ""


@dataclass(frozen=True)
class EngineeringEvidenceReport:
    envelope: EnvelopeEvaluation
    fha_td: FhaTdValidationReport
    validity_map: FhaValidityMap | None
    thermal: ElectroThermalResult | None
    model_rows: tuple[ModelValidityRow, ...]
    worst_case_summary: tuple[str, ...]
    unknowns: tuple[str, ...]

    def as_markdown(self) -> str:
        lines = [
            "# Engineering Evidence Report",
            "",
            "## Model Validity",
            "",
            "| Model | Status | Notes |",
            "| --- | --- | --- |",
        ]
        for row in self.model_rows:
            lines.append(f"| {row.model} | {row.status} | {row.notes} |")
        lines.extend(["", "## Worst Case Summary", ""])
        for item in self.worst_case_summary:
            lines.append(f"- {item}")
        lines.extend(["", "## Uncertainty / Unknown", ""])
        for item in self.unknowns:
            lines.append(f"- {item}")
        lines.extend([
            "",
            f"Envelope overall: {self.envelope.overall_status.value}",
            f"FHA↔TD overall: {self.fha_td.overall_validity.value}",
        ])
        return "\n".join(lines)


def run_engineering_validation(
    spec: LLCDesignSpec,
    *,
    analyzer: LLCSystemAnalyzer | None = None,
    include_validity_map: bool = False,
    include_thermal: bool = True,
) -> EngineeringEvidenceReport:
    """Connect Envelope → critical FHA↔TD → optional thermal → evidence rows."""

    analyzer = analyzer or LLCSystemAnalyzer()
    envelope = analyzer.evaluate_envelope(spec)
    fha_td = validate_fha_against_time_domain(spec, envelope_eval=envelope)
    validity_map = build_fha_validity_map(spec) if include_validity_map else None

    analysis = analyzer.analyze(spec)
    thermal = None
    if include_thermal:
        thermal = iterate_electro_thermal(spec, analysis.nominal.operating_point, analyzer=analyzer)

    primary = analyzer.device_db.get_primary(spec.primary_device)
    provenanced = bridge_loss_with_provenance(
        spec, analysis.tank, analysis.nominal.operating_point, primary)

    worst = tuple(
        f"{f.metric} @ {f.corner_id}: value={f.value:.6g} ({f.status.value}) — {f.reason}"
        for f in envelope.worst_cases
    )

    cred = credibility_from_validity(fha_td.overall_validity)
    td_ok = any(p.td is not None and p.td.convergence.converged for p in fha_td.points)
    rows = (
        ModelValidityRow("FHA", cred.value, "vs switched TD on critical points"),
        ModelValidityRow(
            "Time Domain",
            ModelValidity.PASS.value if td_ok else ModelValidity.UNKNOWN.value,
            "steady-state gated; non-converged ≠ VERIFIED loss source",
        ),
        ModelValidityRow(
            "ZVS Charge Balance", ModelGrade.APPROXIMATION.value,
            f"turn_on_class={provenanced.turn_on_class.value}; const-I deadtime",
        ),
        ModelValidityRow("MOSFET Eoss/Eon", ModelGrade.APPROXIMATION.value,
                         "single-point Coss/Qoss; not full curve"),
        ModelValidityRow("Core Loss", ModelGrade.APPROXIMATION.value,
                         "iGSE on reconstructed B(t); reference materials"),
        ModelValidityRow("Copper AC Loss", ModelGrade.PARTIAL.value,
                         "Litz/Dowell engineering model"),
        ModelValidityRow("Leakage", ModelGrade.ESTIMATED.value,
                         "Lr target vs FEA leakage not closed"),
        ModelValidityRow(
            "Thermal",
            ModelGrade.APPROXIMATION.value,
            "lumped Rθ iteration"
            + (" CONVERGED" if thermal and thermal.converged else " NOT_CONVERGED")
            + " — not a verified electro-thermal solution",
        ),
    )
    unknowns = (
        "Nonlinear Coss(V)/Qoss(V) curves not consumed",
        "Leakage inductance remains ESTIMATED without winding geometry FEA",
        "AC copper model not measurement-validated",
        "Thermal uses lumped Rθ — not a 3D heat map",
        "Default analyze() path still uses FHA scalar loss (waveform path is opt-in)",
    )
    return EngineeringEvidenceReport(
        envelope=envelope,
        fha_td=fha_td,
        validity_map=validity_map,
        thermal=thermal,
        model_rows=rows,
        worst_case_summary=worst,
        unknowns=unknowns,
    )


__all__ = [
    "EngineeringEvidenceReport",
    "ModelValidityRow",
    "run_engineering_validation",
]
