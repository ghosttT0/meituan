import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const demoData = await import(
  pathToFileURL(path.resolve("app/web/static/demo-data.js")).href,
);

test("createInitialState starts in preset mode with the first preset", () => {
  const state = demoData.createInitialState();

  assert.equal(state.mode, "preset");
  assert.equal(state.runMode, "simulation");
  assert.equal(state.activePresetId, "rider_station_task");
  assert.equal(state.simulationConfig.scenarioKey, "main_flow");
  assert.equal(state.simulationConfig.profileId, "cooperative");
  assert.match(state.instructionText, /你是美团外卖骑手的站长/);
  assert.match(state.instructionText, /飞毛腿/);
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
  const next = demoData.applyPreset(state, "course_live_task");

  assert.equal(next.activePresetId, "course_live_task");
  assert.equal(next.simulationConfig.scenarioKey, "main_flow");
  assert.equal(next.simulationConfig.profileId, "cooperative");
  assert.match(next.instructionText, /低延迟直播/);
  assert.match(next.instructionText, /培训机构\/校区的负责人/);
  assert.match(next.conversationText, /user:/);
});

test("applyScenarioToState syncs scenario key with profile and branch", () => {
  const state = demoData.createInitialState();
  const next = demoData.applyScenarioToState(state, "faq_followup");

  assert.equal(next.simulationConfig.scenarioKey, "faq_followup");
  assert.equal(next.simulationConfig.profileId, "questioning");
  assert.equal(next.simulationConfig.primaryBranch, "questioning");
});

test("applyScenarioToState preserves random profile mode while syncing branch", () => {
  const state = {
    ...demoData.createInitialState(),
    simulationConfig: {
      ...demoData.createInitialState().simulationConfig,
      profileId: "random",
    },
  };
  const next = demoData.applyScenarioToState(state, "busy_interrupt");

  assert.equal(next.simulationConfig.scenarioKey, "busy_interrupt");
  assert.equal(next.simulationConfig.profileId, "random");
  assert.equal(next.simulationConfig.primaryBranch, "busy");
});
