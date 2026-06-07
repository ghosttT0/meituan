from app.domain.conversation import Conversation
from app.domain.evaluation_result import EvidenceItem


def build_evidence_items(
    conversation: Conversation, turn_ids: list[int], linked_decision: str, source_type: str = "rule"
) -> list[EvidenceItem]:
    indexed = {turn.turn_id: turn.text for turn in conversation.turns}
    return [
        EvidenceItem(
            evidence_id=f"evidence_{linked_decision}_{turn_id}",
            source_type=source_type,
            turn_ids=[turn_id],
            quote=indexed.get(turn_id, ""),
            linked_decision=linked_decision,
        )
        for turn_id in turn_ids
    ]
