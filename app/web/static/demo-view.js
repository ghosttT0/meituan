import {
  checkModelConnection,
  fetchModelList,
  runEvaluationFlow,
  runSimulationFlow,
} from "./demo-api.js";
import {
  PRESET_CASES,
  applyPreset,
  applyScenarioToState,
  createInitialState,
  getPresetById,
  switchMode,
  switchRunMode,
} from "./demo-data.js";

export { PRESET_CASES, applyPreset, applyScenarioToState, createInitialState, getPresetById, switchMode, switchRunMode };

const RULE_LABELS = {
  required_steps: "必做步骤",
  required_slots: "必填信息",
  forbidden_actions: "禁止项",
};

const SCENARIO_RULE_LABELS = {
  scenario_faq_grounding: "FAQ知识点命中",
  scenario_busy_focus: "忙碌场景聚焦",
  scenario_scope_fallback: "超纲场景兜底",
  scenario_hesitant_clarity: "犹豫场景解释清晰度",
};

const DIMENSION_LABELS = {
  task_focus: "任务聚焦度",
  explanation_quality: "解释充分性",
};

const PROFILE_LABELS = {
  random: "随机匹配",
  cooperative: "配合型",
  hesitant: "犹豫型",
  rejecting: "拒绝型",
  busy: "忙碌型",
  interrupting: "打断型",
  questioning: "追问型",
};

const MODEL_CONFIG_STORAGE_KEY = "demoModelConfig";

