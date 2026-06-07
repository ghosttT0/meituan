from app.domain.eval_spec import EvalSpec
from app.simulators.profiles import DEFAULT_PROFILES
from app.simulators.scenario_builder import ScenarioBuilder
from unittest.mock import patch


def test_default_profiles_cover_required_branches() -> None:
    profile_ids = {profile.profile_id for profile in DEFAULT_PROFILES}

    assert {
        "cooperative",
        "hesitant",
        "rejecting",
        "busy",
        "interrupting",
        "questioning",
    } <= profile_ids


def test_scenario_builder_uses_profile_and_primary_branch() -> None:
    spec = EvalSpec(
        spec_id="spec_1",
        instruction_id="instr_1",
        version="v2",
        task_goal="确认收货时间",
    )

    scenario = ScenarioBuilder().build(
        spec=spec,
        profile_id="busy",
        primary_branch="busy",
        max_turns=5,
    )

    assert scenario.spec_id == "spec_1"
    assert scenario.profile_id == "busy"
    assert scenario.primary_branch == "busy"
    assert scenario.max_turns == 5


def test_scenario_builder_builds_standard_pack_for_rider_task() -> None:
    spec = EvalSpec(
        spec_id="spec_rider",
        instruction_id="instr_rider",
        version="v2",
        task_goal='致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。',
        faq_items=[],
        flow_steps=[],
        constraint_items=[],
        fallback_policy=[],
    )

    scenarios = ScenarioBuilder().build_standard_pack(spec)

    scenario_keys = {item.scenario_key for item in scenarios}
    assert {"main_flow", "faq_followup", "busy_interrupt", "hesitant_risk", "exit_scope"} <= scenario_keys
    faq_scenario = next(item for item in scenarios if item.scenario_key == "faq_followup")
    assert "飞毛腿" in faq_scenario.scenario_label
    assert faq_scenario.primary_branch == "questioning"


def test_scenario_builder_builds_standard_pack_for_course_task() -> None:
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        faq_items=[],
        flow_steps=[],
        constraint_items=[],
        fallback_policy=[],
    )

    scenarios = ScenarioBuilder().build_standard_pack(spec)

    faq_scenario = next(item for item in scenarios if item.scenario_key == "faq_followup")
    assert "直播" in faq_scenario.scenario_label
    assert "区别" in faq_scenario.user_goal or "费用" in faq_scenario.user_goal


def test_scenario_builder_build_uses_selected_scenario_template() -> None:
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        faq_items=[],
        flow_steps=[],
        constraint_items=[],
        fallback_policy=[],
    )

    scenario = ScenarioBuilder().build(
        spec=spec,
        profile_id="cooperative",
        primary_branch="cooperative",
        max_turns=5,
        scenario_key="faq_followup",
    )

    assert scenario.scenario_key == "faq_followup"
    assert scenario.primary_branch == "questioning"
    assert scenario.profile_id == "questioning"


def test_scenario_builder_supports_random_profile_resolution() -> None:
    spec = EvalSpec(
        spec_id="spec_course",
        instruction_id="instr_course",
        version="v2",
        task_goal="告知机构客户低延迟直播和标准直播的区别。",
        faq_items=[],
        flow_steps=[],
        constraint_items=[],
        fallback_policy=[],
    )

    with patch("app.simulators.scenario_builder.random.choice", return_value="hesitant"):
        scenario = ScenarioBuilder().build(
            spec=spec,
            profile_id="random",
            primary_branch="questioning",
            max_turns=5,
            scenario_key="faq_followup",
        )

    assert scenario.scenario_key == "faq_followup"
    assert scenario.profile_id == "hesitant"
