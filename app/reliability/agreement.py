from app.domain.evaluation_result import JudgeResult


class AgreementCalculator:
    def calculate(self, judge_runs: list[list[JudgeResult]]) -> dict:
        flattened = [run[0].score for run in judge_runs if run]
        if not flattened:
            return {"score_span": 1.0, "agreement": 0.0}
        score_span = max(flattened) - min(flattened)
        return {"score_span": round(score_span, 2), "agreement": round(1 - score_span, 2)}
