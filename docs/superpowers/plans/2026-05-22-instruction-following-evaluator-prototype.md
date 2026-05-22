# Instruction Following Evaluator Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零实现一个“履约数字人外呼指令遵循自动评估”原型，支持任务指令编译为 `EvalSpec`、离线单条/批量评估、规则 + LLM Judge 混合打分、证据链输出、低置信与降级标记，并预留在线模拟接口。

**Architecture:** 采用 Python + FastAPI 单体服务。请求进入后先解析或加载 `EvalSpec`，再对对话进行预处理、动作/槽位抽取，随后执行规则引擎与 LLM Judge，最后聚合为结构化评分卡并持久化到 SQLite。系统默认可在无真实 LLM 的情况下通过假适配器与规则降级路径跑通，以保证原型可演示、可测试、可扩展。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, sqlite3, pytest, httpx

---

## File Structure

### Runtime files

- `pyproject.toml`：项目依赖、pytest 配置。
- `.gitignore`：虚拟环境、缓存、SQLite 数据库忽略规则。
- `app/main.py`：FastAPI 入口与路由装配。
- `app/core/config.py`：运行配置与环境变量。
- `app/core/logging.py`：日志初始化。
- `app/api/routes_system.py`：健康检查。
- `app/api/routes_specs.py`：`EvalSpec` 编译、保存、查询。
- `app/api/routes_eval.py`：单条评估、批量评估、评估详情查询。
- `app/api/routes_simulation.py`：在线模拟占位接口。
- `app/domain/task_instruction.py`：任务指令模型。
- `app/domain/eval_spec.py`：`EvalSpec` 与评分规则模型。
- `app/domain/conversation.py`：对话、轮次、事实时间线模型。
- `app/domain/evaluation_result.py`：规则结果、Judge 结果、最终评分输出模型。
- `app/storage/db.py`：SQLite 初始化与连接封装。
- `app/storage/repo_task.py`：任务指令与 Spec 仓储。
- `app/storage/repo_eval.py`：评估结果仓储。
- `app/spec/compiler.py`：指令转 `EvalSpec` 草案。
- `app/pipeline/preprocess.py`：对话预处理。
- `app/pipeline/dialogue_parser.py`：轮次解析。
- `app/pipeline/fact_extractor.py`：动作/槽位/状态提取。
- `app/pipeline/aggregator.py`：总分、维度分、复核标记聚合。
- `app/pipeline/evaluation_runner.py`：评估主链路。
- `app/evaluators/rules/base.py`：规则抽象。
- `app/evaluators/rules/flow_rules.py`：流程规则。
- `app/evaluators/rules/slot_rules.py`：槽位规则。
- `app/evaluators/rules/forbidden_rules.py`：禁用动作规则。
- `app/evaluators/judge/llm_adapter.py`：LLM 适配器协议与假实现。
- `app/evaluators/judge/rubric_judge.py`：结构化软评分。
- `app/evaluators/judge/consistency_judge.py`：多次评分一致性。
- `app/reliability/agreement.py`：一致性计算。
- `app/reliability/confidence.py`：置信度计算。
- `app/reports/scorecard.py`：评分卡摘要。
- `app/reports/evidence_trace.py`：证据链整理。
- `app/reports/exporter.py`：批量结果导出。

### Tests

- `tests/api/test_health.py`
- `tests/domain/test_models.py`
- `tests/storage/test_repos.py`
- `tests/api/test_specs_api.py`
- `tests/pipeline/test_fact_extractor.py`
- `tests/evaluators/test_rules.py`
- `tests/evaluators/test_judge.py`
- `tests/reliability/test_confidence.py`
- `tests/api/test_evaluations_api.py`
- `tests/api/test_batch_and_simulation.py`
- `tests/fixtures/*.json`

---

### Task 1: Bootstrap the service skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/api/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/logging.py`
- Create: `app/api/routes_system.py`
- Create: `app/main.py`
- Test: `tests/api/test_health.py`

- [ ] **Step 1: Initialize git metadata and dependency manifest**

```toml
# pyproject.toml
[project]
name = "instruction-following-evaluator"
version = "0.1.0"
description = "Prototype evaluator for outbound task instruction following"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn[standard]>=0.30,<1.0",
  "pydantic>=2.7,<3.0"
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27,<1.0",
  "pytest>=8.2,<9.0",
  "pytest-cov>=5.0,<6.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
.coverage
*.db
```

Run:

```bash
git init
python -m venv .venv
```

Expected: 输出 `Initialized empty Git repository` 且创建 `.venv`

- [ ] **Step 2: Write the failing health-check test**

```python
# tests/api/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "instruction-following-evaluator"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/api/test_health.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app'` or `cannot import name 'app'`

- [ ] **Step 4: Write the minimal FastAPI app and config**

```python
# app/core/config.py
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "instruction-following-evaluator"
    database_path: str = "instruction_following.db"
    judge_runs: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# app/core/logging.py
import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
```

```python
# app/api/routes_system.py
from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "instruction-following-evaluator"}
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_system import router as system_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/api/test_health.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore app tests
git commit -m "chore: bootstrap fastapi evaluator service"
```

---

### Task 2: Define domain models for instructions, specs, conversations, and evaluation results

**Files:**
- Create: `app/domain/__init__.py`
- Create: `app/domain/task_instruction.py`
- Create: `app/domain/eval_spec.py`
- Create: `app/domain/conversation.py`
- Create: `app/domain/evaluation_result.py`
- Test: `tests/domain/test_models.py`

- [ ] **Step 1: Write the failing domain model tests**

