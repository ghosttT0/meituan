from pydantic import BaseModel, Field


class Turn(BaseModel):
    turn_id: int
    speaker: str
    text: str
    timestamp_start: float | None = None
    timestamp_end: float | None = None


class FactEvent(BaseModel):
    event_id: str
    event_type: str
    turn_id: int
    slot_name: str | None = None
    slot_value: str | None = None
    note: str | None = None


class Conversation(BaseModel):
    conversation_id: str
    instruction_id: str
    source: str = "offline"
    turns: list[Turn]
    metadata: dict = Field(default_factory=dict)
