# User Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有评估系统补齐第一版用户模拟器，支持在线闭环主链路、离线调试模式、规则控制状态流转、模板优先自然回复、Mock/HTTP 模型适配和自动评测结果输出。

**Architecture:** 用户模拟器按“场景生成 → 用户策略 → 回复生成 → 模型适配 → 回复分析 → 对话驱动 → 复用 evaluator 自动评分”组织。第一版默认提供 `MockModelAdapter` 完整闭环，并实现一个通用 `HttpModelAdapter` 契约；所有组件围绕 `SimulationScenario`、`UserProfile`、`ConversationState` 与 `SimulationRunResult` 这些领域对象协作。

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, httpx

---

## File Structure

### Runtime files

- `app/domain/simulation.py`：定义模拟器领域对象，如 `UserProfile`、`SimulationScenario`、`UserIntent`、`ModelReplySignal`、`SimulationRunResult`。
- `app/simulators/__init__.py`
- `app/simulators/scenario_builder.py`：从 `EvalSpec` + 配置生成场景。
- `app/simulators/profiles.py`：预置用户画像仓库。
- `app/simulators/policy_engine.py`：状态机和下一轮用户策略。
- `app/simulators/response_generator.py`：模板优先的自然语言回复生成。
- `app/simulators/model_adapter.py`：定义 `ModelAdapter` 协议、`MockModelAdapter`、`HttpModelAdapter`。
- `app/simulators/reply_analyzer.py`：分析被测模型回复，产出 `ModelReplySignal`。
- `app/simulators/conversation_runner.py`：驱动完整闭环并回调现有 evaluator。
- `app/api/routes_simulation.py`：从 501 占位升级为真实可运行接口。

### Tests

- `tests/simulators/test_domain_models.py`
- `tests/simulators/test_scenario_builder.py`
- `tests/simulators/test_policy_engine.py`
- `tests/simulators/test_response_generator.py`
- `tests/simulators/test_model_adapter.py`
- `tests/simulators/test_reply_analyzer.py`
- `tests/simulators/test_conversation_runner.py`
- `tests/api/test_simulation_api.py`

---

### Task 1: Add simulation domain models and failing API contract tests

**Files:**
- Create: `app/domain/simulation.py`
- Create: `tests/simulators/test_domain_models.py`
- Create: `tests/api/test_simulation_api.py`

- [ ] **Step 1: Write the failing domain model tests**

```python
# tests/simulators/test_domain_models.py
from app.domain.simulation import (
    ConversationState,
    ModelReplySignal,
    SimulationRunResult,
    SimulationScenario,
    UserIntent,
    UserProfile,
)


def test_simulation_scenario_defaults() -> None:
    scenario = SimulationScenario(
        scenario_id="scenario_1",
        spec_id="spec_1",
        profile_id="cooperative",
        primary_branch="cooperative",
        max_turns=8,
        termination_policy="task_complete_or_user_exit",
    )

    assert scenario.primary_branch == "cooperative"
    assert scenario.coverage_mode == "primary"


def test_user_intent_and_reply_signal_models() -> None:
    intent = UserIntent(action="ask_why", state="questioning", target_step_id="step_2")
    signal = ModelReplySignal(
        answered_question=True,
        explained_reason=True,
        followed_flow_step="step_2",
        triggered_forbidden_action=False,
        ignored_user_state=False,
    )

    assert intent.action == "ask_why"
    assert signal.followed_flow_step == "step_2"


def test_simulation_run_result_contains_trace_and_evaluation() -> None:
    result = SimulationRunResult(
        simulation_id="sim_1",
        scenario_id="scenario_1",
        profile_id="busy",
        termination_reason="user_busy_end",
        state_trace=["init", "busy", "terminated"],
        turns=[],
        evaluation={"overall_score": 72},
    )

    assert result.state_trace[-1] == "terminated"
    assert result.evaluation["overall_score"] == 72
```

- [ ] **Step 2: Write the failing simulation API test**

