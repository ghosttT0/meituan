from app.domain.conversation import Conversation, FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.semantic_matcher import semantic_match


class ScenarioRuleEngine:
    def evaluate(self, spec: EvalSpec, conversation: Conversation, events: list[FactEvent]) -> list[RuleResult]:
        scenario_key = conversation.metadata.get("scenario_key", "")
        if scenario_key == "faq_followup":
            return [self._evaluate_faq_grounding(spec, conversation)]
        if scenario_key == "busy_interrupt":
            return [self._evaluate_busy_focus(conversation)]
        if scenario_key == "hesitant_risk":
            return [self._evaluate_hesitant_clarity(conversation)]
        if scenario_key == "exit_scope":
            return [self._evaluate_scope_fallback(spec, conversation)]
        return []

    def _evaluate_faq_grounding(self, spec: EvalSpec, conversation: Conversation) -> RuleResult:
        faq_references = self._extract_faq_references(spec)
        fallback_kws = ["低延迟直播", "标准直播", "小班课", "大班课", "费用", "退出", "派单", "合同"]
        agent_turns = [t for t in conversation.turns if t.speaker == "agent"]
        matched_turn_ids = []
        for turn in agent_turns:
            matched, _ = semantic_match(
                turn.text,
                faq_references or fallback_kws,
                threshold=0.60,
                fallback_keywords=fallback_kws,
            )
            if matched:
                matched_turn_ids.append(turn.turn_id)
        passed = bool(matched_turn_ids)
        return RuleResult(
            rule_id="scenario_faq_grounding",
            passed=passed,
            score_delta=1.0 if passed else 0.0,
            weight=2.0,
            evidence_turn_ids=matched_turn_ids,
            reason="FAQ 追问场景已答到关键知识点" if passed else "FAQ 追问场景未答到关键知识点",
        )

    def _evaluate_busy_focus(self, conversation: Conversation) -> RuleResult:
        agent_turns = [t for t in conversation.turns if t.speaker == "agent"]
        if not agent_turns:
            return RuleResult(rule_id="scenario_busy_focus", passed=False, score_delta=0.0,
                              reason="忙碌打断场景没有有效回复")
        first_reply = agent_turns[0]
        # 语义：是否表达了"快速/简短/重点"的意图
        focus_references = ["我长话短说", "简短说一下重点", "简单说一件重要的事", "只说一个重点"]
        fallback_kws = ["重点", "简短", "1分钟"]
        matched, _ = semantic_match(
            first_reply.text,
            focus_references,
            threshold=0.60,
            fallback_keywords=fallback_kws,
        )
        is_focused = len(first_reply.text) <= 40 or matched
        return RuleResult(
            rule_id="scenario_busy_focus",
            passed=is_focused,
            score_delta=1.0 if is_focused else 0.0,
            weight=1.8,
            evidence_turn_ids=[first_reply.turn_id],
            reason="忙碌打断场景已快速聚焦" if is_focused else "忙碌打断场景回复偏冗长，未快速说重点",
        )

    def _evaluate_scope_fallback(self, spec: EvalSpec, conversation: Conversation) -> RuleResult:
        fallback_references = list(spec.fallback_policy) + [item.raw_text for item in spec.constraint_items]
        fallback_kws = ["回电", "同事确认", "我现在能回答的先回答", "超出职责范围"]
        agent_turns = [t for t in conversation.turns if t.speaker == "agent"]
        matched_turn_ids = []
        for turn in agent_turns:
            matched, _ = semantic_match(
                turn.text,
                fallback_references or fallback_kws,
                threshold=0.65,
                fallback_keywords=fallback_kws,
            )
            if matched:
                matched_turn_ids.append(turn.turn_id)
        passed = bool(matched_turn_ids)
        return RuleResult(
            rule_id="scenario_scope_fallback",
            passed=passed,
            score_delta=1.0 if passed else 0.0,
            weight=2.2,
            evidence_turn_ids=matched_turn_ids,
            reason="退出/超纲场景使用了正确兜底" if passed else "退出/超纲场景未使用正确兜底话术",
        )

    def _evaluate_hesitant_clarity(self, conversation: Conversation) -> RuleResult:
        agent_turns = [t for t in conversation.turns if t.speaker == "agent"]
        if not agent_turns:
            return RuleResult(rule_id="scenario_hesitant_clarity", passed=False, score_delta=0.0,
                              reason="犹豫场景没有有效回复")
        first_reply = agent_turns[0]
        # 语义：是否解释了费用/风险/影响，每个维度独立判断，≥2个维度命中则通过
        dimension_refs = {
            "cost":   (["说明费用变化", "解释费用影响", "告知价格差异"], ["费用", "略高", "更高"]),
            "risk":   (["说明风险", "解释注意事项", "告知可能影响"], ["风险", "影响", "会怎么样"]),
            "choice": (["按需选择", "根据需求决定", "建议对比后选择"], ["按需选择", "互动更顺", "区别"]),
        }
        hit_count = 0
        for refs, kws in dimension_refs.values():
            matched, _ = semantic_match(first_reply.text, refs, threshold=0.60, fallback_keywords=kws)
            if matched:
                hit_count += 1
        passed = hit_count >= 2
        return RuleResult(
            rule_id="scenario_hesitant_clarity",
            passed=passed,
            score_delta=1.0 if passed else 0.0,
            weight=1.9,
            evidence_turn_ids=[first_reply.turn_id],
            reason="犹豫场景已解释风险/影响/费用" if passed else "犹豫场景未充分解释风险、影响或费用",
        )

    def _extract_faq_references(self, spec: EvalSpec) -> list[str]:
        """从 FAQ 条目中提取语义参考句，用于 embedding 比对。"""
        return [item.raw_text for item in spec.faq_items if item.raw_text]
