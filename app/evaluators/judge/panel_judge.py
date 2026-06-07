from statistics import mean

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import (
    ArbitrationRecord,
    JudgePanelResult,
    JudgeResult,
    PanelEvaluation,
    RuleResult,
    StepCandidate,
    StepJudgeResult,
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
        step_candidates: list[StepCandidate] | None = None,
        primary_judge_count: int = 2,
        arbitration_enabled: bool = True,
    ) -> PanelEvaluation:
        transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in conversation.turns)
        step_candidates = step_candidates or []
        active_primary_panel = list(PRIMARY_PANEL[: max(1, min(primary_judge_count, len(PRIMARY_PANEL)))])
        panel_results = [
            self._build_panel_result(
                judge_id=judge["judge_id"],
                judge_role=judge["judge_role"],
                spec=spec,
                transcript=transcript,
                subjective_rules=subjective_rules,
                step_candidates=step_candidates,
            )
            for judge in active_primary_panel
        ]

        arbitration_records: list[ArbitrationRecord] = []
        final_judge_results = self._finalize_dimensions(
            spec=spec,
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            arbitration_enabled=arbitration_enabled,
            transcript=transcript,
            subjective_rules=subjective_rules,
            step_candidates=step_candidates,
        )
        final_rule_results = self._finalize_subjective_rules(
            subjective_rules=subjective_rules,
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            arbitration_enabled=arbitration_enabled,
            transcript=transcript,
            spec=spec,
            step_candidates=step_candidates,
        )
        final_step_results = self._finalize_required_steps(
            step_candidates=step_candidates,
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            arbitration_enabled=arbitration_enabled,
            transcript=transcript,
            spec=spec,
            subjective_rules=subjective_rules,
        )

        return PanelEvaluation(
            panel_results=panel_results,
            arbitration_records=arbitration_records,
            final_judge_results=final_judge_results,
            final_rule_results=final_rule_results,
            final_step_results=final_step_results,
        )

    def _build_panel_result(
        self,
        judge_id: str,
        judge_role: str,
        spec: EvalSpec,
        transcript: str,
        subjective_rules: list[RuleResult],
        step_candidates: list[StepCandidate],
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
            )
            for rule in subjective_rules
        ]
        step_results = [
            StepJudgeResult(
                **self.adapter.review_required_step(
                    step_id=item.step_id,
                    step_name=item.step_name,
                    evidence_requirement=self._step_requirement(spec, item.step_id, item.step_name),
                    conversation_text=transcript,
                    candidate_turn_ids=item.candidate_turn_ids,
                    candidate_reason=item.candidate_reason,
                    judge_role=judge_role,
                ),
                judge_id=judge_id,
                judge_role=judge_role,
            )
            for item in step_candidates
        ]
        return JudgePanelResult(
            judge_id=judge_id,
            judge_role=judge_role,
            dimension_results=dimension_results,
            scenario_rule_results=scenario_rule_results,
            step_results=step_results,
        )

    def _finalize_dimensions(
        self,
        spec: EvalSpec,
        panel_results: list[JudgePanelResult],
        arbitration_records: list[ArbitrationRecord],
        arbitration_enabled: bool,
        transcript: str,
        subjective_rules: list[RuleResult],
        step_candidates: list[StepCandidate],
    ) -> list[JudgeResult]:
        final_results: list[JudgeResult] = []
        for dimension in spec.soft_dimensions:
            primary_results = [
                next(item for item in report.dimension_results if item.dimension_id == dimension.id)
                for report in panel_results
            ]
            valid_results = [item for item in primary_results if item.status == "ok"]
            scoring_results = valid_results or primary_results

            if len(primary_results) == 1:
                final_results.append(primary_results[0])
                continue

            if len(valid_results) == 1:
                chosen = valid_results[0]
                degraded = [item for item in primary_results if item.judge_id != chosen.judge_id]
                final_results.append(
                    chosen.model_copy(
                        update={
                            "judge_id": "panel_consensus",
                            "judge_role": "consensus",
                            "status": "needs_review",
                            "reason": "合议结果：采用 "
                            + chosen.judge_id
                            + " 的评分；"
                            + "；".join(f"{item.judge_id} 降权，原因：{item.reason}" for item in degraded),
                        }
                    )
                )
                continue

            score_gap = abs(scoring_results[0].score - scoring_results[1].score)
            if arbitration_enabled and len(valid_results) == len(primary_results) and score_gap >= self.score_gap_threshold:
                arbitrator_report = self._get_or_create_arbitrator_report(
                    panel_results=panel_results,
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                    step_candidates=step_candidates,
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

            reason = (
                "panel consensus: "
                + "；".join(f"{item.judge_id}={int(item.score * 100)}分({item.reason})" for item in primary_results)
                if len(valid_results) == len(primary_results)
                else "合议结果："
                + "；".join(f"{item.judge_id}={int(item.score * 100)}分({item.reason})" for item in primary_results)
            )
            final_results.append(
                JudgeResult(
                    dimension_id=dimension.id,
                    score=round(mean(item.score for item in scoring_results), 2),
                    confidence=round(mean(item.confidence for item in scoring_results), 2),
                    reason=reason,
                    evidence_turn_ids=sorted(
                        {turn_id for item in scoring_results for turn_id in item.evidence_turn_ids}
                    ),
                    status="ok" if len(valid_results) == len(primary_results) else "needs_review",
                    judge_id="panel_consensus" if arbitration_enabled else "panel_average",
                    judge_role="consensus",
                )
            )
        return final_results

    def _finalize_subjective_rules(
        self,
        subjective_rules: list[RuleResult],
        panel_results: list[JudgePanelResult],
        arbitration_records: list[ArbitrationRecord],
        arbitration_enabled: bool,
        transcript: str,
        spec: EvalSpec,
        step_candidates: list[StepCandidate],
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
                    step_candidates=step_candidates,
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

    def _finalize_required_steps(
        self,
        step_candidates: list[StepCandidate],
        panel_results: list[JudgePanelResult],
        arbitration_records: list[ArbitrationRecord],
        arbitration_enabled: bool,
        transcript: str,
        spec: EvalSpec,
        subjective_rules: list[RuleResult],
    ) -> list[StepJudgeResult]:
        final_results: list[StepJudgeResult] = []
        for candidate in step_candidates:
            primary_reviews = [
                next(item for item in report.step_results if item.step_id == candidate.step_id)
                for report in panel_results
                if report.step_results
            ]
            if not primary_reviews:
                continue

            valid_reviews = [item for item in primary_reviews if item.status == "ok"]
            if len(primary_reviews) == 1:
                final_results.append(primary_reviews[0])
                continue

            if len(valid_reviews) == 1:
                chosen = valid_reviews[0]
                final_results.append(
                    chosen.model_copy(
                        update={
                            "judge_id": "panel_consensus",
                            "judge_role": "consensus",
                            "status": "needs_review",
                            "reason": "合议结果：采用有效评委结论，其他评委需复核",
                        }
                    )
                )
                continue

            disagree = primary_reviews[0].completed != primary_reviews[1].completed
            if arbitration_enabled and len(valid_reviews) == len(primary_reviews) and disagree:
                arbitrator_report = self._get_or_create_arbitrator_report(
                    panel_results=panel_results,
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                    step_candidates=step_candidates,
                )
                arbitration_records.append(
                    ArbitrationRecord(
                        target_type="required_step",
                        target_id=candidate.step_id,
                        triggered_by=[item.judge_id for item in primary_reviews],
                        score_gap=1.0,
                        reason="primary judges disagree on required step completion",
                        resolved_by=ARBITRATOR["judge_id"],
                    )
                )
                final_results.append(
                    next(item for item in arbitrator_report.step_results if item.step_id == candidate.step_id).model_copy(
                        update={"is_arbitration": True}
                    )
                )
                continue

            if not arbitration_enabled and disagree:
                final_results.append(
                    StepJudgeResult(
                        step_id=candidate.step_id,
                        step_name=candidate.step_name,
                        completed=bool(candidate.candidate_turn_ids),
                        confidence=round(mean(item.confidence for item in primary_reviews), 2),
                        reason="step judge disagreement, fallback to candidate recall",
                        evidence_turn_ids=candidate.candidate_turn_ids,
                        status="needs_review",
                        judge_id="rule_engine_fallback",
                        judge_role="fallback",
                    )
                )
                continue

            final_results.append(
                StepJudgeResult(
                    step_id=candidate.step_id,
                    step_name=candidate.step_name,
                    completed=primary_reviews[0].completed,
                    confidence=round(mean(item.confidence for item in primary_reviews), 2),
                    reason=primary_reviews[0].reason,
                    evidence_turn_ids=sorted(
                        {turn_id for item in primary_reviews for turn_id in item.evidence_turn_ids}
                    ),
                    status="ok" if all(item.status == "ok" for item in primary_reviews) else "needs_review",
                    judge_id="panel_consensus",
                    judge_role="consensus",
                )
            )
        return final_results

    def _get_or_create_arbitrator_report(
        self,
        panel_results: list[JudgePanelResult],
        spec: EvalSpec,
        transcript: str,
        subjective_rules: list[RuleResult],
        step_candidates: list[StepCandidate],
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
                    step_candidates=[],
                ).dimension_results
            if subjective_rules and not existing.scenario_rule_results:
                existing.scenario_rule_results = self._build_panel_result(
                    judge_id=ARBITRATOR["judge_id"],
                    judge_role=ARBITRATOR["judge_role"],
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=subjective_rules,
                    step_candidates=[],
                ).scenario_rule_results
            if step_candidates and not existing.step_results:
                existing.step_results = self._build_panel_result(
                    judge_id=ARBITRATOR["judge_id"],
                    judge_role=ARBITRATOR["judge_role"],
                    spec=spec,
                    transcript=transcript,
                    subjective_rules=[],
                    step_candidates=step_candidates,
                ).step_results
            return existing

        report = self._build_panel_result(
            judge_id=ARBITRATOR["judge_id"],
            judge_role=ARBITRATOR["judge_role"],
            spec=spec,
            transcript=transcript,
            subjective_rules=subjective_rules,
            step_candidates=step_candidates,
        )
        panel_results.append(report)
        return report

    def _build_rule_review(self, baseline_rule: RuleResult, payload: dict, judge_id: str) -> RuleResult:
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

    def _step_requirement(self, spec: EvalSpec, step_id: str, fallback_name: str) -> str:
        for step in spec.required_steps:
            if step.id == step_id:
                return step.evidence_requirement
        return fallback_name

    def _build_scenario_criteria(self, rule_id: str) -> list[str]:
        mapping = {
            "scenario_faq_grounding": ["是否正面回答用户追问的关键信息点", "是否避免泛化或敷衍回答"],
            "scenario_busy_focus": ["是否快速说重点", "是否避免冗长铺垫"],
            "scenario_scope_fallback": ["是否使用合规兜底话术", "是否避免越权承诺"],
            "scenario_hesitant_clarity": ["是否解释风险、影响或费用", "是否回应用户犹豫点"],
        }
        return mapping.get(rule_id, ["是否给出合理、可追溯的场景判断"])
