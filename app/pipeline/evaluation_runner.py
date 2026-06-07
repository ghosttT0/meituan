import os
from uuid import uuid4

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import EvaluationResult, PanelEvaluation, RuleResult
from app.evaluators.judge.llm_adapter import FakeLLMAdapter, OpenAILLMAdapter
from app.evaluators.judge.panel_judge import PanelJudge, SUBJECTIVE_SCENARIO_RULE_IDS
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.scenario_rules import ScenarioRuleEngine
from app.evaluators.rules.slot_rules import RequiredSlotRule
from app.evaluators.rules.step_candidates import RequiredStepCandidateCollector
from app.pipeline.aggregator import Aggregator
from app.pipeline.dialogue_parser import DialogueParser
from app.pipeline.fact_extractor import FactExtractor
from app.reliability.agreement import AgreementCalculator
from app.reliability.confidence import ConfidenceScorer
from app.reports.evidence_trace import build_evidence_items
from app.reports.scorecard import render_summary


class EvaluationRunner:
    def run(
        self,
        spec: EvalSpec,
        conversation: Conversation,
        evaluation_mode: str = "dual_arbitration",
    ) -> EvaluationResult:
        parsed = DialogueParser().parse(conversation)
        events = FactExtractor().extract(parsed)
        step_candidates = RequiredStepCandidateCollector().collect(spec, parsed)

        base_rules = [
            RequiredSlotRule().evaluate(spec, events),
            ForbiddenActionRule().evaluate(spec, events),
        ]
        scenario_rules = ScenarioRuleEngine().evaluate(spec, conversation, events)
        objective_scenario_rules = [
            rule for rule in scenario_rules if rule.rule_id not in SUBJECTIVE_SCENARIO_RULE_IDS
        ]
        subjective_scenario_rules = [
            rule for rule in scenario_rules if rule.rule_id in SUBJECTIVE_SCENARIO_RULE_IDS
        ]

        self._decorate_rule_suggestions(base_rules + scenario_rules)

        panel_evaluation = self._run_panel(spec, parsed, subjective_scenario_rules, step_candidates, evaluation_mode)
        judge_results = panel_evaluation.final_judge_results
        final_rules = [
            self._build_required_steps_rule(spec, panel_evaluation.final_step_results, step_candidates),
            *base_rules,
            *objective_scenario_rules,
        ]
        final_rules.extend(
            panel_evaluation.final_rule_results if panel_evaluation.final_rule_results else subjective_scenario_rules
        )

        aggregator = Aggregator()
        aggregate = aggregator.combine(
            hard_results=final_rules,
            judge_results=judge_results,
            parse_warnings=[],
            soft_eval_skipped=not bool(judge_results),
            arbitration_records=panel_evaluation.arbitration_records,
            scoring_policy=spec.scoring_policy,
            soft_dimensions=spec.soft_dimensions,
        )
        needs_review = (
            aggregate["needs_review"]
            or any(item.status != "ok" or item.confidence < 0.5 for item in judge_results)
            or any(
                rule.rule_id in SUBJECTIVE_SCENARIO_RULE_IDS
                and (rule.status != "ok" or rule.review_confidence < 0.5)
                for rule in final_rules
            )
        )

        turn_count = len(conversation.turns)
        detailed_dimensions = aggregator.build_detailed_dimensions(final_rules, judge_results, turn_count, task_type=spec.task_type)
        evaluation_summary = aggregator.build_evaluation_summary(
            aggregate["overall_score"],
            detailed_dimensions,
            final_rules,
            judge_results,
        )

        judge_runs = [item.dimension_results for item in panel_evaluation.panel_results if item.dimension_results]
        agreement = (
            AgreementCalculator().calculate(judge_runs)
            if judge_runs
            else {"score_span": 1.0, "agreement": 0.0}
        )
        confidence = ConfidenceScorer().score(
            parse_warnings=[],
            agreement=agreement,
            soft_eval_skipped=aggregate["soft_eval_skipped"],
            judge_results=judge_results,
        )

        evidence_items = []
        for result in final_rules:
            evidence_items.extend(build_evidence_items(parsed, result.evidence_turn_ids, result.rule_id, source_type="rule"))
        for result in judge_results:
            evidence_items.extend(build_evidence_items(parsed, result.evidence_turn_ids, result.dimension_id, source_type="judge"))
        for result in panel_evaluation.final_step_results:
            evidence_items.extend(build_evidence_items(parsed, result.evidence_turn_ids, result.step_id, source_type="step"))

        evaluation = EvaluationResult(
            run_id=f"run_{uuid4().hex[:8]}",
            conversation_id=conversation.conversation_id,
            spec_id=spec.spec_id,
            evaluation_mode=evaluation_mode,
            overall_score=aggregate["overall_score"],
            dimension_scores={item.dimension_id: item.score for item in judge_results},
            hard_fail=aggregate["hard_fail"],
            confidence=confidence,
            needs_review=needs_review,
            soft_eval_skipped=aggregate["soft_eval_skipped"],
            rule_results=final_rules,
            judge_results=judge_results,
            panel_results=panel_evaluation.panel_results,
            arbitration_records=panel_evaluation.arbitration_records,
            step_results=panel_evaluation.final_step_results,
            evidence_items=evidence_items,
            detailed_dimensions=detailed_dimensions,
            evaluation_summary=evaluation_summary,
        )
        return evaluation.model_copy(update={"summary": render_summary(evaluation)})

    def _run_panel(
        self,
        spec: EvalSpec,
        conversation: Conversation,
        subjective_scenario_rules: list[RuleResult],
        step_candidates,
        evaluation_mode: str,
    ) -> PanelEvaluation:
        if not spec.soft_dimensions and not subjective_scenario_rules and not step_candidates:
            return PanelEvaluation()

        primary_judge_count, arbitration_enabled = self._resolve_panel_mode(evaluation_mode)
        panel = PanelJudge(adapter=self._build_adapter())
        return panel.evaluate(
            spec,
            conversation,
            subjective_scenario_rules,
            step_candidates=step_candidates,
            primary_judge_count=primary_judge_count,
            arbitration_enabled=arbitration_enabled,
        )

    def _resolve_panel_mode(self, evaluation_mode: str) -> tuple[int, bool]:
        normalized = (evaluation_mode or "dual_arbitration").strip().lower()
        if normalized == "single":
            return 1, False
        if normalized == "dual":
            return 2, False
        return 2, True

    def _build_required_steps_rule(self, spec: EvalSpec, step_results, step_candidates) -> RuleResult:
        required_steps = [step for step in spec.required_steps if step.required]
        if not required_steps:
            return RuleResult(
                rule_id="required_steps",
                passed=True,
                score_delta=1.0,
                reason="未配置必做步骤",
            )

        by_id = {item.step_id: item for item in step_results}
        candidate_map = {item.step_id: item for item in step_candidates}
        evidence_turn_ids = sorted({tid for item in step_results for tid in item.evidence_turn_ids})
        avg_conf = round(sum(item.confidence for item in step_results) / max(len(step_results), 1), 2) if step_results else 0.0

        completed_steps = []
        review_steps = []
        missing_hard = []
        for step in required_steps:
            step_result = by_id.get(step.id)
            candidate = candidate_map.get(step.id)
            if step_result and step_result.completed:
                completed_steps.append(step)
            elif step_result and step_result.status == "needs_review":
                review_steps.append(step)
            elif candidate and candidate.candidate_turn_ids:
                review_steps.append(step)
            else:
                missing_hard.append(step)

        if not review_steps and not missing_hard:
            return RuleResult(
                rule_id="required_steps",
                passed=True,
                score_delta=1.0,
                evidence_turn_ids=evidence_turn_ids,
                reason="已完成全部必做步骤",
                status="ok",
                review_source="step_judge",
                review_confidence=avg_conf,
            )

        partial_score = round((len(completed_steps) + 0.5 * len(review_steps)) / max(len(required_steps), 1), 2)

        def format_step_issue(step) -> str:
            step_result = by_id.get(step.id)
            candidate = candidate_map.get(step.id)
            if step_result and step_result.reason:
                return f"{step.name}：{step_result.reason}"
            if candidate and candidate.candidate_turn_ids:
                return f"{step.name}：候选证据已召回，待评委复核"
            return step.name

        if review_steps and not missing_hard:
            return RuleResult(
                rule_id="required_steps",
                passed=False,
                score_delta=partial_score,
                evidence_turn_ids=evidence_turn_ids,
                reason="以下必做步骤待复核：" + "；".join(format_step_issue(step) for step in review_steps),
                status="needs_review",
                review_source="step_judge",
                review_confidence=avg_conf,
            )

        missing_labels = [format_step_issue(step) for step in missing_hard]
        missing_labels.extend(format_step_issue(step) for step in review_steps)
        prefix = "缺少必做步骤：" if missing_hard else "以下必做步骤待复核："
        return RuleResult(
            rule_id="required_steps",
            passed=False,
            score_delta=partial_score,
            evidence_turn_ids=evidence_turn_ids,
            reason=prefix + "；".join(missing_labels),
            status="needs_review" if review_steps else "ok",
            review_source="step_judge",
            review_confidence=avg_conf,
        )

    def _build_adapter(self):
        if os.getenv("PYTEST_CURRENT_TEST"):
            return FakeLLMAdapter()
        return OpenAILLMAdapter()

    def _decorate_rule_suggestions(self, rules: list[RuleResult]) -> None:
        for result in rules:
            if result.passed:
                continue
            if result.rule_id == "required_steps":
                result.improvement_suggestion = "建议补充缺失的对话步骤，确保流程完整"
            elif result.rule_id == "required_slots":
                result.improvement_suggestion = "建议主动询问并收集缺失的关键信息"
            elif result.rule_id == "forbidden_actions":
                result.improvement_suggestion = "避免做出无法兑现的承诺，使用兜底话术"
            elif result.rule_id == "scenario_faq_grounding":
                result.improvement_suggestion = "建议正面回答用户追问的关键信息点，不要只给泛化解释"
            elif result.rule_id == "scenario_busy_focus":
                result.improvement_suggestion = "建议在忙碌场景下先说重点，减少冗长铺垫"
            elif result.rule_id == "scenario_scope_fallback":
                result.improvement_suggestion = "建议使用明确兜底话术，不要承诺超出职责范围的处理"
            elif result.rule_id == "scenario_hesitant_clarity":
                result.improvement_suggestion = "建议补充风险、影响或费用说明，回应用户犹豫点"
