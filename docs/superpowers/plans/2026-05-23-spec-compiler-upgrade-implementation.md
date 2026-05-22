# SpecCompiler Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前基于关键词的 `SpecCompiler` 升级为“轻量中间表示 + 规则优先抽结构 + LLM 只补缺 + 输出增强版 EvalSpec”的可测试原型，用于编译复杂外呼任务指令，同时保持对现有评测器老字段的兼容。

**Architecture:** 先引入 `InstructionIR` 作为中间表示，把原始任务指令拆成 `sections / flow_steps / faq_items / constraint_items / fallback_policy`。再用规则解析器完成主结构提取，用一个可替换的 normalizer 接口做“LLM 辅助补缺/归一化”，最后通过 mapper 生成增强版 `EvalSpec`。mapper 在输出增强字段的同时，继续填充 `required_steps / required_slots / forbidden_actions` 等老字段，保证现有评测器链路可运行。现阶段保持默认 normalizer 为本地规则实现，不依赖外部 API。

**Tech Stack:** Python 3.10+, Pydantic v2, FastAPI, pytest

---

## File Structure

### Runtime files

- `app/domain/eval_spec.py`：扩展 `EvalSpec`，新增复杂任务编译需要的结构字段。
- `app/spec/instruction_ir.py`：定义 `InstructionIR` 及其子模型。
- `app/spec/section_parser.py`：按标题和列表结构切分章节并抽取步骤/FAQ/约束。
- `app/spec/normalizer.py`：定义 normalizer 接口和默认规则 normalizer。
- `app/spec/mapper.py`：把 `InstructionIR` 映射为增强版 `EvalSpec`。
- `app/spec/compiler.py`：重构为 orchestrator，串联 parser / normalizer / mapper。
- `app/api/routes_specs.py`：保持 API 不变，但走新版 compiler。

### Tests & fixtures

- `tests/fixtures/instructions/rider_station_task.md`
- `tests/fixtures/instructions/course_live_task.md`
- `tests/spec/test_section_parser.py`
- `tests/spec/test_normalizer.py`
- `tests/spec/test_mapper.py`
- `tests/spec/test_compiler.py`
- `tests/api/test_specs_api.py`

---

### Task 1: Add fixture instructions and failing parser tests

**Files:**
- Create: `tests/fixtures/instructions/rider_station_task.md`
- Create: `tests/fixtures/instructions/course_live_task.md`
- Create: `tests/spec/test_section_parser.py`

- [ ] **Step 1: Write the fixture files copied from the Excel samples**

```text
# tests/fixtures/instructions/rider_station_task.md
# Role
你是美团外卖骑手的站长。

# Task
致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。

# Opening Line
你好，请问是${rider_name}吗？我是站长。我看到你已报名飞毛腿。请记住，午餐和晚餐高峰期需要上线。单日合同每天至少完成 X 单；多日合同每天至少完成 Y 单。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。
2. 说明单日飞毛腿合同需要连续 Y 天完成配送；否则合同将受到影响。
3. 尽量挽留不想配送的骑手，鼓励能配送的骑手，并提醒他们注意安全。
4. 说明飞毛腿报名是按排名进行的，并非站长干预。骑手应减少拒单、取消和超时。

# Knowledge Points (FAQ)
- 目前，许多骑手正在申请飞毛腿。如果你无法连续配送 Y 天，你的名额可能会被他人占用。
- 单日合同：在生效当天必须完成 X 单，否则合同及派单可能受到影响。
- 多日合同：每天必须完成 Y 单，否则后续合同及派单可能受到影响。
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 遵循对话流程和常见问题解答。
- 如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"
- 保持语气随意，像打电话一样自然。
- 每次回复控制在约 30 个字以内。
- 如果骑手坚持确实无法配送，安慰他们后挂断电话。
```

