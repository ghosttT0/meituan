import random
from uuid import uuid4

from app.domain.eval_spec import EvalSpec
from app.domain.simulation import SimulationScenario


class ScenarioBuilder:
    def build_standard_pack(self, spec: EvalSpec) -> list[SimulationScenario]:
        task_type = self._detect_task_type(spec)
        templates = self._build_templates(task_type)
        return [
            SimulationScenario(
                scenario_id=f"scenario_{uuid4().hex[:8]}",
                spec_id=spec.spec_id,
                profile_id=item["profile_id"],
                primary_branch=item["primary_branch"],
                scenario_key=item["scenario_key"],
                scenario_label=item["scenario_label"],
                user_goal=item["user_goal"],
                secondary_branch=item.get("secondary_branch"),
                max_turns=item.get("max_turns", 8),
                termination_policy="task_complete_or_user_exit",
                coverage_mode="standard_pack",
            )
            for item in templates
        ]

    def build(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int = 8,
        secondary_branch: str | None = None,
        scenario_key: str | None = None,
        random_seed: int | None = None,
    ) -> SimulationScenario:
        if scenario_key:
            standard_pack = self.build_standard_pack(spec)
            matched = next((item for item in standard_pack if item.scenario_key == scenario_key), None)
            if matched:
                matched.max_turns = max_turns
                matched.profile_id = self._resolve_profile_id(
                    profile_id, matched.profile_id, prefer_default=True, random_seed=random_seed
                )
                return matched
        return SimulationScenario(
            scenario_id=f"scenario_{uuid4().hex[:8]}",
            spec_id=spec.spec_id,
            profile_id=self._resolve_profile_id(
                profile_id, profile_id, prefer_default=False, random_seed=random_seed
            ),
            primary_branch=primary_branch,
            scenario_key="custom",
            scenario_label="自定义模拟场景",
            user_goal=spec.task_goal,
            secondary_branch=secondary_branch,
            max_turns=max_turns,
            termination_policy="task_complete_or_user_exit",
        )

    def _resolve_profile_id(
        self,
        requested_profile_id: str,
        default_profile_id: str,
        prefer_default: bool,
        random_seed: int | None = None,
    ) -> str:
        if requested_profile_id == "random":
            picker = random.Random(random_seed) if random_seed is not None else random
            return picker.choice(
                ["cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning", "uninformed"]
            )
        if prefer_default:
            return default_profile_id
        return requested_profile_id or default_profile_id

    def _detect_task_type(self, spec: EvalSpec) -> str:
        # 优先使用 spec 显式声明的 task_type（outbound_sign/survey/faq_service/general）
        # 再退回关键词推断（兼容旧数据）
        task_type_map = {
            "outbound_sign": "rider",
            "faq_service":   "course_live",
        }
        if spec.task_type in task_type_map:
            return task_type_map[spec.task_type]
        text = f"{spec.task_goal}\n" + "\n".join(item.raw_text for item in spec.faq_items) + "\n" + "\n".join(
            step.raw_text for step in spec.flow_steps
        )
        if "飞毛腿" in text or "配送" in text or "骑手" in text:
            return "rider"
        if "直播" in text or "低延迟" in text or "标准直播" in text:
            return "course_live"
        return "generic"

    def _build_templates(self, task_type: str) -> list[dict]:
        if task_type == "rider":
            return [
                {
                    "scenario_key": "main_flow",
                    "scenario_label": "飞毛腿主流程确认",
                    "user_goal": "确认今天是否开始配送并完成主流程通知",
                    "profile_id": "cooperative",
                    "primary_branch": "cooperative",
                },
                {
                    "scenario_key": "faq_followup",
                    "scenario_label": "飞毛腿 FAQ 追问",
                    "user_goal": "追问做不到单量会有什么影响或如何退出飞毛腿",
                    "profile_id": "questioning",
                    "primary_branch": "questioning",
                },
                {
                    "scenario_key": "busy_interrupt",
                    "scenario_label": "飞毛腿忙碌打断",
                    "user_goal": "在忙碌情况下要求对方快速说明重点",
                    "profile_id": "busy",
                    "primary_branch": "busy",
                },
                {
                    "scenario_key": "hesitant_risk",
                    "scenario_label": "飞毛腿风险犹豫",
                    "user_goal": "担心今天跑不了会影响合同和后续派单",
                    "profile_id": "hesitant",
                    "primary_branch": "hesitant",
                },
                {
                    "scenario_key": "exit_scope",
                    "scenario_label": "飞毛腿退出/超纲",
                    "user_goal": "提出退出或超出站长职责范围的问题，观察模型兜底处理",
                    "profile_id": "rejecting",
                    "primary_branch": "rejecting",
                },
            ]
        if task_type == "course_live":
            return [
                {
                    "scenario_key": "main_flow",
                    "scenario_label": "直播升级主流程通知",
                    "user_goal": "确认直播升级信息并理解后续操作",
                    "profile_id": "cooperative",
                    "primary_branch": "cooperative",
                },
                {
                    "scenario_key": "faq_followup",
                    "scenario_label": "直播 FAQ 追问",
                    "user_goal": "追问低延迟直播和标准直播的区别及费用变化",
                    "profile_id": "questioning",
                    "primary_branch": "questioning",
                },
                {
                    "scenario_key": "busy_interrupt",
                    "scenario_label": "直播忙碌打断",
                    "user_goal": "要求客服用最短时间说明升级重点",
                    "profile_id": "busy",
                    "primary_branch": "busy",
                },
                {
                    "scenario_key": "hesitant_risk",
                    "scenario_label": "直播费用犹豫",
                    "user_goal": "担心低延迟直播费用更高或操作更复杂",
                    "profile_id": "hesitant",
                    "primary_branch": "hesitant",
                },
                {
                    "scenario_key": "exit_scope",
                    "scenario_label": "直播超纲/退出",
                    "user_goal": "提出超出客服职责范围的问题，观察模型是否正确兜底",
                    "profile_id": "rejecting",
                    "primary_branch": "rejecting",
                },
            ]
        return [
            {
                "scenario_key": "main_flow",
                "scenario_label": "主流程确认",
                "user_goal": spec.task_goal if False else "完成任务主流程确认",
                "profile_id": "cooperative",
                "primary_branch": "cooperative",
            },
            {
                "scenario_key": "faq_followup",
                "scenario_label": "FAQ 追问",
                "user_goal": "围绕任务关键知识点进行追问",
                "profile_id": "questioning",
                "primary_branch": "questioning",
            },
            {
                "scenario_key": "busy_interrupt",
                "scenario_label": "忙碌打断",
                "user_goal": "在忙碌情况下要求对方说重点",
                "profile_id": "busy",
                "primary_branch": "busy",
            },
            {
                "scenario_key": "hesitant_risk",
                "scenario_label": "犹豫风险",
                "user_goal": "担心执行成本、后果或额外影响",
                "profile_id": "hesitant",
                "primary_branch": "hesitant",
            },
            {
                "scenario_key": "exit_scope",
                "scenario_label": "退出/超纲",
                "user_goal": "提出退出或超纲诉求，测试模型兜底处理",
                "profile_id": "rejecting",
                "primary_branch": "rejecting",
            },
        ]
