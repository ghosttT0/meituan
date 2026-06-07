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
import {
  appendEvaluationHistory,
  buildHistoryPanelHtml,
  clearEvaluationHistory,
  createHistoryEntry,
  loadEvaluationHistory,
  removeEvaluationHistoryItem,
} from "./demo-history.js";

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

export function getScoreLevel(value) {
  if (typeof value !== "number") {
    return "neutral";
  }
  if (value >= 80) {
    return "good";
  }
  if (value >= 60) {
    return "mid";
  }
  return "low";
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
    kind: "dimension",
    title: labels[key] ?? key,
    value: Math.round(value * 100),
  }));
  if (result.evaluation_mode) {
    cards.push({
      key: "evaluation_mode",
      kind: "meta",
      title: "评分模式",
      value: modeLabels[result.evaluation_mode] ?? result.evaluation_mode,
    });
  }
  if (result.panel_results?.length) {
    cards.push({
      key: "panel_count",
      kind: "meta",
      title: "主评委",
      value: String(result.panel_results.length),
    });
  }
  if (typeof result.arbitration_records?.length === "number") {
    cards.push({
      key: "arbitration_count",
      kind: "meta",
      title: "仲裁次数",
      value: String(result.arbitration_records.length),
    });
  }
  return cards;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function buildScorecardHtml(scoreCards, simulationCards = []) {
  const dimensionCards = scoreCards.filter((item) => item.kind === "dimension");
  const metaCards = scoreCards.filter((item) => item.kind === "meta");
  const summaryCard = simulationCards.find((item) => item.emphasis);
  const simulationDetails = simulationCards.filter((item) => !item.emphasis);

  const sections = [];

  if (dimensionCards.length) {
    sections.push(`
      <section class="scorecard-section">
        <h3 class="scorecard-section-title">维度得分</h3>
        <div class="scorecard-dimensions">
          ${dimensionCards
            .map((item) => {
              const level = getScoreLevel(item.value);
              return `<article class="dimension-score" data-level="${level}">
                <span class="dimension-score__label">${escapeHtml(item.title)}</span>
                <span class="dimension-score__value">${escapeHtml(item.value)}</span>
              </article>`;
            })
            .join("")}
        </div>
      </section>
    `);
  }

  if (metaCards.length) {
    sections.push(`
      <section class="scorecard-section scorecard-section--meta">
        <div class="scorecard-meta">
          ${metaCards
            .map(
              (item) =>
                `<span class="meta-item"><em>${escapeHtml(item.title)}</em>${escapeHtml(item.value)}</span>`,
            )
            .join("")}
        </div>
      </section>
    `);
  }

  if (simulationCards.length) {
    sections.push(`
      <section class="scorecard-section">
        <h3 class="scorecard-section-title">模拟信息</h3>
        ${
          summaryCard
            ? `<p class="simulation-summary"><span class="simulation-summary__label">${escapeHtml(summaryCard.title)}</span>${escapeHtml(summaryCard.value)}</p>`
            : ""
        }
        ${
          simulationDetails.length
            ? `<dl class="simulation-details">
                ${simulationDetails
                  .map(
                    (item) =>
                      `<div class="simulation-detail"><dt>${escapeHtml(item.title)}</dt><dd>${escapeHtml(item.value)}</dd></div>`,
                  )
                  .join("")}
              </dl>`
            : ""
        }
      </section>
    `);
  }

  if (!sections.length) {
    return `<p class="scorecard-empty">运行评测后，维度得分与模拟信息会显示在这里。</p>`;
  }

  return `<div class="scorecard-board">${sections.join("")}</div>`;
}

function renderConclusionListSection(title, items, modifier = "") {
  if (!items?.length) {
    return "";
  }
  return `<section class="conclusion-section ${modifier}">
    <h4 class="conclusion-section__title">${escapeHtml(title)}</h4>
    <ul class="conclusion-list">
      ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  </section>`;
}

