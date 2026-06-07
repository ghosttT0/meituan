"""对话失效模式分类器。分析规则结果与状态轨迹，输出可操作的失败模式枚举。"""
from app.domain.evaluation_result import RuleResult


# 失效模式说明，用于生成改进建议
FAILURE_MODE_LABELS = {
    "SLOT_ABANDONMENT":   "槽位收集中断：模型在收集关键信息时中途放弃",
    "FORBIDDEN_PROMISE":  "违规承诺：模型做出了无法兑现的承诺",
    "MISSING_FLOW":       "流程缺失：必需步骤未完成",
    "TOPIC_DRIFT":        "话题偏移：模型未能回应场景关键信息（FAQ/风险/兜底）",
    "LOOP_STUTTER":       "流程循环：同一状态重复出现超过 2 次",
    "ABRUPT_END":         "强制终止：对话在未完成任务时被迫结束",
}


def classify(
    rule_results: list[RuleResult],
    state_trace: list[str] | None = None,
) -> list[str]:
    """
    返回命中的失效模式 key 列表，可直接注入 EvaluationSummary.failure_modes。
    """
    modes: list[str] = []
    failed_ids = {r.rule_id for r in rule_results if not r.passed}

    if "required_slots" in failed_ids:
        modes.append("SLOT_ABANDONMENT")
    if "forbidden_actions" in failed_ids:
        modes.append("FORBIDDEN_PROMISE")
    if "required_steps" in failed_ids:
        modes.append("MISSING_FLOW")

    scenario_failed = any(
        r for r in rule_results
        if not r.passed and r.rule_id.startswith("scenario_")
    )
    if scenario_failed:
        modes.append("TOPIC_DRIFT")

    if state_trace:
        # 同一状态连续出现超过 2 次 → 循环
        for i in range(len(state_trace) - 2):
            if state_trace[i] == state_trace[i + 1] == state_trace[i + 2]:
                modes.append("LOOP_STUTTER")
                break
        # 末态是 terminated 但仍有失败规则 → 强制终止
        if state_trace[-1] == "terminated" and failed_ids:
            modes.append("ABRUPT_END")

    return modes