```python
# tests/api/test_simulation_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_simulation_api_runs_mock_closed_loop() -> None:
    client = TestClient(app)

    response = client.post(
        "/simulations/run",
        json={
            "spec": {
                "spec_id": "spec_sim_1",
                "instruction_id": "instr_sim_1",
                "version": "v2",
                "task_goal": "确认收货时间",
                "role_definition": "你是站长",
                "opening_requirements": ["您好，请问是张先生吗？"],
                "flow_steps": [
                    {
                        "step_id": "step_1",
                        "order": 1,
                        "title": "身份确认",
                        "raw_text": "确认身份",
                    },
                    {
                        "step_id": "step_2",
                        "order": 2,
                        "title": "确认配送时间",
                        "raw_text": "确认收货时间",
                    },
                ],
                "faq_items": [],
                "constraint_items": [],
                "fallback_policy": [],
                "required_steps": [
                    {
                        "id": "identity_check",
                        "name": "确认身份",
                        "order": 0,
                        "required": True,
                        "evidence_requirement": "您好，请问是张先生吗？",
                    }
                ],
                "required_slots": [
                    {
                        "name": "delivery_time",
                        "required": True,
                        "accepted_values": ["今天", "明天", "下午"],
                    }
                ],
                "forbidden_actions": [],
                "completion_conditions": ["完成关键流程步骤", "符合结束要求"],
                "hard_fail_conditions": [],
                "soft_dimensions": [
                    {
                        "id": "task_focus",
                        "name": "任务聚焦度",
                        "weight": 1.0,
                        "rubric": ["保持任务推进"],
                    }
                ],
            },
            "adapter": {"type": "mock"},
            "simulation": {
                "profile_id": "cooperative",
                "primary_branch": "cooperative",
                "max_turns": 6,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] == "cooperative"
    assert body["termination_reason"] in {"task_complete", "max_turns"}
    assert "evaluation" in body
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/simulators/test_domain_models.py tests/api/test_simulation_api.py -v`

Expected: FAIL because `app.domain.simulation` does not exist and `/simulations/run` is still 501

- [ ] **Step 4: Implement the minimal domain models**

```python
# app/domain/simulation.py
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    profile_id: str
    name: str
    cooperation_level: float
    patience_level: float
    interruption_probability: float = 0.0
    question_probability: float = 0.0
    reject_probability: float = 0.0
    style_prompt: str = ""


class SimulationScenario(BaseModel):
    scenario_id: str
    spec_id: str
    profile_id: str
    primary_branch: str
    secondary_branch: str | None = None
    max_turns: int
    termination_policy: str
    coverage_mode: str = "primary"


class ConversationState(BaseModel):
    current_state: str = "init"
    turn_index: int = 0
    completed_steps: list[str] = Field(default_factory=list)


class UserIntent(BaseModel):
    action: str
    state: str
    target_step_id: str | None = None
    note: str = ""


class ModelReplySignal(BaseModel):
    answered_question: bool
    explained_reason: bool
    followed_flow_step: str | None = None
    triggered_forbidden_action: bool = False
    ignored_user_state: bool = False


class SimulationRunResult(BaseModel):
    simulation_id: str
    scenario_id: str
    profile_id: str
    termination_reason: str
    state_trace: list[str] = Field(default_factory=list)
    turns: list[dict] = Field(default_factory=list)
    evaluation: dict = Field(default_factory=dict)
```

- [ ] **Step 5: Run the domain model tests to verify partial green**

Run: `python -m pytest tests/simulators/test_domain_models.py -v`

Expected: PASS and `tests/api/test_simulation_api.py` still FAIL on 501

- [ ] **Step 6: Commit**

```bash
git add app/domain/simulation.py tests/simulators/test_domain_models.py tests/api/test_simulation_api.py
git commit -m "feat: add user simulator domain models and api red test"
```

---

### Task 2: Implement profile registry and scenario builder

**Files:**
- Create: `app/simulators/__init__.py`
- Create: `app/simulators/profiles.py`
- Create: `app/simulators/scenario_builder.py`
- Create: `tests/simulators/test_scenario_builder.py`

- [ ] **Step 1: Write the failing scenario builder tests**

```python
# tests/simulators/test_scenario_builder.py
from app.domain.eval_spec import EvalSpec
from app.simulators.profiles import DEFAULT_PROFILES
from app.simulators.scenario_builder import ScenarioBuilder


def test_default_profiles_cover_required_branches() -> None:
    profile_ids = {profile.profile_id for profile in DEFAULT_PROFILES}

    assert {"cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning"} <= profile_ids


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/simulators/test_scenario_builder.py -v`

