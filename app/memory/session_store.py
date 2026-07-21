"""
In-memory session store for active chat conversations.

Design:
- Every turn (user + assistant) is appended here as it happens.
- Nothing is written to Postgres yet at this point — that only happens when
  the session ends (see routes.py: POST /api/session/end), so we do one
  batch insert per conversation instead of one write per message.
- Because the buffer already holds the full in-progress conversation, it
  doubles as the source of "context from earlier in this chat" for routes.py
  to feed back into the graph on the next turn.

Trade-off worth knowing: if the server process restarts or crashes before a
session is flushed, whatever's still in this buffer is lost. routes.py has a
fallback (querying chat_history by conversation_id) for the context-lookup
side of that, but any turns never explicitly flushed via /session/end simply
never make it to Postgres. If you'd rather not risk that, the safer
alternative is inserting each turn immediately in postgre_insert.py and
treating chat_history as the source of truth instead of this buffer.
"""

import asyncio
from datetime import datetime, timezone
from typing import TypedDict


class ChatTurn(TypedDict):
    role: str          # "user" | "assistant"
    message: str
    token_count: int
    created_at: str    # ISO timestamp


_sessions: dict[str, list[ChatTurn]] = {}
_tool_events: dict[str, list[dict]] = {}
_lock = asyncio.Lock()


async def add_turn(conversation_id: str, role: str, message: str, token_count: int) -> None:
    async with _lock:
        _sessions.setdefault(conversation_id, []).append({
            "role": role,
            "message": message,
            "token_count": token_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


async def get_turns(conversation_id: str) -> list[ChatTurn]:
    async with _lock:
        return list(_sessions.get(conversation_id, []))


async def add_tool_events(conversation_id: str, events: list[dict]) -> None:
    """Keep completed actions available for the active conversation immediately.

    This is deliberately in-process: a slow or unavailable database must not
    make a just-completed send/create action invisible on the next turn.
    """
    if not events:
        return
    async with _lock:
        stored = _tool_events.setdefault(conversation_id, [])
        stored.extend(events)
        # Enough history for references and replay protection, without letting
        # a long-running chat grow without bound.
        del stored[:-50]


async def get_tool_events(conversation_id: str) -> list[dict]:
    """Return newest-first tool actions for short-term reference resolution."""
    async with _lock:
        return list(reversed(_tool_events.get(conversation_id, [])))


async def pop_session(conversation_id: str) -> list[ChatTurn]:
    """Removes and returns all buffered turns for a conversation. Used when flushing to Postgres."""
    async with _lock:
        _tool_events.pop(conversation_id, None)
        return _sessions.pop(conversation_id, [])
