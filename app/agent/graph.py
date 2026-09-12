from langgraph.graph import StateGraph,START, END
from app.agent.state import AgentState
from app.agent.nodes import (
    understand_request,
    retrieve_context,
    agent_decision,
    execute_tool,
    generate_response
)


def route_after_decision(state):
    if state.get("tool_name"):
        return "execute_tool"

    return "generate_response"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node(
        "understand_request",
        understand_request,
    )

    graph.add_node(
        "retrieve_context",
        retrieve_context,
    )

    graph.add_node(
        "agent_decision",
        agent_decision,
    )

    graph.add_node(
        "execute_tool",
        execute_tool,
    )

    graph.add_node(
        "generate_response",
        generate_response,
    )

    graph.add_edge(
        START,
        "understand_request",
    )

    graph.add_edge(
        "understand_request",
        "retrieve_context",
    )

    graph.add_edge(
        "retrieve_context",
        "agent_decision",
    )

    graph.add_conditional_edges(
        "agent_decision",
        route_after_decision,
        {
            "execute_tool": "execute_tool",
            "generate_response": "generate_response",
        },
    )

    graph.add_edge(
        "execute_tool",
        "generate_response",
    )

    graph.add_edge(
        "generate_response",
        END,
    )

    return graph.compile()

agent_graph = build_graph()
