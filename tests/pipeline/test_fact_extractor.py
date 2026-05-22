import json
from pathlib import Path

from app.domain.conversation import Conversation
from app.pipeline.fact_extractor import FactExtractor


def test_fact_extractor_emits_identity_slot_and_end_events() -> None:
    payload = json.loads(Path("tests/fixtures/conversation_delivery_good.json").read_text(encoding="utf-8"))
    conversation = Conversation.model_validate(payload)

    events = FactExtractor().extract(conversation)

    event_types = [event.event_type for event in events]
    assert "identity_check" in event_types
    assert "slot_fill" in event_types
    assert "end_call" in event_types
