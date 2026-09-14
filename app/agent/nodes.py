from app.config import Config
from app.agent.llm import get_llm
from app.agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.rag import EmbeddingService, ChromaVectorStore, KnowledgeRetriever

from pydantic import BaseModel, Field
from app.services import ProductService

class ProductRequest(BaseModel):
    product_name: str | None = Field(
        default=None,
        description="The product name mentioned by the customer.",
    )

    quantity: int | None = Field(
        default=None,
        description="The requested quantity.",
    )


#---------------------------------Intent Understanding Node--------------------------------------
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

#----------------------------------Tool Input Preparation Node--------------------------------------
def prepare_tool_input(state):
    tool_name = state.get("tool_name")
    product_id = state.get("product_id")
    quantity = state.get("quantity")
    customer_id = state.get("customer_id")

    if not tool_name:
        return {
            "tool_input": None
        }

    if not product_id:
        return {
            "error": "Product could not be resolved.",
            "tool_input": None,
        }

    if not quantity or quantity <= 0:
        return {
            "error": "A valid quantity is required.",
            "tool_input": None,
        }

    if tool_name == "check_product_availability":
        return {
            "tool_input": {
                "product_id": product_id,
                "quantity": quantity,
            }
        }

    if tool_name == "create_order":
        if not customer_id:
            return {
                "error": "Customer context is required.",
                "tool_input": None,
            }

        return {
            "tool_input": {
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": quantity,
            }
        }

    return {
        "error": "Unsupported tool.",
        "tool_input": None,
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
    intent = state.get("intent")

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
    tool_input = state.get("tool_input")

    if not tool_name:
        return {
            "tool_result": None
        }

    if not tool_input:
        return {
            "tool_result": {
                "success": False,
                "error": "Tool input is missing.",
            }
        }

    tool = TOOLS.get(tool_name)

    if not tool:
        return {
            "tool_result": {
                "success": False,
                "error": "Unknown tool.",
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
                "success": False,\
                "error": str(exc),
            }
        }
# ---------------------------------Product Extraction--------------------------------------
def extract_product_request(state):
    messages = state.get("messages", [])

    if not messages:
        return {
            "product_name": None,
            "quantity": None,
        }

    intent = state.get("intent")

    if intent not in {
        "availability_check",
        "create_order",
    }:
        return {
            "product_name": None,
            "quantity": None,
        }

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        ProductRequest
    )

    response = structured_llm.invoke(
        [
            {
                "role": "system",
                "content": """
                            Extract the product name and requested quantity
                            from the customer's message.

                            Rules:
                            - Do not invent a product name.
                            - If quantity is not explicitly provided, return null.
                            - Return only the requested product information.
                            """,
            },
            {
                "role": "user",
                "content": messages[-1],
            },
        ]
    )

    return {
        "product_name": response.product_name,
        "quantity": response.quantity,
    }

# ---------------------------------Product Resolution--------------------------------------
def resolve_product(state):
    product_name = state.get("product_name")

    if not product_name:
        return {
            "error": "Product name was not provided."
        }

    products = ProductService.search_products(
        query=product_name
    )

    if not products:
        return {
            "error": f"Product '{product_name}' was not found."
        }

    if len(products) > 1:
        return {
            "error": "Multiple products matched the request."
        }

    return {
        "product_id": products[0].id
    }