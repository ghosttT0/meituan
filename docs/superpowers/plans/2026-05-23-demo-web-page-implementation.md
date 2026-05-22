# Demo Web Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有 FastAPI 评估系统补充一个产品化的单页 Demo 驾驶舱，支持预置案例、手动试跑、结果摘要卡、Accordion 细节区和响应式布局。

**Architecture:** 采用 FastAPI 下挂轻量 SPA 单页，不引入独立前端工程。页面通过一个 `/demo` 路由返回 HTML，静态资源从 `/demo/assets/*` 提供，前端使用原生 ES Modules 拆分为数据状态、API 调用、页面渲染三个模块，直接复用现有 `/specs/compile`、`/evaluations/run`、`/evaluations/{run_id}` 接口。

**Tech Stack:** Python 3.10+, FastAPI, Starlette StaticFiles, HTML, CSS, ES Modules, Node built-in test runner, pytest

---

## File Structure

### Runtime files

- `app/api/routes_demo.py`：提供 `/demo` HTML 页面和静态资源挂载对象。
- `app/main.py`：注册 demo 路由与静态资源。
- `app/web/templates/demo.html`：Demo 页结构骨架。
- `app/web/static/demo.css`：页面样式与响应式规则。
- `app/web/static/demo-data.js`：预置案例、模式切换、前端状态 helpers。
- `app/web/static/demo-api.js`：对话文本解析、构造 compile/evaluation payload、调用后端评估链路。
- `app/web/static/demo-view.js`：页面渲染、Accordion 绑定、运行按钮、导出按钮、加载与错误状态。

### Tests

- `tests/api/test_demo_page.py`：Demo 页面与静态资源的路由/HTML contract 测试。
- `tests/web/demo_data.test.mjs`：预置案例和模式切换测试。
- `tests/web/demo_api.test.mjs`：payload 构造与 API flow 测试。
- `tests/web/demo_view.test.mjs`：评分卡、Accordion、导出文件名等视图 helper 测试。

---

### Task 1: Serve the demo page and static assets

**Files:**
- Create: `app/api/routes_demo.py`
- Create: `app/web/templates/demo.html`
- Create: `app/web/static/demo.css`
- Create: `app/web/static/demo-view.js`
- Modify: `app/main.py`
- Test: `tests/api/test_demo_page.py`

- [ ] **Step 1: Write the failing route test**

```python
# tests/api/test_demo_page.py
from fastapi.testclient import TestClient

from app.main import app


def test_demo_page_and_assets_are_available() -> None:
    client = TestClient(app)

    page = client.get("/demo")
    css = client.get("/demo/assets/demo.css")
    script = client.get("/demo/assets/demo-view.js")

    assert page.status_code == 200
    assert 'id="demo-root"' in page.text
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/api/test_demo_page.py::test_demo_page_and_assets_are_available -v`

Expected: FAIL with `404 Not Found` on `/demo`

- [ ] **Step 3: Write the minimal route and placeholder assets**

```python
# app/api/routes_demo.py
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
TEMPLATE_PATH = WEB_DIR / "templates" / "demo.html"
STATIC_DIR = WEB_DIR / "static"

router = APIRouter(tags=["demo"])
demo_static = StaticFiles(directory=str(STATIC_DIR))


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> HTMLResponse:
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))
```

```html
<!-- app/web/templates/demo.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>履约数字人外呼评估驾驶舱</title>
    <link rel="stylesheet" href="/demo/assets/demo.css" />
  </head>
  <body>
    <div id="demo-root">demo shell</div>
    <script type="module" src="/demo/assets/demo-view.js"></script>
  </body>
</html>
```

```css
/* app/web/static/demo.css */
body {
  margin: 0;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
```

