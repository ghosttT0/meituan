from app.domain.conversation import Conversation
from app.pipeline.preprocess import Preprocessor


class DialogueParser:
    def parse(self, conversation: Conversation) -> Conversation:
        return Preprocessor().run(conversation)
