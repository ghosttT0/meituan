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
