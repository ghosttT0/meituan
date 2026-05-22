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


class SimulationScenario(BaseModel):
    scenario_id: str
    spec_id: str
    profile_id: str
    primary_branch: str
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


class ModelReplySignal(BaseModel):
    answered_question: bool
    explained_reason: bool
    followed_flow_step: str | None = None
    triggered_forbidden_action: bool = False
    ignored_user_state: bool = False


class SimulationRunResult(BaseModel):
    simulation_id: str
    scenario_id: str
    profile_id: str
    termination_reason: str
    state_trace: list[str] = Field(default_factory=list)
    turns: list[dict] = Field(default_factory=list)
    evaluation: dict = Field(default_factory=dict)