Expected: FAIL because `app.simulators.profiles` and `app.simulators.scenario_builder` do not exist

- [ ] **Step 3: Implement profile registry and scenario builder**

```python
# app/simulators/profiles.py
from app.domain.simulation import UserProfile

DEFAULT_PROFILES = [
    UserProfile(profile_id="cooperative", name="配合型", cooperation_level=0.9, patience_level=0.8),
    UserProfile(profile_id="hesitant", name="犹豫型", cooperation_level=0.5, patience_level=0.7, question_probability=0.6),
    UserProfile(profile_id="rejecting", name="拒绝型", cooperation_level=0.2, patience_level=0.4, reject_probability=0.8),
    UserProfile(profile_id="busy", name="忙碌型", cooperation_level=0.4, patience_level=0.2),
    UserProfile(profile_id="interrupting", name="打断型", cooperation_level=0.5, patience_level=0.4, interruption_probability=0.8),
    UserProfile(profile_id="questioning", name="追问型", cooperation_level=0.6, patience_level=0.7, question_probability=0.9),
]


def get_profile(profile_id: str) -> UserProfile:
    for profile in DEFAULT_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(profile_id)
```

```python
# app/simulators/scenario_builder.py
from uuid import uuid4

from app.domain.eval_spec import EvalSpec
from app.domain.simulation import SimulationScenario


class ScenarioBuilder:
    def build(
        self,
        spec: EvalSpec,
        profile_id: str,
        primary_branch: str,
        max_turns: int = 8,
        secondary_branch: str | None = None,
    ) -> SimulationScenario:
        return SimulationScenario(
            scenario_id=f"scenario_{uuid4().hex[:8]}",
            spec_id=spec.spec_id,
            profile_id=profile_id,
            primary_branch=primary_branch,
            secondary_branch=secondary_branch,
            max_turns=max_turns,
            termination_policy="task_complete_or_user_exit",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/simulators/test_scenario_builder.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/simulators/__init__.py app/simulators/profiles.py app/simulators/scenario_builder.py tests/simulators/test_scenario_builder.py
git commit -m "feat: add user profiles and scenario builder"
```

---

### Task 3: Implement policy engine and response generator

**Files:**
- Create: `app/simulators/policy_engine.py`
- Create: `app/simulators/response_generator.py`
- Create: `tests/simulators/test_policy_engine.py`
- Create: `tests/simulators/test_response_generator.py`

- [ ] **Step 1: Write the failing policy/response tests**

```python
# tests/simulators/test_policy_engine.py
from app.domain.simulation import ConversationState, ModelReplySignal
from app.simulators.policy_engine import UserPolicyEngine


def test_policy_engine_returns_busy_intent_for_busy_branch() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="init", turn_index=0)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    intent = engine.next_intent(primary_branch="busy", state=state, signal=signal)

    assert intent.state == "busy"
    assert intent.action == "say_busy"


def test_policy_engine_returns_questioning_intent_when_reason_missing() -> None:
    engine = UserPolicyEngine()
    state = ConversationState(current_state="listening", turn_index=1)
    signal = ModelReplySignal(answered_question=False, explained_reason=False)

    intent = engine.next_intent(primary_branch="questioning", state=state, signal=signal)

    assert intent.state == "questioning"
    assert intent.action == "ask_why"
```

```python
# tests/simulators/test_response_generator.py
from app.domain.simulation import UserIntent, UserProfile
from app.simulators.response_generator import TemplateFirstResponseGenerator


def test_response_generator_emits_busy_phrase() -> None:
    generator = TemplateFirstResponseGenerator()
    profile = UserProfile(profile_id="busy", name="忙碌型", cooperation_level=0.4, patience_level=0.2)

    reply = generator.render(UserIntent(action="say_busy", state="busy"), profile)

    assert "忙" in reply or "稍后" in reply


def test_response_generator_emits_question_phrase() -> None:
    generator = TemplateFirstResponseGenerator()
    profile = UserProfile(profile_id="questioning", name="追问型", cooperation_level=0.6, patience_level=0.7)

    reply = generator.render(UserIntent(action="ask_why", state="questioning"), profile)

    assert "为什么" in reply or "啥意思" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/simulators/test_policy_engine.py tests/simulators/test_response_generator.py -v`

