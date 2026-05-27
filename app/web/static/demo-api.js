export function buildConversationTurns(conversationText) {
  return conversationText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [speakerPart, ...rest] = line.split(":");
      const speaker = speakerPart.trim().toLowerCase();
      const text = rest.join(":").trim();
      return {
        turn_id: index + 1,
        speaker: speaker === "user" ? "user" : "agent",
        text,
      };
    });
}

export function buildCompilePayload({ instructionText }) {
  return {
    instruction_id: "demo_instruction",
    name: "手动试跑任务",
    raw_text: instructionText.trim(),
  };
}

export function buildEvaluationPayload(spec, state) {
  return {
    spec,
    conversation: {
      conversation_id: "demo_conversation",
      instruction_id: "demo_instruction",
      turns: buildConversationTurns(state.conversationText),
    },
  };
}

export function buildSimulationPayload(spec, state, simulationConfig) {
  const endpoint = simulationConfig.endpoint || state.modelConfig?.apiUrl || null;
  return {
    spec,
    task_instruction_text: state.instructionText,
    adapter: {
      type: simulationConfig.adapterType,
      endpoint,
      api_key: state.modelConfig?.apiKey ?? "",
      model: state.modelConfig?.model ?? "",
      auth_type: state.modelConfig?.authType ?? "bearer",
      protocol_mode: state.modelConfig?.protocolMode ?? "auto",
    },
    simulation: {
      profile_id: simulationConfig.profileId,
      primary_branch: simulationConfig.primaryBranch,
      max_turns: Number(simulationConfig.maxTurns),
    },
  };
}

export async function runEvaluationFlow(fetchImpl, state) {
  const compileResponse = await fetchImpl("/specs/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildCompilePayload(state)),
  });
  if (!compileResponse.ok) {
    throw new Error("compile request failed");
  }
  const spec = await compileResponse.json();

  const evaluationResponse = await fetchImpl("/evaluations/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildEvaluationPayload(spec, state)),
  });
  if (!evaluationResponse.ok) {
    throw new Error("evaluation request failed");
  }
  return evaluationResponse.json();
}

export async function runSimulationFlow(fetchImpl, state, simulationConfig) {
  if (
    simulationConfig.adapterType === "http" &&
    !(simulationConfig.endpoint || state.modelConfig?.apiUrl)
  ) {
    throw new Error("missing simulation endpoint");
  }

  const compileResponse = await fetchImpl("/specs/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildCompilePayload(state)),
  });
  if (!compileResponse.ok) {
    throw new Error("compile request failed");
  }
  const spec = await compileResponse.json();

  const simulationResponse = await fetchImpl("/simulations/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildSimulationPayload(spec, state, simulationConfig)),
  });
  if (!simulationResponse.ok) {
    throw new Error("simulation request failed");
  }
  return simulationResponse.json();
}

export async function checkModelConnection(fetchImpl, modelConfig) {
  const response = await fetchImpl("/simulations/check-model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: modelConfig.name ?? "",
      api_url: modelConfig.apiUrl,
      api_key: modelConfig.apiKey,
      model: modelConfig.model,
      protocol_mode: modelConfig.protocolMode ?? "auto",
      auth_type: modelConfig.authType ?? "bearer",
    }),
  });
  if (!response.ok) {
    throw new Error("model check failed");
  }
  return response.json();
}

export async function fetchModelList(fetchImpl, modelConfig) {
  const response = await fetchImpl("/simulations/list-models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: modelConfig.name ?? "",
      api_url: modelConfig.apiUrl,
      api_key: modelConfig.apiKey,
      model: modelConfig.model ?? "",
      protocol_mode: modelConfig.protocolMode ?? "auto",
      auth_type: modelConfig.authType ?? "bearer",
    }),
  });
  if (!response.ok) {
    throw new Error("list models failed");
  }
  return response.json();
}
