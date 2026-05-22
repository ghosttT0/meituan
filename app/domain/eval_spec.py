from pydantic import BaseModel, Field


class RequiredStep(BaseModel):
    id: str
    name: str
    order: int
    required: bool = True
    evidence_requirement: str


class RequiredSlot(BaseModel):
    name: str
    required: bool = True
    accepted_values: list[str] = Field(default_factory=list)


class ForbiddenAction(BaseModel):
    id: str
    description: str
    severity: str = "fatal"


class SoftDimension(BaseModel):
    id: str
    name: str
    weight: float
    rubric: list[str]


class ScoringPolicy(BaseModel):
    hard_rules_weight: float = 0.7
    soft_rules_weight: float = 0.3
    hard_fail_zero_out: bool = True


class EvalSpec(BaseModel):
    spec_id: str
    instruction_id: str
    version: str
    task_goal: str
    required_steps: list[RequiredStep] = Field(default_factory=list)
    optional_steps: list[RequiredStep] = Field(default_factory=list)
    required_slots: list[RequiredSlot] = Field(default_factory=list)
    forbidden_actions: list[ForbiddenAction] = Field(default_factory=list)
    completion_conditions: list[str] = Field(default_factory=list)
    hard_fail_conditions: list[str] = Field(default_factory=list)
    soft_dimensions: list[SoftDimension] = Field(default_factory=list)
    scoring_policy: ScoringPolicy = Field(default_factory=ScoringPolicy)
    review_status: str = "draft"
