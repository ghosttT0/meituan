from app.domain.evaluation_result import JudgeResult
from app.reliability.agreement import AgreementCalculator
from app.reliability.confidence import ConfidenceScorer


def test_confidence_is_reduced_on_disagreement() -> None:
    judge_runs = [
        [JudgeResult(dimension_id="x", score=0.9, confidence=0.9, reason="ok", evidence_turn_ids=[1])],
        [JudgeResult(dimension_id="x", score=0.4, confidence=0.5, reason="weak", evidence_turn_ids=[1])],
    ]

    agreement = AgreementCalculator().calculate(judge_runs)
    confidence = ConfidenceScorer().score(
        parse_warnings=["speaker_normalized"],
        agreement=agreement,
        soft_eval_skipped=False,
    )

    assert agreement["score_span"] == 0.5
    assert confidence < 0.8