```javascript
// app/web/static/demo-view.js
console.log("demo-view loaded");
```

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes_demo import demo_static, router as demo_router
from app.api.routes_eval import router as eval_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_specs import router as specs_router
from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.mount("/demo/assets", demo_static, name="demo-assets")
app.include_router(system_router)
app.include_router(specs_router)
app.include_router(eval_router)
app.include_router(simulation_router)
app.include_router(demo_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/api/test_demo_page.py::test_demo_page_and_assets_are_available -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routes_demo.py app/web/templates/demo.html app/web/static/demo.css app/web/static/demo-view.js app/main.py tests/api/test_demo_page.py
git commit -m "feat: add demo page route and static assets"
```

---

### Task 2: Build the responsive dashboard shell

**Files:**
- Modify: `app/web/templates/demo.html`
- Modify: `app/web/static/demo.css`
- Modify: `tests/api/test_demo_page.py`

- [ ] **Step 1: Extend the failing HTML contract test**

```python
# append to tests/api/test_demo_page.py
def test_demo_page_contains_dashboard_shell_and_accordions() -> None:
    client = TestClient(app)

    response = client.get("/demo")
    html = response.text

    for token in [
        "履约数字人外呼评估驾驶舱",
        'id="demo-header"',
        'id="demo-input-panel"',
        'id="demo-summary-panel"',
        'id="scorecard-grid"',
        'data-accordion=\"evidence\"',
        'data-accordion=\"rules\"',
        'data-accordion=\"judge\"',
        'data-accordion=\"raw-json\"',
    ]:
        assert token in html


def test_demo_styles_include_responsive_dashboard_rules() -> None:
    client = TestClient(app)

    css = client.get("/demo/assets/demo.css").text

    assert ".demo-shell" in css
    assert "grid-template-columns: 400px minmax(0, 1fr);" in css
    assert "@media (max-width: 1100px)" in css
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api/test_demo_page.py -v`

Expected: FAIL because the HTML shell and responsive CSS rules are missing

- [ ] **Step 3: Replace the placeholder HTML and CSS with the actual dashboard shell**

```html
<!-- app/web/templates/demo.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>履约数字人外呼评估驾驶舱</title>
    <link rel="stylesheet" href="/demo/assets/demo.css" />
  </head>
  <body>
    <div id="demo-root" class="demo-shell">
      <header id="demo-header" class="demo-header">
        <div>
          <p class="eyebrow">Instruction Following Evaluator Demo</p>
          <h1>履约数字人外呼评估驾驶舱</h1>
          <p class="subhead">任务指令遵循自动评估 Demo</p>
        </div>
        <div class="header-actions">
          <button id="preset-mode-button" type="button">预置案例</button>
          <button id="manual-mode-button" type="button">手动试跑</button>
          <button id="export-result-button" type="button">导出结果</button>
        </div>
      </header>

      <main class="demo-main">
        <aside id="demo-input-panel" class="panel"></aside>

        <section id="demo-summary-panel" class="summary-column">
          <section class="summary-strip">
            <article class="hero-card">
              <p class="card-label">总分</p>
              <div id="summary-score" class="hero-score">--</div>
              <p id="summary-confidence" class="hero-meta">等待运行</p>
            </article>
            <article class="summary-card">
              <p class="card-label">总体结论</p>
              <p id="summary-headline">等待运行</p>
            </article>
            <article class="summary-card">
              <p class="card-label">复核状态</p>
              <p id="summary-review-flag">等待运行</p>
            </article>
          </section>

          <section class="panel">
            <div class="section-header">
              <h2>评分卡</h2>
            </div>
            <div id="scorecard-grid" class="scorecard-grid"></div>
          </section>

          <section class="accordion-stack">
            <details data-accordion="evidence" class="accordion-item">
              <summary>证据链</summary>
              <div id="accordion-evidence" class="accordion-content"></div>
            </details>
            <details data-accordion="rules" class="accordion-item">
              <summary>规则命中详情</summary>
              <div id="accordion-rules" class="accordion-content"></div>
            </details>
            <details data-accordion="judge" class="accordion-item">
              <summary>LLM 判分理由</summary>
              <div id="accordion-judge" class="accordion-content"></div>
            </details>
            <details data-accordion="raw-json" class="accordion-item">
              <summary>原始 JSON / 技术细节</summary>
              <pre id="accordion-json" class="json-block"></pre>
            </details>
          </section>
        </section>
      </main>

      <script type="module" src="/demo/assets/demo-view.js"></script>
    </div>
  </body>
</html>
```

```css
/* app/web/static/demo.css */
:root {
  color-scheme: light;
  --bg: #f4f7fb;
  --panel: #ffffff;
  --panel-border: #dbe4f0;
  --text: #172033;
  --muted: #5f6b7c;
  --primary: #1677ff;
  --primary-soft: #eaf3ff;
  --success-soft: #effaf3;
  --warning-soft: #fff8eb;
  --shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.demo-shell {
  min-height: 100vh;
  padding: 24px;
}

.demo-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  border: 1px solid #d9e8ff;
  border-radius: 20px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  box-shadow: var(--shadow);
}

.eyebrow {
  margin: 0 0 8px 0;
  color: #7d8aa0;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.demo-header h1 {
  margin: 0;
  font-size: 30px;
}

.subhead {
  margin: 8px 0 0 0;
  color: var(--muted);
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.header-actions button,
.input-actions button {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
}

.demo-main {
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 20px;
  margin-top: 20px;
  align-items: start;
}

.panel,
.summary-card,
.hero-card,
.accordion-item {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  box-shadow: var(--shadow);
}

.summary-column {
  display: grid;
  gap: 16px;
}

.summary-strip {
  display: grid;
  grid-template-columns: 1.15fr 1fr 1fr;
  gap: 16px;
}

.hero-card,
.summary-card,
.panel {
  padding: 18px;
}

.card-label {
  margin: 0;
  color: #8190a8;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.hero-score {
  margin-top: 10px;
  font-size: 54px;
  font-weight: 800;
  line-height: 1;
  color: #10213f;
}

.hero-meta {
  margin: 10px 0 0 0;
  color: var(--muted);
}

.scorecard-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.accordion-stack {
  display: grid;
  gap: 12px;
}

.accordion-item summary {
  cursor: pointer;
  list-style: none;
  padding: 16px 18px;
  font-weight: 600;
}

.accordion-item summary::-webkit-details-marker {
  display: none;
}

.accordion-content,
.json-block {
  margin: 0;
  padding: 0 18px 18px 18px;
  color: var(--muted);
}

@media (max-width: 1100px) {
  .demo-main {
    grid-template-columns: 340px minmax(0, 1fr);
  }

  .summary-strip {
    grid-template-columns: 1fr;
  }

  .scorecard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .demo-shell {
    padding: 16px;
  }

  .demo-main {
    grid-template-columns: 1fr;
  }

  .scorecard-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_demo_page.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/templates/demo.html app/web/static/demo.css tests/api/test_demo_page.py
git commit -m "feat: add responsive dashboard shell for demo page"
```

---

### Task 3: Add preset cases and mode switching state

**Files:**
- Create: `app/web/static/demo-data.js`
- Modify: `app/web/static/demo-view.js`
- Test: `tests/web/demo_data.test.mjs`

- [ ] **Step 1: Write the failing Node state test**

```javascript
// tests/web/demo_data.test.mjs
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const demoData = await import(
  pathToFileURL(path.resolve("app/web/static/demo-data.js")).href
);

test("createInitialState starts in preset mode with the first preset", () => {
  const state = demoData.createInitialState();

  assert.equal(state.mode, "preset");
  assert.equal(state.activePresetId, "delivery_time");
  assert.match(state.instructionText, /确认用户身份/);
  assert.match(state.conversationText, /agent:/);
});

test("switchMode preserves current text when switching to manual", () => {
  const state = demoData.createInitialState();
  const next = demoData.switchMode(state, "manual");

  assert.equal(next.mode, "manual");
  assert.equal(next.instructionText, state.instructionText);
  assert.equal(next.conversationText, state.conversationText);
});

test("applyPreset swaps the active preset fields", () => {
  const state = demoData.createInitialState();
  const next = demoData.applyPreset(state, "address_check");

  assert.equal(next.activePresetId, "address_check");
  assert.match(next.instructionText, /地址/);
  assert.match(next.conversationText, /user:/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/web/demo_data.test.mjs`

Expected: FAIL with `Cannot find module 'app/web/static/demo-data.js'`

- [ ] **Step 3: Implement preset data and state helpers**

```javascript
// app/web/static/demo-data.js
export const PRESET_CASES = [
  {
    id: "delivery_time",
    label: "案例 1：收货时间确认",
    instructionText: "请先确认用户身份，再确认收货时间，不要承诺一定送达。",
    conversationText: [
      "agent: 您好，请问是张先生吗？",
      "user: 是的。",
      "agent: 来电是为了确认收货时间，您明天下午方便收货吗？",
      "user: 明天下午可以。",
      "agent: 好的，感谢您的配合，再见。",
    ].join("\\n"),
  },
  {
    id: "address_check",
    label: "案例 2：地址核验",
    instructionText: "请先确认身份，再核验详细地址，避免直接承诺配送结果。",
    conversationText: [
      "agent: 您好，请问是李女士吗？",
      "user: 是我。",
      "agent: 来电是为了核验收货地址，您当前地址还是朝阳区望京街道 8 号吗？",
      "user: 改成朝阳区望京街道 10 号了。",
      "agent: 好的，我帮您记录最新地址，感谢配合。",
    ].join("\\n"),
  },
  {
    id: "objection_handle",
    label: "案例 3：异常异议处理",
    instructionText: "先说明来电目的，再处理用户异议，收集失败原因并完成结束语。",
    conversationText: [
      "agent: 您好，请问是王女士吗？",
      "user: 你们怎么老打电话？",
      "agent: 抱歉打扰，这次来电是为了确认收货安排，方便我核对一下明天是否可以签收吗？",
      "user: 明天不方便。",
      "agent: 好的，我记录为明天不便签收，感谢您的反馈，再见。",
    ].join("\\n"),
  },
];

export function createInitialState() {
  const first = PRESET_CASES[0];
  return {
    mode: "preset",
    activePresetId: first.id,
    instructionText: first.instructionText,
    conversationText: first.conversationText,
    lastResult: null,
    status: "idle",
    errorMessage: "",
  };
}

export function applyPreset(state, presetId) {
  const preset = PRESET_CASES.find((item) => item.id === presetId);
  if (!preset) {
    return state;
  }
  return {
    ...state,
    mode: "preset",
    activePresetId: preset.id,
    instructionText: preset.instructionText,
    conversationText: preset.conversationText,
    errorMessage: "",
  };
}

export function switchMode(state, mode) {
  return {
    ...state,
    mode,
    errorMessage: "",
  };
}
```

```javascript
// app/web/static/demo-view.js
import { PRESET_CASES, applyPreset, createInitialState, switchMode } from "./demo-data.js";

export { PRESET_CASES, applyPreset, createInitialState, switchMode };

console.log("demo-view loaded");
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/web/demo_data.test.mjs`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/static/demo-data.js app/web/static/demo-view.js tests/web/demo_data.test.mjs
git commit -m "feat: add demo preset cases and mode state helpers"
```

---

### Task 4: Build compile/evaluation payloads and API flow

**Files:**
- Create: `app/web/static/demo-api.js`
- Test: `tests/web/demo_api.test.mjs`

- [ ] **Step 1: Write the failing API helper test**

```javascript
// tests/web/demo_api.test.mjs
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const demoApi = await import(
  pathToFileURL(path.resolve("app/web/static/demo-api.js")).href
);

test("buildConversationTurns parses speaker-prefixed transcript", () => {
  const turns = demoApi.buildConversationTurns("agent: 您好\\nuser: 是的");

  assert.deepEqual(turns, [
    { turn_id: 1, speaker: "agent", text: "您好" },
    { turn_id: 2, speaker: "user", text: "是的" },
  ]);
});

test("buildCompilePayload trims instruction text", () => {
  const payload = demoApi.buildCompilePayload({
    instructionText: "  请确认收货时间  ",
  });

  assert.deepEqual(payload, {
    instruction_id: "demo_instruction",
    name: "手动试跑任务",
    raw_text: "请确认收货时间",
  });
});

test("buildEvaluationPayload includes parsed turns", () => {
  const payload = demoApi.buildEvaluationPayload(
    { spec_id: "spec_demo" },
    {
      instructionText: "请确认收货时间",
      conversationText: "agent: 您好\\nuser: 今天下午可以",
    },
  );

  assert.equal(payload.spec.spec_id, "spec_demo");
  assert.equal(payload.conversation.turns[1].speaker, "user");
  assert.equal(payload.conversation.turns[1].text, "今天下午可以");
});

test("runEvaluationFlow calls compile then evaluation endpoints", async () => {
  const calls = [];
  const fakeFetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    if (url === "/specs/compile") {
      return {
        ok: true,
        json: async () => ({ spec_id: "spec_compiled" }),
      };
    }
    return {
      ok: true,
      json: async () => ({ run_id: "run_1", overall_score: 88 }),
    };
  };

  const result = await demoApi.runEvaluationFlow(fakeFetch, {
    instructionText: "请确认收货时间",
    conversationText: "agent: 您好\\nuser: 明天下午可以",
  });

  assert.equal(calls[0].url, "/specs/compile");
  assert.equal(calls[1].url, "/evaluations/run");
  assert.equal(result.run_id, "run_1");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/web/demo_api.test.mjs`

Expected: FAIL with `Cannot find module 'app/web/static/demo-api.js'`

- [ ] **Step 3: Implement transcript parsing and API flow helpers**

```javascript
// app/web/static/demo-api.js
export function buildConversationTurns(conversationText) {
  return conversationText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [speakerPart, ...rest] = line.split(":");
      const speaker = speakerPart.trim().toLowerCase();
      const text = rest.join(":").trim();
      return {
        turn_id: index + 1,
        speaker: speaker === "user" ? "user" : "agent",
        text,
      };
    });
}

export function buildCompilePayload({ instructionText }) {
  return {
    instruction_id: "demo_instruction",
    name: "手动试跑任务",
    raw_text: instructionText.trim(),
  };
}

export function buildEvaluationPayload(spec, state) {
  return {
    spec,
    conversation: {
      conversation_id: "demo_conversation",
      instruction_id: "demo_instruction",
      turns: buildConversationTurns(state.conversationText),
    },
  };
}

export async function runEvaluationFlow(fetchImpl, state) {
  const compileResponse = await fetchImpl("/specs/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildCompilePayload(state)),
  });
  if (!compileResponse.ok) {
    throw new Error("compile request failed");
  }
  const spec = await compileResponse.json();

  const evaluationResponse = await fetchImpl("/evaluations/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildEvaluationPayload(spec, state)),
  });
  if (!evaluationResponse.ok) {
    throw new Error("evaluation request failed");
  }
  return evaluationResponse.json();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/web/demo_api.test.mjs`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/static/demo-api.js tests/web/demo_api.test.mjs
git commit -m "feat: add demo api helpers and evaluation flow"
```

---

### Task 5: Render summary cards, accordions, loading, and export behavior

**Files:**
- Modify: `app/web/static/demo-view.js`
- Test: `tests/web/demo_view.test.mjs`

- [ ] **Step 1: Write the failing view helper test**

```javascript
// tests/web/demo_view.test.mjs
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const view = await import(
  pathToFileURL(path.resolve("app/web/static/demo-view.js")).href
);

test("buildScoreCards maps dimension scores into dashboard cards", () => {
  const cards = view.buildScoreCards({
    dimension_scores: {
      flow_following: 0.92,
      slot_collection: 0.95,
      explanation_quality: 0.78,
      task_focus: 0.84,
    },
  });

  assert.equal(cards.length, 4);
  assert.equal(cards[0].title, "流程遵循");
  assert.equal(cards[0].value, 92);
});

test("buildAccordionSections returns evidence, rules, judge, and raw json", () => {
  const sections = view.buildAccordionSections({
    evidence_items: [{ quote: "您好，请问是张先生吗？", linked_decision: "required_steps" }],
    rule_results: [{ rule_id: "required_steps", passed: true, reason: "all required steps found" }],
    judge_results: [{ dimension_id: "task_focus", score: 0.84, reason: "rubric hit" }],
    run_id: "run_demo",
    spec_id: "spec_demo",
    confidence: 0.9,
  });

  assert.equal(sections.evidence.length, 1);
  assert.equal(sections.rules[0].title, "required_steps");
  assert.equal(sections.judge[0].title, "task_focus");
  assert.match(sections.rawJson, /run_demo/);
});

test("buildInputPanelHtml exposes action hooks for browser binding", () => {
  const markup = view.buildInputPanelHtml({
    mode: "preset",
    activePresetId: "delivery_time",
    instructionText: "请确认收货时间",
    conversationText: "agent: 您好",
    status: "idle",
    errorMessage: "",
  });

  assert.match(markup, /id="run-evaluation-button"/);
  assert.match(markup, /id="reset-demo-button"/);
  assert.match(markup, /id="status-banner"/);
});

test("buildExportFilename uses the run id", () => {
  assert.equal(view.buildExportFilename("run_demo"), "evaluation-run_demo.json");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/web/demo_view.test.mjs`

Expected: FAIL because the view helpers do not exist yet

- [ ] **Step 3: Implement rendering helpers and browser bootstrap**

```javascript
// app/web/static/demo-view.js
import { runEvaluationFlow } from "./demo-api.js";
import { PRESET_CASES, applyPreset, createInitialState, switchMode } from "./demo-data.js";

export function buildScoreCards(result) {
  const labels = {
    flow_following: "流程遵循",
    slot_collection: "槽位收集",
    explanation_quality: "解释充分性",
    task_focus: "任务聚焦度",
  };
  return Object.entries(result.dimension_scores ?? {}).map(([key, value]) => ({
    key,
    title: labels[key] ?? key,
    value: Math.round(value * 100),
  }));
}

export function buildAccordionSections(result) {
  return {
    evidence: (result.evidence_items ?? []).map((item) => ({
      title: item.linked_decision,
      body: item.quote,
    })),
    rules: (result.rule_results ?? []).map((item) => ({
      title: item.rule_id,
      body: `${item.passed ? "通过" : "未通过"}：${item.reason}`,
    })),
    judge: (result.judge_results ?? []).map((item) => ({
      title: item.dimension_id,
      body: `${Math.round(item.score * 100)} 分：${item.reason}`,
    })),
    rawJson: JSON.stringify(
      {
        run_id: result.run_id,
        spec_id: result.spec_id,
        confidence: result.confidence,
      },
      null,
      2,
    ),
  };
}

export function buildExportFilename(runId) {
  return `evaluation-${runId}.json`;
}

export function buildInputPanelHtml(state) {
  const presetButtons = PRESET_CASES.map(
    (item) => `
      <button
        type="button"
        class="preset-button${item.id === state.activePresetId ? " is-active" : ""}"
        data-preset-id="${item.id}">
        ${item.label}
      </button>
    `,
  ).join("");

  return `
    <section class="panel">
      <div class="section-header">
        <h2>输入区</h2>
      </div>
      <div class="mode-toggle">
        <button id="mode-preset" type="button"${state.mode === "preset" ? ' data-active="true"' : ""}>预置案例</button>
        <button id="mode-manual" type="button"${state.mode === "manual" ? ' data-active="true"' : ""}>手动试跑</button>
      </div>
      <label class="field-label" for="instruction-input">任务指令</label>
      <textarea id="instruction-input" class="text-input">${state.instructionText}</textarea>
      <label class="field-label" for="conversation-input">对话转写</label>
      <textarea id="conversation-input" class="text-input transcript-input">${state.conversationText}</textarea>
      <div class="input-actions">
        <button id="run-evaluation-button" type="button">运行评估</button>
        <button id="reset-demo-button" type="button">重置</button>
      </div>
    </section>
    <section class="panel">
      <div class="section-header">
        <h2>案例切换</h2>
      </div>
      <div class="preset-list">${presetButtons}</div>
    </section>
    <section id="status-banner" class="status-banner">${state.status === "error" ? state.errorMessage : "就绪"}</section>
  `;
}

function renderInputPanel(documentRef, state) {
  const panel = documentRef.getElementById("demo-input-panel");
  panel.innerHTML = buildInputPanelHtml(state);
}

function renderResultPanel(documentRef, state) {
  const result = state.lastResult ?? {
    overall_score: 0,
    hard_fail: false,
    needs_review: false,
    confidence: 0,
    summary: "等待运行",
    dimension_scores: {},
    evidence_items: [],
    rule_results: [],
    judge_results: [],
    run_id: "pending",
    spec_id: "pending",
  };

  documentRef.getElementById("summary-score").textContent = String(result.overall_score ?? 0);
  documentRef.getElementById("summary-confidence").textContent = `置信度 ${Math.round((result.confidence ?? 0) * 100)}%`;
  documentRef.getElementById("summary-headline").textContent = result.summary;
  documentRef.getElementById("summary-review-flag").textContent = result.needs_review ? "建议人工复核" : "无需人工复核";

  documentRef.getElementById("scorecard-grid").innerHTML = buildScoreCards(result)
    .map((item) => `<article class="scorecard-item"><p>${item.title}</p><strong>${item.value}</strong></article>`)
    .join("");

  const sections = buildAccordionSections(result);
  documentRef.getElementById("accordion-evidence").innerHTML = sections.evidence.map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`).join("");
  documentRef.getElementById("accordion-rules").innerHTML = sections.rules.map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`).join("");
  documentRef.getElementById("accordion-judge").innerHTML = sections.judge.map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`).join("");
  documentRef.getElementById("accordion-json").textContent = sections.rawJson;
}

export function bootstrapDemo(documentRef = document, fetchImpl = fetch) {
  let state = createInitialState();

  const syncStateFromInputs = () => {
    state = {
      ...state,
      instructionText: documentRef.getElementById("instruction-input").value,
      conversationText: documentRef.getElementById("conversation-input").value,
    };
  };

  const rerender = () => {
    renderInputPanel(documentRef, state);
    renderResultPanel(documentRef, state);

    documentRef.getElementById("mode-preset").onclick = () => {
      state = switchMode(state, "preset");
      rerender();
    };
    documentRef.getElementById("mode-manual").onclick = () => {
      state = switchMode(state, "manual");
      rerender();
    };

    documentRef.querySelectorAll("[data-preset-id]").forEach((button) => {
      button.onclick = () => {
        state = applyPreset(state, button.dataset.presetId);
        rerender();
      };
    });

    documentRef.getElementById("reset-demo-button").onclick = () => {
      state = createInitialState();
      rerender();
    };

    documentRef.getElementById("run-evaluation-button").onclick = async () => {
      syncStateFromInputs();
      state = { ...state, status: "loading", errorMessage: "" };
      documentRef.getElementById("status-banner").textContent = "评估运行中...";
      try {
        const result = await runEvaluationFlow(fetchImpl, state);
        state = { ...state, status: "success", lastResult: result };
        rerender();
      } catch (error) {
        state = { ...state, status: "error", errorMessage: "运行评估失败，请检查输入格式。" };
        rerender();
      }
    };

    documentRef.getElementById("export-result-button").onclick = () => {
      if (!state.lastResult) return;
      const blob = new Blob([JSON.stringify(state.lastResult, null, 2)], { type: "application/json" });
      const link = documentRef.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = buildExportFilename(state.lastResult.run_id);
      link.click();
      URL.revokeObjectURL(link.href);
    };
  };

  rerender();
}

if (typeof document !== "undefined") {
  bootstrapDemo(document, fetch);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/web/demo_view.test.mjs`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/static/demo-view.js tests/web/demo_view.test.mjs
git commit -m "feat: add demo page rendering and export behavior"
```

---

### Task 6: Polish the visual styling and run the full regression suite

**Files:**
- Modify: `app/web/static/demo.css`
- Test: `tests/api/test_demo_page.py`
- Test: `tests/web/demo_data.test.mjs`
- Test: `tests/web/demo_api.test.mjs`
- Test: `tests/web/demo_view.test.mjs`

- [ ] **Step 1: Polish the CSS for readability and product feel**

```css
/* append to app/web/static/demo.css */
.field-label {
  display: block;
  margin: 14px 0 8px 0;
  color: #66758d;
  font-size: 13px;
  font-weight: 600;
}

.text-input {
  width: 100%;
  min-height: 64px;
  padding: 12px 14px;
  border: 1px solid #d7e0eb;
  border-radius: 12px;
  resize: vertical;
  font: inherit;
  color: var(--text);
  background: #fbfdff;
}

.transcript-input {
  min-height: 180px;
}

.mode-toggle,
.preset-list,
.input-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.preset-list {
  flex-direction: column;
}

.preset-button,
.mode-toggle button {
  border: 1px solid #d7e0eb;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  color: var(--text);
  cursor: pointer;
}

.preset-button.is-active,
.mode-toggle button[data-active="true"] {
  border-color: #a4c9ff;
  background: var(--primary-soft);
  color: #124ca3;
}

.status-banner {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px dashed #cbd8e6;
  color: var(--muted);
}

.scorecard-item {
  padding: 14px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #e4edf7;
}

.scorecard-item p {
  margin: 0 0 8px 0;
  color: var(--muted);
}

.scorecard-item strong {
  font-size: 28px;
  color: #17305a;
}
```

- [ ] **Step 2: Run the full regression suite**

Run: `python -m pytest -v`

Expected: PASS with all existing API and Python tests green

- [ ] **Step 3: Run the frontend module tests**

Run: `node --test tests/web/demo_data.test.mjs tests/web/demo_api.test.mjs tests/web/demo_view.test.mjs`

Expected: PASS

- [ ] **Step 4: Run a live demo smoke check**

Run:

```powershell
$proc = Start-Process python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010' -WorkingDirectory 'E:\1\meituan' -PassThru
Start-Sleep -Seconds 2
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/demo').status)"
Stop-Process -Id $proc.Id
```

Expected: print `200`

- [ ] **Step 5: Commit**

```bash
git add app/web/static/demo.css tests/web
git commit -m "test: add regression coverage for demo web page"
```

---

## Self-Review Checklist

- Spec coverage:
  - 产品化单页 dashboard：Task 2
  - 预置案例 + 手动试跑：Task 3
  - 复用 `/specs/compile` 与 `/evaluations/run`：Task 4
  - Accordion 技术细节区：Task 2, Task 5
  - 导出结果与状态反馈：Task 5
  - 宽屏铺满与响应式：Task 2, Task 6
- Placeholder scan: 本计划未使用任何占位符式描述。
- Type consistency:
  - `createInitialState`, `applyPreset`, `switchMode` 定义在 `demo-data.js`，后续 `demo-view.js` 直接复用这些名称。
  - `buildConversationTurns`, `buildCompilePayload`, `buildEvaluationPayload`, `runEvaluationFlow` 定义在 `demo-api.js`，后续 `demo-view.js` 只调用这些接口。
  - `buildScoreCards`, `buildAccordionSections`, `buildExportFilename`, `bootstrapDemo` 均定义在 `demo-view.js` 并在视图测试中验证。