export function buildConclusionFromText(text) {
  const lines = String(text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return '<p class="conclusion-empty">暂无结论。</p>';
  }

  const sections = [];
  let current = null;

  const pushSection = () => {
    if (!current || !current.items.length) {
      return;
    }
    sections.push(current);
    current = null;
  };

  for (const line of lines) {
    const bulletMatch = line.match(/^[-•]\s*(.+)$/);
    const labeledBulletMatch = line.match(/^\s*[-•]\s*(.+)$/);
    const headingMatch = line.match(/^(主要优点|主要问题|改进建议|各维度得分)[:：]?$/);
    const metricMatch = line.match(/^(.+?)[:：]\s*(.+)$/);

    if (headingMatch) {
      pushSection();
      current = { title: headingMatch[1], items: [], type: "list" };
      continue;
    }

    if (bulletMatch || labeledBulletMatch) {
      if (!current) {
        current = { title: "", items: [], type: "list" };
      }
      current.items.push((bulletMatch ?? labeledBulletMatch)[1]);
      continue;
    }

    if (metricMatch && !line.startsWith("综合评分")) {
      sections.push({ title: metricMatch[1], items: [metricMatch[2]], type: "metric" });
      continue;
    }

    sections.push({ title: "", items: [line], type: "paragraph" });
  }
  pushSection();

  const metrics = sections.filter((item) => item.type === "metric");
  const lists = sections.filter((item) => item.type === "list");
  const paragraphs = sections.filter((item) => item.type === "paragraph");

  return `<div class="conclusion-board">
    ${
      metrics.length
        ? `<div class="conclusion-metrics">
            ${metrics
              .map(
                (item) =>
                  `<div class="conclusion-metric"><span>${escapeHtml(item.title)}</span><strong>${escapeHtml(item.items[0])}</strong></div>`,
              )
              .join("")}
          </div>`
        : ""
    }
    <div class="conclusion-sections">
      ${lists
        .map((item) => {
          const modifier =
            item.title === "主要优点"
              ? "conclusion-section--good"
              : item.title === "主要问题"
                ? "conclusion-section--warn"
                : item.title === "改进建议"
                  ? "conclusion-section--info"
                  : "";
          return renderConclusionListSection(item.title || "详情", item.items, modifier);
        })
        .join("")}
      ${paragraphs
        .map((item) => `<p class="conclusion-paragraph">${escapeHtml(item.items[0])}</p>`)
        .join("")}
    </div>
  </div>`;
}

export function buildConclusionHtml(result) {
  const evaluationSummary = result.evaluation_summary ?? result.evaluation?.evaluation_summary;
  if (evaluationSummary) {
    const metrics = [
      { label: "任务完成度", value: `${Math.round((evaluationSummary.task_success_rate ?? 0) * 100)}%` },
      { label: "对话效率", value: Number(evaluationSummary.efficiency_score ?? 0).toFixed(1) },
      { label: "用户体验", value: Number(evaluationSummary.experience_score ?? 0).toFixed(1) },
      { label: "鲁棒性", value: Number(evaluationSummary.robustness_score ?? 0).toFixed(1) },
    ];
    return `<div class="conclusion-board">
      <div class="conclusion-headline">
        <span class="conclusion-grade">${escapeHtml(evaluationSummary.grade ?? "-")}</span>
        <span class="conclusion-scoreline">综合 ${Number(evaluationSummary.overall_score ?? result.overall_score ?? 0).toFixed(1)} 分</span>
      </div>
      <div class="conclusion-metrics">
        ${metrics
          .map(
            (item) =>
              `<div class="conclusion-metric"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>`,
          )
          .join("")}
      </div>
      <div class="conclusion-sections">
        ${renderConclusionListSection("主要优点", evaluationSummary.key_strengths, "conclusion-section--good")}
        ${renderConclusionListSection("主要问题", evaluationSummary.key_weaknesses, "conclusion-section--warn")}
        ${renderConclusionListSection("改进建议", evaluationSummary.improvement_suggestions, "conclusion-section--info")}
      </div>
    </div>`;
  }

  const text = result.summary ?? result.termination_reason ?? "";
  if (!text || text === "等待运行") {
    return '<p class="conclusion-empty">运行评测后，总体结论会按维度、优缺点与建议分块展示。</p>';
  }

  if (result.hard_fail && text.length < 80) {
    return `<p class="conclusion-alert">${escapeHtml(text)}</p>`;
  }

  return buildConclusionFromText(text);
}