Expected: FAIL because `policy_engine.py` and `response_generator.py` do not exist

- [ ] **Step 3: Implement a rules-only state engine and template-first generator**

```python
# app/simulators/policy_engine.py
from app.domain.simulation import ConversationState, ModelReplySignal, UserIntent


class UserPolicyEngine:
    def next_intent(self, primary_branch: str, state: ConversationState, signal: ModelReplySignal) -> UserIntent:
        if primary_branch == "busy":
            return UserIntent(action="say_busy", state="busy")
        if primary_branch == "rejecting":
            return UserIntent(action="refuse", state="rejecting")
        if primary_branch == "interrupting":
            return UserIntent(action="interrupt", state="interrupting")
        if primary_branch == "questioning" and not signal.explained_reason:
            return UserIntent(action="ask_why", state="questioning")
        if primary_branch == "hesitant":
            return UserIntent(action="say_unsure", state="hesitant")
        return UserIntent(action="answer_slot", state="cooperative")
```

```python
# app/simulators/response_generator.py
from app.domain.simulation import UserIntent, UserProfile


class TemplateFirstResponseGenerator:
    def render(self, intent: UserIntent, profile: UserProfile) -> str:
        if intent.action == "say_busy":
            return "我现在有点忙，能快点说吗？"
        if intent.action == "ask_why":
            return "为什么必须这样？"
        if intent.action == "refuse":
            return "这个我不想做。"
        if intent.action == "interrupt":
            return "等一下，你先说重点。"
        if intent.action == "say_unsure":
            return "我现在还不太确定。"
        return "可以，你继续说。"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/simulators/test_policy_engine.py tests/simulators/test_response_generator.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/simulators/policy_engine.py app/simulators/response_generator.py tests/simulators/test_policy_engine.py tests/simulators/test_response_generator.py
git commit -m "feat: add simulator policy engine and response generator"
```

---

### Task 4: Implement model adapters and reply analyzer

**Files:**
- Create: `app/simulators/model_adapter.py`
- Create: `app/simulators/reply_analyzer.py`
- Create: `tests/simulators/test_model_adapter.py`
- Create: `tests/simulators/test_reply_analyzer.py`

- [ ] **Step 1: Write the failing adapter/analyzer tests**

```python
# tests/simulators/test_model_adapter.py
import asyncio

from app.simulators.model_adapter import HttpModelAdapter, MockModelAdapter


def test_mock_model_adapter_returns_scripted_reply() -> None:
    adapter = MockModelAdapter()

    asyncio.run(adapter.start_session({}))
    reply = asyncio.run(adapter.send_user_message("您好"))
    asyncio.run(adapter.end_session())

    assert "您好" in reply or "请问" in reply


def test_http_model_adapter_builds_request_payload() -> None:
    adapter = HttpModelAdapter(endpoint="http://localhost/mock")
    payload = adapter.build_payload(session_id="session_1", history=[{"speaker": "user", "text": "你好"}])

    assert payload["session_id"] == "session_1"
    assert payload["history"][0]["speaker"] == "user"
```

```python
# tests/simulators/test_reply_analyzer.py
from app.simulators.reply_analyzer import RuleBasedReplyAnalyzer


def test_reply_analyzer_marks_reason_explained() -> None:
    signal = RuleBasedReplyAnalyzer().analyze("来电是为了确认收货时间，所以想确认您明天下午是否在家。")

    assert signal.explained_reason is True


def test_reply_analyzer_marks_forbidden_promise() -> None:
    signal = RuleBasedReplyAnalyzer().analyze("您放心，一定送达。")

    assert signal.triggered_forbidden_action is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/simulators/test_model_adapter.py tests/simulators/test_reply_analyzer.py -v`

Expected: FAIL because adapter and analyzer files do not exist

- [ ] **Step 3: Implement adapters and rule-based analyzer**

