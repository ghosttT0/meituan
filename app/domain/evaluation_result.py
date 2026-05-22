from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    rule_id: str
    passed: bool = False
    score_delta: float = 0.0
    severity: str = "normal"
    evidence_turn_ids: list[int] = Field(default_factory=list)
    reason: str
    status: str = "ok"


class JudgeResult(BaseModel):
    dimension_id: str
    score: float
    confidence: float
    reason: str
    evidence_turn_ids: list[int] = Field(default_factory=list)
    status: str = "ok"


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: str
    turn_ids: list[int]
    quote: str
    linked_decision: str
    note: str = ""


class EvaluationResult(BaseModel):
    run_id: str
    conversation_id: str
    spec_id: str
    overall_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    hard_fail: bool = False
    confidence: float = 0.0
    needs_review: bool = False
    soft_eval_skipped: bool = False
    parse_warnings: list[str] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    judge_results: list[JudgeResult] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    summary: str = ""
