import asyncio
import uuid
import traceback
import logging
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from langchain_core.messages import HumanMessage, AIMessage

from schemas import (
    ChatRequest,
    ChatResponse,
    EndSessionRequest,
    EndSessionResponse,
    ReminderAcknowledgeRequest,
    TaskActionRequest,
    WhatsAppToggleRequest,
    GmailActionRequest,
    ExpenseImportActionRequest,
    GoogleOAuthConfigRequest,
)
from graph import app
from session_store import add_turn, get_turns, pop_session
from token_utils import count_tokens
from Server.postgre_insert import insert_chat_history_batch
from Server.postgre_search import fetch_conversation_history, fetch_user_facts, fetch_user_profile_name
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client
from mcp_servers.tasks.client import tasks_client
from mcp_servers.gmail.client import gmail_client
from mcp_servers.calendar.client import calendar_client
from action_history_store import fetch_action_history, save_action_history_events
from follow_up_suggestions import choose_follow_up
from working_context import build_tool_event
from working_context_store import fetch_working_context, save_working_context_events
from daily_briefing import generate_daily_briefing
from daily_briefing_store import get_daily_briefing_preference
from google_oauth import (
    begin_authorization,
    complete_authorization,
    connection_status as google_connection_status,
    delete_credentials as delete_google_credentials,
    save_client_config as save_google_client_config,
)
from expense_email_ingestion import pending_imports, resolve_import, scan_transaction_emails
from debug_log import debug

router = APIRouter()
logger = logging.getLogger(__name__)


def _time_period(hour: int) -> tuple[str, str]:
    if hour < 12:
        return "morning", "Good morning"
    if hour < 17:
        return "afternoon", "Good afternoon"
    return "evening", "Good evening"


