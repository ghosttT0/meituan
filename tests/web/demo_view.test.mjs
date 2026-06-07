import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const view = await import(
  pathToFileURL(path.resolve("app/web/static/demo-view.js")).href,
);

test("buildScoreCards maps dimension scores into dashboard cards", () => {
  const cards = view.buildScoreCards({
    dimension_scores: {
      flow_following: 0.92,
      slot_collection: 0.95,
      explanation_quality: 0.78,
      task_focus: 0.84,
    },
    evaluation_mode: "dual_arbitration",
    panel_results: [{ judge_id: "judge_a" }, { judge_id: "judge_b" }],
    arbitration_records: [{ target_id: "task_focus" }],
  });

  assert.equal(cards.length, 7);
  assert.equal(cards[0].title, "流程遵循");
  assert.equal(cards[0].value, 92);
  assert.equal(cards[4].title, "评分模式");
  assert.equal(cards[4].value, "双评委 + 仲裁");
  assert.equal(cards[5].title, "主评委");
  assert.equal(cards[5].value, 2);
  assert.equal(cards[6].title, "仲裁次数");
  assert.equal(cards[6].value, 1);
});

test("buildAccordionSections returns evidence, rules, judge, and raw json", () => {
  const sections = view.buildAccordionSections({
    evidence_items: [{ quote: "您好，请问是张先生吗？", linked_decision: "required_steps" }],
    rule_results: [{ rule_id: "required_steps", passed: true, reason: "已完成全部必做步骤" }],
    judge_results: [{ dimension_id: "task_focus", score: 0.84, reason: "命中评分标准" }],
    run_id: "run_demo",
    spec_id: "spec_demo",
    confidence: 0.9,
  });

  assert.equal(sections.evidence.length, 1);
  assert.equal(sections.rules[0].title, "必做步骤");
  assert.equal(sections.scenarioRules.length, 0);
  assert.equal(sections.judge[0].title, "任务聚焦度");
  assert.match(sections.rawJson, /run_demo/);
});

test("buildAccordionSections includes panel judge details and arbitration records", () => {
  const sections = view.buildAccordionSections({
    judge_results: [{ dimension_id: "task_focus", score: 0.74, reason: "final result" }],
    panel_results: [
      {
        judge_id: "judge_a",
        judge_role: "task_alignment",
        dimension_results: [{ dimension_id: "task_focus", score: 0.9, reason: "judge a reason" }],
        scenario_rule_results: [],
      },
      {
        judge_id: "judge_b",
        judge_role: "experience_risk",
        dimension_results: [{ dimension_id: "task_focus", score: 0.4, reason: "judge b reason" }],
        scenario_rule_results: [],
      },
    ],
    arbitration_records: [
      {
        target_type: "dimension",
        target_id: "task_focus",
        resolved_by: "judge_c",
        score_gap: 0.5,
        reason: "disagree",
      },
    ],
    run_id: "run_panel",
    spec_id: "spec_panel",
    confidence: 0.8,
  });

  assert.ok(sections.judge.some((item) => String(item.title).includes("judge_a")));
  assert.ok(sections.judge.some((item) => String(item.title).includes("仲裁")));
  assert.match(sections.rawJson, /"panel_count": 2/);
  assert.match(sections.rawJson, /"arbitration_count": 1/);
});

test("buildInputPanelHtml exposes action hooks for browser binding", () => {
  const markup = view.buildInputPanelHtml({
    mode: "preset",
    runMode: "simulation",
    evaluationMode: "dual_arbitration",
    activePresetId: "rider_station_task",
    instructionText: "请确认收货时间",
    conversationText: "agent: 您好",
    status: "idle",
    errorMessage: "",
  });

  assert.match(markup, /id="run-evaluation-button"/);
  assert.match(markup, /id="reset-demo-button"/);
  assert.match(markup, /id="status-banner"/);
  assert.match(markup, /id="evaluation-mode-select"/);
  assert.match(markup, />双评委 \+ 仲裁</);
  assert.doesNotMatch(markup, /id="conversation-input"/);
  assert.doesNotMatch(markup, /id="run-mode-evaluation"/);
  assert.doesNotMatch(markup, /id="run-mode-simulation"/);
  assert.match(markup, /运行模拟/);
});