```python
# tests/domain/test_models.py
from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, RequiredSlot, RequiredStep, SoftDimension


def test_eval_spec_validates_required_sections() -> None:
    spec = EvalSpec(
        spec_id="spec_demo",
        instruction_id="instr_demo",
        version="v1",
        task_goal="确认收货时间",
        required_steps=[
            RequiredStep(
                id="identity_check",
                name="确认身份",
                order=1,
                required=True,
                evidence_requirement="需要身份确认话术",
            )
        ],
        required_slots=[
            RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天"])
        ],
        soft_dimensions=[
            SoftDimension(
                id="explanation_quality",
                name="解释充分性",
                weight=0.3,
                rubric=["说明来电原因", "说明追问原因"],
            )
        ],
    )

    assert spec.spec_id == "spec_demo"
    assert spec.required_slots[0].name == "delivery_time"


def test_conversation_defaults_metadata() -> None:
    conversation = Conversation(
        conversation_id="conv_1",
        instruction_id="instr_demo",
        turns=[Turn(turn_id=1, speaker="agent", text="您好，请问是王女士吗？")],
    )

    assert conversation.turns[0].speaker == "agent"
    assert conversation.metadata == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domain/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain'`

- [ ] **Step 3: Write the minimal domain models**

```python
# app/domain/task_instruction.py
from pydantic import BaseModel, Field


class TaskInstruction(BaseModel):
    instruction_id: str
    name: str
    business_scene: str = "fulfillment_outbound"
    raw_text: str
    version: str = "v1"
    created_at: str | None = None
```

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


class EvalSpec(BaseModel):
    spec_id: str
    instruction_id: str
    version: str
    task_goal: str
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
# app/domain/conversation.py
from pydantic import BaseModel, Field


class Turn(BaseModel):
    turn_id: int
    speaker: str
    text: str
    timestamp_start: float | None = None
    timestamp_end: float | None = None


class FactEvent(BaseModel):
    event_id: str
    event_type: str
    turn_id: int
    slot_name: str | None = None
    slot_value: str | None = None
    note: str | None = None


class Conversation(BaseModel):
    conversation_id: str
    instruction_id: str
    source: str = "offline"
    turns: list[Turn]
    metadata: dict = Field(default_factory=dict)
```

```python
# app/domain/evaluation_result.py
from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    rule_id: str
    passed: bool = False
    score_delta: float = 0.0
    severity: str = "normal"
    evidence_turn_ids: list[int] = Field(default_factory=list)
    reason: str
    status: str = "ok"


class JudgeResult(BaseModel):
    dimension_id: str
    score: float
    confidence: float
    reason: str
    evidence_turn_ids: list[int] = Field(default_factory=list)
    status: str = "ok"


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: str
    turn_ids: list[int]
    quote: str
    linked_decision: str
    note: str = ""


class EvaluationResult(BaseModel):
    run_id: str
    conversation_id: str
    spec_id: str
    overall_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    hard_fail: bool = False
    confidence: float = 0.0
    needs_review: bool = False
    soft_eval_skipped: bool = False
    parse_warnings: list[str] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    judge_results: list[JudgeResult] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    summary: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domain/test_models.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/domain tests/domain
git commit -m "feat: add evaluator domain models"
```

---

### Task 3: Add SQLite storage for specs and evaluation runs

**Files:**
- Create: `app/storage/__init__.py`
- Create: `app/storage/db.py`
- Create: `app/storage/repo_task.py`
- Create: `app/storage/repo_eval.py`
- Modify: `app/main.py`
- Test: `tests/storage/test_repos.py`

- [ ] **Step 1: Write the failing repository tests**

```python
# tests/storage/test_repos.py
from pathlib import Path

from app.domain.eval_spec import EvalSpec
from app.storage.db import Database
from app.storage.repo_eval import EvaluationRepository
from app.storage.repo_task import SpecRepository


def test_spec_repository_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init()
    repo = SpecRepository(db)

    spec = EvalSpec(
        spec_id="spec_roundtrip",
        instruction_id="instr_1",
        version="v1",
        task_goal="确认地址",
    )
    repo.save(spec)

    loaded = repo.get("spec_roundtrip")

    assert loaded is not None
    assert loaded.spec_id == "spec_roundtrip"


def test_evaluation_repository_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init()
    repo = EvaluationRepository(db)

    payload = {
        "run_id": "run_1",
        "conversation_id": "conv_1",
        "spec_id": "spec_1",
        "overall_score": 88.0,
    }
    repo.save_json("run_1", payload)

    assert repo.get_json("run_1")["overall_score"] == 88.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/storage/test_repos.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage'`

- [ ] **Step 3: Implement the database and repositories**

```python
# app/storage/db.py
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS eval_spec (
                    spec_id TEXT PRIMARY KEY,
                    instruction_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_run (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )
```

```python
# app/storage/repo_task.py
import json

from app.domain.eval_spec import EvalSpec
from app.storage.db import Database


class SpecRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, spec: EvalSpec) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO eval_spec(spec_id, instruction_id, version, payload)
                VALUES (?, ?, ?, ?)
                """,
                (spec.spec_id, spec.instruction_id, spec.version, spec.model_dump_json()),
            )

    def get(self, spec_id: str) -> EvalSpec | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM eval_spec WHERE spec_id = ?",
                (spec_id,),
            ).fetchone()
        return EvalSpec.model_validate_json(row["payload"]) if row else None
```

```python
# app/storage/repo_eval.py
import json

from app.storage.db import Database


class EvaluationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_json(self, run_id: str, payload: dict) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_run(run_id, payload)
                VALUES (?, ?)
                """,
                (run_id, json.dumps(payload, ensure_ascii=False)),
            )

    def get_json(self, run_id: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM evaluation_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/storage/test_repos.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/storage app/main.py tests/storage
git commit -m "feat: add sqlite repositories for specs and evaluations"
```

---

### Task 4: Compile instructions into `EvalSpec` and expose spec APIs

**Files:**
- Create: `app/api/routes_specs.py`
- Create: `app/spec/__init__.py`
- Create: `app/spec/compiler.py`
- Modify: `app/main.py`
- Test: `tests/api/test_specs_api.py`

- [ ] **Step 1: Write the failing spec API tests**

