import os
from uuid import uuid4

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import EvaluationResult, PanelEvaluation, RuleResult
from app.evaluators.judge.llm_adapter import FakeLLMAdapter, OpenAILLMAdapter
from app.evaluators.judge.panel_judge import PanelJudge, SUBJECTIVE_SCENARIO_RULE_IDS
from app.evaluators.rules.flow_rules import RequiredStepRule
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.scenario_rules import ScenarioRuleEngine
from app.evaluators.rules.slot_rules import RequiredSlotRule
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

        base_rules = [
            RequiredStepRule().evaluate(spec, events),
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

        panel_evaluation = self._run_panel(spec, parsed, subjective_scenario_rules, evaluation_mode)
        judge_results = panel_evaluation.final_judge_results
        final_rules = [*base_rules, *objective_scenario_rules]
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
        evaluation_mode: str,
    ) -> PanelEvaluation:
        if not spec.soft_dimensions and not subjective_scenario_rules:
            return PanelEvaluation()

        primary_judge_count, arbitration_enabled = self._resolve_panel_mode(evaluation_mode)
        panel = PanelJudge(adapter=self._build_adapter())
        return panel.evaluate(
            spec,
            conversation,
            subjective_scenario_rules,
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
