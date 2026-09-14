from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes import (
    understand_request,
    retrieve_context,
    extract_product_request,
    resolve_product,
    agent_decision,
    prepare_tool_input,
    execute_tool,
    generate_response,
)


def route_after_decision(state):
    if state.get("tool_name"):
        return "extract_product_request"

    return "generate_response"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("understand_request", understand_request)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("extract_product_request", extract_product_request)
    graph.add_node("resolve_product", resolve_product,)
    graph.add_node("agent_decision", agent_decision)
    graph.add_node("prepare_tool_input", prepare_tool_input)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("generate_response", generate_response)

    graph.add_edge(START, "understand_request")
    graph.add_edge("understand_request", "retrieve_context")
    graph.add_edge("retrieve_context", "agent_decision")

    graph.add_conditional_edges(
        "agent_decision",
        route_after_decision,
        {
            "extract_product_request": "extract_product_request",
            "generate_response":"generate_response"
        },
    )

    graph.add_edge("extract_product_request", "resolve_product")
    graph.add_edge("resolve_product","prepare_tool_input")
    graph.add_edge("prepare_tool_input", "execute_tool")
    graph.add_edge("execute_tool", "generate_response")
    graph.add_edge("generate_response",END)

    return graph.compile()


agent_graph = build_graph()