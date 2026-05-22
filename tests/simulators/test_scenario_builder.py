from app.domain.eval_spec import EvalSpec
from app.simulators.profiles import DEFAULT_PROFILES
from app.simulators.scenario_builder import ScenarioBuilder


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
