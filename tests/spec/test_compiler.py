from pathlib import Path

from app.domain.task_instruction import TaskInstruction
from app.spec.compiler import SpecCompiler


def read_fixture(name: str) -> str:
    return Path(f"tests/fixtures/instructions/{name}").read_text(encoding="utf-8")


def test_compiler_builds_enhanced_eval_spec_from_rider_instruction() -> None:
    compiler = SpecCompiler()

    spec = compiler.compile(
        TaskInstruction(
            instruction_id="instr_rider",
            name="飞毛腿骑手外呼任务",
            raw_text=read_fixture("rider_station_task.md"),
        )
    )

    assert spec.role_definition == "你是美团外卖骑手的站长。"
    assert len(spec.flow_steps) == 4
    assert len(spec.faq_items) == 4
    assert len(spec.constraint_items) == 5
    assert "我向同事确认后再回电给你" in spec.fallback_policy[0]
    assert any(item.id == "identity_check" for item in spec.required_steps)


def test_compiler_builds_enhanced_eval_spec_from_course_instruction() -> None:
    compiler = SpecCompiler()

    spec = compiler.compile(
        TaskInstruction(
            instruction_id="instr_course",
            name="课程直播线路通知",
            raw_text=read_fixture("course_live_task.md"),
        )
    )

    assert spec.role_definition == "Customer Support Specialist for Course Publishing Platform"
    assert len(spec.flow_steps) == 7
    assert any(item.category == "length_limit" for item in spec.constraint_items)
    assert any("稍后再打" in item for item in spec.fallback_policy)


def test_compiler_keeps_legacy_keyword_fallback_for_plain_text_instruction() -> None:
    compiler = SpecCompiler()

    spec = compiler.compile(
        TaskInstruction(
            instruction_id="instr_plain",
            name="确认送达时间",
            raw_text="请先确认用户身份，再确认收货时间，不要承诺一定送达。",
        )
    )

    assert any(item.id == "identity_check" for item in spec.required_steps)
    assert spec.required_slots[0].name == "delivery_time"
    assert spec.forbidden_actions[0].id in {"forbid_commitment", "forbid_false_promise"}


def test_compiler_marks_forbidden_commitment_and_fallback_together() -> None:
    compiler = SpecCompiler()

    spec = compiler.compile(
        TaskInstruction(
            instruction_id="instr_course",
            name="课程直播线路通知",
            raw_text="# Role\n你是客服\n\n# Task\n通知直播升级\n\n# Constraints\n- 不能承诺给商家折扣券或优惠券\n- 若商家说在开车，礼貌说“那我稍后再打”后挂断",
        )
    )

    assert spec.forbidden_actions[0].id == "forbid_commitment"
    assert "稍后再打" in spec.fallback_policy[0]
