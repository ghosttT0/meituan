import { runEvaluationFlow } from "./demo-api.js";
import { PRESET_CASES, applyPreset, createInitialState, switchMode } from "./demo-data.js";

export { PRESET_CASES, applyPreset, createInitialState, switchMode };

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
  documentRef.getElementById("accordion-evidence").innerHTML = sections.evidence
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-rules").innerHTML = sections.rules
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-judge").innerHTML = sections.judge
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
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

    documentRef.getElementById("preset-mode-button").onclick = () => {
      state = switchMode(state, "preset");
      rerender();
    };

    documentRef.getElementById("manual-mode-button").onclick = () => {
      state = switchMode(state, "manual");
      rerender();
    };

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
      } catch (_error) {
        state = {
          ...state,
          status: "error",
          errorMessage: "运行评估失败，请检查输入格式。",
        };
        rerender();
      }
    };

    documentRef.getElementById("export-result-button").onclick = () => {
      if (!state.lastResult) return;
      const blob = new Blob([JSON.stringify(state.lastResult, null, 2)], {
        type: "application/json",
      });
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