```text
# tests/fixtures/instructions/course_live_task.md
# Role
Customer Support Specialist for Course Publishing Platform

# Task
告知机构客户，课程发布页面将新增"标准直播"和"低延迟直播"两个独立选项。当需要实时互动时，鼓励选择低延迟直播。

# Constraints
- 每次回复极简——最多15-20个字
- 使用简短、自然的口语化表达，符合电话沟通风格
- 频繁给商家发言和提问的机会
- 若对话被打断，使用简短过渡语
- 不说“好的”“哈哈”等语气词
- 不能承诺给商家折扣券或优惠券
- 若老板说忙，说“就1分钟，保证简短”后继续简短说明
- 若商家说在开车，礼貌说“那我稍后再打”后挂断

# Opening Line
您好，请问您是贵培训机构/校区的负责人吗？

# Conversation Flow
## Step 1: 身份确认
- 若是负责人 → 进入第2步
- 若不是 → 请其转达，然后进入第2步

## Step 2: 确认是否知情
- 询问：您之前选的是标准直播，但我们后台其实已为您走低延迟线路以保障质量，您知道吗？

## Step 3: 传达升级内容
- 标准直播：费用较低；延迟约5-10秒；适合大班课
- 低延迟直播：延迟约1-2秒；互动更流畅；适合小班课/实操课

## Step 4: 确认前端是否可见
- 询问：您是通过Web控制台、校务系统A，还是SaaS系统B发课？

## Step 5: 检查学员端费用
- 若已设置费用 → 提醒确认低延迟直播也已适用该费用

## Step 6: 企业微信添加
- 若当前号码可添加 → 告知稍后通过企业微信添加

## Step 7: 结束通话
- 若无问题，祝其课程顺利、招生满满，结束通话
```

- [ ] **Step 2: Write the failing parser tests**

```python
# tests/spec/test_section_parser.py
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
    assert "call_flow" in parsed.sections


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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_section_parser.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.spec.section_parser'`

- [ ] **Step 4: Commit the red test fixtures and parser tests**

```bash
git add tests/fixtures/instructions tests/spec/test_section_parser.py
git commit -m "test: add fixtures and failing parser tests for spec compiler upgrade"
```

---

### Task 2: Add InstructionIR models and rule-first section parser

**Files:**
- Create: `app/spec/instruction_ir.py`
- Create: `app/spec/section_parser.py`
- Test: `tests/spec/test_section_parser.py`

- [ ] **Step 1: Implement InstructionIR models**

