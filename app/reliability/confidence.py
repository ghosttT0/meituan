class ConfidenceScorer:
    def score(
        self,
        parse_warnings: list[str],
        agreement: dict,
        soft_eval_skipped: bool,
        judge_results: list | None = None,
    ) -> float:
        confidence = 0.9
        confidence -= min(len(parse_warnings) * 0.1, 0.3)
        confidence -= (1 - agreement["agreement"]) * 0.4
        if soft_eval_skipped:
            confidence -= 0.2
        # 评委自身置信度不足时额外扣分（最多 -0.15）
        if judge_results:
            avg_judge_conf = sum(r.confidence for r in judge_results) / len(judge_results)
            confidence -= max(0.0, (0.7 - avg_judge_conf)) * 0.5
        return round(max(confidence, 0.0), 2)
