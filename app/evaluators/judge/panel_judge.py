from statistics import mean

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import (
    ArbitrationRecord,
    JudgePanelResult,
    JudgeResult,
    PanelEvaluation,
    RuleResult,
)
from app.evaluators.judge.llm_adapter import LLMAdapter


PRIMARY_PANEL = (
    {"judge_id": "judge_a", "judge_role": "task_alignment"},
    {"judge_id": "judge_b", "judge_role": "experience_risk"},
)
ARBITRATOR = {"judge_id": "judge_c", "judge_role": "arbitrator"}
SUBJECTIVE_SCENARIO_RULE_IDS = {
    "scenario_faq_grounding",
    "scenario_busy_focus",
    "scenario_scope_fallback",
    "scenario_hesitant_clarity",
}


class PanelJudge:
    def __init__(self, adapter: LLMAdapter, score_gap_threshold: float = 0.25) -> None:
        self.adapter = adapter
        self.score_gap_threshold = score_gap_threshold

    def evaluate(
        self,
        spec: EvalSpec,
        conversation: Conversation,
        subjective_rules: list[RuleResult],
        primary_judge_count: int = 2,
        arbitration_enabled: bool = True,
    ) -> PanelEvaluation:
        transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in conversation.turns)
        active_primary_panel = list(PRIMARY_PANEL[: max(1, min(primary_judge_count, len(PRIMARY_PANEL)))])
        panel_results = [
            self._build_panel_result(
                judge_id=judge["judge_id"],
                judge_role=judge["judge_role"],
                spec=spec,
                transcript=transcript,
                subjective_rules=subjective_rules,
            )
            for judge in active_primary_panel
        ]

        arbitration_records: list[ArbitrationRecord] = []
        final_judge_results = self._finalize_dimensions(
            spec=spec,
            transcript=transcript,
            subjective_rules=subjective_rules,
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            arbitration_enabled=arbitration_enabled,
        )
        final_rule_results = self._finalize_subjective_rules(
            transcript=transcript,
            subjective_rules=subjective_rules,
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            spec=spec,
            arbitration_enabled=arbitration_enabled,
        )

        return PanelEvaluation(
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            final_judge_results=final_judge_results,
            final_rule_results=final_rule_results,
        )

    def _build_panel_result(
        self,
        judge_id: str,
        judge_role: str,
        spec: EvalSpec,
        transcript: str,
        subjective_rules: list[RuleResult],
    ) -> JudgePanelResult:
        dimension_results = [
            JudgeResult(
                **self.adapter.score_dimension(
                    dimension_id=dimension.id,
                    rubric=dimension.rubric,
                    conversation_text=transcript,
                    judge_role=judge_role,
                ),
                judge_id=judge_id,
                judge_role=judge_role,
            )
            for dimension in spec.soft_dimensions
        ]

        scenario_rule_results = [
            self._build_rule_review(
                baseline_rule=rule,
                payload=self.adapter.review_scenario(
                    rule_id=rule.rule_id,
                    criteria=self._build_scenario_criteria(rule.rule_id),
                    conversation_text=transcript,
                    baseline_passed=rule.passed,
                    baseline_reason=rule.reason,
                    judge_role=judge_role,
                ),
                judge_id=judge_id,
                judge_role=judge_role,
            )
            for rule in subjective_rules
        ]

        return JudgePanelResult(
            judge_id=judge_id,
            judge_role=judge_role,
            dimension_results=dimension_results,
            scenario_rule_results=scenario_rule_results,
        )

    def _finalize_dimensions(
        self,
        spec: EvalSpec,
        transcript: str,
        subjective_rules: list[RuleResult],
        panel_results: list[JudgePanelResult],
        arbitration_records: list[ArbitrationRecord],
        arbitration_enabled: bool,
    ) -> list[JudgeResult]:
        final_results: list[JudgeResult] = []
        for dimension in spec.soft_dimensions:
            primary_results = [
                next(item for item in report.dimension_results if item.dimension_id == dimension.id)
                for report in panel_results
            ]
            if len(primary_results) == 1:
                final_results.append(primary_results[0])
                continue

            score_gap = abs(primary_results[0].score - primary_results[1].score)
            if arbitration_enabled and score_gap >= self.score_gap_threshold:
                arbitrator_report = self._get_or_create_arbitrator_report(
                    panel_results=panel_results,
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                )
                arbitration_records.append(
                    ArbitrationRecord(
                        target_type="dimension",
                        target_id=dimension.id,
                        triggered_by=[item.judge_id for item in primary_results],
                        score_gap=round(score_gap, 2),
                        reason="primary judges disagree on dimension score",
                        resolved_by=ARBITRATOR["judge_id"],
                    )
                )
                arbitrate_result = next(
                    item for item in arbitrator_report.dimension_results if item.dimension_id == dimension.id
                )
                final_results.append(arbitrate_result.model_copy(update={"is_arbitration": True}))
                continue

            final_results.append(
                JudgeResult(
                    dimension_id=dimension.id,
                    score=round(mean(item.score for item in primary_results), 2),
                    confidence=round(mean(item.confidence for item in primary_results), 2),
                    reason="panel consensus" if arbitration_enabled else "panel average without arbitration",
                    evidence_turn_ids=sorted(
                        {
                            turn_id
                            for item in primary_results
                            for turn_id in item.evidence_turn_ids
                        }
                    ),
                    status="ok" if arbitration_enabled or score_gap < self.score_gap_threshold else "needs_review",
                    judge_id="panel_consensus" if arbitration_enabled else "panel_average",
                    judge_role="consensus",
                )
            )
        return final_results

    def _finalize_subjective_rules(
        self,
        transcript: str,
        subjective_rules: list[RuleResult],
        panel_results: list[JudgePanelResult],
        arbitration_records: list[ArbitrationRecord],
        spec: EvalSpec,
        arbitration_enabled: bool,
    ) -> list[RuleResult]:
        final_results: list[RuleResult] = []
        for rule in subjective_rules:
            primary_reviews = [
                next(item for item in report.scenario_rule_results if item.rule_id == rule.rule_id)
                for report in panel_results
            ]
            if len(primary_reviews) == 1:
                final_results.append(primary_reviews[0])
                continue

            if arbitration_enabled and primary_reviews[0].passed != primary_reviews[1].passed:
                arbitrator_report = self._get_or_create_arbitrator_report(
                    panel_results=panel_results,
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                )
                arbitration_records.append(
                    ArbitrationRecord(
                        target_type="scenario_rule",
                        target_id=rule.rule_id,
                        triggered_by=[item.review_source for item in primary_reviews],
                        score_gap=1.0,
                        reason="primary judges disagree on scenario rule decision",
                        resolved_by=ARBITRATOR["judge_id"],
                    )
                )
                final_results.append(
                    next(item for item in arbitrator_report.scenario_rule_results if item.rule_id == rule.rule_id)
                )
                continue

            if not arbitration_enabled and primary_reviews[0].passed != primary_reviews[1].passed:
                final_results.append(
                    rule.model_copy(
                        update={
                            "status": "needs_review",
                            "review_source": "rule_engine_fallback",
                            "review_confidence": round(mean(item.review_confidence for item in primary_reviews), 2),
                        }
                    )
                )
                continue

            final_results.append(
                rule.model_copy(
                    update={
                        "passed": primary_reviews[0].passed,
                        "score_delta": 1.0 if primary_reviews[0].passed else 0.0,
                        "reason": primary_reviews[0].reason,
                        "evidence_turn_ids": primary_reviews[0].evidence_turn_ids,
                        "review_source": "panel_consensus",
                        "review_confidence": round(mean(item.review_confidence for item in primary_reviews), 2),
                    }
                )
            )
        return final_results

    def _get_or_create_arbitrator_report(
        self,
        panel_results: list[JudgePanelResult],
        spec: EvalSpec,
        transcript: str,
        subjective_rules: list[RuleResult],
    ) -> JudgePanelResult:
        existing = next((item for item in panel_results if item.judge_id == ARBITRATOR["judge_id"]), None)
        if existing is not None:
            if spec.soft_dimensions and not existing.dimension_results:
                existing.dimension_results = self._build_panel_result(
                    judge_id=ARBITRATOR["judge_id"],
                    judge_role=ARBITRATOR["judge_role"],
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=[],
                ).dimension_results
            if subjective_rules and not existing.scenario_rule_results:
                existing.scenario_rule_results = self._build_panel_result(
                    judge_id=ARBITRATOR["judge_id"],
                    judge_role=ARBITRATOR["judge_role"],
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                ).scenario_rule_results
            return existing

        report = self._build_panel_result(
            judge_id=ARBITRATOR["judge_id"],
            judge_role=ARBITRATOR["judge_role"],
            spec=spec,
            transcript=transcript,
            subjective_rules=subjective_rules,
        )
        panel_results.append(report)
        return report

    def _build_rule_review(
        self,
        baseline_rule: RuleResult,
        payload: dict,
        judge_id: str,
        judge_role: str,
    ) -> RuleResult:
        passed = bool(payload.get("passed", baseline_rule.passed))
        return baseline_rule.model_copy(
            update={
                "passed": passed,
                "score_delta": 1.0 if passed else 0.0,
                "reason": payload.get("reason", baseline_rule.reason),
                "evidence_turn_ids": payload.get("evidence_turn_ids", baseline_rule.evidence_turn_ids),
                "status": payload.get("status", "ok"),
                "review_source": judge_id,
                "review_confidence": float(payload.get("confidence", 0.5)),
            }
        )

    def _build_scenario_criteria(self, rule_id: str) -> list[str]:
        mapping = {
            "scenario_faq_grounding": ["是否正面回答用户追问的关键信息点", "是否避免泛化或敷衍回答"],
            "scenario_busy_focus": ["是否快速说重点", "是否避免冗长铺垫"],
            "scenario_scope_fallback": ["是否使用合规兜底话术", "是否避免越权承诺"],
            "scenario_hesitant_clarity": ["是否解释风险、影响或费用", "是否回应用户犹豫点"],
        }
        return mapping.get(rule_id, ["是否给出合理、可追溯的场景判断"])
