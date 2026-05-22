class ConfidenceScorer:
    def score(self, parse_warnings: list[str], agreement: dict, soft_eval_skipped: bool) -> float:
        confidence = 0.9
        confidence -= min(len(parse_warnings) * 0.1, 0.3)
        confidence -= (1 - agreement["agreement"]) * 0.4
        if soft_eval_skipped:
            confidence -= 0.2
        return round(max(confidence, 0.0), 2)
