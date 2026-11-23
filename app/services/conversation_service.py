
class ConversationService:
    MAX_HISTORY: int = 20
    MAX_CONVERSATIONS: int = 1000
    _conversations: dict[str, list[str]] = {}

    @classmethod
    def get_history(cls, conversation_id: str) -> list[str]:
        return cls._conversations.get(conversation_id, []).copy()

    @classmethod
    def add_message(cls, conversation_id: str, message: str) -> None:
        if conversation_id not in cls._conversations:
            if len(cls._conversations) >= cls.MAX_CONVERSATIONS:
                oldest_key = next(iter(cls._conversations))
                cls._conversations.pop(oldest_key, None)
            cls._conversations[conversation_id] = []

        cls._conversations[conversation_id].append(message)
        if len(cls._conversations[conversation_id]) > cls.MAX_HISTORY:
            cls._conversations[conversation_id] = cls._conversations[conversation_id][-cls.MAX_HISTORY:]

    @classmethod
    def clear(cls, conversation_id: str) -> None:
        cls._conversations.pop(conversation_id, None)