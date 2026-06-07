from app.domain.evaluation_result import EvaluationResult


def render_summary(result: EvaluationResult) -> str:
    """生成评测摘要文本"""
    if result.hard_fail:
        return "命中硬性失败项，需要人工复核。"

    if result.evaluation_summary:
        summary = result.evaluation_summary
        lines = [
            f"综合评分: {summary.overall_score:.1f}/100 (等级: {summary.grade})",
            f"",
            f"各维度得分:",
            f"  任务完成度: {summary.task_success_rate * 100:.1f}%",
            f"  对话效率: {summary.efficiency_score:.1f}/100",
            f"  用户体验: {summary.experience_score:.1f}/100",
            f"  鲁棒性: {summary.robustness_score:.1f}/100",
            f"",
        ]

        if summary.key_strengths:
            lines.append("主要优点:")
            for strength in summary.key_strengths:
                lines.append(f"  - {strength}")
            lines.append("")

        if summary.key_weaknesses:
            lines.append("主要问题:")
            for weakness in summary.key_weaknesses:
                lines.append(f"  - {weakness}")
            lines.append("")

        if summary.improvement_suggestions:
            lines.append("改进建议:")
            for suggestion in summary.improvement_suggestions:
                lines.append(f"  - {suggestion}")

        return "\n".join(lines)

    # 降级到简单摘要
    if result.overall_score >= 85:
        return "整体指令遵循良好，关键流程已完成。"
    return "存在流程或话术问题，建议重点查看扣分证据。"
