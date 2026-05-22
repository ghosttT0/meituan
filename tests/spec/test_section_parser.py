from pathlib import Path

from app.spec.section_parser import InstructionSectionParser


def read_fixture(name: str) -> str:
    return Path(f"tests/fixtures/instructions/{name}").read_text(encoding="utf-8")


def test_parser_splits_sections_and_extracts_opening_line() -> None:
    parser = InstructionSectionParser()

    parsed = parser.parse(
        instruction_id="instr_rider",
        title="飞毛腿骑手外呼任务",
        raw_text=read_fixture("rider_station_task.md"),
    )

    assert parsed.role_definition == "你是美团外卖骑手的站长。"
    assert "你好，请问是" in parsed.opening_line
    assert "conversation_flow" in parsed.sections


def test_parser_extracts_ordered_flow_steps() -> None:
    parser = InstructionSectionParser()

    parsed = parser.parse(
        instruction_id="instr_course",
        title="课程直播线路通知",
        raw_text=read_fixture("course_live_task.md"),
    )

    assert len(parsed.flow_steps) == 7
    assert parsed.flow_steps[0].step_id == "step_1"
    assert parsed.flow_steps[0].title == "身份确认"
    assert "负责人" in parsed.flow_steps[0].raw_text


def test_parser_extracts_faq_and_constraints() -> None:
    parser = InstructionSectionParser()

    parsed = parser.parse(
        instruction_id="instr_rider",
        title="飞毛腿骑手外呼任务",
        raw_text=read_fixture("rider_station_task.md"),
    )

    assert len(parsed.faq_items) == 4
    assert len(parsed.constraint_items) == 5
    assert "超出职责范围" in parsed.constraint_items[1].raw_text