test("buildInputPanelHtml exposes simulation controls in simulation mode", () => {
  const markup = view.buildInputPanelHtml({
    mode: "preset",
    runMode: "simulation",
    activePresetId: "rider_station_task",
    instructionText: "请确认收货时间",
    conversationText: "agent: 您好",
    status: "idle",
    errorMessage: "",
    simulationConfig: {
      adapterType: "http",
      endpoint: "http://localhost:9000/chat",
      scenarioKey: "busy_interrupt",
      profileId: "busy",
      primaryBranch: "busy",
      maxTurns: 4,
    },
  });

  assert.match(markup, /id="simulation-profile-select"/);
  assert.match(markup, /id="simulation-scenario-select"/);
  assert.match(markup, /id="simulation-branch-select"/);
  assert.match(markup, /id="simulation-max-turns"/);
  assert.match(markup, /id="simulation-adapter-select"/);
  assert.match(markup, /id="simulation-endpoint-input"/);
  assert.match(markup, />随机匹配</);
  assert.match(markup, /系统提示词（任务指令）/);
  assert.match(markup, />忙碌打断</);
  assert.match(markup, />忙碌型</);
  assert.doesNotMatch(markup, /评估模式/);
});

test("buildSimulationCards maps simulation metadata into cards", () => {
  const cards = view.buildSimulationCards({
    scenario_key: "busy_interrupt",
    scenario_label: "忙碌打断",
    scenario_focus: ["重点检查是否快速说重点"],
    profile_id: "busy",
    termination_reason: "user_busy_end",
    state_trace: ["init", "busy", "terminated"],
    generation_mode: "ai",
    adapter_mode: "http",
  });

  assert.equal(cards[0].title, "测试场景");
  assert.equal(cards[0].value, "忙碌打断");
  assert.equal(cards[1].title, "场景重点");
  assert.match(cards[1].value, /说重点/);
  assert.equal(cards[2].title, "模拟画像");
  assert.equal(cards[2].value, "忙碌型");
  assert.equal(cards[3].value, "AI生成");
  assert.equal(cards[4].value, "真实模型接口");
  assert.equal(cards[6].value, "3");
});

test("buildAccordionSections includes simulation trace when available", () => {
  const sections = view.buildAccordionSections({
    run_id: "run_demo",
    spec_id: "spec_demo",
    confidence: 0.9,
    scenario_key: "faq_followup",
    scenario_label: "直播 FAQ 追问",
    user_goal: "追问低延迟直播和标准直播的区别及费用变化",
    scenario_focus: ["重点检查 FAQ / 知识点是否答到位", "重点检查模型是否保持任务聚焦"],
    scenario_diagnosis: ["FAQ 追问场景得分偏低，说明知识点解释或追问处理可能不足。"],
    state_trace: ["init", "questioning", "terminated"],
    rule_results: [{ rule_id: "scenario_faq_grounding", passed: true, reason: "FAQ 追问场景已答到关键知识点" }],
    turns: [{ turn_id: 1, speaker: "user", text: "为什么必须这样？" }],
    debug_logs: ["第1轮：从问题池选择了任务相关问题 -> 低延迟直播和标准直播差在哪？"],
  });

  assert.equal(sections.scenarioRules[0].title, "FAQ知识点命中");
  assert.equal(sections.simulation[0].title, "测试场景");
  assert.equal(sections.simulation[1].title, "用户目标");
  assert.equal(sections.simulation[2].title, "场景重点");
  assert.equal(sections.simulation[3].title, "场景诊断");
  assert.equal(sections.simulation[4].title, "状态轨迹");
  assert.match(sections.simulation[4].body, /questioning/);
  assert.equal(sections.simulation[6].title, "模拟日志");
  assert.match(sections.simulation[6].body, /问题池/);
});