```python
# app/simulators/model_adapter.py
import httpx
from typing import Protocol
from uuid import uuid4


class ModelAdapter(Protocol):
    async def start_session(self, config: dict) -> str:
        ...

    async def send_user_message(self, message: str) -> str:
        ...

    async def end_session(self) -> None:
        ...


class MockModelAdapter:
    def __init__(self) -> None:
        self.session_id = ""
        self.history: list[dict] = []

    async def start_session(self, config: dict) -> str:
        self.session_id = f"mock_{uuid4().hex[:8]}"
        self.history = []
        return self.session_id

    async def send_user_message(self, message: str) -> str:
        self.history.append({"speaker": "user", "text": message})
        if "为什么" in message:
            reply = "因为这次主要是确认安排，避免耽误配送。"
        elif "忙" in message:
            reply = "我就简短说一下，主要想确认您明天下午是否方便。"
        else:
            reply = "您好，请问您明天下午方便收货吗？"
        self.history.append({"speaker": "assistant", "text": reply})
        return reply

    async def end_session(self) -> None:
        self.history = []


class HttpModelAdapter:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.session_id = ""
        self.history: list[dict] = []

    def build_payload(self, session_id: str, history: list[dict]) -> dict:
        return {"session_id": session_id, "history": history}

    async def start_session(self, config: dict) -> str:
        self.session_id = config.get("session_id", f"http_{uuid4().hex[:8]}")
        self.history = []
        return self.session_id

    async def send_user_message(self, message: str) -> str:
        self.history.append({"speaker": "user", "text": message})
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.endpoint, json=self.build_payload(self.session_id, self.history))
        response.raise_for_status()
        data = response.json()
        reply = data["reply"]
        self.history.append({"speaker": "assistant", "text": reply})
        return reply

    async def end_session(self) -> None:
        self.history = []
```

```python
# app/simulators/reply_analyzer.py
from app.domain.simulation import ModelReplySignal


class RuleBasedReplyAnalyzer:
    def analyze(self, reply: str) -> ModelReplySignal:
        return ModelReplySignal(
            answered_question="？" not in reply,
            explained_reason=("因为" in reply) or ("来电是为了" in reply) or ("主要是" in reply),
            followed_flow_step="step_2" if "收货时间" in reply or "方便收货" in reply else None,
            triggered_forbidden_action=("一定送达" in reply) or ("保证送达" in reply),
            ignored_user_state=("继续说一下" in reply),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/simulators/test_model_adapter.py tests/simulators/test_reply_analyzer.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/simulators/model_adapter.py app/simulators/reply_analyzer.py tests/simulators/test_model_adapter.py tests/simulators/test_reply_analyzer.py
git commit -m "feat: add simulator model adapters and reply analyzer"
```

---

### Task 5: Implement conversation runner and real `/simulations/run`

**Files:**
- Create: `app/simulators/conversation_runner.py`
- Modify: `app/api/routes_simulation.py`
- Create: `tests/simulators/test_conversation_runner.py`

- [ ] **Step 1: Write the failing runner tests**

```python
# tests/simulators/test_conversation_runner.py
import asyncio

from app.domain.eval_spec import EvalSpec, RequiredSlot, RequiredStep, SoftDimension
from app.simulators.conversation_runner import ConversationRunner


def build_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_sim",
        instruction_id="instr_sim",
        version="v2",
        task_goal="确认收货时间",
        role_definition="你是站长",
        opening_requirements=["您好，请问是张先生吗？"],
        flow_steps=[],
        faq_items=[],
        constraint_items=[],
        fallback_policy=[],
        required_steps=[
            RequiredStep(id="identity_check", name="确认身份", order=0, required=True, evidence_requirement="您好，请问是张先生吗？")
        ],
        required_slots=[
            RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天", "下午"])
        ],
        soft_dimensions=[
            SoftDimension(id="task_focus", name="任务聚焦度", weight=1.0, rubric=["保持任务推进"])
        ],
    )


def test_conversation_runner_returns_turns_trace_and_evaluation() -> None:
    runner = ConversationRunner()

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="cooperative",
            primary_branch="cooperative",
            max_turns=4,
        )
    )

    assert result.profile_id == "cooperative"
    assert result.turns
    assert result.state_trace[-1] == "terminated"
    assert "overall_score" in result.evaluation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/simulators/test_conversation_runner.py tests/api/test_simulation_api.py -v`

Expected: FAIL because `ConversationRunner` is missing and `/simulations/run` is still 501

- [ ] **Step 3: Implement the runner and simulation API**

