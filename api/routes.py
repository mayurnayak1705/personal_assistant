import asyncio
import uuid
import traceback

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from schemas import ChatRequest, ChatResponse, EndSessionRequest, EndSessionResponse
from graph import app
from session_store import add_turn, get_turns, pop_session
from token_utils import count_tokens
from Server.postgre_insert import insert_chat_history_batch
from Server.postgre_search import fetch_conversation_history

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:
        conversation_id = request.conversation_id or str(uuid.uuid4())
        user_id = request.user_id or "mayur"

        # Context from earlier in this chat: prefer the in-memory session
        # buffer (cheap, no DB round-trip). If it's empty — server restarted
        # mid-session, or this conversation_id was already flushed once and
        # is now continuing — fall back to what's already in Postgres.
        prior_turns = await get_turns(conversation_id)
        if not prior_turns:
            prior_turns = await asyncio.to_thread(fetch_conversation_history, conversation_id)

        history_messages = [
            HumanMessage(content=t["message"]) if t["role"] == "user"
            else AIMessage(content=t["message"])
            for t in prior_turns
        ]

        state = {
            # Conversation - now includes everything said earlier in this
            # session, not just the latest message
            "messages": [*history_messages, HumanMessage(content=request.message)],
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

        response_text = (
            result.get("final_response")
            or result.get("memory_result")
            or result.get("clarification_question")
            or "I couldn't generate a response."
        )
        response_text = str(response_text)

        # Buffer this turn. It isn't written to Postgres yet — that happens
        # once, in a batch, when the session ends (see /session/end below).
        await add_turn(conversation_id, "user", request.message, count_tokens(request.message))
        await add_turn(conversation_id, "assistant", response_text, count_tokens(response_text))

        return ChatResponse(
            response=response_text,
            conversation_id=conversation_id,
            success=True,
        )

    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Internal server error. Check terminal for traceback."
        )


@router.post("/session/end", response_model=EndSessionResponse)
async def end_session(request: EndSessionRequest):
    """
    Flushes every buffered turn for a conversation into chat_history as one
    batch insert, then clears the buffer.

    Called two ways:
    - Automatically by the frontend via navigator.sendBeacon when the tab
      closes or is refreshed (see app.js: the 'pagehide' listener).
    - Explicitly, if you add a "New chat" / "End session" action later.

    Note: if the tab is killed without a pagehide event ever firing (browser
    crash, force-quit), whatever's still buffered is lost — see the
    trade-off note at the top of session_store.py.
    """
    turns = await pop_session(request.conversation_id)

    if not turns:
        return EndSessionResponse(success=True, messages_saved=0)

    inserted_ids = await asyncio.to_thread(
        insert_chat_history_batch,
        conversation_id=request.conversation_id,
        user_id=request.user_id or "mayur",
        turns=turns,
    )

    return EndSessionResponse(success=True, messages_saved=len(inserted_ids))


@router.get("/health")
async def health():
    return {
        "status": "online",
        "assistant": "ready"
    }