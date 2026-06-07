from app.domain.eval_spec import ConstraintItemSpec, EvalSpec, FAQItemSpec, FlowStepSpec
from app.simulators.question_pool import TaskQuestionPoolBuilder


def test_question_pool_builder_generates_rider_specific_questions() -> None:
    spec = EvalSpec(
        spec_id="spec_rider",
        instruction_id="instr_rider",
        version="v2",
        task_goal='致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。',
        flow_steps=[
            FlowStepSpec(
                step_id="step_1",
                order=1,
                title="确认是否可以开始配送",
                raw_text="告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。",
            )
        ],
        faq_items=[
            FAQItemSpec(faq_id="faq_1", raw_text="如需退出飞毛腿，必须在前一天 Z 点之前取消。"),
            FAQItemSpec(faq_id="faq_2", raw_text="单日合同必须完成 X 单，否则合同及派单可能受到影响。"),
        ],
        constraint_items=[
            ConstraintItemSpec(constraint_id="c_1", raw_text="如果骑手坚持确实无法配送，安慰他们后挂断电话。")
        ],
        fallback_policy=["如被问及超出职责范围的问题，回复固定兜底话术。"],
    )

    pool = TaskQuestionPoolBuilder().build(spec)

    joined = "\n".join([item.prompt_text for item in pool.faq_questions + pool.step_questions + pool.objection_questions])
    assert "退出" in joined
    assert "做不到" in joined or "跑不了" in joined
    assert "今天" in joined and "配送" in joined


def test_question_pool_builder_generates_course_specific_questions() -> None:
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        flow_steps=[
            FlowStepSpec(
                step_id="step_1",
                order=1,
                title="传达升级内容",
                raw_text="说明标准直播与低延迟直播的区别。",
            ),
            FlowStepSpec(
                step_id="step_2",
                order=2,
                title="确认前端是否可见",
                raw_text="询问对方是否在前端看到了低延迟直播选项。",
            ),
        ],
        faq_items=[
            FAQItemSpec(faq_id="faq_1", raw_text="低延迟直播更适合小班课，费用略高。"),
            FAQItemSpec(faq_id="faq_2", raw_text="第三方系统未显示时，可在直播平台里勾选低延迟直播。"),
        ],
    )

    pool = TaskQuestionPoolBuilder().build(spec)

    joined = "\n".join([item.prompt_text for item in pool.faq_questions + pool.step_questions + pool.objection_questions])
    assert "低延迟直播" in joined
    assert "费用" in joined
    assert "没看到" in joined or "在哪里" in joined
