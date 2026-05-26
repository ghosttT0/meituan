export const PRESET_CASES = [
  {
    id: "delivery_time",
    label: "案例 1：收货时间确认",
    instructionText: "请先确认用户身份，再确认收货时间，不要承诺一定送达。",
    conversationText: [
      "agent: 您好，请问是张先生吗？",
      "user: 是的。",
      "agent: 来电是为了确认收货时间，您明天下午方便收货吗？",
      "user: 明天下午可以。",
      "agent: 好的，感谢您的配合，再见。",
    ].join("\n"),
  },
  {
    id: "address_check",
    label: "案例 2：地址核验",
    instructionText: "请先确认身份，再核验详细地址，避免直接承诺配送结果。",
    conversationText: [
      "agent: 您好，请问是李女士吗？",
      "user: 是我。",
      "agent: 来电是为了核验收货地址，您当前地址还是朝阳区望京街道 8 号吗？",
      "user: 改成朝阳区望京街道 10 号了。",
      "agent: 好的，我帮您记录最新地址，感谢配合。",
    ].join("\n"),
  },
  {
    id: "objection_handle",
    label: "案例 3：异常异议处理",
    instructionText: "先说明来电目的，再处理用户异议，收集失败原因并完成结束语。",
    conversationText: [
      "agent: 您好，请问是王女士吗？",
      "user: 你们怎么老打电话？",
      "agent: 抱歉打扰，这次来电是为了确认收货安排，方便我核对一下明天是否可以签收吗？",
      "user: 明天不方便。",
      "agent: 好的，我记录为明天不便签收，感谢您的反馈，再见。",
    ].join("\n"),
  },
];

export function createInitialState() {
  const first = PRESET_CASES[0];
  return {
    mode: "preset",
    runMode: "evaluation",
    rightPanelMode: "results",
    activePresetId: first.id,
    instructionText: first.instructionText,
    conversationText: first.conversationText,
    lastResult: null,
    status: "idle",
    errorMessage: "",
    simulationConfig: {
      adapterType: "http",
      endpoint: "",
      profileId: "cooperative",
      primaryBranch: "cooperative",
      maxTurns: 6,
    },
    modelConfig: {
      name: "配置 1",
      apiUrl: "",
      apiKey: "",
      model: "",
      authType: "bearer",
      protocolMode: "auto",
      modelOptions: [],
      lastCheck: null,
    },
    modelConfigOpen: false,
  };
}

export function applyPreset(state, presetId) {
  const preset = PRESET_CASES.find((item) => item.id === presetId);
  if (!preset) {
    return state;
  }
  return {
    ...state,
    mode: "preset",
    activePresetId: preset.id,
    instructionText: preset.instructionText,
    conversationText: preset.conversationText,
    errorMessage: "",
  };
}

export function switchMode(state, mode) {
  return {
    ...state,
    mode,
    errorMessage: "",
  };
}

export function switchRunMode(state, runMode) {
  return {
    ...state,
    runMode,
    rightPanelMode: runMode === "simulation" ? "conversation" : "results",
    errorMessage: "",
  };
}
