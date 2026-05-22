from app.domain.conversation import Conversation, FactEvent


class FactExtractor:
    def extract(self, conversation: Conversation) -> list[FactEvent]:
        events: list[FactEvent] = []
        for turn in conversation.turns:
            text = turn.text
            if turn.speaker == "agent" and "请问是" in text:
                events.append(
                    FactEvent(
                        event_id=f"evt_{turn.turn_id}_identity",
                        event_type="identity_check",
                        turn_id=turn.turn_id,
                    )
                )
            if turn.speaker == "agent" and "收货时间" in text:
                events.append(
                    FactEvent(
                        event_id=f"evt_{turn.turn_id}_slot_ask",
                        event_type="slot_ask",
                        turn_id=turn.turn_id,
                        slot_name="delivery_time",
                    )
                )
            if turn.speaker == "user" and ("下午" in text or "今天" in text or "明天" in text):
                events.append(
                    FactEvent(
                        event_id=f"evt_{turn.turn_id}_slot_fill",
                        event_type="slot_fill",
                        turn_id=turn.turn_id,
                        slot_name="delivery_time",
                        slot_value=text,
                    )
                )
            if turn.speaker == "agent" and ("感谢" in text or "再见" in text):
                events.append(
                    FactEvent(
                        event_id=f"evt_{turn.turn_id}_end",
                        event_type="end_call",
                        turn_id=turn.turn_id,
                    )
                )
            if "保证送达" in text or "一定送达" in text:
                events.append(
                    FactEvent(
                        event_id=f"evt_{turn.turn_id}_promise",
                        event_type="promise",
                        turn_id=turn.turn_id,
                        note=text,
                    )
                )
        return events
