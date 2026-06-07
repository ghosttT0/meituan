from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    rule_id: str
    passed: bool = False
    score_delta: float = 0.0
    weight: float = 1.0
    severity: str = "normal"
    evidence_turn_ids: list[int] = Field(default_factory=list)
    reason: str
    status: str = "ok"
    improvement_suggestion: str = ""
    review_source: str = "rule_engine"
    review_confidence: float = 1.0


class JudgeResult(BaseModel):
    dimension_id: str
    score: float
    confidence: float
    reason: str
    evidence_turn_ids: list[int] = Field(default_factory=list)
    status: str = "ok"
    deduction_details: list[str] = Field(default_factory=list)
    judge_id: str = ""
    judge_role: str = "general"
    is_arbitration: bool = False


class JudgePanelResult(BaseModel):
    judge_id: str
    judge_role: str
    dimension_results: list[JudgeResult] = Field(default_factory=list)
    scenario_rule_results: list[RuleResult] = Field(default_factory=list)


class ArbitrationRecord(BaseModel):
    target_type: str
    target_id: str
    triggered_by: list[str] = Field(default_factory=list)
    score_gap: float = 0.0
    reason: str = ""
    resolved_by: str = ""


class PanelEvaluation(BaseModel):
    panel_results: list[JudgePanelResult] = Field(default_factory=list)
    arbitration_records: list[ArbitrationRecord] = Field(default_factory=list)
    final_judge_results: list[JudgeResult] = Field(default_factory=list)
    final_rule_results: list[RuleResult] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: str
    turn_ids: list[int]
    quote: str
    linked_decision: str
    note: str = ""


class DimensionScore(BaseModel):
    dimension_name: str
    category: str
    score: float
    weight: float
    max_score: float
    sub_scores: dict[str, float] = Field(default_factory=dict)
    reason: str = ""
    evidence_turn_ids: list[int] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    overall_score: float
    grade: str
    task_success_rate: float
    efficiency_score: float
    experience_score: float
    robustness_score: float
    key_strengths: list[str] = Field(default_factory=list)
    key_weaknesses: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)  # e.g. ["SLOT_ABANDONMENT", "TOPIC_DRIFT"]


class EvaluationResult(BaseModel):
    run_id: str
    conversation_id: str
    spec_id: str
    evaluation_mode: str = "dual_arbitration"
    overall_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    hard_fail: bool = False
    confidence: float = 0.0
    needs_review: bool = False
    soft_eval_skipped: bool = False
    parse_warnings: list[str] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    judge_results: list[JudgeResult] = Field(default_factory=list)
    panel_results: list[JudgePanelResult] = Field(default_factory=list)
    arbitration_records: list[ArbitrationRecord] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    summary: str = ""
    detailed_dimensions: list[DimensionScore] = Field(default_factory=list)
    evaluation_summary: EvaluationSummary | None = None
