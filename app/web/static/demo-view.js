import { runEvaluationFlow, runSimulationFlow } from "./demo-api.js";
import {
  PRESET_CASES,
  applyPreset,
  createInitialState,
  switchMode,
  switchRunMode,
} from "./demo-data.js";

export { PRESET_CASES, applyPreset, createInitialState, switchMode, switchRunMode };

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

export function buildSimulationCards(result) {
  return [
    { title: "模拟画像", value: result.profile_id ?? "-" },
    { title: "结束原因", value: result.termination_reason ?? "-" },
    { title: "状态步数", value: String((result.state_trace ?? []).length) },
  ];
}

export function buildAccordionSections(result) {
  const simulation = result.state_trace
    ? [
        { title: "state_trace", body: (result.state_trace ?? []).join(" → ") },
        {
          title: "turns",
          body: (result.turns ?? [])
            .map((turn) => `${turn.speaker}: ${turn.text}`)
            .join("\n"),
        },
      ]
    : [];

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
    simulation,
    rawJson: JSON.stringify(
      {
        run_id: result.run_id,
        spec_id: result.spec_id,
        confidence: result.confidence,
        simulation_id: result.simulation_id,
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

  const simulationControls =
    state.runMode === "simulation"
      ? `
      <section class="panel simulation-panel">
        <div class="section-header">
          <h2>模拟配置</h2>
        </div>
        <div class="mode-toggle">
          <button id="run-mode-evaluation" type="button">评估模式</button>
          <button id="run-mode-simulation" type="button" data-active="true">模拟模式</button>
        </div>
        <label class="field-label" for="simulation-profile-select">用户画像</label>
        <select id="simulation-profile-select" class="text-input">
          ${["cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning"]
            .map(
              (item) =>
                `<option value="${item}"${item === state.simulationConfig.profileId ? " selected" : ""}>${item}</option>`,
            )
            .join("")}
        </select>
        <label class="field-label" for="simulation-branch-select">主分支</label>
        <select id="simulation-branch-select" class="text-input">
          ${["cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning"]
            .map(
              (item) =>
                `<option value="${item}"${item === state.simulationConfig.primaryBranch ? " selected" : ""}>${item}</option>`,
            )
            .join("")}
        </select>
        <label class="field-label" for="simulation-max-turns">最大轮次</label>
        <input id="simulation-max-turns" class="text-input" type="number" value="${state.simulationConfig.maxTurns}" min="2" max="12" />
      </section>
    `
      : `
      <section class="panel simulation-panel">
        <div class="section-header">
          <h2>运行模式</h2>
        </div>
        <div class="mode-toggle">
          <button id="run-mode-evaluation" type="button" data-active="true">评估模式</button>
          <button id="run-mode-simulation" type="button">模拟模式</button>
        </div>
      </section>
    `;

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
        <button id="run-evaluation-button" type="button">${state.runMode === "simulation" ? "运行模拟" : "运行评估"}</button>
        <button id="reset-demo-button" type="button">重置</button>
      </div>
    </section>
    ${simulationControls}
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
  const baseResult = {
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
  const result = state.lastResult?.evaluation
    ? { ...baseResult, ...state.lastResult.evaluation, ...state.lastResult }
    : { ...baseResult, ...(state.lastResult ?? {}) };

  documentRef.getElementById("summary-score").textContent = String(result.overall_score ?? 0);
  documentRef.getElementById("summary-confidence").textContent = `置信度 ${Math.round((result.confidence ?? 0) * 100)}%`;
  documentRef.getElementById("summary-headline").textContent = result.summary ?? result.termination_reason ?? "等待运行";
  documentRef.getElementById("summary-review-flag").textContent = result.needs_review ? "建议人工复核" : "无需人工复核";

  const scoreCards = buildScoreCards(result);
  const simulationCards = state.runMode === "simulation" && state.lastResult ? buildSimulationCards(state.lastResult) : [];
  documentRef.getElementById("scorecard-grid").innerHTML = [
    ...scoreCards.map(
      (item) => `<article class="scorecard-item"><p>${item.title}</p><strong>${item.value}</strong></article>`,
    ),
    ...simulationCards.map(
      (item) => `<article class="scorecard-item simulation-card"><p>${item.title}</p><strong>${item.value}</strong></article>`,
    ),
  ].join("");

  const sections = buildAccordionSections(result);
  documentRef.getElementById("accordion-evidence").innerHTML = sections.evidence
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-rules").innerHTML = sections.rules
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-judge").innerHTML = [
    ...sections.judge,
    ...sections.simulation,
  ]
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-json").textContent = sections.rawJson;
}

function syncStateFromInputs(documentRef, state) {
  const next = {
    ...state,
    instructionText: documentRef.getElementById("instruction-input").value,
    conversationText: documentRef.getElementById("conversation-input").value,
  };

  if (next.runMode === "simulation") {
    next.simulationConfig = {
      ...next.simulationConfig,
      profileId: documentRef.getElementById("simulation-profile-select").value,
      primaryBranch: documentRef.getElementById("simulation-branch-select").value,
      maxTurns: Number(documentRef.getElementById("simulation-max-turns").value),
    };
  }

  return next;
}

export function bootstrapDemo(documentRef = document, fetchImpl = fetch) {
  let state = createInitialState();

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

    documentRef.getElementById("run-mode-evaluation").onclick = () => {
      state = switchRunMode(state, "evaluation");
      rerender();
    };

    documentRef.getElementById("run-mode-simulation").onclick = () => {
      state = switchRunMode(state, "simulation");
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
      state = syncStateFromInputs(documentRef, state);
      state = { ...state, status: "loading", errorMessage: "" };
      documentRef.getElementById("status-banner").textContent =
        state.runMode === "simulation" ? "模拟运行中..." : "评估运行中...";
      try {
        const result =
          state.runMode === "simulation"
            ? await runSimulationFlow(fetchImpl, state, state.simulationConfig)
            : await runEvaluationFlow(fetchImpl, state);
        state = { ...state, status: "success", lastResult: result };
        rerender();
      } catch (_error) {
        state = {
          ...state,
          status: "error",
          errorMessage: state.runMode === "simulation" ? "运行模拟失败，请检查配置。" : "运行评估失败，请检查输入格式。",
        };
        rerender();
      }
    };

    documentRef.getElementById("export-result-button").onclick = () => {
      if (!state.lastResult) return;
      const exportSource = state.lastResult.evaluation ?? state.lastResult;
      const exportId = exportSource.run_id ?? state.lastResult.simulation_id ?? "result";
      const blob = new Blob([JSON.stringify(state.lastResult, null, 2)], {
        type: "application/json",
      });
      const link = documentRef.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = buildExportFilename(exportId);
      link.click();
      URL.revokeObjectURL(link.href);
    };
  };

  rerender();
}

if (typeof document !== "undefined") {
  bootstrapDemo(document, fetch);
}
