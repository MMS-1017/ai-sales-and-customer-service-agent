from typing import TypedDict

class AgentState(TypedDict, total=False): 
    messages: list
    intent: str
    customer_id: int | None 
    retrieved_context: list 
    tool_name: str | None 
    tool_input: dict | None
    tool_result: dict | None 
    response: str | None 
    error: str | None