export function loadModelConfigFromStorage(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(MODEL_CONFIG_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveModelConfigToStorage(modelConfig, storage = globalThis.localStorage) {
  storage?.setItem(MODEL_CONFIG_STORAGE_KEY, JSON.stringify(modelConfig));
}

export function mergeModelConfigIntoState(state, modelConfig) {
  return {
    ...state,
    modelConfig,
    simulationConfig: {
      ...state.simulationConfig,
      adapterType: modelConfig.apiUrl ? "http" : state.simulationConfig.adapterType,
      endpoint: modelConfig.apiUrl || state.simulationConfig.endpoint,
    },
  };
}

export function buildScoreCards(result) {
  const labels = {
    flow_following: "流程遵循",
    slot_collection: "槽位收集",
    explanation_quality: "解释充分性",
    task_focus: "任务聚焦度",
  };
  const modeLabels = {
    single: "单评委",
    dual: "双评委",
    dual_arbitration: "双评委 + 仲裁",
  };
  const cards = Object.entries(result.dimension_scores ?? {}).map(([key, value]) => ({
    key,
    title: labels[key] ?? key,
    value: Math.round(value * 100),
  }));
  if (result.evaluation_mode) {
    cards.push({
      key: "evaluation_mode",
      title: "评分模式",
      value: modeLabels[result.evaluation_mode] ?? result.evaluation_mode,
    });
  }
  if (result.panel_results?.length) {
    cards.push({
      key: "panel_count",
      title: "主评委",
      value: result.panel_results.length,
    });
  }
  if (typeof result.arbitration_records?.length === "number") {
    cards.push({
      key: "arbitration_count",
      title: "仲裁次数",
      value: result.arbitration_records.length,
    });
  }
  return cards;
}

export function buildSimulationCards(result) {
  const cards = [
    { title: "测试场景", value: result.scenario_label ?? result.scenario_key ?? "-" },
    { title: "场景重点", value: result.scenario_focus?.[0] ?? "-" },
    {
      title: "场景摘要",
      value: result.scenario_summary ?? result.scenario_diagnosis?.[0] ?? "-",
      emphasis: true,
    },
    { title: "模拟画像", value: PROFILE_LABELS[result.profile_id] ?? result.profile_id ?? "-" },
    { title: "用户生成", value: result.generation_mode === "ai" ? "AI生成" : "模板兜底" },
    { title: "助手来源", value: result.adapter_mode === "http" ? "真实模型接口" : "Mock演示" },
    { title: "结束原因", value: result.termination_reason ?? "-" },
    { title: "状态步数", value: String((result.state_trace ?? []).length) },
  ];
  if (result.batch_mode) {
    cards.push({ title: "批量运行", value: `${result.batch_count ?? 1} 次` });
    cards.push({ title: "随机种子", value: String(result.random_seed ?? "-") });
  }
  return cards;
}

export function buildAccordionSections(result) {
  const roleLabels = {
    task_alignment: "任务对齐",
    experience_risk: "体验与风险",
    arbitrator: "仲裁评委",
    consensus: "合议结果",
  };
  const allRules = result.rule_results ?? [];
  const scenarioRuleResults = allRules.filter((item) => item.rule_id?.startsWith("scenario_"));
  const normalRuleResults = allRules.filter((item) => !item.rule_id?.startsWith("scenario_"));
  const panelJudgeSections = (result.panel_results ?? []).map((panel) => {
    const dimensionLines = (panel.dimension_results ?? []).map((item) => {
      const label = DIMENSION_LABELS[item.dimension_id] ?? item.dimension_id;
      return `[${panel.judge_id}] ${label}: ${Math.round((item.score ?? 0) * 100)} 分 / ${item.reason ?? "-"}`;
    });
    const scenarioLines = (panel.scenario_rule_results ?? []).map((item) => {
      const label = SCENARIO_RULE_LABELS[item.rule_id] ?? item.rule_id;
      return `[${panel.judge_id}] ${label}: ${item.passed ? "通过" : "未通过"} / ${item.reason ?? "-"}`;
    });
    return {
      title: `评委 ${panel.judge_id}`,
      body: [
        `角色：${roleLabels[panel.judge_role] ?? panel.judge_role ?? "-"}`,
        ...dimensionLines,
        ...scenarioLines,
      ].join("<br />"),
    };
  });
  const arbitrationSections = (result.arbitration_records ?? []).map((item, index) => ({
    title: `仲裁记录 ${index + 1}`,
    body: [
      `争议对象：${item.target_type ?? "-"}/${item.target_id ?? "-"}`,
      `仲裁人：${item.resolved_by ?? "-"}`,
      `分歧差值：${item.score_gap ?? 0}`,
      `原因：${item.reason ?? "-"}`,
    ].join("<br />"),
  }));
  const simulation = result.state_trace
    ? [
        ...(result.scenario_label || result.user_goal
          ? [
              { title: "测试场景", body: result.scenario_label ?? result.scenario_key ?? "-" },
              { title: "用户目标", body: result.user_goal ?? "-" },
              ...(result.scenario_focus?.length
                ? [{ title: "场景重点", body: result.scenario_focus.join("<br />") }]
                : []),
              ...(result.scenario_diagnosis?.length
                ? [{ title: "场景诊断", body: result.scenario_diagnosis.join("<br />") }]
                : []),
              ...(result.batch_mode
                ? [
                    { title: "批量运行", body: `本次共运行 ${result.batch_count ?? 1} 次` },
                    { title: "画像分布", body: JSON.stringify(result.profile_distribution ?? {}, null, 2) },
                    { title: "随机种子", body: String(result.random_seed ?? "-") },
                  ]
                : []),
            ]
          : []),
        { title: "状态轨迹", body: (result.state_trace ?? []).join(" → ") },
        {
          title: "模拟对话",
          body: (result.turns ?? []).map((turn) => `${turn.speaker}: ${turn.text}`).join("<br />"),
        },
        ...(result.debug_logs?.length
          ? [{ title: "模拟日志", body: result.debug_logs.join("<br />") }]
          : []),
      ]
    : [];

  return {
    evidence: (result.evidence_items ?? []).map((item) => ({
      title: item.linked_decision,
      body: item.quote,
    })),
    rules: normalRuleResults.map((item) => ({
      title: RULE_LABELS[item.rule_id] ?? item.rule_id,
      body: `${item.passed ? "通过" : "未通过"}：${item.reason}`,
    })),
    scenarioRules: scenarioRuleResults.map((item) => ({
      title: SCENARIO_RULE_LABELS[item.rule_id] ?? item.rule_id,
      body: `${item.passed ? "通过" : "未通过"}：${item.reason}`,
    })),
    judge: [
      ...(result.judge_results ?? []).map((item) => ({
        title: DIMENSION_LABELS[item.dimension_id] ?? item.dimension_id,
        body: `${Math.round(item.score * 100)} 分：${item.reason}`,
      })),
      ...panelJudgeSections,
      ...arbitrationSections,
    ],
    simulation,
    rawJson: JSON.stringify(
      {
        run_id: result.run_id,
        spec_id: result.spec_id,
        confidence: result.confidence,
        simulation_id: result.simulation_id,
        panel_count: (result.panel_results ?? []).length,
        arbitration_count: (result.arbitration_records ?? []).length,
      },
      null,
      2,
    ),
  };
}

export function buildExportFilename(runId) {
  return `evaluation-${runId}.json`;
}

export function buildModelConfigModalHtml(modelConfig) {
  const modelOptions = (modelConfig.modelOptions ?? [])
    .map(
      (item) =>
        `<option value="${item}"${item === modelConfig.model ? " selected" : ""}>${item}</option>`,
    )
    .join("");

  return `
    <div class="modal-backdrop">
      <section class="modal-card">
        <div class="section-header modal-header">
          <h2>API 配置列表</h2>
          <button id="close-model-config-button" type="button" class="ghost-button">关闭</button>
        </div>
        <div class="model-config-block">
          <p class="config-title">配置 1（使用中）</p>
          <label class="field-label" for="model-config-name">名称（选填）</label>
          <input id="model-config-name" class="text-input" type="text" value="${modelConfig.name ?? ""}" />
          <label class="field-label" for="model-config-api-url">API 地址</label>
          <input id="model-config-api-url" class="text-input" type="text" value="${modelConfig.apiUrl ?? ""}" />
          <label class="field-label" for="model-config-api-key">API 密钥</label>
          <div class="api-key-row">
            <input id="model-config-api-key" class="text-input" type="password" value="${modelConfig.apiKey ?? ""}" />
            <button id="toggle-model-config-key" type="button" class="icon-button">显示</button>
          </div>
          <label class="field-label" for="model-config-model">模型名称</label>
          <div class="model-row">
            <input id="model-config-model" class="text-input" type="text" value="${modelConfig.model ?? ""}" list="model-options-list" />
            <button id="fetch-model-list-button" type="button" class="ghost-button">获取</button>
          </div>
          <datalist id="model-options-list">${modelOptions}</datalist>
          <div class="mode-toggle">
            <button id="check-model-button" type="button">测试连接</button>
            <button id="save-model-config-button" type="button">保存配置</button>
          </div>
          <section id="model-check-result" class="status-banner">${modelConfig.lastCheck?.message ?? "尚未检测模型连接"}</section>
        </div>
      </section>
    </div>
  `;
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
  const activePreset = getPresetById(state.activePresetId);
  const scenarioOptions = activePreset?.scenarioOptions ?? [];

  const simulationControls = `
      <section class="panel simulation-panel">
        <div class="section-header">
          <h2>模拟配置</h2>
        </div>
        <label class="field-label" for="simulation-adapter-select">被测模型来源</label>
        <select id="simulation-adapter-select" class="text-input">
          <option value="http"${state.simulationConfig.adapterType === "http" ? " selected" : ""}>真实模型接口</option>
          <option value="mock"${state.simulationConfig.adapterType === "mock" ? " selected" : ""}>Mock演示</option>
        </select>
        <label class="field-label" for="simulation-endpoint-input">模型接口地址</label>
        <input id="simulation-endpoint-input" class="text-input" type="text" value="${state.simulationConfig.endpoint ?? ""}" placeholder="http://你的模型接口地址" />
        <label class="field-label" for="simulation-profile-select">用户画像</label>
        <select id="simulation-profile-select" class="text-input">
          ${["random", "cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning"]
            .map(
              (item) =>
                `<option value="${item}"${item === state.simulationConfig.profileId ? " selected" : ""}>${PROFILE_LABELS[item]}</option>`,
            )
            .join("")}
        </select>
        ${
          state.simulationConfig.profileId === "random"
            ? `<p class="dialogue-note profile-random-note">当前已启用随机匹配：每次运行会在 6 类用户画像中随机抽取 1 类，但主分支仍按测试场景约束。</p>`
            : ""
        }
        <label class="field-label" for="simulation-scenario-select">测试场景</label>
        <select id="simulation-scenario-select" class="text-input">
          ${scenarioOptions
            .map(
              (item) =>
                `<option value="${item.key}"${item.key === state.simulationConfig.scenarioKey ? " selected" : ""}>${item.label}</option>`,
            )
            .join("")}
        </select>
        <label class="field-label" for="simulation-branch-select">主分支</label>
        <select id="simulation-branch-select" class="text-input">
          ${["cooperative", "hesitant", "rejecting", "busy", "interrupting", "questioning"]
            .map(
              (item) =>
                `<option value="${item}"${item === state.simulationConfig.primaryBranch ? " selected" : ""}>${PROFILE_LABELS[item]}</option>`,
            )
            .join("")}
        </select>
        <label class="field-label" for="simulation-batch-runs">运行次数</label>
        <input id="simulation-batch-runs" class="text-input" type="number" value="${state.simulationConfig.batchRuns ?? 1}" min="1" max="10" />
        <label class="field-label" for="simulation-random-seed">随机种子</label>
        <input id="simulation-random-seed" class="text-input" type="number" value="${state.simulationConfig.randomSeed ?? 2026}" min="1" />
        <label class="field-label" for="simulation-max-turns">最大轮次</label>
        <input id="simulation-max-turns" class="text-input" type="number" value="${state.simulationConfig.maxTurns}" min="2" max="12" />
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
      <label class="field-label" for="evaluation-mode-select">评分机制</label>
      <select id="evaluation-mode-select" class="text-input">
        <option value="single"${state.evaluationMode === "single" ? " selected" : ""}>单评委</option>
        <option value="dual"${state.evaluationMode === "dual" ? " selected" : ""}>双评委</option>
        <option value="dual_arbitration"${state.evaluationMode === "dual_arbitration" ? " selected" : ""}>双评委 + 仲裁</option>
      </select>
      <label class="field-label" for="instruction-input">系统提示词（任务指令）</label>
      <textarea id="instruction-input" class="text-input">${state.instructionText}</textarea>
      <p class="dialogue-note">当前页面仅保留模拟模式，对话将由系统自动生成并在右侧以聊天形式展示。</p>
      <div class="input-actions">
        <button id="run-evaluation-button" type="button">运行模拟</button>
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

export function buildSimulationDialogueHtml(turns) {
  if (!turns?.length) {
    return `
      <h2 class="dialogue-title">模拟对话</h2>
      <p class="simulation-placeholder">运行模拟后，这里会以对话气泡形式展示“模拟用户”与“被测模型”的完整往返过程。</p>
    `;
  }

  const items = turns
    .map((turn) => {
      const isUser = turn.speaker === "user";
      return `
        <article class="chat-message ${isUser ? "user" : "agent"}">
          <div class="chat-bubble">
            <span class="chat-role">${isUser ? "模拟用户" : "被测模型"}</span>
            <p class="chat-text">${turn.text}</p>
          </div>
        </article>
      `;
    })
    .join("");

  return `
    <h2 class="dialogue-title">对话回放</h2>
    <div class="chat-thread-scroll">
      <div class="chat-thread">${items}</div>
    </div>
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
  const simulationCards =
    state.runMode === "simulation" && state.lastResult ? buildSimulationCards(state.lastResult) : [];
  documentRef.getElementById("scorecard-grid").innerHTML = [
    ...scoreCards.map(
      (item) => `<article class="scorecard-item"><p>${item.title}</p><strong>${item.value}</strong></article>`,
    ),
    ...simulationCards.map(
      (item) =>
        `<article class="scorecard-item simulation-card${item.emphasis ? " summary-highlight" : ""}"><p>${item.title}</p><strong>${item.value}</strong></article>`,
    ),
  ].join("");

  const sections = buildAccordionSections(result);
  documentRef.getElementById("accordion-evidence").innerHTML = sections.evidence
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-rules").innerHTML = sections.rules
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-scenario-rules").innerHTML = sections.scenarioRules
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-judge").innerHTML = [...sections.judge, ...sections.simulation]
    .map((item) => `<article><strong>${item.title}</strong><p>${item.body}</p></article>`)
    .join("");
  documentRef.getElementById("accordion-json").textContent = sections.rawJson;

  const dialoguePanel = documentRef.getElementById("simulation-dialogue-panel");
  dialoguePanel.innerHTML = buildSimulationDialogueHtml(state.lastResult?.turns ?? []);

  const resultDetailsPanel = documentRef.getElementById("result-details-panel");
  const resultsButton = documentRef.getElementById("view-mode-results");
  const conversationButton = documentRef.getElementById("view-mode-conversation");
  const conversationEnabled = state.runMode === "simulation";
  resultsButton.dataset.active = state.rightPanelMode === "results" ? "true" : "false";
  conversationButton.dataset.active = state.rightPanelMode === "conversation" ? "true" : "false";
  conversationButton.disabled = !conversationEnabled;
  resultDetailsPanel.style.display = state.rightPanelMode === "results" ? "grid" : "none";
  dialoguePanel.style.display = state.rightPanelMode === "conversation" ? "block" : "none";
}

function renderModelConfigModal(documentRef, state) {
  const modal = documentRef.getElementById("model-config-modal");
  modal.innerHTML = state.modelConfigOpen ? buildModelConfigModalHtml(state.modelConfig) : "";
  modal.hidden = !state.modelConfigOpen;
}

function syncStateFromInputs(documentRef, state) {
  const next = {
    ...state,
    runMode: "simulation",
    evaluationMode: documentRef.getElementById("evaluation-mode-select").value,
    instructionText: documentRef.getElementById("instruction-input").value,
    conversationText: state.conversationText,
  };

  if (next.runMode === "simulation") {
    const selectedScenarioKey = documentRef.getElementById("simulation-scenario-select").value;
    let scenarioSynced = applyScenarioToState(next, selectedScenarioKey);
    next.simulationConfig = {
      ...scenarioSynced.simulationConfig,
      profileId: documentRef.getElementById("simulation-profile-select").value,
      primaryBranch: documentRef.getElementById("simulation-branch-select").value,
      scenarioKey: selectedScenarioKey,
      batchRuns: Number(documentRef.getElementById("simulation-batch-runs").value),
      randomSeed: Number(documentRef.getElementById("simulation-random-seed").value),
      maxTurns: Number(documentRef.getElementById("simulation-max-turns").value),
      adapterType: documentRef.getElementById("simulation-adapter-select").value,
      endpoint: documentRef.getElementById("simulation-endpoint-input").value.trim(),
    };
  }

  return next;
}

export function bootstrapDemo(documentRef = document, fetchImpl = fetch, storage = globalThis.localStorage) {
  const initial = createInitialState();
  const savedModelConfig = loadModelConfigFromStorage(storage);
  let state = mergeModelConfigIntoState(
    initial,
    { ...initial.modelConfig, ...(savedModelConfig ?? {}) },
  );

  const bindModelModal = () => {
    if (!state.modelConfigOpen) return;

    documentRef.getElementById("close-model-config-button").onclick = () => {
      state = { ...state, modelConfigOpen: false };
      rerender();
    };

    documentRef.getElementById("toggle-model-config-key").onclick = () => {
      const input = documentRef.getElementById("model-config-api-key");
      input.type = input.type === "password" ? "text" : "password";
    };

    documentRef.getElementById("save-model-config-button").onclick = () => {
      const nextModelConfig = {
        ...state.modelConfig,
        name: documentRef.getElementById("model-config-name").value.trim(),
        apiUrl: documentRef.getElementById("model-config-api-url").value.trim(),
        apiKey: documentRef.getElementById("model-config-api-key").value.trim(),
        model: documentRef.getElementById("model-config-model").value.trim(),
      };
      state = mergeModelConfigIntoState(state, nextModelConfig);
      saveModelConfigToStorage(state.modelConfig, storage);
      rerender();
    };

    documentRef.getElementById("fetch-model-list-button").onclick = async () => {
      const draft = {
        ...state.modelConfig,
        name: documentRef.getElementById("model-config-name").value.trim(),
        apiUrl: documentRef.getElementById("model-config-api-url").value.trim(),
        apiKey: documentRef.getElementById("model-config-api-key").value.trim(),
        model: documentRef.getElementById("model-config-model").value.trim(),
      };
      try {
        const result = await fetchModelList(fetchImpl, draft);
        state = mergeModelConfigIntoState(state, {
          ...draft,
          modelOptions: result.models ?? [],
          lastCheck: {
            message: result.ok
              ? `已获取 ${result.models.length} 个模型`
              : result.error_message,
          },
        });
        saveModelConfigToStorage(state.modelConfig, storage);
        rerender();
      } catch (_error) {
        state = mergeModelConfigIntoState(state, {
          ...draft,
          lastCheck: { message: "获取模型列表失败" },
        });
        rerender();
      }
    };

    documentRef.getElementById("check-model-button").onclick = async () => {
      const draft = {
        ...state.modelConfig,
        name: documentRef.getElementById("model-config-name").value.trim(),
        apiUrl: documentRef.getElementById("model-config-api-url").value.trim(),
        apiKey: documentRef.getElementById("model-config-api-key").value.trim(),
        model: documentRef.getElementById("model-config-model").value.trim(),
      };
      try {
        const result = await checkModelConnection(fetchImpl, draft);
        state = mergeModelConfigIntoState(state, {
          ...draft,
          lastCheck: {
            message: result.ok
              ? `检测成功：${result.protocol_type} / ${result.reply_preview}`
              : result.error_message,
          },
        });
        saveModelConfigToStorage(state.modelConfig, storage);
        rerender();
      } catch (_error) {
        state = mergeModelConfigIntoState(state, {
          ...draft,
          lastCheck: { message: "检测模型失败" },
        });
        rerender();
      }
    };
  };

  const rerender = () => {
    renderInputPanel(documentRef, state);
    renderResultPanel(documentRef, state);
    renderModelConfigModal(documentRef, state);

    documentRef.getElementById("open-model-config-button").onclick = () => {
      state = { ...state, modelConfigOpen: true };
      rerender();
    };

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

    documentRef.getElementById("view-mode-results").onclick = () => {
      state = { ...state, rightPanelMode: "results" };
      rerender();
    };

    documentRef.getElementById("view-mode-conversation").onclick = () => {
      state = { ...state, rightPanelMode: "conversation" };
      rerender();
    };

    documentRef.querySelectorAll("[data-preset-id]").forEach((button) => {
      button.onclick = () => {
        state = applyPreset(state, button.dataset.presetId);
        rerender();
      };
    });

    const scenarioSelect = documentRef.getElementById("simulation-scenario-select");
    if (scenarioSelect) {
      scenarioSelect.onchange = () => {
        state = applyScenarioToState(state, scenarioSelect.value);
        rerender();
      };
    }

    documentRef.getElementById("reset-demo-button").onclick = () => {
      state = {
        ...createInitialState(),
        modelConfig: state.modelConfig,
        modelConfigOpen: false,
      };
      rerender();
    };

    documentRef.getElementById("run-evaluation-button").onclick = async () => {
      state = syncStateFromInputs(documentRef, state);
      state = { ...state, status: "loading", errorMessage: "" };
      documentRef.getElementById("status-banner").textContent =
        state.runMode === "simulation" ? "模拟运行中..." : "评估运行中...";
      try {
        const result = await runSimulationFlow(fetchImpl, state, state.simulationConfig);
        state = {
          ...state,
          status: "success",
          lastResult: result,
          rightPanelMode: state.runMode === "simulation" ? "conversation" : "results",
        };
        rerender();
      } catch (_error) {
        state = {
          ...state,
          status: "error",
          errorMessage:
            state.runMode === "simulation" ? "运行模拟失败，请检查配置。" : "运行评估失败，请检查输入格式。",
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

    bindModelModal();
  };

  rerender();
}

if (typeof document !== "undefined") {
  bootstrapDemo(document, fetch);
}
