"""Two-stage LLC optimizer: fast FHA screening → engineering verification.

Stage A: existing grid search.
Stage B: Top-N feasible survivors — envelope gate + FHA↔TD + ZVS L2.
FAIL candidates never enter the ranked shortlist.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..analysis.fha_td_validation import ModelValidity, validate_fha_against_time_domain
from ..core.engineering import (
    ConstraintStatus,
    evaluate_operating_envelope,
    merge_status,
)
from ..core.spec import LLCDesignSpec
from ..core.zvs_margin import evaluate_zvs_margin
from ..models.system import LLCSystemAnalyzer, SystemAnalysis
from .sweep import LLCOptimizer, OptimizationConfig, OptimizationResult


@dataclass(frozen=True)
class VerifiedCandidate:
    spec: LLCDesignSpec
    analysis: SystemAnalysis
    envelope_status: ConstraintStatus
    fha_td_validity: ModelValidity
    zvs_margin_worst: float | None
    total_loss_w: float
    efficiency: float
    rank_metrics: dict[str, float]
    rejected: bool
    reject_reason: str = ""


@dataclass
class TwoStageOptimizationResult:
    stage_a: OptimizationResult
    verified: tuple[VerifiedCandidate, ...]
    ranking_weights: dict[str, float]
    warnings: tuple[str, ...]


DEFAULT_WEIGHTS = {
    "efficiency": 1.0,
    "total_loss_w": -0.002,
    "zvs_margin_worst": 0.15,
}


def _envelope_status(spec: LLCDesignSpec, analyzer: LLCSystemAnalyzer) -> ConstraintStatus:
    primary = analyzer.device_db.get_primary(spec.primary_device)
    evaluation = evaluate_operating_envelope(
        spec,
        device_qoss_c=primary.qoss_c,
        device_coss_f=primary.coss_er_f,
        zvs_level=1,
    )
    statuses = [c.status for point in evaluation.points for c in point.constraints]
    return merge_status(*statuses) if statuses else ConstraintStatus.UNKNOWN


class TwoStageLLCOptimizer:
    def __init__(self, analyzer: LLCSystemAnalyzer | None = None):
        self.analyzer = analyzer or LLCSystemAnalyzer()
        self.fast = LLCOptimizer(self.analyzer)

    def run(
        self,
        base_spec: LLCDesignSpec,
        config: OptimizationConfig | None = None,
        *,
        maximum_candidates: int | None = None,
        top_n: int = 3,
        ranking_weights: dict[str, float] | None = None,
        run_stage_b: bool = True,
    ) -> TwoStageOptimizationResult:
        weights = dict(DEFAULT_WEIGHTS if ranking_weights is None else ranking_weights)
        stage_a = self.fast.run(base_spec, config, maximum_candidates=maximum_candidates)
        warnings: list[str] = []
        table = stage_a.table
        if table is None or table.empty or "feasible" not in table.columns:
            return TwoStageOptimizationResult(stage_a, (), weights, ("stage A empty",))

        feasible = table[table["feasible"] == True].copy()
        if feasible.empty:
            return TwoStageOptimizationResult(stage_a, (), weights, ("no feasible Stage-A candidates",))

        if "weighted_loss_w" in feasible.columns:
            feasible = feasible.sort_values("weighted_loss_w", ascending=True)
        shortlist = feasible.head(max(top_n * 4, top_n))

        verified: list[VerifiedCandidate] = []
        accepted_count = 0
        for _, row in shortlist.iterrows():
            spec = base_spec.clone(
                ln_ratio=float(row["ln"]),
                q_full_load=float(row["q_full"]),
                resonant_frequency_hz=float(row["fr_khz"]) * 1e3,
                primary_turns=int(row["primary_turns"]),
                secondary_turns=int(row["secondary_turns"]),
                primary_device=str(row["primary_device"]),
                sr_parallel_devices_per_position=int(row["sr_parallel"]),
            )
            try:
                analysis = self.analyzer.analyze(spec)
            except Exception as exc:
                warnings.append(f"analyze failed: {exc}")
                continue

            try:
                env_status = _envelope_status(spec, self.analyzer)
            except Exception as exc:
                env_status = ConstraintStatus.UNKNOWN
                warnings.append(f"envelope: {exc}")

            if env_status == ConstraintStatus.FAIL:
                verified.append(VerifiedCandidate(
                    spec, analysis, env_status, ModelValidity.UNKNOWN, None,
                    analysis.worst_loss.total_loss_w, analysis.minimum_efficiency.efficiency,
                    {}, True, "envelope constraint FAIL",
                ))
                continue

            validity = ModelValidity.UNKNOWN
            if run_stage_b:
                report = validate_fha_against_time_domain(spec)
                validity = report.overall_validity
                if validity == ModelValidity.FAIL:
                    verified.append(VerifiedCandidate(
                        spec, analysis, env_status, validity, None,
                        analysis.worst_loss.total_loss_w, analysis.minimum_efficiency.efficiency,
                        {}, True, "FHA↔TD MODEL_VALIDITY FAIL",
                    ))
                    continue

            primary = self.analyzer.device_db.get_primary(spec.primary_device)
            worst_zvs = None
            for point in analysis.operating_points:
                zvs = evaluate_zvs_margin(
                    spec, analysis.tank, point.operating_point, device=primary, level=2)
                if zvs.zvs_margin != zvs.zvs_margin:
                    continue
                if worst_zvs is None or zvs.zvs_margin < worst_zvs:
                    worst_zvs = zvs.zvs_margin

            metrics = {
                "efficiency": float(analysis.minimum_efficiency.efficiency),
                "total_loss_w": float(analysis.worst_loss.total_loss_w),
                "zvs_margin_worst": float(worst_zvs if worst_zvs is not None else 0.0),
            }
            verified.append(VerifiedCandidate(
                spec, analysis, env_status, validity, worst_zvs,
                metrics["total_loss_w"], metrics["efficiency"], metrics, False,
            ))
            accepted_count += 1
            if accepted_count >= top_n:
                break

        accepted = [v for v in verified if not v.rejected]
        rejected = [v for v in verified if v.rejected]

        def score(v: VerifiedCandidate) -> float:
            return sum(weights.get(k, 0.0) * v.rank_metrics.get(k, 0.0) for k in weights)

        accepted.sort(key=score, reverse=True)
        return TwoStageOptimizationResult(
            stage_a=stage_a,
            verified=tuple(accepted + rejected),
            ranking_weights=weights,
            warnings=tuple(dict.fromkeys(warnings)),
        )


__all__ = [
    "DEFAULT_WEIGHTS",
    "TwoStageLLCOptimizer",
    "TwoStageOptimizationResult",
    "VerifiedCandidate",
]
