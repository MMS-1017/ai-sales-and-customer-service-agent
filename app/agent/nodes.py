from app.config import Config
from app.agent.llm import get_llm
from app.agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.rag import get_embedding_service, ChromaVectorStore, KnowledgeRetriever
from app.services import ProductService

from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
    product_name: str | None = Field(
                                    default=None,
                                    description="The product name mentioned by the customer.",
                                )

    quantity: int | None = Field(
                                default=None,
                                gt=0,
                                description="The requested quantity."
                            )


class CategoryRequest(BaseModel):
    category: str | None = Field(
                                default=None,
                                description=(
                                    "The product category mentioned by the customer "
                                    "(e.g. 'headphones', 'laptops', 'smartphones'). "
                                    "Return null if no specific category is mentioned."
                                ),
                            )


#---------------------------------Conversation Formatter--------------------------------------
def format_conversation_history(messages: list) -> str:
    """Label alternating turns so the LLM can resolve pronouns like 'it'/'this product'.

    The messages list alternates: customer, agent, customer, agent …
    The very last message is always the current customer turn and is excluded
    from the history (it is passed separately as the latest message).
    """
    if not messages:
        return "(no prior conversation)"

    lines = []
    for i, msg in enumerate(messages):
        role = "Customer" if i % 2 == 0 else "Agent"
        lines.append(f"{role}: {msg}")
    return "\n".join(lines)


#---------------------------------Intent Understanding Node--------------------------------------
def understand_request(state):
    llm = get_llm()

    messages = state.get("messages", [])
    # Format history (all but latest) with role labels for the intent classifier
    conversation_history = format_conversation_history(messages[:-1])
    latest_message = messages[-1]

    prompt = INTENT_PROMPT.format(
        conversation_history=conversation_history,
        message=latest_message,
    )

    result = llm.invoke(prompt)

    intent = result.content.strip().lower()

    allowed_intents = {
        "product_search",
        "product_question",
        "recommendation",
        "policy_question",
        "availability_check",
        "create_order",
        "general_customer_service",
        "unknown",
    }

    if intent not in allowed_intents:
        intent = "unknown"

    return {"intent": intent}

