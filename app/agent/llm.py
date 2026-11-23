from functools import lru_cache
from langchain_groq import ChatGroq
from app.config import Config


@lru_cache(maxsize=4)
def get_llm(model: str | None = None, temperature: float = 0.0):
    if not Config.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not configured."
        )

    return ChatGroq(
        model=model or Config.GROQ_MODEL,
        temperature=temperature,
        api_key=Config.GROQ_API_KEY,
    )