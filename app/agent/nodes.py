from app.config import Config
from app.agent.llm import get_llm
from app.agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.rag import get_embedding_service, ChromaVectorStore, KnowledgeRetriever

from pydantic import BaseModel, Field
from app.services import ProductService

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


#---------------------------------Intent Understanding Node--------------------------------------
def understand_request(state):
    llm = get_llm()

    messages = state.get("messages", [])
    conversation_history = "\n".join(str(message) for message in messages[:-1])
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

    print("========== PREPARE TOOL DEBUG ==========")
    print("TOOL:", tool_name)
    print("PRODUCT ID:", product_id)
    print("QUANTITY:", quantity)
    print("CUSTOMER ID:", customer_id)
    print("========================================")

    if not product_id:
        return {
            "tool_input": {},
            "error": "Product could not be identified."
        }

    if tool_name == "get_product_details":
        return {
            "tool_input": {
                "product_id": product_id
            }
        }

    if tool_name == "check_product_availability":
        if not quantity:
            return {
                "tool_input": {},
                "error": "Please specify the quantity."
            }

        return {
            "tool_input": {
                "product_id": product_id,
                "quantity": quantity
            }
        }

    if tool_name == "create_order":
        if not quantity:
            return {
                "tool_input": {},
                "error": "Please specify the quantity."
            }

        return {
            "tool_input": {
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": quantity
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

    else:
        tool_name = None

    print("========== AGENT DEBUG ==========")
    print("INTENT:", intent)
    print("PRODUCT:", state.get("product_name"))
    print("PRODUCT ID:", state.get("product_id"))
    print("TOOL:", tool_name)
    print("=================================")

    return {"tool_name": tool_name}

# ---------------------------------Generation Node--------------------------------------
def generate_response(state):

    llm = get_llm()

    conversation_history = "\n".join(
                                    str(message)
                                    for message in state.get("messages", [])
                                )

    retrieved_context = state.get("retrieved_context", [])

    tool_result = state.get("tool_result")

    prompt = f"""
            {SYSTEM_PROMPT}

            Conversation history:
            {conversation_history}

            Current intent:
            {state.get("intent", "unknown")}

            Retrieved knowledge:
            {retrieved_context}

            Backend tool result:
            {tool_result}

            Answer the user's latest message.

            The backend tool result has priority for:
            - product price
            - product stock
            - product existence
            - order status
            - order details

            If the backend tool result contains the requested information,
            answer directly using that information.

            Do not ask for additional product attributes unless they are
            required by the actual backend data model.

            Do not invent variants or configurations.

            Latest user message:
            {state["messages"][-1]}
        """

    result = llm.invoke(prompt)

    return {"response": result.content}

# ---------------------------------Tool Execution Node--------------------------------------
def execute_tool(state):
    print("========== TOOL DEBUG ==========")
    print("TOOL NAME:", state.get("tool_name"))
    print("TOOL INPUT:", state.get("tool_input"))
    print("================================")

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

    conversation_history = "\n".join(
                                    str(message)
                                    for message in state.get("messages", [])
                                )

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

    print("========== RESOLVE DEBUG ==========")
    print("PRODUCT NAME:", product_name)
    print("===================================")

    if not product_name:
        return {
            "error": "Product name could not be identified."
        }

    products = ProductService.search_products(query=product_name)

    print("MATCHED PRODUCTS:", [
        (product.id, product.name) for product in products
    ])

    if len(products) == 1:
        return {
            "product_id": products[0].id
        }

    if not products:
        return {
            "error": f"Product '{product_name}' was not found."
        }

    return {
        "error": "Multiple products matched the request."
    }