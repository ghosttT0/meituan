import re
from collections import OrderedDict

from app.spec.instruction_ir import IRConstraintItem, IRFAQItem, IRFlowStep, InstructionIR


SECTION_ALIASES = OrderedDict(
    {
        "role": ["role"],
        "task": ["task"],
        "opening_line": ["opening line", "opening"],
        "conversation_flow": ["conversation flow", "call flow"],
        "faq": ["knowledge points", "faq", "knowledge points (faq)"],
        "constraints": ["constraints", "constraint"],
    }
)


class InstructionSectionParser:
    def parse(self, instruction_id: str, title: str, raw_text: str) -> InstructionIR:
        normalized = raw_text.replace("\r\n", "\n")
        section_map = self._split_sections(normalized)
        return InstructionIR(
            instruction_id=instruction_id,
            title=title,
            role_definition=section_map.get("role", "").strip(),
            task_goal=section_map.get("task", "").strip(),
            opening_line=section_map.get("opening_line", "").strip(),
            sections=section_map,
            flow_steps=self._extract_flow_steps(section_map.get("conversation_flow", "")),
            faq_items=self._extract_bullets(section_map.get("faq", ""), IRFAQItem, "faq"),
            constraint_items=self._extract_bullets(section_map.get("constraints", ""), IRConstraintItem, "constraint"),
            fallback_policy=[],
        )

    def parse_legacy_keywords(self, instruction_id: str, title: str, raw_text: str) -> InstructionIR:
        flow_steps: list[IRFlowStep] = []
        if "身份" in raw_text:
            flow_steps.append(
                IRFlowStep(
                    step_id="identity_check",
                    order=1,
                    title="确认身份",
                    raw_text="需要明确身份确认话术",
                )
            )

        constraint_items: list[IRConstraintItem] = []
        if "不要承诺" in raw_text or "不要保证" in raw_text:
            constraint_items.append(
                IRConstraintItem(
                    constraint_id="constraint_1",
                    raw_text="不能承诺一定送达",
                    category="forbidden_commitment",
                )
            )

        return InstructionIR(
            instruction_id=instruction_id,
            title=title,
            task_goal=title,
            sections={},
            flow_steps=flow_steps,
            constraint_items=constraint_items,
        )

    def _split_sections(self, raw_text: str) -> dict[str, str]:
        pattern = re.compile(r"^\s*#{1,3}\s*(.+?)\s*$", re.MULTILINE)
        matches = [match for match in pattern.finditer(raw_text) if not match.group(1).strip().lower().startswith("step ")]
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            label = match.group(1).strip().lower().rstrip(":")
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
            key = self._resolve_section_key(label)
            if key:
                sections[key] = raw_text[start:end].strip()
        return sections

    def _resolve_section_key(self, label: str) -> str | None:
        for key, aliases in SECTION_ALIASES.items():
            if any(alias in label for alias in aliases):
                return key
        return None

    def _extract_flow_steps(self, text: str) -> list[IRFlowStep]:
        step_matches = list(
            re.finditer(r"^\s*##\s*Step\s*(\d+)\s*:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
        )
        steps: list[IRFlowStep] = []
        for index, match in enumerate(step_matches):
            start = match.end()
            end = step_matches[index + 1].start() if index + 1 < len(step_matches) else len(text)
            steps.append(
                IRFlowStep(
                    step_id=f"step_{match.group(1)}",
                    order=int(match.group(1)),
                    title=match.group(2).strip(),
                    raw_text=text[start:end].strip(),
                )
            )
        if steps:
            return steps

        bullet_steps = re.findall(r"^\s*(\d+)\.\s*(.+)$", text, re.MULTILINE)
        return [
            IRFlowStep(step_id=f"step_{order}", order=int(order), title=content.strip(), raw_text=content.strip())
            for order, content in bullet_steps
        ]

    def _extract_bullets(self, text: str, item_cls, prefix: str):
        bullets = re.findall(r"^\s*[-*]\s+(.+)$", text, re.MULTILINE)
        return [item_cls(**{f"{prefix}_id": f"{prefix}_{i + 1}", "raw_text": bullet}) for i, bullet in enumerate(bullets)]