test("buildAccordionSections renders scenario focus and diagnosis for busy scene", () => {
  const sections = view.buildAccordionSections({
    run_id: "run_busy",
    spec_id: "spec_busy",
    confidence: 0.8,
    scenario_key: "busy_interrupt",
    scenario_label: "忙碌打断",
    user_goal: "要求对方快速说明重点",
    scenario_focus: ["重点检查是否快速说重点", "重点检查是否尊重用户忙碌状态"],
    scenario_diagnosis: ["用户在忙碌状态下结束，建议检查模型是否过于冗长。"],
    state_trace: ["init", "busy", "terminated"],
    turns: [{ turn_id: 1, speaker: "user", text: "我现在有点忙。" }],
    debug_logs: ["第1轮：状态=init，意图=say_busy，未命中任务问题池"],
  });

  assert.equal(sections.simulation[0].title, "测试场景");
  assert.match(sections.simulation[2].body, /说重点/);
  assert.match(sections.simulation[3].body, /冗长/);
});

test("buildSimulationDialogueHtml renders chat bubbles", () => {
  const html = view.buildSimulationDialogueHtml([
    { turn_id: 1, speaker: "user", text: "为什么必须这样？" },
    { turn_id: 2, speaker: "agent", text: "因为这次主要是确认安排。" },
  ]);

  assert.match(html, /对话回放/);
  assert.match(html, /chat-thread-scroll/);
  assert.match(html, /chat-message user/);
  assert.match(html, /chat-message agent/);
  assert.match(html, /模拟用户/);
  assert.match(html, /被测模型/);
});

test("buildExportFilename uses the run id", () => {
  assert.equal(view.buildExportFilename("run_demo"), "evaluation-run_demo.json");
});

test("buildModelConfigModalHtml renders config fields and actions", () => {
  const html = view.buildModelConfigModalHtml({
    name: "mimo",
    apiUrl: "https://hotaruapi.com/v1",
    apiKey: "secret-key",
    model: "gpt-4o-mini",
    authType: "bearer",
    protocolMode: "auto",
  });

  assert.match(html, /API 配置列表/);
  assert.match(html, /id="model-config-name"/);
  assert.match(html, /id="model-config-api-url"/);
  assert.match(html, /id="model-config-api-key"/);
  assert.match(html, /id="model-config-model"/);
  assert.match(html, /id="fetch-model-list-button"/);
  assert.match(html, /id="check-model-button"/);
  assert.match(html, /id="save-model-config-button"/);
});

test("mergeModelConfigIntoState syncs modal config into simulation config", () => {
  const state = {
    simulationConfig: {
      adapterType: "mock",
      endpoint: "",
      profileId: "busy",
      primaryBranch: "busy",
      maxTurns: 4,
    },
    modelConfig: {},
  };

  const next = view.mergeModelConfigIntoState(state, {
    name: "mimo",
    apiUrl: "https://hotaruapi.com/v1",
    apiKey: "secret-key",
    model: "gpt-4o-mini",
    authType: "bearer",
    protocolMode: "auto",
  });

  assert.equal(next.simulationConfig.adapterType, "http");
  assert.equal(next.simulationConfig.endpoint, "https://hotaruapi.com/v1");
  assert.equal(next.modelConfig.apiKey, "secret-key");
});

test("mergeModelConfigIntoState syncs modal config to simulation config", () => {
  const next = view.mergeModelConfigIntoState(
    {
      simulationConfig: { adapterType: "mock", endpoint: "", profileId: "busy", primaryBranch: "busy", maxTurns: 4 },
      modelConfig: {},
    },
    {
      name: "mimo",
      apiUrl: "https://hotaruapi.com/v1",
      apiKey: "secret-key",
      model: "gpt-4o-mini",
      authType: "bearer",
      protocolMode: "auto",
    },
  );

  assert.equal(next.simulationConfig.adapterType, "http");
  assert.equal(next.simulationConfig.endpoint, "https://hotaruapi.com/v1");
  assert.equal(next.modelConfig.apiKey, "secret-key");
});
