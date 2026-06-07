import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const history = await import(
  pathToFileURL(path.resolve("app/web/static/demo-history.js")).href,
);

class MemoryStorage {
  constructor() {
    this.store = new Map();
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, value);
  }

  removeItem(key) {
    this.store.delete(key);
  }
}

test("appendEvaluationHistory stores newest records first with cap", () => {
  const storage = new MemoryStorage();
  history.appendEvaluationHistory({ id: "a", savedAt: "2026-01-01T00:00:00.000Z" }, storage);
  history.appendEvaluationHistory({ id: "b", savedAt: "2026-01-02T00:00:00.000Z" }, storage);

  const items = history.loadEvaluationHistory(storage);
  assert.equal(items[0].id, "b");
  assert.equal(items[1].id, "a");
});

test("createHistoryEntry captures preset and scenario metadata", () => {
  const entry = history.createHistoryEntry(
    {
      activePresetId: "rider_station_task",
      simulationConfig: { scenarioKey: "busy_interrupt" },
    },
    {
      simulation_id: "sim_1",
      scenario_label: "忙碌打断",
      evaluation: {
        run_id: "run_1",
        overall_score: 67.6,
        confidence: 0.82,
        needs_review: true,
        evaluation_summary: { grade: "B" },
      },
    },
    () => ({ label: "案例 1：飞毛腿骑手外呼任务" }),
  );

  assert.equal(entry.id, "run_1");
  assert.equal(entry.scenarioLabel, "忙碌打断");
  assert.match(entry.presetLabel, /飞毛腿/);
  assert.equal(entry.overallScore, 67.6);
  assert.equal(entry.needsReview, true);
  assert.equal(entry.grade, "B");
});

test("buildHistoryPanelHtml renders empty and active states", () => {
  const empty = history.buildHistoryPanelHtml([], null);
  assert.match(empty, /暂无记录/);

  const html = history.buildHistoryPanelHtml(
    [
      {
        id: "run_1",
        scenarioLabel: "忙碌打断",
        presetLabel: "案例 1",
        overallScore: 88,
        needsReview: false,
        grade: "A",
        savedAt: "2026-06-07T10:30:00.000Z",
      },
    ],
    "run_1",
  );

  assert.match(html, /history-item is-active/);
  assert.match(html, /忙碌打断/);
  assert.match(html, /data-level="good"/);
  assert.match(html, /data-history-delete="run_1"/);
  assert.match(html, /删除/);
});

test("removeEvaluationHistoryItem deletes a single record", () => {
  const storage = new MemoryStorage();
  history.appendEvaluationHistory({ id: "a", savedAt: "2026-01-01T00:00:00.000Z" }, storage);
  history.appendEvaluationHistory({ id: "b", savedAt: "2026-01-02T00:00:00.000Z" }, storage);

  const next = history.removeEvaluationHistoryItem("a", storage);
  assert.equal(next.length, 1);
  assert.equal(next[0].id, "b");
});
