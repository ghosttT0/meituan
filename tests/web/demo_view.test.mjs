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
  });

  assert.equal(cards.length, 4);
  assert.equal(cards[0].title, "流程遵循");
  assert.equal(cards[0].value, 92);
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
  assert.equal(sections.judge[0].title, "任务聚焦度");
  assert.match(sections.rawJson, /run_demo/);
});

test("buildInputPanelHtml exposes action hooks for browser binding", () => {
  const markup = view.buildInputPanelHtml({
    mode: "preset",
    runMode: "evaluation",
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

test("buildInputPanelHtml exposes simulation controls in simulation mode", () => {
  const markup = view.buildInputPanelHtml({
    mode: "preset",
    runMode: "simulation",
    activePresetId: "delivery_time",
    instructionText: "请确认收货时间",
    conversationText: "agent: 您好",
    status: "idle",
    errorMessage: "",
    simulationConfig: {
      adapterType: "mock",
      profileId: "busy",
      primaryBranch: "busy",
      maxTurns: 4,
    },
  });

  assert.match(markup, /id="run-mode-evaluation"/);
  assert.match(markup, /id="run-mode-simulation"/);
  assert.match(markup, /id="simulation-profile-select"/);
  assert.match(markup, /id="simulation-branch-select"/);
  assert.match(markup, /id="simulation-max-turns"/);
});

test("buildSimulationCards maps simulation metadata into cards", () => {
  const cards = view.buildSimulationCards({
    profile_id: "busy",
    termination_reason: "user_busy_end",
    state_trace: ["init", "busy", "terminated"],
  });

  assert.equal(cards[0].title, "模拟画像");
  assert.equal(cards[0].value, "busy");
  assert.equal(cards[2].value, "3");
});

test("buildAccordionSections includes simulation trace when available", () => {
  const sections = view.buildAccordionSections({
    run_id: "run_demo",
    spec_id: "spec_demo",
    confidence: 0.9,
    state_trace: ["init", "questioning", "terminated"],
    turns: [{ turn_id: 1, speaker: "user", text: "为什么必须这样？" }],
  });

  assert.equal(sections.simulation[0].title, "state_trace");
  assert.match(sections.simulation[0].body, /questioning/);
});

test("buildExportFilename uses the run id", () => {
  assert.equal(view.buildExportFilename("run_demo"), "evaluation-run_demo.json");
});
