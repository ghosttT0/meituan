from app.domain.evaluation_result import JudgeResult, RuleResult


class Aggregator:
    def combine(
        self,
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        parse_warnings: list[str],
        soft_eval_skipped: bool = False,
    ) -> dict:
        hard_fail = any(result.severity == "fatal" and not result.passed for result in hard_results)
        hard_score = 100.0 * (sum(result.score_delta for result in hard_results) / max(len(hard_results), 1))
        soft_score = (
            100.0 * (sum(result.score for result in judge_results) / max(len(judge_results), 1))
            if judge_results
            else 0.0
        )
        overall_score = 0.0 if hard_fail else round(hard_score * 0.7 + soft_score * 0.3, 2)
        needs_review = bool(parse_warnings) or soft_eval_skipped
        return {
            "hard_fail": hard_fail,
            "hard_score": round(hard_score, 2),
            "soft_score": round(soft_score, 2),
            "overall_score": overall_score,
            "needs_review": needs_review,
            "soft_eval_skipped": soft_eval_skipped,
        }
