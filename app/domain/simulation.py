from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    profile_id: str
    name: str
    cooperation_level: float
    patience_level: float
    interruption_probability: float = 0.0
    question_probability: float = 0.0
    reject_probability: float = 0.0
    style_prompt: str = ""
    persona_note: str = ""  # 画像背景描述，注入 prompt 增强真实感
    preferred_question_sources: list[str] = Field(default_factory=list)
    preferred_question_tags: list[str] = Field(default_factory=list)
    max_question_rounds: int = 1
    max_objection_rounds: int = 1
    max_interrupt_rounds: int = 1


class SimulationScenario(BaseModel):
    scenario_id: str
    spec_id: str
    profile_id: str
    primary_branch: str
    scenario_key: str = "custom"
    scenario_label: str = ""
    user_goal: str = ""
    secondary_branch: str | None = None
    max_turns: int
    termination_policy: str
    coverage_mode: str = "primary"


class ConversationState(BaseModel):
    current_state: str = "init"
    turn_index: int = 0
    completed_steps: list[str] = Field(default_factory=list)


class UserIntent(BaseModel):
    action: str
    state: str
    target_step_id: str | None = None
    note: str = ""


class SimulatedUserReply(BaseModel):
    state: str
    intent: str
    reply: str
    should_end: bool = False
    emotion: str = "neutral"  # neutral | skeptical | resistant | rejecting


class ModelReplySignal(BaseModel):
    answered_question: bool
    explained_reason: bool
    followed_flow_step: str | None = None
    triggered_forbidden_action: bool = False
    ignored_user_state: bool = False


class SimulationRunResult(BaseModel):
    simulation_id: str
    batch_mode: bool = False
    batch_count: int = 1
    scenario_id: str
    scenario_key: str = "custom"
    scenario_label: str = ""
    user_goal: str = ""
    scenario_focus: list[str] = Field(default_factory=list)
    scenario_diagnosis: list[str] = Field(default_factory=list)
    scenario_summary: str = ""
    profile_distribution: dict[str, int] = Field(default_factory=dict)
    requested_profile_id: str = ""
    random_seed: int | None = None
    profile_id: str
    termination_reason: str
    generation_mode: str = "template_fallback"
    adapter_mode: str = "mock"
    state_trace: list[str] = Field(default_factory=list)
    turns: list[dict] = Field(default_factory=list)
    evaluation: dict = Field(default_factory=dict)
    debug_logs: list[str] = Field(default_factory=list)
    runs: list[dict] = Field(default_factory=list)
