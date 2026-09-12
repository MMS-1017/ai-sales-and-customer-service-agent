from app.agent.llm import get_llm
from app.agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT
from app.config import Config
from app.rag import EmbeddingService, ChromaVectorStore, KnowledgeRetriever
from app.agent.tools import TOOLS


def understand_request(state):
    messages = state.get("messages", [])

    if not messages:
        return {
            "intent": "unknown",
            "error": "No user message provided.",
        }

    user_message = messages[-1]

    llm = get_llm()

    prompt = INTENT_PROMPT.format(
        message=user_message
    )

    response = llm.invoke(prompt)

    intent = response.content.strip().lower()

    valid_intents = {
        "product_search",
        "product_question",
        "recommendation",
        "policy_question",
        "availability_check",
        "create_order",
        "general_customer_service",
        "unknown",
    }

    if intent not in valid_intents:
        intent = "unknown"

    return {
        "intent": intent
    }



# ---------------------------------Retrieval Node--------------------------------------
def retrieve_context(state):
    intent = state.get("intent", "")
    messages = state.get("messages", [])

    if not messages:
        return {
            "retrieved_context": []
        }

    retrieval_intents = {
        "product_question",
        "recommendation",
        "policy_question",
        "general_customer_service",
    }

    if intent not in retrieval_intents:
        return {
            "retrieved_context": []
        }

    embedding_service = EmbeddingService(
        Config.EMBEDDING_MODEL
    )

    vector_store = ChromaVectorStore(
        Config.CHROMA_PATH
    )

    retriever = KnowledgeRetriever(
        embedding_service,
        vector_store,
    )

    results = retriever.retrieve(
        messages[-1],
        top_k=3,
    )

    return {
        "retrieved_context": results
    }

# ---------------------------------Decision Node--------------------------------------
def agent_decision(state):
    intent = state.get("intent", "unknown")

    if intent == "availability_check":
        return {
            "tool_name": "check_product_availability"
        }

    if intent == "create_order":
        return {
            "tool_name": "create_order"
        }

    return {
        "tool_name": None
    }

# ---------------------------------Generation Node--------------------------------------
def generate_response(state):
    messages = state.get("messages", [])
    intent = state.get("intent", "unknown")
    context = state.get("retrieved_context", [])
    tool_result = state.get("tool_result")

    if not messages:
        return {
            "response": "I couldn't process your request."
        }

    user_message = messages[-1]

    llm = get_llm()

    context_text = "\n\n".join(
        item["content"]
        for item in context
    )

    tool_text = ""

    if tool_result:
        tool_text = str(tool_result)

    prompt = f"""
{SYSTEM_PROMPT}

Intent:
{intent}

Retrieved context:
{context_text or "No relevant context found."}

Tool result:
{tool_text or "No tool was used."}

Customer message:
{user_message}

Generate the final answer to the customer.
"""

    response = llm.invoke(prompt)

    return {
        "response": response.content.strip()
    }

# ---------------------------------Tool Execution Node--------------------------------------
def execute_tool(state):
    tool_name = state.get("tool_name")

    if not tool_name:
        return {
            "tool_result": None
        }

    tool_input = state.get("tool_input", {})

    tool = TOOLS.get(tool_name)

    if not tool:
        return {
            "tool_result": {
                "success": False,
                "error": "Unknown tool."
            }
        }

    try:
        result = tool.invoke(tool_input)

        return {
            "tool_result": result
        }

    except Exception as exc:
        return {
            "tool_result": {
                "success": False,
                "error": str(exc),
            }
        }