```python
# app/simulators/conversation_runner.py
import asyncio
from uuid import uuid4

from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec
from app.domain.simulation import ConversationState, SimulationRunResult
from app.pipeline.evaluation_runner import EvaluationRunner
from app.simulators.model_adapter import HttpModelAdapter, MockModelAdapter
from app.simulators.policy_engine import UserPolicyEngine
from app.simulators.profiles import get_profile
from app.simulators.reply_analyzer import RuleBasedReplyAnalyzer
from app.simulators.response_generator import TemplateFirstResponseGenerator
from app.simulators.scenario_builder import ScenarioBuilder


class ConversationRunner:
    def __init__(self) -> None:
        self.scenario_builder = ScenarioBuilder()
        self.policy_engine = UserPolicyEngine()
        self.response_generator = TemplateFirstResponseGenerator()
        self.reply_analyzer = RuleBasedReplyAnalyzer()

    async def run_mock(self, spec: EvalSpec, profile_id: str, primary_branch: str, max_turns: int = 8) -> SimulationRunResult:
        adapter = MockModelAdapter()
        return await self._run(adapter, spec, profile_id, primary_branch, max_turns)

    async def run_http(self, spec: EvalSpec, profile_id: str, primary_branch: str, endpoint: str, max_turns: int = 8) -> SimulationRunResult:
        adapter = HttpModelAdapter(endpoint=endpoint)
        return await self._run(adapter, spec, profile_id, primary_branch, max_turns)

    async def _run(self, adapter, spec: EvalSpec, profile_id: str, primary_branch: str, max_turns: int) -> SimulationRunResult:
        scenario = self.scenario_builder.build(spec, profile_id=profile_id, primary_branch=primary_branch, max_turns=max_turns)
        profile = get_profile(profile_id)
        state = ConversationState(current_state="init", turn_index=0)
        state_trace = [state.current_state]
        turns: list[dict] = []
        signal = self.reply_analyzer.analyze("")

        await adapter.start_session({})

        for turn_index in range(max_turns):
            intent = self.policy_engine.next_intent(primary_branch=primary_branch, state=state, signal=signal)
            user_text = self.response_generator.render(intent, profile)
            model_reply = await adapter.send_user_message(user_text)
            turns.append({"turn_id": len(turns) + 1, "speaker": "user", "text": user_text})
            turns.append({"turn_id": len(turns) + 1, "speaker": "agent", "text": model_reply})

            signal = self.reply_analyzer.analyze(model_reply)
            state = ConversationState(current_state="terminated" if turn_index == max_turns - 1 else intent.state, turn_index=turn_index + 1)
            state_trace.append(state.current_state)

            if intent.state in {"busy", "rejecting"}:
                state_trace.append("terminated")
                break

        await adapter.end_session()

        conversation = Conversation(
            conversation_id=f"simulation_{uuid4().hex[:8]}",
            instruction_id=spec.instruction_id,
            source="simulation",
            turns=[Turn(**turn) for turn in turns],
        )
        evaluation = EvaluationRunner().run(spec, conversation).model_dump()

        return SimulationRunResult(
            simulation_id=f"sim_{uuid4().hex[:8]}",
            scenario_id=scenario.scenario_id,
            profile_id=profile_id,
            termination_reason="user_busy_end" if "busy" in state_trace else "task_complete",
            state_trace=state_trace if state_trace[-1] == "terminated" else [*state_trace, "terminated"],
            turns=turns,
            evaluation=evaluation,
        )
```

```python
# app/api/routes_simulation.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.domain.eval_spec import EvalSpec
from app.simulators.conversation_runner import ConversationRunner


class AdapterConfig(BaseModel):
    type: str = "mock"
    endpoint: str | None = None


class SimulationConfig(BaseModel):
    profile_id: str = "cooperative"
    primary_branch: str = "cooperative"
    max_turns: int = 8


class SimulationRequest(BaseModel):
    spec: EvalSpec
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    model_config = ConfigDict(populate_by_name=True)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run")
async def run_simulation(payload: SimulationRequest) -> dict:
    runner = ConversationRunner()

    if payload.adapter.type == "mock":
        result = await runner.run_mock(
            spec=payload.spec,
            profile_id=payload.simulation.profile_id,
            primary_branch=payload.simulation.primary_branch,
            max_turns=payload.simulation.max_turns,
        )
        return result.model_dump()

    if payload.adapter.type == "http" and payload.adapter.endpoint:
        result = await runner.run_http(
            spec=payload.spec,
            profile_id=payload.simulation.profile_id,
            primary_branch=payload.simulation.primary_branch,
            endpoint=payload.adapter.endpoint,
            max_turns=payload.simulation.max_turns,
        )
        return result.model_dump()

    raise HTTPException(status_code=400, detail="unsupported simulation adapter")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/simulators/test_conversation_runner.py tests/api/test_simulation_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/simulators/conversation_runner.py app/api/routes_simulation.py tests/simulators/test_conversation_runner.py
git commit -m "feat: add simulation conversation runner and api"
```

