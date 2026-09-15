from typing import Any


class ConversationService:

    _conversations: dict[str, list[str]] = {}

    @classmethod
    def get_history(cls, conversation_id: str) -> list[str]:
        return cls._conversations.get(conversation_id, []).copy()

    @classmethod
    def add_message(cls, conversation_id: str, message: str,) -> None:
        
        if conversation_id not in cls._conversations:
            cls._conversations[conversation_id] = []

        cls._conversations[conversation_id].append(message)

    @classmethod
    def clear(cls, conversation_id: str) -> None:
        cls._conversations.pop(conversation_id, None)