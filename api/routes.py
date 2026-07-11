from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
import traceback

from schemas import ChatRequest, ChatResponse
from graph import app

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:

        state = {
            # Conversation
            "messages": [
                HumanMessage(content=request.message)
            ],
            "user_input": request.message,

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

            # Final Response
            "final_response": "",
        }

        result = await app.ainvoke(state)

        response = (
            result.get("final_response")
            or result.get("memory_result")
            or result.get("clarification_question")
            or "I couldn't generate a response."
        )

        return ChatResponse(
            response=str(response),
            success=True,
        )

    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Internal server error. Check terminal for traceback."
        )


@router.get("/health")
async def health():
    return {
        "status": "online",
        "assistant": "ready"
    }