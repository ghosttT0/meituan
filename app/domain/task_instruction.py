from pydantic import BaseModel


class TaskInstruction(BaseModel):
    instruction_id: str
    name: str
    business_scene: str = "fulfillment_outbound"
    raw_text: str
    version: str = "v1"
    created_at: str | None = None
