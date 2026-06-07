from app.domain.evaluation_result import JudgeResult


class AgreementCalculator:
    def calculate(self, judge_runs: list[list[JudgeResult]]) -> dict:
        dimension_map: dict[str, list[float]] = {}
        for run in judge_runs:
            for item in run:
                dimension_map.setdefault(item.dimension_id, []).append(item.score)

        if not dimension_map:
            return {"score_span": 1.0, "agreement": 0.0}

        spans = [max(scores) - min(scores) for scores in dimension_map.values() if scores]
        score_span = round(sum(spans) / max(len(spans), 1), 2)
        return {"score_span": round(score_span, 2), "agreement": round(1 - score_span, 2)}