```python
# tests/api/test_specs_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_compile_spec_returns_draft_spec() -> None:
    client = TestClient(app)

    response = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_delivery_time",
            "name": "确认送达时间",
            "raw_text": "请先确认用户身份，再确认收货时间，不要承诺一定送达。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["review_status"] == "draft"
    assert data["required_steps"][0]["id"] == "identity_check"


def test_save_and_get_spec() -> None:
    client = TestClient(app)
    spec_payload = {
        "spec_id": "spec_saved",
        "instruction_id": "instr_saved",
        "version": "v1",
        "task_goal": "确认收货时间",
        "required_steps": [],
        "required_slots": [],
        "soft_dimensions": [],
    }

    save_response = client.post("/specs", json=spec_payload)
    get_response = client.get("/specs/spec_saved")

    assert save_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["spec_id"] == "spec_saved"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api/test_specs_api.py -v`

Expected: FAIL with `404 Not Found` on `/specs/compile`

- [ ] **Step 3: Implement the compiler and spec routes**

```python
# app/spec/compiler.py
from uuid import uuid4

from app.domain.eval_spec import EvalSpec, ForbiddenAction, RequiredSlot, RequiredStep, SoftDimension
from app.domain.task_instruction import TaskInstruction


class SpecCompiler:
    def compile(self, instruction: TaskInstruction) -> EvalSpec:
        required_steps: list[RequiredStep] = []
        required_slots: list[RequiredSlot] = []
        forbidden_actions: list[ForbiddenAction] = []

        if "身份" in instruction.raw_text:
            required_steps.append(
                RequiredStep(
                    id="identity_check",
                    name="确认身份",
                    order=1,
                    required=True,
                    evidence_requirement="需要明确身份确认话术",
                )
            )

        if "时间" in instruction.raw_text:
            required_slots.append(
                RequiredSlot(
                    name="delivery_time",
                    required=True,
                    accepted_values=["今天", "明天", "上午", "下午"],
                )
            )

        if "不要承诺" in instruction.raw_text or "不要保证" in instruction.raw_text:
            forbidden_actions.append(
                ForbiddenAction(
                    id="forbid_false_promise",
                    description="禁止承诺无法保证的送达结果",
                )
            )

        return EvalSpec(
            spec_id=f"spec_{uuid4().hex[:8]}",
            instruction_id=instruction.instruction_id,
            version="v1",
            task_goal=instruction.name,
            required_steps=required_steps,
            required_slots=required_slots,
            forbidden_actions=forbidden_actions,
            completion_conditions=["关键槽位完成或失败原因明确", "以结束语收尾"],
            hard_fail_conditions=["触发禁用承诺"],
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

```python
# app/api/routes_specs.py
from fastapi import APIRouter, HTTPException, Request

from app.domain.eval_spec import EvalSpec
from app.domain.task_instruction import TaskInstruction
from app.spec.compiler import SpecCompiler
from app.storage.repo_task import SpecRepository

router = APIRouter(prefix="/specs", tags=["specs"])
compiler = SpecCompiler()


@router.post("/compile", response_model=EvalSpec)
def compile_spec(payload: TaskInstruction) -> EvalSpec:
    return compiler.compile(payload)


@router.post("", response_model=EvalSpec)
def save_spec(payload: EvalSpec, request: Request) -> EvalSpec:
    repo = SpecRepository(request.app.state.db)
    repo.save(payload)
    return payload