export function getDisplayResult(state) {
  if (state.viewingHistoryId) {
    const entry = state.history.find((item) => item.id === state.viewingHistoryId);
    return entry?.result ?? state.lastResult;
  }
  return state.lastResult;
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
        <button id="run-evaluation-button" type="button"${state.status === "loading" ? " disabled" : ""}>
          ${state.status === "loading" ? "运行中..." : "运行模拟"}
        </button>
        <button id="reset-demo-button" type="button"${state.status === "loading" ? " disabled" : ""}>重置</button>
      </div>
    </section>
    ${simulationControls}
    <section class="panel">
      <div class="section-header">
        <h2>案例切换</h2>
      </div>
      <div class="preset-list">${presetButtons}</div>
    </section>
    <section id="status-banner" class="status-banner${
      state.status === "loading" ? " status-banner--loading" : state.status === "error" ? " status-banner--error" : ""
    }">${
      state.status === "error"
        ? state.errorMessage
        : state.status === "loading"
          ? getLoadingBannerContent(state)?.title ?? "运行中..."
          : "就绪"
    }</section>
  `;
}

export function getLoadingBannerContent(state) {
  if (state.status !== "loading") {
    return null;
  }
  if (state.runMode === "simulation") {
    return {
      title: "正在模拟对话与评测",
      detail: "系统正在生成用户回复、调用被测模型并提交评委打分，通常需要几十秒，请稍候。",
    };
  }
  return {
    title: "正在运行评测",
    detail: "正在编译任务指令并执行评测流程，请稍候。",
  };
}

function renderLoadingBanner(documentRef, state) {
  const banner = documentRef.getElementById("demo-loading-banner");
  const shell = documentRef.getElementById("demo-root");
  if (!banner) {
    return;
  }

  const content = getLoadingBannerContent(state);
  const isLoading = Boolean(content);
  banner.hidden = !isLoading;
  shell?.classList.toggle("is-loading", isLoading);

  if (!content) {
    return;
  }

  const title = documentRef.getElementById("loading-banner-title");
  const detail = documentRef.getElementById("loading-banner-detail");
  if (title) {
    title.textContent = content.title;
  }
  if (detail) {
    detail.textContent = content.detail;
  }

  const runButton = documentRef.getElementById("run-evaluation-button");
  if (runButton) {
    runButton.disabled = true;
  }
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

function renderHistoryPanel(documentRef, state) {
  const list = documentRef.getElementById("history-list");
  if (!list) {
    return;
  }
  const activeId = state.viewingHistoryId ?? state.lastResult?.evaluation?.run_id ?? state.lastResult?.simulation_id ?? null;
  list.innerHTML = buildHistoryPanelHtml(state.history, activeId);
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
  const displayResult = getDisplayResult(state);
  const result = displayResult?.evaluation
    ? { ...baseResult, ...displayResult.evaluation, ...displayResult }
    : { ...baseResult, ...(displayResult ?? {}) };

  documentRef.getElementById("summary-score").textContent = String(result.overall_score ?? 0);
  documentRef.getElementById("summary-confidence").textContent = `置信度 ${Math.round((result.confidence ?? 0) * 100)}%`;
  documentRef.getElementById("summary-conclusion").innerHTML = buildConclusionHtml(result);

  const reviewFlag = documentRef.getElementById("summary-review-flag");
  reviewFlag.textContent = result.needs_review ? "建议人工复核" : "无需人工复核";
  reviewFlag.dataset.status = result.needs_review ? "review" : "ok";

  const historyBanner = documentRef.getElementById("history-view-banner");
  const historyBackButton = documentRef.getElementById("history-back-button");
  if (state.viewingHistoryId) {
    const entry = state.history.find((item) => item.id === state.viewingHistoryId);
    if (historyBanner) {
      historyBanner.hidden = false;
      historyBanner.textContent = entry
        ? `正在查看历史记录：${entry.scenarioLabel}（${entry.presetLabel}）`
        : "正在查看历史记录";
    }
    if (historyBackButton) {
      historyBackButton.hidden = false;
    }
  } else {
    if (historyBanner) {
      historyBanner.hidden = true;
      historyBanner.textContent = "";
    }
    if (historyBackButton) {
      historyBackButton.hidden = true;
    }
  }

  const scoreCards = buildScoreCards(result);
  const simulationCards =
    state.runMode === "simulation" && displayResult ? buildSimulationCards(displayResult) : [];
  documentRef.getElementById("scorecard-grid").innerHTML = buildScorecardHtml(scoreCards, simulationCards);

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
  dialoguePanel.innerHTML = buildSimulationDialogueHtml(displayResult?.turns ?? []);

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
    {
      ...initial,
      history: loadEvaluationHistory(storage),
      viewingHistoryId: null,
    },
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

  const bindHistoryPanel = () => {
    documentRef.querySelectorAll("[data-history-open]").forEach((button) => {
      button.onclick = () => {
        state = { ...state, viewingHistoryId: button.dataset.historyOpen };
        rerender();
      };
    });

    documentRef.querySelectorAll("[data-history-delete]").forEach((button) => {
      button.onclick = (event) => {
        event.stopPropagation();
        const historyId = button.dataset.historyDelete;
        if (!historyId) {
          return;
        }
        if (!globalThis.confirm("确定删除这条评估记录吗？")) {
          return;
        }
        const nextHistory = removeEvaluationHistoryItem(historyId, storage);
        state = {
          ...state,
          history: nextHistory,
          viewingHistoryId: state.viewingHistoryId === historyId ? null : state.viewingHistoryId,
        };
        rerender();
      };
    });

    const clearButton = documentRef.getElementById("clear-history-button");
    if (clearButton) {
      clearButton.onclick = () => {
        if (!state.history.length) {
          return;
        }
        if (!globalThis.confirm("确定清空全部历史记录吗？")) {
          return;
        }
        state = {
          ...state,
          history: clearEvaluationHistory(storage),
          viewingHistoryId: null,
        };
        rerender();
      };
    }

    const backButton = documentRef.getElementById("history-back-button");
    if (backButton) {
      backButton.onclick = () => {
        state = { ...state, viewingHistoryId: null };
        rerender();
      };
    }
  };

  const rerender = () => {
    renderLoadingBanner(documentRef, state);
    renderInputPanel(documentRef, state);
    renderResultPanel(documentRef, state);
    renderHistoryPanel(documentRef, state);
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
      if (state.status === "loading") {
        return;
      }
      state = syncStateFromInputs(documentRef, state);
      state = { ...state, status: "loading", errorMessage: "" };
      renderLoadingBanner(documentRef, state);
      renderInputPanel(documentRef, state);
      try {
        const result = await runSimulationFlow(fetchImpl, state, state.simulationConfig);
        const historyEntry = createHistoryEntry(state, result, getPresetById);
        state = {
          ...state,
          status: "success",
          lastResult: result,
          history: appendEvaluationHistory(historyEntry, storage),
          viewingHistoryId: null,
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
      const activeResult = getDisplayResult(state);
      if (!activeResult) return;
      const exportSource = activeResult.evaluation ?? activeResult;
      const exportId = exportSource.run_id ?? activeResult.simulation_id ?? "result";
      const blob = new Blob([JSON.stringify(activeResult, null, 2)], {
        type: "application/json",
      });
      const link = documentRef.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = buildExportFilename(exportId);
      link.click();
      URL.revokeObjectURL(link.href);
    };

    bindModelModal();
    bindHistoryPanel();
  };

  rerender();
}

if (typeof document !== "undefined") {
  bootstrapDemo(document, fetch);
}
