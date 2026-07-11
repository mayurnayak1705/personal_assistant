from typing import TypedDict, Annotated, Literal, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class PlanStep(TypedDict):
    id: int
    description: str
    tool: str
    inputs: dict
    status: Literal[
        "pending",
        "running",
        "completed",
        "failed",
        "skipped",
    ]


class GraphState(TypedDict):
    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str
    user_facts: str
    # Orchestrator Output
    intent: str
    routing_decision: str
    confidence: float
    confidence_threshold: float
    clarification_question: str

    # Memory Agent
    memory_result: dict

    # Planner
    execution_plan: list[PlanStep]
    current_step: int

    # Executor
    artifacts: dict[str, Any]
    tool_results: dict[str, Any]

    # Errors
    errors: list[str]

    # Final answer
    final_response: str