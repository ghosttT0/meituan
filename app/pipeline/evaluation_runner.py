from uuid import uuid4

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import EvaluationResult
from app.evaluators.judge.consistency_judge import ConsistencyJudge
from app.evaluators.judge.llm_adapter import FakeLLMAdapter
from app.evaluators.judge.rubric_judge import RubricJudge
from app.evaluators.rules.flow_rules import RequiredStepRule
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.slot_rules import RequiredSlotRule
from app.pipeline.aggregator import Aggregator
from app.pipeline.dialogue_parser import DialogueParser
from app.pipeline.fact_extractor import FactExtractor
from app.reliability.agreement import AgreementCalculator
from app.reliability.confidence import ConfidenceScorer
from app.reports.evidence_trace import build_evidence_items
from app.reports.scorecard import render_summary


class EvaluationRunner:
    def run(self, spec: EvalSpec, conversation: Conversation) -> EvaluationResult:
        parsed = DialogueParser().parse(conversation)
        events = FactExtractor().extract(parsed)

        hard_results = [
            RequiredStepRule().evaluate(spec, events),
            RequiredSlotRule().evaluate(spec, events),
            ForbiddenActionRule().evaluate(spec, events),
        ]

        judge = RubricJudge(FakeLLMAdapter())
        judge_runs = ConsistencyJudge(judge, runs=2).evaluate(spec, parsed) if spec.soft_dimensions else []
        judge_results = judge_runs[0] if judge_runs else []

        aggregate = Aggregator().combine(
            hard_results=hard_results,
            judge_results=judge_results,
            parse_warnings=[],
            soft_eval_skipped=not bool(judge_results),
        )
        agreement = (
            AgreementCalculator().calculate(judge_runs) if judge_runs else {"score_span": 1.0, "agreement": 0.0}
        )
        confidence = ConfidenceScorer().score(
            parse_warnings=[],
            agreement=agreement,
            soft_eval_skipped=aggregate["soft_eval_skipped"],
        )

        evidence_items = []
        for result in hard_results:
            evidence_items.extend(build_evidence_items(parsed, result.evidence_turn_ids, result.rule_id))

        evaluation = EvaluationResult(
            run_id=f"run_{uuid4().hex[:8]}",
            conversation_id=conversation.conversation_id,
            spec_id=spec.spec_id,
            overall_score=aggregate["overall_score"],
            dimension_scores={item.dimension_id: item.score for item in judge_results},
            hard_fail=aggregate["hard_fail"],
            confidence=confidence,
            needs_review=aggregate["needs_review"],
            soft_eval_skipped=aggregate["soft_eval_skipped"],
            rule_results=hard_results,
            judge_results=judge_results,
            evidence_items=evidence_items,
        )
        return evaluation.model_copy(update={"summary": render_summary(evaluation)})
