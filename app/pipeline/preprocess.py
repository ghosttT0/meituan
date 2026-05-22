from app.domain.conversation import Conversation, Turn


class Preprocessor:
    def run(self, conversation: Conversation) -> Conversation:
        cleaned_turns = [
            Turn(**{**turn.model_dump(), "text": turn.text.strip().replace("  ", " ")})
            for turn in conversation.turns
            if turn.text.strip()
        ]
        return conversation.model_copy(update={"turns": cleaned_turns})
