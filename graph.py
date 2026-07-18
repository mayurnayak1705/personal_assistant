from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import asyncio

from graph_state import GraphState

from Agent_Definations.orchestrator import orchestrator_node
from Agent_Definations.memory import memory_node
from Agent_Definations.planner import planner_node
from Agent_Definations.respond import respond_node
from debug_log import debug

load_dotenv()

workflow = StateGraph(GraphState)

# ------------------------
# Nodes
# ------------------------

workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("memory", memory_node)
workflow.add_node("planner", planner_node)
workflow.add_node("respond", respond_node)

# ------------------------
# Entry
# ------------------------

workflow.set_entry_point("orchestrator")

# ------------------------
# Router
# ------------------------

def orchestrator_router(state: GraphState):
    decision = state["routing_decision"]
    debug("AGENT", "route", from_agent="orchestrator", to_agent=decision,
          intent=state.get("intent"), confidence=state.get("confidence"))
    return decision


workflow.add_conditional_edges(
    "orchestrator",
    orchestrator_router,
    {
        "planner": "planner",
        "memory": "memory",
        "planner_with_memory": END,     # Later -> memory -> planner
        "respond": "respond",
        "clarify": END,
    },
)

# ------------------------
# Memory
# ------------------------

workflow.add_edge(
    "memory",
    "respond",
)

workflow.add_edge(
    "planner",
    "respond",
)


# ------------------------
# Respond
# ------------------------

workflow.add_edge(
    "respond",
    END,
)

app = workflow.compile()


# ------------------------
# Test State
# ------------------------

state = {
    "conversation_id": "graph-manual-test",
    "user_id": "local-user",
    "messages": [
        HumanMessage(content="Can you add expense for travel 100 rupees on 10th July 2026")
    ],

    "user_input": "Can you add expense for travel 100 rupees on 10th July 2026",
    "working_context": [],

    # Orchestrator
    "intent": "",
    "routing_decision": "",
    "confidence": 0.0,
    "confidence_threshold": 0.85,
    "clarification_question": "",

    # Memory
    "memory_result": None,

    # Planner
    "execution_plan": [],
    "current_step": 0,
    "planner_result": None,

    # Execution
    "artifacts": {},
    "tool_results": {},

    # Errors
    "errors": [],

    # Final
    "final_response": "",
}

if __name__ == "__main__":

    result = asyncio.run(app.ainvoke(state))

    if result.get("memory_result"):
        print(result["memory_result"])

    elif result.get("final_response"):
        print(result["final_response"])

    elif result.get("clarification_question"):
        print(result["clarification_question"])
