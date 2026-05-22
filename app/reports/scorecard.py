from app.domain.evaluation_result import EvaluationResult


def render_summary(result: EvaluationResult) -> str:
    if result.hard_fail:
        return "命中硬性失败项，需要人工复核。"
    if result.overall_score >= 85:
        return "整体指令遵循良好，关键流程已完成。"
    return "存在流程或话术问题，建议重点查看扣分证据。"
