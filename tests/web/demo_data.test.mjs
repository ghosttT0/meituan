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