---

### Task 6: Full regression, branch coverage smoke checks, and manual simulation output check

**Files:**
- Modify: `tests/simulators/test_conversation_runner.py`

- [ ] **Step 1: Add branch-coverage regression tests**

```python
# append to tests/simulators/test_conversation_runner.py
def test_conversation_runner_handles_busy_branch() -> None:
    runner = ConversationRunner()

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="busy",
            primary_branch="busy",
            max_turns=4,
        )
    )

    assert "busy" in result.state_trace
    assert result.termination_reason == "user_busy_end"


def test_conversation_runner_handles_questioning_branch() -> None:
    runner = ConversationRunner()

    result = asyncio.run(
        runner.run_mock(
            spec=build_spec(),
            profile_id="questioning",
            primary_branch="questioning",
            max_turns=4,
        )
    )

    assert "questioning" in result.state_trace
    assert "overall_score" in result.evaluation
```

- [ ] **Step 2: Run the full Python regression suite**

Run: `python -m pytest -v`

Expected: PASS with previous evaluator, demo, and compiler tests still green

- [ ] **Step 3: Print a mock simulation result for manual inspection**

Run:

```powershell
@'
import asyncio
import json
from app.domain.eval_spec import EvalSpec, RequiredSlot, RequiredStep, SoftDimension
from app.simulators.conversation_runner import ConversationRunner

spec = EvalSpec(
    spec_id="spec_manual",
    instruction_id="instr_manual",
    version="v2",
    task_goal="确认收货时间",
    role_definition="你是站长",
    opening_requirements=["您好，请问是张先生吗？"],
    flow_steps=[],
    faq_items=[],
    constraint_items=[],
    fallback_policy=[],
    required_steps=[
        RequiredStep(id="identity_check", name="确认身份", order=0, required=True, evidence_requirement="您好，请问是张先生吗？")
    ],
    required_slots=[
        RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天", "下午"])
    ],
    soft_dimensions=[
        SoftDimension(id="task_focus", name="任务聚焦度", weight=1.0, rubric=["保持任务推进"])
    ],
)

result = asyncio.run(
    ConversationRunner().run_mock(
        spec=spec,
        profile_id="questioning",
        primary_branch="questioning",
        max_turns=4,
    )
)
print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
'@ | python -X utf8 -
```

Expected: 输出中包含 `state_trace`、`turns`、`termination_reason`、`evaluation`

- [ ] **Step 4: Commit**

```bash
git add tests/simulators/test_conversation_runner.py
git commit -m "test: add regression coverage for user simulator"
```

---

## Self-Review Checklist

- Spec coverage:
  - 模型适配层：Task 4
  - 场景生成器：Task 2
  - 用户画像：Task 2
  - 状态机 / 策略引擎：Task 3
  - 回复生成器：Task 3
  - Conversation Runner：Task 5
  - `/simulations/run` 真正可运行：Task 5
  - 复用 evaluator 自动评分：Task 5, Task 6
- Placeholder scan: 本计划未使用任何占位符式描述。
- Type consistency:
  - `SimulationScenario`、`UserProfile`、`ConversationState`、`UserIntent`、`ModelReplySignal`、`SimulationRunResult` 均定义在 `app/domain/simulation.py`，后续组件直接复用。
  - `ScenarioBuilder.build()`、`UserPolicyEngine.next_intent()`、`TemplateFirstResponseGenerator.render()`、`RuleBasedReplyAnalyzer.analyze()`、`ConversationRunner.run_mock()` / `run_http()` 是整个模拟链路的固定接口。
  - `/simulations/run` 通过 `SimulationRequest` 统一接收 `spec`、`adapter`、`simulation` 三段配置，避免后续字段命名漂移。

