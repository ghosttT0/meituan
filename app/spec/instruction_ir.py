from pydantic import BaseModel, Field


class IRFlowStep(BaseModel):
    step_id: str
    order: int
    title: str
    raw_text: str


class IRFAQItem(BaseModel):
    faq_id: str
    raw_text: str


class IRConstraintItem(BaseModel):
    constraint_id: str
    raw_text: str
    category: str | None = None


class InstructionIR(BaseModel):
    instruction_id: str
    title: str
    role_definition: str = ""
    task_goal: str = ""
    opening_line: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    flow_steps: list[IRFlowStep] = Field(default_factory=list)
    faq_items: list[IRFAQItem] = Field(default_factory=list)
    constraint_items: list[IRConstraintItem] = Field(default_factory=list)
    fallback_policy: list[str] = Field(default_factory=list)
