from langgraph.graph import StateGraph, END

from graph_state import GraphState

from Agent_Definations.orchestrator import orchestrator_node
from Agent_Definations.memory import memory_node
from dotenv import load_dotenv

load_dotenv()

workflow = StateGraph(GraphState)

# ------------------------
# Nodes
# ------------------------

workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("memory", memory_node)

# Planner node will be added later
# workflow.add_node("planner", planner_node)

# ------------------------
# Entry
# ------------------------

workflow.set_entry_point("orchestrator")


# ------------------------
# Router
# ------------------------

def orchestrator_router(state: GraphState):
    return state["routing_decision"]


workflow.add_conditional_edges(
    "orchestrator",
    orchestrator_router,
    {
        "planner": END,                 # Add planner node later
        "memory": "memory",
        "planner_with_memory": END,     # Later -> memory -> planner
        "respond": END,
        "clarify": END,
    },
)

# ------------------------
# Memory
# ------------------------

workflow.add_edge(
    "memory",
    END,
)

app = workflow.compile()


from langchain_core.messages import HumanMessage

state = {
    "messages": [
        HumanMessage(content="Can you update my name from Mayur to Mayur Nayak")
    ],

    "user_input": "Can you update my name from Mayur to Mayur Nayak",

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

    # Execution
    "artifacts": {},
    "tool_results": {},

    # Errors
    "errors": [],

    # Final
    "final_response": "",
}


import asyncio
result = asyncio.run(app.ainvoke(state))
print(result["memory_result"])