async def _record_action_events(
    *,
    conversation_id: str,
    user_id: str,
    events: list[dict],
) -> dict | None:
    if not events:
        return None

    # A suggestion is computed from the same immutable events as history.
    # It never executes automatically and at most one is returned per turn.
    suggestion = choose_follow_up(events)
    writes = await asyncio.gather(
        asyncio.to_thread(
            save_working_context_events,
            conversation_id=conversation_id,
            user_id=user_id,
            events=events,
        ),
        asyncio.to_thread(
            save_action_history_events,
            conversation_id=conversation_id,
            user_id=user_id,
            events=events,
        ),
        return_exceptions=True,
    )
    for store_name, result in zip(("working context", "action history"), writes):
        if isinstance(result, Exception):
            # Persistence is an enhancement; it must never turn a successful
            # external action into a reported failure.
            logger.warning("Could not persist %s: %s", store_name, result)
    return suggestion


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:
        conversation_id = request.conversation_id or str(uuid.uuid4())
        user_id = request.user_id or "mayur"

        try:
            working_context = await asyncio.to_thread(
                fetch_working_context,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("Could not load working context: %s", exc)
            working_context = []

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
        user_facts = await asyncio.to_thread(fetch_user_facts)
        debug("API", "chat_context", conversation_id=conversation_id, user_id=user_id,
              prior_turn_count=len(prior_turns), user_facts_chars=len(str(user_facts)))
        state = {
            # Conversation - now includes everything said earlier in this
            # session, not just the latest message
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": [*history_messages, HumanMessage(content=request.message)],
            "user_input": request.message,
            "user_facts": user_facts,
            "working_context": working_context,
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

        suggestion = await _record_action_events(
            conversation_id=conversation_id,
            user_id=user_id,
            events=(result.get("tool_results") or {}).get("events", []),
        )

        # Buffer this turn. It isn't written to Postgres yet — that happens
        # once, in a batch, when the session ends (see /session/end below).
        await add_turn(conversation_id, "user", request.message, count_tokens(request.message))
        await add_turn(conversation_id, "assistant", response_text, count_tokens(response_text))

        return ChatResponse(
            response=response_text,
            conversation_id=conversation_id,
            success=True,
            artifact=(result.get("artifacts") or {}).get("expense_report"),
            suggestion=suggestion,
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
        "assistant": "ready",
        "whatsapp": whatsapp_client.status,
        "reminders": reminder_client.status,
        "tasks": tasks_client.status,
        "gmail": gmail_client.status,
        "calendar": calendar_client.status,
    }


@router.get("/user/profile")
async def user_profile(user_id: str = "mayur"):
    """Return the database-backed display name and server-authoritative greeting."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    period, greeting = _time_period(now.hour)
    try:
        profile = await asyncio.to_thread(fetch_user_profile_name, user_id)
    except Exception as exc:
        logger.warning("Could not load user profile name: %s", exc)
        profile = None
    return {
        "user_id": user_id,
        "display_name": profile.get("display_name") if profile else None,
        "first_name": profile.get("first_name") if profile else None,
        "greeting": greeting,
        "time_period": period,
        "current_time": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Kolkata",
    }


@router.get("/actions/recent")
async def recent_actions(
    user_id: str = "mayur",
    conversation_id: str | None = None,
    limit: int = 50,
):
    """Return structured durable history for audit and future assistant features."""
    try:
        return {
            "actions": await asyncio.to_thread(
                fetch_action_history,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/briefing/daily")
async def daily_briefing(user_id: str = "mayur", force: bool = False):
    """Generate once after the user's scheduled time during morning hours."""
    try:
        if not force:
            preference = await asyncio.to_thread(
                get_daily_briefing_preference,
                user_id=user_id,
            )
            timezone_name = preference.get("timezone") or "Asia/Kolkata"
            try:
                now = datetime.now(ZoneInfo(timezone_name))
            except Exception:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
            scheduled_time = preference["briefing_time"]
            if not preference.get("enabled", True):
                return {"should_show": False, "reason": "disabled"}
            if now.hour >= 12:
                return {"should_show": False, "reason": "morning_window_closed"}
            if now.time().replace(tzinfo=None) < scheduled_time:
                return {
                    "should_show": False,
                    "reason": "not_due",
                    "scheduled_time": scheduled_time.strftime("%H:%M"),
                }
        return await generate_daily_briefing(user_id=user_id, force=force)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/gmail/status")
async def gmail_status():
    """Return Gmail OAuth connection status without exposing token data."""
    try:
        return await gmail_client.connection_status()
    except Exception as exc:
        return {"authenticated": False, "email": None, "error": str(exc)}


@router.get("/integrations/google/status")
async def google_integration_status(user_id: str = "mayur"):
    """Return the shared Gmail and Calendar connection state."""
    return await asyncio.to_thread(google_connection_status, user_id)


@router.post("/integrations/google/connect")
async def google_integration_connect(request: Request, user_id: str = "mayur"):
    """Start a PKCE-protected Google desktop authorization flow."""
    redirect_uri = str(request.url_for("google_oauth_callback"))
    try:
        return begin_authorization(user_id=user_id, redirect_uri=redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/integrations/google/configure")
async def google_integration_configure(request: GoogleOAuthConfigRequest):
    """Validate and store a user-provided Google Desktop OAuth JSON."""
    try:
        return await asyncio.to_thread(
            save_google_client_config,
            request.user_id,
            request.client_config,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/integrations/google/callback",
    response_class=HTMLResponse,
    name="google_oauth_callback",
)
async def google_oauth_callback(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
):
    """Exchange Google's authorization code and notify the Settings popup."""
    success = False
    message = "Google connection was cancelled."
    if not error and state and code:
        try:
            await asyncio.to_thread(complete_authorization, state=state, code=code)
            success = True
            message = "Google connected. You can close this window."
        except Exception as exc:
            message = str(exc)
    elif error:
        message = f"Google authorization failed: {error}"

    origin = f"{request.url.scheme}://{request.url.netloc}"
    payload = json.dumps({"type": "deep-thought-google-oauth", "success": success})
    return HTMLResponse(
        "<!doctype html><html><head><meta charset='utf-8'><title>Deep Thought Google connection</title>"
        "<style>body{font:16px system-ui;background:#0b1020;color:#f8fafc;display:grid;place-items:center;"
        "min-height:100vh;margin:0}.card{max-width:520px;padding:28px;border:1px solid #29334f;"
        "border-radius:18px;background:#121a2d;text-align:center}p{color:#aab4ca}</style></head><body>"
        f"<div class='card'><h1>{'Connected' if success else 'Connection failed'}</h1>"
        f"<p>{html.escape(message)}</p></div><script>"
        f"if(window.opener){{window.opener.postMessage({payload},{json.dumps(origin)});}}"
        "setTimeout(()=>window.close(),700);</script></body></html>"
    )


@router.post("/integrations/google/disconnect")
async def google_integration_disconnect(user_id: str = "mayur"):
    """Remove locally stored Google authorization for this user."""
    await asyncio.to_thread(delete_google_credentials, user_id)
    return {"connected": False, "gmail": False, "calendar": False}


@router.get("/calendar/status")
async def calendar_status():
    """Return Calendar OAuth connection status without exposing token data."""
    try:
        return await calendar_client.connection_status()
    except Exception as exc:
        return {"authenticated": False, "calendar_id": None, "error": str(exc)}


@router.get("/calendar/events")
async def calendar_events(limit: int = 20):
    """Return upcoming Calendar events for UI integrations."""
    try:
        return await calendar_client.upcoming_events(limit=max(1, min(limit, 50)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/gmail/unread")
async def gmail_unread(limit: int = 20):
    """Return unread inbox messages for the Gmail UI panel."""
    try:
        return await gmail_client.unread_emails(limit=max(1, min(limit, 50)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/expense-imports")
async def expense_import_notifications(scan: bool = False, limit: int = 50):
    """Return Gmail-derived expenses awaiting review, optionally scanning first."""
    try:
        scan_result = await asyncio.to_thread(scan_transaction_emails, min(limit, 50)) if scan else None
        imports = await asyncio.to_thread(pending_imports, limit)
        return {"imports": imports, "count": len(imports), "scan": scan_result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/expense-imports/{import_id}/resolve")
async def resolve_expense_import(import_id: int, request: ExpenseImportActionRequest):
    """Keep, delete, or categorize an automatically imported expense."""
    try:
        result = await asyncio.to_thread(resolve_import, import_id, request.action, request.category)
        if not result:
            raise HTTPException(status_code=404, detail="Expense import not found")
        result["suggestion"] = await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(
                integration="expenses",
                tool_name=f"{request.action}_email_import",
                arguments={"import_id": import_id, "category": request.category},
                output=result,
            )],
        )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/gmail/messages/{message_id}")
async def gmail_message(
    message_id: str,
    user_id: str = "mayur",
    conversation_id: str | None = None,
):
    """Return one complete Gmail message for the safe reader modal."""
    try:
        result = await gmail_client.read_email(message_id)
        await _record_action_events(
            conversation_id=conversation_id or f"ui:{user_id}",
            user_id=user_id,
            events=[build_tool_event(
                integration="gmail",
                tool_name="read_email",
                arguments={"message_id": message_id},
                output=result,
            )],
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/gmail/scheduled")
async def gmail_scheduled(user_id: str = "mayur", limit: int = 20):
    try:
        return await gmail_client.scheduled_emails(user_id=user_id, limit=max(1, min(limit, 50)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/gmail/messages/{message_id}/read")
async def gmail_mark_read(message_id: str, request: GmailActionRequest):
    try:
        result = await gmail_client.mark_read(message_id)
        await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(integration="gmail", tool_name="mark_email_read", arguments={"message_id": message_id}, output=result)],
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/gmail/messages/{message_id}/archive")
async def gmail_archive(message_id: str, request: GmailActionRequest):
    try:
        result = await gmail_client.archive(message_id)
        await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(integration="gmail", tool_name="archive_email", arguments={"message_id": message_id}, output=result)],
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/gmail/scheduled/{schedule_id}/cancel")
async def gmail_cancel_scheduled(schedule_id: str, request: GmailActionRequest):
    try:
        result = await gmail_client.cancel_scheduled(schedule_id, request.user_id)
        await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(
                integration="gmail",
                tool_name="cancel_scheduled_email",
                arguments={"schedule_id": schedule_id, "user_id": request.user_id},
                output=result,
                is_error=result.get("status") == "not_found",
            )],
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/whatsapp/messages")
async def whatsapp_messages(
    after_id: int | None = None,
    limit: int = 50,
    user_id: str = "mayur",
    conversation_id: str | None = None,
):
    """Poll new inbound WhatsApp messages for the browser UI."""
    if not whatsapp_client.enabled:
        return {
            "cursor": after_id,
            "messages": [],
            "enabled": False,
            "connected": False,
        }
    try:
        payload = await whatsapp_client.poll_messages(
            after_id=after_id,
            limit=max(1, min(limit, 200)),
        )
        payload["enabled"] = True
        payload["connected"] = whatsapp_client.connected
        inbound_events = [
            build_tool_event(
                integration="whatsapp",
                tool_name="receive_message",
                arguments={},
                output={"message": message},
            )
            for message in payload.get("messages", [])
        ]
        await _record_action_events(
            conversation_id=conversation_id or f"ui:{user_id}",
            user_id=user_id,
            events=inbound_events,
        )
        return payload
    except Exception as exc:
        # A normal JSON response lets the UI show an offline state without
        # generating a noisy failed HTTP request every polling interval.
        return {
            "cursor": after_id,
            "messages": [],
            "connected": False,
            "enabled": whatsapp_client.enabled,
            "error": str(exc),
        }


@router.get("/whatsapp/state")
async def whatsapp_state():
    """Return the persisted WhatsApp integration state."""
    return whatsapp_client.status


@router.put("/whatsapp/state")
async def update_whatsapp_state(request: WhatsAppToggleRequest):
    """Enable or disable all WhatsApp sending and receiving."""
    try:
        return await whatsapp_client.set_enabled(request.enabled)
    except Exception as exc:
        # Return the state as well as the error so the UI can accurately show
        # an enabled integration that failed to connect.
        raise HTTPException(
            status_code=503,
            detail={**whatsapp_client.status, "error": str(exc)},
        ) from exc


@router.post("/whatsapp/pairing/start")
async def start_whatsapp_pairing():
    """Start first-time WhatsApp linking and QR generation."""
    try:
        return await whatsapp_client.start_pairing()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/whatsapp/pairing")
async def whatsapp_pairing_status():
    """Return the latest QR image or terminal pairing state."""
    return whatsapp_client.pairing_status


@router.delete("/whatsapp/pairing")
async def cancel_whatsapp_pairing():
    """Cancel an in-progress QR pairing attempt."""
    return await whatsapp_client.cancel_pairing()


@router.get("/whatsapp/contacts")
async def whatsapp_contacts(query: str = ""):
    """Expose the name/number mapping used by contact disambiguation."""
    if not whatsapp_client.enabled:
        raise HTTPException(status_code=409, detail="WhatsApp integration is turned off")
    try:
        return await whatsapp_client.list_contacts(query)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/reminders/due")
async def due_reminders(user_id: str = "mayur", limit: int = 50):
    """Return pending reminders whose scheduled time has passed."""
    try:
        return await reminder_client.due_reminders(
            user_id=user_id,
            limit=max(1, min(limit, 200)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reminders/{reminder_id}/acknowledge")
async def acknowledge_reminder(
    reminder_id: str,
    request: ReminderAcknowledgeRequest,
):
    """Acknowledge a reminder and delete it from PostgreSQL."""
    try:
        result = await reminder_client.acknowledge(
            reminder_id=reminder_id,
            user_id=request.user_id,
        )
        suggestion = await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(
                integration="reminders",
                tool_name="acknowledge_reminder",
                arguments={"reminder_id": reminder_id, "user_id": request.user_id},
                output=result,
                is_error=result.get("status") == "not_found",
            )],
        )
        return {**result, "suggestion": suggestion}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tasks/notifications")
async def task_notifications(user_id: str = "mayur", limit: int = 50):
    """Return open tasks that are due now or overdue for the notification panel."""
    try:
        return await tasks_client.notification_tasks(
            user_id=user_id,
            limit=max(1, min(limit, 200)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tasks")
async def list_tasks(user_id: str = "mayur", view: str = "all", limit: int = 200):
    """Return task records and statuses for the dedicated Tasks panel."""
    try:
        return await tasks_client.list_tasks(
            user_id=user_id,
            view=view,
            limit=max(1, min(limit, 200)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, request: TaskActionRequest):
    """Complete one task from the notification panel."""
    try:
        result = await tasks_client.complete(task_id=task_id, user_id=request.user_id)
        suggestion = await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(
                integration="tasks",
                tool_name="complete_task",
                arguments={"task_id": task_id, "user_id": request.user_id},
                output=result,
                is_error=result.get("status") == "not_found",
            )],
        )
        return {**result, "suggestion": suggestion}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/tomorrow")
async def postpone_task_until_tomorrow(task_id: str, request: TaskActionRequest):
    """Move one due task to tomorrow at 09:00 local time."""
    try:
        result = await tasks_client.postpone_until_tomorrow(
            task_id=task_id,
            user_id=request.user_id,
        )
        suggestion = await _record_action_events(
            conversation_id=request.conversation_id or f"ui:{request.user_id}",
            user_id=request.user_id,
            events=[build_tool_event(
                integration="tasks",
                tool_name="update_task",
                arguments={
                    "task_id": task_id,
                    "user_id": request.user_id,
                    "relative_due": "tomorrow 09:00",
                },
                output=result,
                is_error=result.get("status") == "not_found",
            )],
        )
        return {**result, "suggestion": suggestion}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
