from langchain_groq import ChatGroq

from app.config import Config


def get_llm():
    if not Config.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not configured."
        )

    return ChatGroq(
        model=Config.GROQ_MODEL,
        temperature=0,
        api_key=Config.GROQ_API_KEY,
    )