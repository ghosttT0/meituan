import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const demoApi = await import(
  pathToFileURL(path.resolve("app/web/static/demo-api.js")).href,
);

test("buildConversationTurns parses speaker-prefixed transcript", () => {
  const turns = demoApi.buildConversationTurns("agent: 您好\nuser: 是的");

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
      conversationText: "agent: 您好\nuser: 今天下午可以",
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
    conversationText: "agent: 您好\nuser: 明天下午可以",
  });

  assert.equal(calls[0].url, "/specs/compile");
  assert.equal(calls[1].url, "/evaluations/run");
  assert.equal(result.run_id, "run_1");
});

test("runSimulationFlow calls compile then simulation endpoint", async () => {
  const calls = [];
  const fakeFetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    if (url === "/specs/compile") {
      return {
        ok: true,
        json: async () => ({ spec_id: "spec_compiled", task_goal: "确认收货时间" }),
      };
    }
    return {
      ok: true,
      json: async () => ({
        simulation_id: "sim_1",
        profile_id: "questioning",
        state_trace: ["init", "questioning", "terminated"],
        evaluation: { overall_score: 66 },
      }),
    };
  };

  const result = await demoApi.runSimulationFlow(
    fakeFetch,
    {
      instructionText: "请确认收货时间",
      conversationText: "agent: 您好\nuser: 明天下午可以",
      modelConfig: {
        apiUrl: "https://hotaruapi.com/v1",
        apiKey: "secret-key",
        model: "gpt-4o-mini",
        authType: "bearer",
        protocolMode: "auto",
      },
    },
    {
      adapterType: "http",
      endpoint: "",
      profileId: "questioning",
      primaryBranch: "questioning",
      maxTurns: 4,
    },
  );

  assert.equal(calls[0].url, "/specs/compile");
  assert.equal(calls[1].url, "/simulations/run");
  assert.equal(calls[1].body.adapter.type, "http");
  assert.equal(calls[1].body.adapter.endpoint, "https://hotaruapi.com/v1");
  assert.equal(calls[1].body.adapter.api_key, "secret-key");
  assert.equal(calls[1].body.adapter.model, "gpt-4o-mini");
  assert.equal(calls[1].body.adapter.auth_type, "bearer");
  assert.equal(calls[1].body.simulation.profile_id, "questioning");
  assert.equal(calls[1].body.task_instruction_text, "请确认收货时间");
  assert.equal(result.simulation_id, "sim_1");
});
