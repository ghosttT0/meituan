from app.domain.eval_spec import ScoringPolicy, SoftDimension
from app.domain.evaluation_result import (
    ArbitrationRecord,
    DimensionScore,
    EvaluationSummary,
    JudgeResult,
    RuleResult,
)
from app.reports.failure_classifier import classify as classify_failures, FAILURE_MODE_LABELS

# task_type → (task_success, efficiency, experience, robustness)
_DIMENSION_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "outbound_sign":  (0.50, 0.20, 0.20, 0.10),  # 催收/签约：任务优先
    "survey":         (0.20, 0.15, 0.50, 0.15),  # 满意度回访：体验优先
    "faq_service":    (0.35, 0.30, 0.25, 0.10),  # FAQ解答：效率次之
    "general":        (0.40, 0.20, 0.30, 0.10),  # 默认
}


class Aggregator:
    def combine(
        self,
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        parse_warnings: list[str],
        soft_eval_skipped: bool = False,
        arbitration_records: list[ArbitrationRecord] | None = None,
        scoring_policy: ScoringPolicy | None = None,
        soft_dimensions: list[SoftDimension] | None = None,
    ) -> dict:
        policy = scoring_policy or ScoringPolicy()
        hard_fail = any(result.severity == "fatal" and not result.passed for result in hard_results)
        total_hard_weight = sum(max(result.weight, 0.0) for result in hard_results)
        hard_score = 100.0 * (
            sum(result.score_delta * max(result.weight, 0.0) for result in hard_results)
            / max(total_hard_weight, 1.0)
        )

        # soft_score：按 SoftDimension.weight 加权平均，降级时等权平均
        if judge_results:
            weight_map = {d.id: d.weight for d in soft_dimensions} if soft_dimensions else {}
            total_w = sum(weight_map.get(r.dimension_id, 1.0) for r in judge_results)
            soft_score = 100.0 * sum(
                r.score * weight_map.get(r.dimension_id, 1.0) for r in judge_results
            ) / max(total_w, 1e-9)
        else:
            soft_score = 0.0

        if hard_fail and policy.hard_fail_zero_out:
            overall_score = 0.0
        else:
            overall_score = round(hard_score * policy.hard_rules_weight + soft_score * policy.soft_rules_weight, 2)
        needs_review = bool(parse_warnings) or soft_eval_skipped or bool(arbitration_records)
        return {
            "hard_fail": hard_fail,
            "hard_score": round(hard_score, 2),
            "soft_score": round(soft_score, 2),
            "overall_score": overall_score,
            "needs_review": needs_review,
            "soft_eval_skipped": soft_eval_skipped,
        }

    def build_detailed_dimensions(
        self,
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        turn_count: int,
        task_type: str = "general",
    ) -> list[DimensionScore]:
        w_task, w_eff, w_exp, w_rob = _DIMENSION_WEIGHTS.get(task_type, _DIMENSION_WEIGHTS["general"])
        dimensions: list[DimensionScore] = []

        task_success_score = sum(r.score_delta for r in hard_results) / max(len(hard_results), 1)
        dimensions.append(
            DimensionScore(
                dimension_name="任务完成度",
                category="task_success",
                score=task_success_score * 100,
                weight=w_task,
                max_score=100.0,
                sub_scores={
                    "必需步骤完成": next((r.score_delta * 100 for r in hard_results if r.rule_id == "required_steps"), 0.0),
                    "必需槽位收集": next((r.score_delta * 100 for r in hard_results if r.rule_id == "required_slots"), 0.0),
                    "禁止行为规避": next((r.score_delta * 100 for r in hard_results if r.rule_id == "forbidden_actions"), 0.0),
                },
                reason=f"基于规则检查的任务完成情况（权重 {w_task:.0%}，任务类型：{task_type}）",
                evidence_turn_ids=[tid for r in hard_results for tid in r.evidence_turn_ids],
            )
        )

        efficiency_score = max(0, 100 - (turn_count - 4) * 10)
        dimensions.append(
            DimensionScore(
                dimension_name="对话效率",
                category="efficiency",
                score=efficiency_score,
                weight=w_eff,
                max_score=100.0,
                sub_scores={"轮次控制": efficiency_score, "信息密度": 80.0},
                reason=f"对话共 {turn_count} 轮，{'效率良好' if turn_count <= 6 else '轮次偏多'}",
            )
        )

        if judge_results:
            experience_score = sum(r.score for r in judge_results) / len(judge_results) * 100
            dimensions.append(
                DimensionScore(
                    dimension_name="用户体验",
                    category="experience",
                    score=experience_score,
                    weight=w_exp,
                    max_score=100.0,
                    sub_scores={r.dimension_id: r.score * 100 for r in judge_results},
                    reason="基于多评委软评分的主观体验维度",
                    evidence_turn_ids=[tid for r in judge_results for tid in r.evidence_turn_ids],
                )
            )

        forbidden_passed = next((r.passed for r in hard_results if r.rule_id == "forbidden_actions"), True)
        # 鲁棒性：衡量模型在压力下的稳健性，独立于任务完成度
        # - 违规承诺（fatal）→ 直接归零
        # - 场景规则失败（模型应对异常场景时失败）→ 各扣 20 分
        # - 流程/槽位失败不影响鲁棒性（属于任务完成度范畴）
        scenario_fails = sum(
            1 for r in hard_results
            if not r.passed and r.rule_id.startswith("scenario_")
        )
        if not forbidden_passed:
            robustness_score = 0.0
            robustness_reason = "检测到违规承诺，鲁棒性归零"
        elif scenario_fails > 0:
            robustness_score = max(0.0, 100.0 - scenario_fails * 20.0)
            robustness_reason = f"存在 {scenario_fails} 个场景规则失败，稳健性不足"
        else:
            robustness_score = 100.0
            robustness_reason = "对话中未出现异常处理问题"
        robustness_sub = {
            "违规承诺规避": 100.0 if forbidden_passed else 0.0,
            "场景应对能力": max(0.0, 100.0 - scenario_fails * 20.0),
        }
        dimensions.append(
            DimensionScore(
                dimension_name="鲁棒性",
                category="robustness",
                score=robustness_score,
                weight=w_rob,
                max_score=100.0,
                sub_scores=robustness_sub,
                reason=robustness_reason,
                evidence_turn_ids=[
                    tid for r in hard_results
                    if not r.passed and (not forbidden_passed or r.rule_id.startswith("scenario_"))
                    for tid in r.evidence_turn_ids
                ],
            )
        )

        return dimensions

    def build_evaluation_summary(
        self,
        overall_score: float,
        detailed_dimensions: list[DimensionScore],
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        state_trace: list[str] | None = None,
    ) -> EvaluationSummary:
        if overall_score >= 95:
            grade = "A+"
        elif overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"

        task_success = next((d.score for d in detailed_dimensions if d.category == "task_success"), 0.0)
        efficiency = next((d.score for d in detailed_dimensions if d.category == "efficiency"), 0.0)
        experience = next((d.score for d in detailed_dimensions if d.category == "experience"), 0.0)
        robustness = next((d.score for d in detailed_dimensions if d.category == "robustness"), 0.0)

        strengths: list[str] = []
        if task_success >= 90:
            strengths.append("任务完成度高，关键步骤和槽位收集完整")
        if efficiency >= 85:
            strengths.append("对话效率好，轮次控制合理")
        if experience >= 85:
            strengths.append("用户体验较好，表达清晰礼貌")

        weaknesses: list[str] = []
        for result in hard_results:
            if not result.passed:
                prefix = "[待复核]" if result.status == "needs_review" else "[失败]"
                weaknesses.append(f"{prefix} {result.reason}")
        for result in judge_results:
            if result.status != "ok" or result.score < 0.7:
                prefix = "[待复核]" if result.status != "ok" else "[偏低]"
                weaknesses.append(f"{prefix} {result.dimension_id} 得分偏低：{result.reason}")

        suggestions: list[str] = []
        for result in hard_results:
            if not result.passed and result.improvement_suggestion:
                suggestions.append(result.improvement_suggestion)
        if efficiency < 70:
            suggestions.append("建议优化对话流程，减少不必要的轮次")
        if experience < 70:
            suggestions.append("建议改进话术表达，提升用户体验")

        failure_modes = classify_failures(hard_results, state_trace)

        return EvaluationSummary(
            overall_score=overall_score,
            grade=grade,
            task_success_rate=task_success / 100,
            efficiency_score=efficiency,
            experience_score=experience,
            robustness_score=robustness,
            key_strengths=strengths if strengths else ["暂无明显优点"],
            key_weaknesses=weaknesses if weaknesses else ["暂无明显缺点"],
            improvement_suggestions=suggestions if suggestions else ["整体表现良好，继续保持"],
            failure_modes=failure_modes,
        )