```python
# app/spec/instruction_ir.py
from pydantic import BaseModel, Field


class IRFlowStep(BaseModel):
    step_id: str
    order: int
    title: str
    raw_text: str


class IRFAQItem(BaseModel):
    faq_id: str
    raw_text: str


class IRConstraintItem(BaseModel):
    constraint_id: str
    raw_text: str
    category: str | None = None


class InstructionIR(BaseModel):
    instruction_id: str
    title: str
    role_definition: str = ""
    task_goal: str = ""
    opening_line: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    flow_steps: list[IRFlowStep] = Field(default_factory=list)
    faq_items: list[IRFAQItem] = Field(default_factory=list)
    constraint_items: list[IRConstraintItem] = Field(default_factory=list)
    fallback_policy: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Implement the rule-first section parser**

```python
# app/spec/section_parser.py
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
        flow_steps = []
        if "身份" in raw_text:
            flow_steps.append(
                IRFlowStep(
                    step_id="identity_check",
                    order=1,
                    title="确认身份",
                    raw_text="需要明确身份确认话术",
                )
            )

        constraint_items = []
        if "不要承诺" in raw_text or "不要保证" in raw_text:
            constraint_items.append(
                IRConstraintItem(
                    constraint_id="constraint_1",
                    raw_text="不能做出超出范围的承诺",
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
        matches = list(pattern.finditer(raw_text))
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
        step_matches = list(re.finditer(r"^\s*##\s*Step\s*(\d+)\s*:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE))
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
```

- [ ] **Step 3: Run parser tests to verify they pass**

Run: `python -m pytest tests/spec/test_section_parser.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/spec/instruction_ir.py app/spec/section_parser.py
git commit -m "feat: add instruction ir and rule-based section parser"
```

---

### Task 3: Add normalizer and fallback policy classification

**Files:**
- Create: `app/spec/normalizer.py`
- Create: `tests/spec/test_normalizer.py`

- [ ] **Step 1: Write the failing normalizer tests**

```python
# tests/spec/test_normalizer.py
from app.spec.instruction_ir import InstructionIR, IRConstraintItem
from app.spec.normalizer import RuleFirstInstructionNormalizer


def test_normalizer_classifies_constraint_categories() -> None:
    ir = InstructionIR(
        instruction_id="instr_1",
        title="demo",
        constraint_items=[
            IRConstraintItem(constraint_id="constraint_1", raw_text="每次回复控制在约30个字以内。"),
            IRConstraintItem(constraint_id="constraint_2", raw_text="不能承诺给商家折扣券或优惠券。"),
        ],
    )

    normalized = RuleFirstInstructionNormalizer().normalize(ir)

    assert normalized.constraint_items[0].category == "length_limit"
    assert normalized.constraint_items[1].category == "forbidden_commitment"


def test_normalizer_extracts_fallback_policy_from_constraints() -> None:
    ir = InstructionIR(
        instruction_id="instr_2",
        title="demo",
        constraint_items=[
            IRConstraintItem(constraint_id="constraint_1", raw_text='如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。"'),
            IRConstraintItem(constraint_id="constraint_2", raw_text="若商家说在开车，礼貌说“那我稍后再打”后挂断。"),
        ],
    )

    normalized = RuleFirstInstructionNormalizer().normalize(ir)

    assert len(normalized.fallback_policy) == 2
    assert "超出职责范围" in normalized.fallback_policy[0]
    assert "开车" in normalized.fallback_policy[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_normalizer.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.spec.normalizer'`

- [ ] **Step 3: Implement a rule-first normalizer with a replaceable interface**

```python
# app/spec/normalizer.py
from typing import Protocol

from app.spec.instruction_ir import InstructionIR


class InstructionNormalizer(Protocol):
    def normalize(self, ir: InstructionIR) -> InstructionIR:
        ...


class RuleFirstInstructionNormalizer:
    def normalize(self, ir: InstructionIR) -> InstructionIR:
        updated_constraints = []
        fallback_policy: list[str] = list(ir.fallback_policy)

        for item in ir.constraint_items:
            category = self._classify(item.raw_text)
            updated_constraints.append(item.model_copy(update={"category": category}))

            if "超出职责范围" in item.raw_text or "稍后再打" in item.raw_text or "挂断" in item.raw_text:
                fallback_policy.append(item.raw_text)

        return ir.model_copy(
            update={
                "constraint_items": updated_constraints,
                "fallback_policy": fallback_policy,
            }
        )

    def _classify(self, text: str) -> str:
        if "字以内" in text or "15-20个字" in text:
            return "length_limit"
        if "不能承诺" in text or "不承诺" in text or "折扣券" in text or "优惠券" in text:
            return "forbidden_commitment"
        if "语气" in text or "口语化" in text:
            return "style_constraint"
        if "超出职责范围" in text or "稍后再打" in text or "挂断" in text:
            return "fallback_policy"
        return "general_constraint"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/spec/test_normalizer.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/spec/normalizer.py tests/spec/test_normalizer.py
git commit -m "feat: add rule-first normalizer for instruction ir"
```

---

### Task 4: Extend EvalSpec and add IR-to-spec mapper

**Files:**
- Modify: `app/domain/eval_spec.py`
- Create: `app/spec/mapper.py`
- Create: `tests/spec/test_mapper.py`

- [ ] **Step 1: Write the failing mapper tests**

```python
# tests/spec/test_mapper.py
from app.spec.instruction_ir import InstructionIR, IRConstraintItem, IRFAQItem, IRFlowStep
from app.spec.mapper import InstructionIRMapper


def test_mapper_builds_enhanced_eval_spec_fields() -> None:
    ir = InstructionIR(
        instruction_id="instr_demo",
        title="demo",
        role_definition="你是客服",
        task_goal="通知升级",
        opening_line="您好，请问您是负责人吗？",
        flow_steps=[IRFlowStep(step_id="step_1", order=1, title="身份确认", raw_text="确认负责人身份")],
        faq_items=[IRFAQItem(faq_id="faq_1", raw_text="低延迟直播适合强互动")],
        constraint_items=[IRConstraintItem(constraint_id="constraint_1", raw_text="每次回复15-20个字", category="length_limit")],
        fallback_policy=["若商家说在开车，礼貌说稍后再打。"],
    )

    spec = InstructionIRMapper().to_eval_spec(ir)

    assert spec.role_definition == "你是客服"
    assert spec.opening_requirements[0] == "您好，请问您是负责人吗？"
    assert spec.flow_steps[0].title == "身份确认"
    assert spec.constraint_items[0].category == "length_limit"
    assert spec.faq_items[0].raw_text == "低延迟直播适合强互动"
    assert spec.required_steps[0].id == "step_1"


def test_mapper_keeps_legacy_rule_fields_for_existing_evaluator() -> None:
    ir = InstructionIR(
        instruction_id="instr_legacy",
        title="demo",
        task_goal="确认收货时间",
        opening_line="您好，请问是张先生吗？",
        flow_steps=[IRFlowStep(step_id="step_1", order=1, title="身份确认", raw_text="确认负责人身份")],
        constraint_items=[IRConstraintItem(constraint_id="constraint_1", raw_text="不能承诺给商家优惠券", category="forbidden_commitment")],
    )

    spec = InstructionIRMapper().to_eval_spec(ir)

    assert any(item.id == "identity_check" for item in spec.required_steps)
    assert spec.required_slots[0].name == "delivery_time"
    assert spec.forbidden_actions[0].id == "forbid_commitment"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_mapper.py -v`

Expected: FAIL because the enhanced EvalSpec fields and mapper do not exist

- [ ] **Step 3: Extend EvalSpec and implement the mapper**

```python
# app/domain/eval_spec.py
from pydantic import BaseModel, Field


class RequiredStep(BaseModel):
    id: str
    name: str
    order: int
    required: bool = True
    evidence_requirement: str


class RequiredSlot(BaseModel):
    name: str
    required: bool = True
    accepted_values: list[str] = Field(default_factory=list)


class ForbiddenAction(BaseModel):
    id: str
    description: str
    severity: str = "fatal"


class SoftDimension(BaseModel):
    id: str
    name: str
    weight: float
    rubric: list[str]


class ScoringPolicy(BaseModel):
    hard_rules_weight: float = 0.7
    soft_rules_weight: float = 0.3
    hard_fail_zero_out: bool = True


class FlowStepSpec(BaseModel):
    step_id: str
    order: int
    title: str
    raw_text: str


class FAQItemSpec(BaseModel):
    faq_id: str
    raw_text: str


class ConstraintItemSpec(BaseModel):
    constraint_id: str
    raw_text: str
    category: str | None = None


class EvalSpec(BaseModel):
    spec_id: str
    instruction_id: str
    version: str
    task_goal: str
    role_definition: str = ""
    opening_requirements: list[str] = Field(default_factory=list)
    flow_steps: list[FlowStepSpec] = Field(default_factory=list)
    faq_items: list[FAQItemSpec] = Field(default_factory=list)
    constraint_items: list[ConstraintItemSpec] = Field(default_factory=list)
    fallback_policy: list[str] = Field(default_factory=list)
    required_steps: list[RequiredStep] = Field(default_factory=list)
    optional_steps: list[RequiredStep] = Field(default_factory=list)
    required_slots: list[RequiredSlot] = Field(default_factory=list)
    forbidden_actions: list[ForbiddenAction] = Field(default_factory=list)
    completion_conditions: list[str] = Field(default_factory=list)
    hard_fail_conditions: list[str] = Field(default_factory=list)
    soft_dimensions: list[SoftDimension] = Field(default_factory=list)
    scoring_policy: ScoringPolicy = Field(default_factory=ScoringPolicy)
    review_status: str = "draft"
```

```python
# app/spec/mapper.py
from uuid import uuid4

from app.domain.eval_spec import (
    ConstraintItemSpec,
    EvalSpec,
    FAQItemSpec,
    FlowStepSpec,
    ForbiddenAction,
    RequiredStep,
    RequiredSlot,
    SoftDimension,
)
from app.spec.instruction_ir import InstructionIR


class InstructionIRMapper:
    def to_eval_spec(self, ir: InstructionIR) -> EvalSpec:
        required_steps = [
            RequiredStep(
                id=step.step_id,
                name=step.title,
                order=step.order,
                required=True,
                evidence_requirement=step.raw_text,
            )
            for step in ir.flow_steps
        ]

        forbidden_actions = []
        if any(item.category == "forbidden_commitment" for item in ir.constraint_items):
            forbidden_actions.append(
                ForbiddenAction(
                    id="forbid_commitment",
                    description="禁止做出超出约束范围的承诺",
                )
            )

        required_steps = [
            RequiredStep(
                id=step.step_id,
                name=step.title,
                order=step.order,
                required=True,
                evidence_requirement=step.raw_text,
            )
            for step in ir.flow_steps
        ]
        if ir.opening_line and ("请问是" in ir.opening_line or "负责人吗" in ir.opening_line):
            required_steps.insert(
                0,
                RequiredStep(
                    id="identity_check",
                    name="确认身份",
                    order=0,
                    required=True,
                    evidence_requirement=ir.opening_line,
                ),
            )

        required_slots = []
        combined_text = "\n".join([ir.task_goal, ir.opening_line, *(step.raw_text for step in ir.flow_steps)])
        if "时间" in combined_text:
            required_slots.append(
                RequiredSlot(
                    name="delivery_time",
                    required=True,
                    accepted_values=["今天", "明天", "上午", "下午"],
                )
            )

        return EvalSpec(
            spec_id=f"spec_{uuid4().hex[:8]}",
            instruction_id=ir.instruction_id,
            version="v2",
            task_goal=ir.task_goal or ir.title,
            role_definition=ir.role_definition,
            opening_requirements=[ir.opening_line] if ir.opening_line else [],
            flow_steps=[FlowStepSpec(**step.model_dump()) for step in ir.flow_steps],
            faq_items=[FAQItemSpec(**item.model_dump()) for item in ir.faq_items],
            constraint_items=[ConstraintItemSpec(**item.model_dump()) for item in ir.constraint_items],
            fallback_policy=ir.fallback_policy,
            required_steps=required_steps,
            required_slots=required_slots,
            forbidden_actions=forbidden_actions,
            completion_conditions=["完成关键流程步骤", "符合结束要求"],
            hard_fail_conditions=["触发禁止承诺"],
            soft_dimensions=[
                SoftDimension(
                    id="explanation_quality",
                    name="解释充分性",
                    weight=0.5,
                    rubric=["说明来电目的", "解释追问原因"],
                ),
                SoftDimension(
                    id="task_focus",
                    name="任务聚焦度",
                    weight=0.5,
                    rubric=["不跑题", "保持任务推进"],
                ),
            ],
            review_status="draft",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/spec/test_mapper.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/domain/eval_spec.py app/spec/mapper.py tests/spec/test_mapper.py
git commit -m "feat: extend eval spec and add instruction ir mapper"
```

---

### Task 5: Refactor compiler orchestration and API regression

**Files:**
- Modify: `app/spec/compiler.py`
- Modify: `tests/api/test_specs_api.py`
- Create: `tests/spec/test_compiler.py`

- [ ] **Step 1: Write the failing compiler regression tests**

```python
# tests/spec/test_compiler.py
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
```

```python
# append to tests/api/test_specs_api.py
def test_compile_spec_returns_enhanced_fields() -> None:
    client = TestClient(app)

    response = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_delivery_time",
            "name": "确认送达时间",
            "raw_text": "# Role\n你是骑手站长\n\n# Task\n确认配送\n\n# Opening Line\n您好，请问是张先生吗？\n\n# Call Flow\n1. 确认身份\n2. 确认是否可配送\n\n# Constraints\n- 每次回复控制在约30个字以内。\n- 如被问及超出职责范围的问题，回复：我向同事确认后再回电给你。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role_definition"] == "你是骑手站长"
    assert len(data["flow_steps"]) == 2
    assert data["opening_requirements"][0] == "您好，请问是张先生吗？"
    assert data["constraint_items"][0]["category"] == "length_limit"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/spec/test_compiler.py tests/api/test_specs_api.py -v`

Expected: FAIL because `SpecCompiler` still uses the legacy keyword-only path and没有增强字段/兼容回填

- [ ] **Step 3: Refactor compiler to orchestrate parser → normalizer → mapper**

```python
# app/spec/compiler.py
from app.domain.task_instruction import TaskInstruction
from app.spec.mapper import InstructionIRMapper
from app.spec.normalizer import RuleFirstInstructionNormalizer
from app.spec.section_parser import InstructionSectionParser


class SpecCompiler:
    def __init__(
        self,
        parser: InstructionSectionParser | None = None,
        normalizer: RuleFirstInstructionNormalizer | None = None,
        mapper: InstructionIRMapper | None = None,
    ) -> None:
        self.parser = parser or InstructionSectionParser()
        self.normalizer = normalizer or RuleFirstInstructionNormalizer()
        self.mapper = mapper or InstructionIRMapper()

    def compile(self, instruction: TaskInstruction):
        ir = self.parser.parse(
            instruction_id=instruction.instruction_id,
            title=instruction.name,
            raw_text=instruction.raw_text,
        )
        if not ir.sections:
            return self._compile_legacy_keyword_spec(instruction)
        normalized = self.normalizer.normalize(ir)
        return self.mapper.to_eval_spec(normalized)

    def _compile_legacy_keyword_spec(self, instruction: TaskInstruction):
        ir = self.parser.parse_legacy_keywords(
            instruction_id=instruction.instruction_id,
            title=instruction.name,
            raw_text=instruction.raw_text,
        )
        normalized = self.normalizer.normalize(ir)
        return self.mapper.to_eval_spec(normalized)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/spec/test_compiler.py tests/api/test_specs_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/spec/compiler.py tests/spec/test_compiler.py tests/api/test_specs_api.py
git commit -m "feat: refactor spec compiler to use ir pipeline"
```

---

### Task 6: Run full regression and inspect enhanced spec output

**Files:**
- Modify: `tests/spec/test_compiler.py`

- [ ] **Step 1: Add a final regression that checks fallback and forbidden mapping together**

```python
# append to tests/spec/test_compiler.py
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
```

- [ ] **Step 2: Run the full Python regression suite**

Run: `python -m pytest -v`

Expected: PASS with all previous evaluator and demo tests still green

- [ ] **Step 3: Print one compiled enhanced spec for manual inspection**

Run:

```powershell
@'
from pathlib import Path
from app.domain.task_instruction import TaskInstruction
from app.spec.compiler import SpecCompiler
import json

raw_text = Path("tests/fixtures/instructions/rider_station_task.md").read_text(encoding="utf-8")
spec = SpecCompiler().compile(
    TaskInstruction(
        instruction_id="instr_rider",
        name="飞毛腿骑手外呼任务",
        raw_text=raw_text,
    )
)
print(json.dumps(spec.model_dump(), ensure_ascii=False, indent=2))
'@ | python -X utf8 -
```

Expected: 输出中应包含 `role_definition`、`opening_requirements`、`flow_steps`、`faq_items`、`constraint_items`、`fallback_policy`

- [ ] **Step 4: Commit**

```bash
git add tests/spec/test_compiler.py
git commit -m "test: add regression coverage for enhanced spec compiler"
```

---

## Self-Review Checklist

- Spec coverage:
  - `InstructionIR`：Task 2
  - 规则切 section：Task 2
  - 约束分类与 fallback：Task 3
  - 增强版 `EvalSpec`：Task 4
  - 编译 orchestration：Task 5
  - 样例回归：Task 1, Task 5, Task 6
- Placeholder scan: 本计划未使用任何占位符式描述。
- Type consistency:
  - `InstructionIR`, `IRFlowStep`, `IRFAQItem`, `IRConstraintItem` 定义在 `instruction_ir.py`，后续 parser / normalizer / mapper 都复用这些名称。
  - `FlowStepSpec`, `FAQItemSpec`, `ConstraintItemSpec` 定义在 `eval_spec.py`，并由 `mapper.py` 统一构造。
  - `SpecCompiler.compile()` 在最终阶段始终返回增强版 `EvalSpec`，`routes_specs.py` 无需改签名即可复用。
