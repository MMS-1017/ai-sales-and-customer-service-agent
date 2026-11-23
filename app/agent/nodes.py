from app.config import Config
from app.agent.llm import get_llm
from app.agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.rag import get_embedding_service, ChromaVectorStore, KnowledgeRetriever
from app.services import ProductService

from pydantic import BaseModel, Field
import re


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


class ProductComparisonRequest(BaseModel):
    product_names: list[str] = Field(
        default_factory=list,
        description=(
            "Names of the two or more distinct products explicitly present in the "
            "conversation and being compared. Do not invent or add products."
        ),
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
        "product_comparison",
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

# ---------------------------------Product Comparison--------------------------------------
def extract_comparison_products(state):
    """Extract only products already mentioned in the conversation."""
    messages = state.get("messages", [])
    conversation = format_conversation_history(messages)
    prompt = f"""
        The customer is asking to compare products mentioned earlier.
        Extract the names of the distinct products that are actually present in the
        conversation, especially product names in the Agent's most recent product list.

        Rules:
        - Return at least two products only when at least two are explicitly present.
        - Copy product names as accurately as possible from the conversation.
        - Do not invent, infer, or add products.
        - Do not return generic category names.
        - If fewer than two products can be identified, return an empty list.

        Conversation:
        {conversation}
    """
    result = get_llm().with_structured_output(ProductComparisonRequest).invoke(prompt)
    names = []
    seen = set()
    for name in result.product_names:
        cleaned = name.strip()
        key = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
        if cleaned and key and key not in seen:
            names.append(cleaned)
            seen.add(key)
    return {"comparison_product_names": names}


def fetch_comparison_products(state):
    """Resolve extracted names against active DB products and return authoritative facts."""
    names = state.get("comparison_product_names") or []
    if len(names) < 2:
        return {"error": "I couldn't identify the products to compare. Please send their names again."}

    resolved = []
    used_ids = set()
    for name in names[:5]:
        match_result = ProductService.match_product(query=name)
        product = match_result.get("product") if match_result.get("success") else None

        if product is None or product.id in used_ids:
            return {
                "error": f"I couldn't confidently match '{name}' to a unique product in the catalog. Please confirm the product names."
            }

        used_ids.add(product.id)
        resolved.append({
            "product_id": product.id,
            "product_name": product.name,
            "description": product.description,
            "category": product.category,
            "price": f"${product.price:.2f}",
            "is_available": product.stock_quantity > 0,
        })

    if len(resolved) < 2:
        return {"error": "Please mention at least two products that you want to compare."}

    return {"comparison_products": resolved}


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

        if not customer_id:
            return {
                "tool_input": {},
                "error": "Customer identification is missing. Please provide your customer details.",
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

    try:
        embedding_service = get_embedding_service(Config.EMBEDDING_MODEL)
        vector_store = ChromaVectorStore(Config.CHROMA_PATH)
        retriever = KnowledgeRetriever(embedding_service, vector_store)
        results = retriever.retrieve(messages[-1], top_k=3)
        return {"retrieved_context": results}
    except Exception as exc:
        print(f"[RAG WARNING] Retrieval failed gracefully: {exc}")
        return {"retrieved_context": []}

# ---------------------------------Decision Node--------------------------------------
def agent_decision(state):
    intent = state.get("intent")

    if intent == "product_comparison":
        return {"tool_name": None}

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

    comparison_products = state.get("comparison_products") or []
    if comparison_products:
        comparison_prompt = f"""
            {SYSTEM_PROMPT}

            The customer asked to compare products. Compare ONLY the products and facts
            in the authoritative database data below. Explain the practical differences
            using available descriptions, categories, prices, and availability status.
            Never reveal exact inventory counts or the stock_quantity field.
            If a product is in stock, say it is available to order; otherwise say it is
            currently unavailable.
            Do not invent technical specifications or features. If a useful specification
            is missing, explicitly say it is not available in the store data.
            Do not claim one is better unless the supplied data supports that conclusion.
            Answer in the same language as the customer's latest message.
            Keep the comparison clear and easy to read, preferably one short section per product
            followed by a concise recommendation only if supported by the data.

            AUTHORITATIVE PRODUCT DATA:
            {comparison_products}

            Conversation:
            {format_conversation_history(messages)}
        """
        response = get_llm().invoke(comparison_prompt)
        return {"response": response.content}

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

    match_result = ProductService.match_product(query=product_name)

    print("PRODUCT MATCH RESULT:", {
        "query": product_name,
        "match_type": match_result.get("match_type"),
        "product_id": match_result.get("product_id"),
        "is_ambiguous": match_result.get("is_ambiguous"),
        "error": match_result.get("error"),
    })

    if match_result.get("success") and match_result.get("product_id"):
        return {"product_id": match_result["product_id"]}

    return {
        "error": match_result.get("error", f"Product '{product_name}' was not found.")
    }