@router.get("/{spec_id}", response_model=EvalSpec)
def get_spec(spec_id: str, request: Request) -> EvalSpec:
    repo = SpecRepository(request.app.state.db)
    spec = repo.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="spec not found")
    return spec
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_specs import router as specs_router
from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)
app.include_router(specs_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_specs_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/spec app/api/routes_specs.py app/main.py tests/api/test_specs_api.py
git commit -m "feat: add eval spec compiler and spec APIs"
```

---

### Task 5: Parse conversations into fact timelines

**Files:**
- Create: `app/pipeline/__init__.py`
- Create: `app/pipeline/preprocess.py`
- Create: `app/pipeline/dialogue_parser.py`
- Create: `app/pipeline/fact_extractor.py`
- Create: `tests/fixtures/conversation_delivery_good.json`
- Test: `tests/pipeline/test_fact_extractor.py`

- [ ] **Step 1: Write the failing fact extraction test**

```python
# tests/pipeline/test_fact_extractor.py
import json
from pathlib import Path

from app.domain.conversation import Conversation
from app.pipeline.fact_extractor import FactExtractor


def test_fact_extractor_emits_identity_slot_and_end_events() -> None:
    payload = json.loads(Path("tests/fixtures/conversation_delivery_good.json").read_text(encoding="utf-8"))
    conversation = Conversation.model_validate(payload)

    events = FactExtractor().extract(conversation)

    event_types = [event.event_type for event in events]
    assert "identity_check" in event_types
    assert "slot_fill" in event_types
    assert "end_call" in event_types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_fact_extractor.py -v`

Expected: FAIL with `FileNotFoundError` or `ModuleNotFoundError: No module named 'app.pipeline'`

- [ ] **Step 3: Add fixture and implement preprocessing/parser/extractor**

```json
// tests/fixtures/conversation_delivery_good.json
{
  "conversation_id": "conv_good_1",
  "instruction_id": "instr_delivery_time",
  "turns": [
    {"turn_id": 1, "speaker": "agent", "text": "您好，请问是王女士吗？"},
    {"turn_id": 2, "speaker": "user", "text": "是的。"},
    {"turn_id": 3, "speaker": "agent", "text": "来电是为了确认今天收货时间，方便问下您下午是否在家？"},
    {"turn_id": 4, "speaker": "user", "text": "下午三点后可以。"},
    {"turn_id": 5, "speaker": "agent", "text": "好的，已为您记录下午三点后收货，感谢您的配合，再见。"}
  ]
}
```

```python
# app/pipeline/preprocess.py
from app.domain.conversation import Conversation, Turn


class Preprocessor:
    def run(self, conversation: Conversation) -> Conversation:
        cleaned_turns = [
            Turn(**{**turn.model_dump(), "text": turn.text.strip().replace("  ", " ")})
            for turn in conversation.turns
            if turn.text.strip()
        ]
        return conversation.model_copy(update={"turns": cleaned_turns})
```

```python
# app/pipeline/dialogue_parser.py
from app.domain.conversation import Conversation
from app.pipeline.preprocess import Preprocessor


class DialogueParser:
    def parse(self, conversation: Conversation) -> Conversation:
        return Preprocessor().run(conversation)
```

```python
# app/pipeline/fact_extractor.py
from app.domain.conversation import Conversation, FactEvent


class FactExtractor:
    def extract(self, conversation: Conversation) -> list[FactEvent]:
        events: list[FactEvent] = []
        for turn in conversation.turns:
            text = turn.text
            if turn.speaker == "agent" and "请问是" in text:
                events.append(FactEvent(event_id=f"evt_{turn.turn_id}_identity", event_type="identity_check", turn_id=turn.turn_id))
            if turn.speaker == "agent" and "收货时间" in text:
                events.append(FactEvent(event_id=f"evt_{turn.turn_id}_slot_ask", event_type="slot_ask", turn_id=turn.turn_id, slot_name="delivery_time"))
            if turn.speaker == "user" and ("下午" in text or "今天" in text or "明天" in text):
                events.append(FactEvent(event_id=f"evt_{turn.turn_id}_slot_fill", event_type="slot_fill", turn_id=turn.turn_id, slot_name="delivery_time", slot_value=text))
            if turn.speaker == "agent" and ("感谢" in text or "再见" in text):
                events.append(FactEvent(event_id=f"evt_{turn.turn_id}_end", event_type="end_call", turn_id=turn.turn_id))
            if "保证送达" in text or "一定送达" in text:
                events.append(FactEvent(event_id=f"evt_{turn.turn_id}_promise", event_type="promise", turn_id=turn.turn_id, note=text))
        return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_fact_extractor.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline tests/pipeline tests/fixtures
git commit -m "feat: add conversation preprocessing and fact extraction"
```

---

### Task 6: Implement hard-rule evaluators, aggregation, and scorecard reporting

**Files:**
- Create: `app/evaluators/__init__.py`
- Create: `app/evaluators/rules/__init__.py`
- Create: `app/evaluators/rules/base.py`
- Create: `app/evaluators/rules/flow_rules.py`
- Create: `app/evaluators/rules/slot_rules.py`
- Create: `app/evaluators/rules/forbidden_rules.py`
- Create: `app/pipeline/aggregator.py`
- Create: `app/reports/__init__.py`
- Create: `app/reports/scorecard.py`
- Create: `app/reports/evidence_trace.py`
- Test: `tests/evaluators/test_rules.py`

- [ ] **Step 1: Write the failing rule and aggregation tests**

```python
# tests/evaluators/test_rules.py
from app.domain.conversation import Conversation, FactEvent, Turn
from app.domain.eval_spec import EvalSpec, ForbiddenAction, RequiredSlot, RequiredStep
from app.evaluators.rules.flow_rules import RequiredStepRule
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.slot_rules import RequiredSlotRule
from app.pipeline.aggregator import Aggregator


def build_spec() -> EvalSpec:
    return EvalSpec(
        spec_id="spec_rule",
        instruction_id="instr_rule",
        version="v1",
        task_goal="确认收货时间",
        required_steps=[RequiredStep(id="identity_check", name="确认身份", order=1, required=True, evidence_requirement="身份确认")],
        required_slots=[RequiredSlot(name="delivery_time", required=True, accepted_values=["今天", "明天"])],
        forbidden_actions=[ForbiddenAction(id="forbid_false_promise", description="禁止承诺一定送达")],
    )


def test_required_slot_rule_passes_when_slot_filled() -> None:
    result = RequiredSlotRule().evaluate(
        build_spec(),
        [FactEvent(event_id="evt_1", event_type="slot_fill", turn_id=3, slot_name="delivery_time", slot_value="明天下午")],
    )

    assert result.passed is True


def test_forbidden_rule_fails_on_promise() -> None:
    result = ForbiddenActionRule().evaluate(
        build_spec(),
        [FactEvent(event_id="evt_2", event_type="promise", turn_id=4, note="一定送达")],
    )

    assert result.passed is False
    assert result.severity == "fatal"


def test_aggregator_zeroes_score_on_hard_fail() -> None:
    aggregate = Aggregator().combine(
        hard_results=[ForbiddenActionRule().evaluate(build_spec(), [FactEvent(event_id="evt_2", event_type="promise", turn_id=4)])],
        judge_results=[],
        parse_warnings=[],
    )

    assert aggregate["hard_fail"] is True
    assert aggregate["overall_score"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/evaluators/test_rules.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.evaluators'`

- [ ] **Step 3: Implement the hard rules, aggregator, and scorecard helpers**

```python
# app/evaluators/rules/base.py
from abc import ABC, abstractmethod

from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult


class Rule(ABC):
    @abstractmethod
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        raise NotImplementedError
```

```python
# app/evaluators/rules/flow_rules.py
from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class RequiredStepRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        required_ids = {step.id for step in spec.required_steps if step.required}
        observed = {event.event_type for event in events}
        missing = sorted(required_ids - observed)
        return RuleResult(
            rule_id="required_steps",
            passed=not missing,
            score_delta=1.0 if not missing else 0.0,
            evidence_turn_ids=[event.turn_id for event in events if event.event_type in required_ids],
            reason="all required steps found" if not missing else f"missing steps: {', '.join(missing)}",
        )
```

```python
# app/evaluators/rules/slot_rules.py
from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class RequiredSlotRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        filled_slots = {event.slot_name for event in events if event.event_type == "slot_fill"}
        required_slots = {slot.name for slot in spec.required_slots if slot.required}
        missing = sorted(required_slots - filled_slots)
        return RuleResult(
            rule_id="required_slots",
            passed=not missing,
            score_delta=1.0 if not missing else 0.0,
            evidence_turn_ids=[event.turn_id for event in events if event.event_type == "slot_fill"],
            reason="all required slots filled" if not missing else f"missing slots: {', '.join(missing)}",
        )
```

```python
# app/evaluators/rules/forbidden_rules.py
from app.domain.conversation import FactEvent
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import RuleResult
from app.evaluators.rules.base import Rule


class ForbiddenActionRule(Rule):
    def evaluate(self, spec: EvalSpec, events: list[FactEvent]) -> RuleResult:
        forbidden_hit = [event for event in events if event.event_type == "promise"]
        return RuleResult(
            rule_id="forbidden_actions",
            passed=not forbidden_hit,
            score_delta=1.0 if not forbidden_hit else 0.0,
            severity="fatal" if forbidden_hit else "normal",
            evidence_turn_ids=[event.turn_id for event in forbidden_hit],
            reason="no forbidden action found" if not forbidden_hit else "forbidden promise detected",
        )
```

```python
# app/pipeline/aggregator.py
from app.domain.evaluation_result import JudgeResult, RuleResult


class Aggregator:
    def combine(
        self,
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        parse_warnings: list[str],
        soft_eval_skipped: bool = False,
    ) -> dict:
        hard_fail = any(result.severity == "fatal" and not result.passed for result in hard_results)
        hard_score = 100.0 * (sum(result.score_delta for result in hard_results) / max(len(hard_results), 1))
        soft_score = 100.0 * (sum(result.score for result in judge_results) / max(len(judge_results), 1)) if judge_results else 0.0
        overall_score = 0.0 if hard_fail else round(hard_score * 0.7 + soft_score * 0.3, 2)
        return {
            "hard_fail": hard_fail,
            "hard_score": round(hard_score, 2),
            "soft_score": round(soft_score, 2),
            "overall_score": overall_score,
            "needs_review": bool(parse_warnings),
            "soft_eval_skipped": soft_eval_skipped,
        }
```

```python
# app/reports/scorecard.py
from app.domain.evaluation_result import EvaluationResult


def render_summary(result: EvaluationResult) -> str:
    if result.hard_fail:
        return "命中硬性失败项，需要人工复核。"
    if result.overall_score >= 85:
        return "整体指令遵循良好，关键流程已完成。"
    return "存在流程或话术问题，建议重点查看扣分证据。"
```

```python
# app/reports/evidence_trace.py
from app.domain.conversation import Conversation
from app.domain.evaluation_result import EvidenceItem


def build_evidence_items(conversation: Conversation, turn_ids: list[int], linked_decision: str) -> list[EvidenceItem]:
    indexed = {turn.turn_id: turn.text for turn in conversation.turns}
    return [
        EvidenceItem(
            evidence_id=f"evidence_{linked_decision}_{turn_id}",
            source_type="rule",
            turn_ids=[turn_id],
            quote=indexed.get(turn_id, ""),
            linked_decision=linked_decision,
        )
        for turn_id in turn_ids
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/evaluators/test_rules.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/evaluators app/pipeline/aggregator.py app/reports tests/evaluators
git commit -m "feat: add hard rule engine and score aggregation"
```

---

### Task 7: Implement structured LLM judging and reliability scoring

**Files:**
- Create: `app/evaluators/judge/__init__.py`
- Create: `app/evaluators/judge/llm_adapter.py`
- Create: `app/evaluators/judge/rubric_judge.py`
- Create: `app/evaluators/judge/consistency_judge.py`
- Create: `app/reliability/__init__.py`
- Create: `app/reliability/agreement.py`
- Create: `app/reliability/confidence.py`
- Test: `tests/evaluators/test_judge.py`
- Test: `tests/reliability/test_confidence.py`

- [ ] **Step 1: Write the failing judge and reliability tests**

```python
# tests/evaluators/test_judge.py
from app.domain.conversation import Conversation, Turn
from app.domain.eval_spec import EvalSpec, SoftDimension
from app.evaluators.judge.llm_adapter import FakeLLMAdapter
from app.evaluators.judge.rubric_judge import RubricJudge


def test_rubric_judge_returns_structured_scores() -> None:
    conversation = Conversation(
        conversation_id="conv_judge",
        instruction_id="instr_judge",
        turns=[Turn(turn_id=1, speaker="agent", text="来电是为了确认收货时间。")],
    )
    spec = EvalSpec(
        spec_id="spec_judge",
        instruction_id="instr_judge",
        version="v1",
        task_goal="确认收货时间",
        soft_dimensions=[
            SoftDimension(id="explanation_quality", name="解释充分性", weight=1.0, rubric=["说明来电目的"])
        ],
    )

    results = RubricJudge(FakeLLMAdapter()).evaluate(spec, conversation)

    assert results[0].dimension_id == "explanation_quality"
    assert 0.0 <= results[0].score <= 1.0
```

```python
# tests/reliability/test_confidence.py
from app.domain.evaluation_result import JudgeResult
from app.reliability.agreement import AgreementCalculator
from app.reliability.confidence import ConfidenceScorer


def test_confidence_is_reduced_on_disagreement() -> None:
    judge_runs = [
        [JudgeResult(dimension_id="x", score=0.9, confidence=0.9, reason="ok", evidence_turn_ids=[1])],
        [JudgeResult(dimension_id="x", score=0.4, confidence=0.5, reason="weak", evidence_turn_ids=[1])],
    ]

    agreement = AgreementCalculator().calculate(judge_runs)
    confidence = ConfidenceScorer().score(parse_warnings=["speaker_normalized"], agreement=agreement, soft_eval_skipped=False)

    assert agreement["score_span"] == 0.5
    assert confidence < 0.8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/evaluators/test_judge.py tests/reliability/test_confidence.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.evaluators.judge'`

- [ ] **Step 3: Implement the fake adapter, rubric judge, agreement, and confidence logic**

```python
# app/evaluators/judge/llm_adapter.py
from typing import Protocol


class LLMAdapter(Protocol):
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        ...


class FakeLLMAdapter:
    def score_dimension(self, dimension_id: str, rubric: list[str], conversation_text: str) -> dict:
        hit = "确认" in conversation_text or "来电" in conversation_text
        return {
            "dimension_id": dimension_id,
            "score": 0.9 if hit else 0.3,
            "confidence": 0.8 if hit else 0.5,
            "reason": "rubric hit" if hit else "rubric weak",
            "evidence_turn_ids": [1] if hit else [],
        }
```

```python
# app/evaluators/judge/rubric_judge.py
from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import JudgeResult
from app.evaluators.judge.llm_adapter import LLMAdapter


class RubricJudge:
    def __init__(self, adapter: LLMAdapter) -> None:
        self.adapter = adapter

    def evaluate(self, spec: EvalSpec, conversation: Conversation) -> list[JudgeResult]:
        transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in conversation.turns)
        results: list[JudgeResult] = []
        for dimension in spec.soft_dimensions:
            payload = self.adapter.score_dimension(dimension.id, dimension.rubric, transcript)
            results.append(JudgeResult(**payload))
        return results
```

```python
# app/reliability/agreement.py
from app.domain.evaluation_result import JudgeResult


class AgreementCalculator:
    def calculate(self, judge_runs: list[list[JudgeResult]]) -> dict:
        flattened = [run[0].score for run in judge_runs if run]
        if not flattened:
            return {"score_span": 1.0, "agreement": 0.0}
        score_span = max(flattened) - min(flattened)
        return {"score_span": round(score_span, 2), "agreement": round(1 - score_span, 2)}
```

```python
# app/reliability/confidence.py
class ConfidenceScorer:
    def score(self, parse_warnings: list[str], agreement: dict, soft_eval_skipped: bool) -> float:
        confidence = 0.9
        confidence -= min(len(parse_warnings) * 0.1, 0.3)
        confidence -= (1 - agreement["agreement"]) * 0.4
        if soft_eval_skipped:
            confidence -= 0.2
        return round(max(confidence, 0.0), 2)
```

```python
# app/evaluators/judge/consistency_judge.py
from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import JudgeResult
from app.evaluators.judge.rubric_judge import RubricJudge


class ConsistencyJudge:
    def __init__(self, judge: RubricJudge, runs: int = 2) -> None:
        self.judge = judge
        self.runs = runs

    def evaluate(self, spec: EvalSpec, conversation: Conversation) -> list[list[JudgeResult]]:
        return [self.judge.evaluate(spec, conversation) for _ in range(self.runs)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/evaluators/test_judge.py tests/reliability/test_confidence.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/evaluators/judge app/reliability tests/evaluators/test_judge.py tests/reliability
git commit -m "feat: add structured llm judge and reliability scoring"
```

---

### Task 8: Wire the end-to-end evaluation pipeline and APIs

**Files:**
- Create: `app/pipeline/evaluation_runner.py`
- Create: `app/api/routes_eval.py`
- Modify: `app/main.py`
- Test: `tests/api/test_evaluations_api.py`

- [ ] **Step 1: Write the failing end-to-end evaluation API tests**

```python
# tests/api/test_evaluations_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_run_evaluation_returns_scorecard() -> None:
    client = TestClient(app)
    spec = {
        "spec_id": "spec_eval_api",
        "instruction_id": "instr_eval_api",
        "version": "v1",
        "task_goal": "确认收货时间",
        "required_steps": [{"id": "identity_check", "name": "确认身份", "order": 1, "required": True, "evidence_requirement": "身份确认"}],
        "required_slots": [{"name": "delivery_time", "required": True, "accepted_values": ["今天", "明天"]}],
        "forbidden_actions": [{"id": "forbid_false_promise", "description": "禁止承诺一定送达"}],
        "soft_dimensions": [{"id": "explanation_quality", "name": "解释充分性", "weight": 1.0, "rubric": ["说明来电目的"]}]
    }
    conversation = {
        "conversation_id": "conv_eval_api",
        "instruction_id": "instr_eval_api",
        "turns": [
            {"turn_id": 1, "speaker": "agent", "text": "您好，请问是王女士吗？"},
            {"turn_id": 2, "speaker": "user", "text": "是的。"},
            {"turn_id": 3, "speaker": "agent", "text": "来电是为了确认收货时间，您今天下午在家吗？"},
            {"turn_id": 4, "speaker": "user", "text": "下午三点后可以。"},
            {"turn_id": 5, "speaker": "agent", "text": "好的，感谢您的配合，再见。"}
        ]
    }

    response = client.post("/evaluations/run", json={"spec": spec, "conversation": conversation})

    assert response.status_code == 200
    assert response.json()["overall_score"] >= 80
    assert response.json()["hard_fail"] is False


def test_get_evaluation_run_returns_saved_payload() -> None:
    client = TestClient(app)
    run_response = client.post(
        "/evaluations/run",
        json={
            "spec": {"spec_id": "spec_lookup", "instruction_id": "instr_lookup", "version": "v1", "task_goal": "确认时间", "required_steps": [], "required_slots": [], "soft_dimensions": []},
            "conversation": {"conversation_id": "conv_lookup", "instruction_id": "instr_lookup", "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}]}
        },
    )

    run_id = run_response.json()["run_id"]
    get_response = client.get(f"/evaluations/{run_id}")

    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == run_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api/test_evaluations_api.py -v`

Expected: FAIL with `404 Not Found` on `/evaluations/run`

- [ ] **Step 3: Implement the evaluation runner and routes**

```python
# app/pipeline/evaluation_runner.py
from uuid import uuid4

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.domain.evaluation_result import EvaluationResult
from app.evaluators.judge.consistency_judge import ConsistencyJudge
from app.evaluators.judge.llm_adapter import FakeLLMAdapter
from app.evaluators.judge.rubric_judge import RubricJudge
from app.evaluators.rules.flow_rules import RequiredStepRule
from app.evaluators.rules.forbidden_rules import ForbiddenActionRule
from app.evaluators.rules.slot_rules import RequiredSlotRule
from app.pipeline.aggregator import Aggregator
from app.pipeline.dialogue_parser import DialogueParser
from app.pipeline.fact_extractor import FactExtractor
from app.reliability.agreement import AgreementCalculator
from app.reliability.confidence import ConfidenceScorer
from app.reports.evidence_trace import build_evidence_items
from app.reports.scorecard import render_summary


class EvaluationRunner:
    def run(self, spec: EvalSpec, conversation: Conversation) -> EvaluationResult:
        parsed = DialogueParser().parse(conversation)
        events = FactExtractor().extract(parsed)

        hard_results = [
            RequiredStepRule().evaluate(spec, events),
            RequiredSlotRule().evaluate(spec, events),
            ForbiddenActionRule().evaluate(spec, events),
        ]

        judge = RubricJudge(FakeLLMAdapter())
        judge_runs = ConsistencyJudge(judge, runs=2).evaluate(spec, parsed) if spec.soft_dimensions else []
        judge_results = judge_runs[0] if judge_runs else []

        aggregate = Aggregator().combine(hard_results=hard_results, judge_results=judge_results, parse_warnings=[])
        agreement = AgreementCalculator().calculate(judge_runs) if judge_runs else {"score_span": 1.0, "agreement": 0.0}
        confidence = ConfidenceScorer().score(parse_warnings=[], agreement=agreement, soft_eval_skipped=not bool(judge_results))

        evidence_items = []
        for result in hard_results:
            evidence_items.extend(build_evidence_items(parsed, result.evidence_turn_ids, result.rule_id))

        evaluation = EvaluationResult(
            run_id=f"run_{uuid4().hex[:8]}",
            conversation_id=conversation.conversation_id,
            spec_id=spec.spec_id,
            overall_score=aggregate["overall_score"],
            dimension_scores={item.dimension_id: item.score for item in judge_results},
            hard_fail=aggregate["hard_fail"],
            confidence=confidence,
            needs_review=aggregate["needs_review"],
            soft_eval_skipped=aggregate["soft_eval_skipped"],
            rule_results=hard_results,
            judge_results=judge_results,
            evidence_items=evidence_items,
        )
        return evaluation.model_copy(update={"summary": render_summary(evaluation)})
```

```python
# app/api/routes_eval.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.pipeline.evaluation_runner import EvaluationRunner
from app.storage.repo_eval import EvaluationRepository


class EvaluationRequest(BaseModel):
    spec: EvalSpec
    conversation: Conversation


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run")
def run_evaluation(payload: EvaluationRequest, request: Request) -> dict:
    result = EvaluationRunner().run(payload.spec, payload.conversation)
    repo = EvaluationRepository(request.app.state.db)
    repo.save_json(result.run_id, result.model_dump())
    return result.model_dump()


@router.get("/{run_id}")
def get_evaluation(run_id: str, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    payload = repo.get_json(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return payload
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_eval import router as eval_router
from app.api.routes_specs import router as specs_router
from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)
app.include_router(specs_router)
app.include_router(eval_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_evaluations_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/evaluation_runner.py app/api/routes_eval.py app/main.py tests/api/test_evaluations_api.py
git commit -m "feat: add end-to-end evaluation pipeline"
```

---

### Task 9: Add batch evaluation, simulation placeholder, and export support

**Files:**
- Create: `app/api/routes_simulation.py`
- Create: `app/reports/exporter.py`
- Modify: `app/api/routes_eval.py`
- Modify: `app/main.py`
- Test: `tests/api/test_batch_and_simulation.py`

- [ ] **Step 1: Write the failing batch/simulation tests**

```python
# tests/api/test_batch_and_simulation.py
from fastapi.testclient import TestClient

from app.main import app


def test_batch_evaluation_returns_multiple_results() -> None:
    client = TestClient(app)
    payload = {
        "items": [
            {
                "spec": {"spec_id": "spec_batch", "instruction_id": "instr_batch", "version": "v1", "task_goal": "确认时间", "required_steps": [], "required_slots": [], "soft_dimensions": []},
                "conversation": {"conversation_id": "conv_batch_1", "instruction_id": "instr_batch", "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}]}
            },
            {
                "spec": {"spec_id": "spec_batch", "instruction_id": "instr_batch", "version": "v1", "task_goal": "确认时间", "required_steps": [], "required_slots": [], "soft_dimensions": []},
                "conversation": {"conversation_id": "conv_batch_2", "instruction_id": "instr_batch", "turns": [{"turn_id": 1, "speaker": "agent", "text": "您好"}]}
            }
        ]
    }

    response = client.post("/evaluations/batch", json=payload)

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_simulation_endpoint_is_reserved_but_not_implemented() -> None:
    client = TestClient(app)

    response = client.post("/simulations/run", json={"spec_id": "spec_demo", "model_config": {"name": "stub"}})

    assert response.status_code == 501
    assert response.json()["detail"] == "simulation runner not implemented in prototype"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api/test_batch_and_simulation.py -v`

Expected: FAIL with `404 Not Found` on `/evaluations/batch` and `/simulations/run`

- [ ] **Step 3: Implement batch evaluation, exporter, and simulation placeholder**

```python
# app/reports/exporter.py
import csv
from pathlib import Path


def export_batch_summary(rows: list[dict], destination: str) -> str:
    path = Path(destination)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["run_id", "conversation_id", "overall_score", "hard_fail", "confidence"])
        writer.writeheader()
        writer.writerows(rows)
    return str(path)
```

```python
# app/api/routes_simulation.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    spec_id: str
    model_config: dict = Field(default_factory=dict)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run")
def run_simulation(_: SimulationRequest) -> None:
    raise HTTPException(status_code=501, detail="simulation runner not implemented in prototype")
```

```python
# app/api/routes_eval.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.pipeline.evaluation_runner import EvaluationRunner
from app.reports.exporter import export_batch_summary
from app.storage.repo_eval import EvaluationRepository


class EvaluationRequest(BaseModel):
    spec: EvalSpec
    conversation: Conversation


class BatchEvaluationRequest(BaseModel):
    items: list[EvaluationRequest] = Field(default_factory=list)


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run")
def run_evaluation(payload: EvaluationRequest, request: Request) -> dict:
    result = EvaluationRunner().run(payload.spec, payload.conversation)
    repo = EvaluationRepository(request.app.state.db)
    repo.save_json(result.run_id, result.model_dump())
    return result.model_dump()


@router.post("/batch")
def run_batch(payload: BatchEvaluationRequest, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    results = []
    for item in payload.items:
        result = EvaluationRunner().run(item.spec, item.conversation)
        repo.save_json(result.run_id, result.model_dump())
        results.append(result.model_dump())
    export_path = export_batch_summary(
        [
            {
                "run_id": item["run_id"],
                "conversation_id": item["conversation_id"],
                "overall_score": item["overall_score"],
                "hard_fail": item["hard_fail"],
                "confidence": item["confidence"],
            }
            for item in results
        ],
        "batch_summary.csv",
    )
    return {"results": results, "export_path": export_path}


@router.get("/{run_id}")
def get_evaluation(run_id: str, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    payload = repo.get_json(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return payload
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_eval import router as eval_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_specs import router as specs_router
from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)
app.include_router(specs_router)
app.include_router(eval_router)
app.include_router(simulation_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_batch_and_simulation.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routes_simulation.py app/reports/exporter.py app/api/routes_eval.py app/main.py tests/api/test_batch_and_simulation.py
git commit -m "feat: add batch evaluation and simulation placeholder"
```

---

### Task 10: Add full regression coverage and final verification pass

**Files:**
- Modify: `tests/api/test_health.py`
- Modify: `tests/api/test_specs_api.py`
- Modify: `tests/pipeline/test_fact_extractor.py`
- Modify: `tests/evaluators/test_rules.py`
- Modify: `tests/api/test_evaluations_api.py`

- [ ] **Step 1: Add one integrated regression test covering compile → evaluate → fetch**

```python
# append to tests/api/test_evaluations_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_compile_then_evaluate_then_fetch_round_trip() -> None:
    client = TestClient(app)
    compiled = client.post(
        "/specs/compile",
        json={
            "instruction_id": "instr_round_trip",
            "name": "确认送达时间",
            "raw_text": "请先确认身份，再确认收货时间，不要承诺一定送达。",
        },
    ).json()

    result = client.post(
        "/evaluations/run",
        json={
            "spec": compiled,
            "conversation": {
                "conversation_id": "conv_round_trip",
                "instruction_id": "instr_round_trip",
                "turns": [
                    {"turn_id": 1, "speaker": "agent", "text": "您好，请问是张先生吗？"},
                    {"turn_id": 2, "speaker": "user", "text": "是的。"},
                    {"turn_id": 3, "speaker": "agent", "text": "来电是为了确认收货时间，您明天下午方便收货吗？"},
                    {"turn_id": 4, "speaker": "user", "text": "明天下午可以。"},
                    {"turn_id": 5, "speaker": "agent", "text": "好的，感谢您的配合，再见。"}
                ]
            }
        },
    )

    fetched = client.get(f"/evaluations/{result.json()['run_id']}")

    assert result.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["conversation_id"] == "conv_round_trip"
```

- [ ] **Step 2: Run the full test suite and capture the final regression state**

Run: `python -m pytest -v`

Expected: 若前 9 个任务已按计划完成，此处应只可能暴露聚合字段或置信度字段的一致性问题

- [ ] **Step 3: Apply the final consistency patch**

```python
# app/pipeline/aggregator.py
from app.domain.evaluation_result import JudgeResult, RuleResult


class Aggregator:
    def combine(
        self,
        hard_results: list[RuleResult],
        judge_results: list[JudgeResult],
        parse_warnings: list[str],
        soft_eval_skipped: bool = False,
    ) -> dict:
        hard_fail = any(result.severity == "fatal" and not result.passed for result in hard_results)
        hard_score = 100.0 * (sum(result.score_delta for result in hard_results) / max(len(hard_results), 1))
        soft_score = (
            100.0 * (sum(result.score for result in judge_results) / max(len(judge_results), 1))
            if judge_results
            else 0.0
        )
        overall_score = 0.0 if hard_fail else round(hard_score * 0.7 + soft_score * 0.3, 2)
        needs_review = bool(parse_warnings) or soft_eval_skipped
        return {
            "hard_fail": hard_fail,
            "hard_score": round(hard_score, 2),
            "soft_score": round(soft_score, 2),
            "overall_score": overall_score,
            "needs_review": needs_review,
            "soft_eval_skipped": soft_eval_skipped,
        }
```

```python
# app/pipeline/evaluation_runner.py
        aggregate = Aggregator().combine(
            hard_results=hard_results,
            judge_results=judge_results,
            parse_warnings=[],
            soft_eval_skipped=not bool(judge_results),
        )
        agreement = AgreementCalculator().calculate(judge_runs) if judge_runs else {"score_span": 1.0, "agreement": 0.0}
        confidence = ConfidenceScorer().score(
            parse_warnings=[],
            agreement=agreement,
            soft_eval_skipped=aggregate["soft_eval_skipped"],
        )

        evaluation = EvaluationResult(
            run_id=f"run_{uuid4().hex[:8]}",
            conversation_id=conversation.conversation_id,
            spec_id=spec.spec_id,
            overall_score=aggregate["overall_score"],
            dimension_scores={item.dimension_id: item.score for item in judge_results},
            hard_fail=aggregate["hard_fail"],
            confidence=confidence,
            needs_review=aggregate["needs_review"],
            soft_eval_skipped=aggregate["soft_eval_skipped"],
            rule_results=hard_results,
            judge_results=judge_results,
            evidence_items=evidence_items,
        )
```

- [ ] **Step 4: Run the full test suite again**

Run: `python -m pytest -v`

Expected: 全量 PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "test: add regression coverage for evaluator prototype"
```

---

## Self-Review Checklist

- Spec coverage:
  - `EvalSpec` 作为核心中间层：Task 2, Task 4
  - 对话理解层：Task 5
  - 规则 + LLM 混合评估：Task 6, Task 7, Task 8
  - 评分卡、证据链、置信度：Task 6, Task 7, Task 8
  - 批量评估与在线模拟预留：Task 9
  - 回归验证：Task 10
- Placeholder scan: 本计划未使用任何占位符式描述。
- Type consistency:
  - `EvalSpec`, `Conversation`, `EvaluationResult` 在 Task 2 定义，并在后续任务中保持一致。
  - `overall_score`, `hard_fail`, `needs_review`, `soft_eval_skipped`, `dimension_scores` 在聚合与 API 返回中保持同名。