#----------------------------------Tool Input Preparation Node--------------------------------------
def prepare_tool_input(state):
    tool_name = state.get("tool_name")
    product_id = state.get("product_id")
    quantity = state.get("quantity")
    customer_id = state.get("customer_id")
    category = state.get("category")

    if tool_name == "get_best_sellers":
        return {
            "tool_input": {
                "category": category,
                "limit": 5,
            }
        }

    if not product_id:
        return {
            "tool_input": {},
            "error": "Product could not be identified.",
        }

    if tool_name == "get_product_details":
        return {
            "tool_input": {
                "product_id": product_id,
            }
        }

    if tool_name == "check_product_availability":
        quantity = quantity or 1

        return {
            "tool_input": {
                "product_id": product_id,
                "quantity": quantity,
            }
        }

    if tool_name == "create_order":
        if not quantity:
            return {
                "tool_input": {},
                "error": "Please specify the quantity.",
            }

        return {
            "tool_input": {
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": quantity,
            }
        }

    return {
        "tool_input": {}
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

    embedding_service = get_embedding_service(Config.EMBEDDING_MODEL)

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
    intent = state.get("intent")

    if intent == "availability_check":
        tool_name = "check_product_availability"

    elif intent == "create_order":
        tool_name = "create_order"

    elif intent in {"product_question", "product_search"}:
        tool_name = "get_product_details"

    elif intent == "recommendation":
        tool_name = "get_best_sellers"

    else:
        tool_name = None

    return {"tool_name": tool_name}

# ---------------------------------Category Extraction Node--------------------------------------
def extract_category(state):
    llm = get_llm()

    messages = state.get("messages", [])
    conversation_history = format_conversation_history(messages)

    prompt = f"""
                Extract the product category from the customer's request.

                Rules:
                - Return only a generic category keyword such as 'headphones',
                  'laptops', 'smartphones', 'tablets', 'cameras', etc.
                - Do NOT return a brand or model name.
                - Return null if no specific category is mentioned
                  (the customer is asking for best sellers in general).

                Conversation:
                {conversation_history}
            """

    structured_llm = llm.with_structured_output(CategoryRequest)
    result = structured_llm.invoke(prompt)

    print("========== CATEGORY EXTRACTION ==========")
    print("CATEGORY:", result.category)
    print("=========================================")

    return {"category": result.category}

# ---------------------------------Generation Node--------------------------------------
def generate_response(state):
    messages = state.get("messages", [])
    tool_result = state.get("tool_result")
    retrieved_context = state.get("retrieved_context", [])
    error = state.get("error")

    # Never ask the LLM to recover from a failed backend operation.
    # A failed tool must result in a controlled response rather than
    # a guessed price, stock value, order ID, or other business fact.
    if error:
        return {
            "response": error,
        }

    if isinstance(tool_result, dict) and not tool_result.get("success", True):
        tool_error = tool_result.get("error", "The requested operation could not be completed.")
        return {
            "response": f"I couldn't complete that request: {tool_error}",
        }

    context_text = "\n\n".join(
        item["content"] for item in retrieved_context
        if item.get("content")
    )

    tool_text = ""
    if tool_result:
        tool_text = f"""
                    AUTHORITATIVE BACKEND TOOL RESULT:
                    {tool_result}

                    IMPORTANT:
                    - Treat this backend result as the source of truth for current product price,
                    stock, and order information.
                    - Preserve numeric values exactly. Do not round, approximate, convert, or
                    replace them with values from conversation history or general knowledge.
                    - For product descriptions, use only the description returned by the tool.
                    - Do not add product specifications from model knowledge.
                    """

    conversation_text = format_conversation_history(messages)

    prompt = f"""
                {SYSTEM_PROMPT}

                Retrieved knowledge:
                {context_text or "No relevant knowledge retrieved."}

                {tool_text}

                Conversation:
                {conversation_text}

                Generate the final response to the customer.
            """

    response = get_llm().invoke(prompt)

    return {
        "response": response.content,
    }

# ---------------------------------Tool Execution Node--------------------------------------
def execute_tool(state):

    tool_name = state.get("tool_name")
    tool_input = state.get("tool_input")

    tool = TOOLS.get(tool_name)

    if not tool:
        result = {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }
        print("TOOL RESULT:", result)
        return {"tool_result": result}

    try:
        result = tool.invoke(tool_input)

        print("TOOL RESULT:", result)

        return {
            "tool_result": result
        }

    except Exception as exc:
        print("TOOL ERROR:", exc)

        return {
            "tool_result": {
                "success": False,
                "error": str(exc)
            }
        }
# ---------------------------------Product Extraction--------------------------------------
def extract_product_request(state):
    llm = get_llm()

    messages = state.get("messages", [])
    # Include the full conversation (including latest message) with role labels
    # so the LLM can resolve pronouns like "it", "this product", "that phone".
    conversation_history = format_conversation_history(messages)

    prompt = f"""
                Extract the product request from the conversation.

                Rules:
                - Use the conversation history to resolve references such as:
                "it", "this product", "that phone".
                - Only extract product information that exists in the conversation.
                - Do not invent storage, color, network type, variants, or specifications.
                - If the product is already mentioned earlier, reuse it.
                - Quantity should only be extracted when explicitly stated.
                - Return null when a value cannot be determined.

                Conversation:
                {conversation_history}
            """

    structured_llm = llm.with_structured_output(ProductRequest)

    request = structured_llm.invoke(prompt)

    print("========== EXTRACTION DEBUG ==========")
    print("PRODUCT NAME:", request.product_name)
    print("QUANTITY:", request.quantity)
    print("======================================")

    return {
        "product_name": request.product_name,
        "quantity": request.quantity,
    }
# ---------------------------------Product Resolution--------------------------------------
def resolve_product(state):
    product_name = state.get("product_name")

    if not product_name:
        return {
            "error": "Product name could not be identified."
        }

    # Stage 1: exact ILIKE search
    products = ProductService.search_products(query=product_name)

    print("MATCHED PRODUCTS (exact):", [
        (product.id, product.name) for product in products
    ])

    if len(products) == 1:
        return {"product_id": products[0].id}

    # Stage 2: fuzzy fallback when ILIKE returned nothing (typos, misspellings)
    if not products:
        fuzzy_matches = ProductService.fuzzy_search_products(query=product_name)

        print("FUZZY MATCHES:", [
            (p.name, score) for p, score in fuzzy_matches
        ])

        if len(fuzzy_matches) == 1:
            # Single confident match — use it
            return {"product_id": fuzzy_matches[0][0].id}

        if len(fuzzy_matches) > 1:
            # Multiple close candidates — ask the customer to clarify
            options = ", ".join(p.name for p, _ in fuzzy_matches[:3])
            return {
                "error": f"Did you mean one of these? {options}"
            }

        # Nothing found even with fuzzy
        return {
            "error": f"Product '{product_name}' was not found."
        }

    # Stage 1 returned multiple results
    return {
        "error": "Multiple products matched the request. Please be more specific."
    }