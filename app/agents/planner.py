"""Planner agent for action-oriented requests."""

import asyncio
import re
from datetime import time

from app.orchestration.state import GraphState
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client
from mcp_servers.tasks.client import tasks_client
from mcp_servers.gmail.client import gmail_client
from mcp_servers.calendar.client import calendar_client
from mcp_servers.wellness.client import wellness_client
from mcp_servers.finance.client import finance_client
from app.features.briefing.service import generate_daily_briefing
from app.features.briefing.store import set_daily_briefing_preference
from app.memory.working_context import ToolExecutionResult, build_tool_event, context_instructions, replay_protection_message
from app.core.debug import debug
from app.features.profile.store import DEFAULT_USER_ID


WHATSAPP_SYSTEM_PROMPT = """
# WhatsApp Planner Agent

You plan and execute WhatsApp text-message actions exclusively through the
WhatsApp MCP tools. Never claim a message was sent unless send_message returns
success.

Rules:
- For a send request, identify both the intended contact and exact message.
- The user's instruction to send is already authorization. Once one exact
  contact is resolved, call send_message immediately in the same turn. Never
  ask "shall I send", "should I proceed", or request another confirmation.
- Use list_contacts when resolving a human name.
- A case-insensitive exact saved-name match always wins over partial matches.
- Never choose between multiple contacts only when there is no unique exact
  saved-name/number match.
- If multiple contacts match, do not call send_message. Ask one clarification
  question and show every matching name with its phone number.
- A user's follow-up may select a contact by phone number or by referring to an
  option in the prior conversation. Use the conversation to resolve it.
- Send only the message the user requested. Do not add greetings, signatures,
  or extra wording.
- read_messages may be used only when the user asks to read WhatsApp history.
- Keep the final result concise.
"""


REMINDER_SYSTEM_PROMPT = """
# Reminder Planner Agent

You create and manage durable reminders exclusively through Reminder MCP tools.

Rules:
- An explicit "remind me" request is authorization to create the reminder now.
- Resolve relative times using the current datetime supplied by the client.
- Call create_reminder in the same turn; do not ask for confirmation when the
  reminder text and time are both clear.
- The title should be short. The description must preserve what the user wants
  to be reminded about, without the scheduling phrase.
- Never claim a reminder was created unless the MCP tool returned success.
- If the time is genuinely missing, ask one concise clarification question.
"""


TASK_SYSTEM_PROMPT = """
# Tasks Planner Agent

You create and manage persistent personal tasks exclusively through Tasks MCP tools.

Rules:
- A task is work to track; it does not execute an email, WhatsApp message, or other external action.
- An explicit request to add a task is authorization to create it immediately.
- Tasks may have no due date. Do not ask for a due date unless the user explicitly indicates one is needed but the date is ambiguous.
- Extract a short title, optional description, due date, priority, and category from natural language.
- Resolve relative dates using the current datetime supplied by the client.
- Use list_tasks to resolve a task by title before updating, completing, reopening, or deleting it.
- If exactly one task matches, act on it in the same turn.
- If multiple tasks match, ask one clarification question showing the matching titles, due dates, and IDs.
- Completing a task keeps it in history. It does not delete it.
- A request to delete one uniquely identified task may be executed directly.
- Never bulk-delete tasks. If the user asks to delete several or all tasks, ask for confirmation and do not call delete_task in that turn.
- "Undo" means call undo_latest_task_change.
- Never claim an operation succeeded unless its tool result confirms success.
- Keep list responses structured and concise; show at most 10 tasks unless the user asks for more.
"""


GMAIL_SYSTEM_PROMPT = """
# Gmail Planner Agent

You read and manage Gmail exclusively through Gmail MCP tools.

Rules:
- Use only the Gmail account authenticated by the user or its configured GMAIL_FROM_EMAIL address. Never invent or substitute another sender.
- Reading, searching, drafting, marking read, and archiving may be executed when requested.
- Call send_email or reply_to_email only when the user explicitly asks to send or reply. A request to "write" or "compose" without "send" creates a draft.
- Scheduling an email is explicit authorization to store it for automatic delivery at the requested time. Call schedule_email immediately when recipient, content, and time are clear.
- Resolve relative schedule times using the current datetime supplied by the client.
- Never guess an email address from a name. Use an exact address from the request or recent compatible context. If it is unavailable or ambiguous, ask one concise clarification question.
- Use stable Gmail message IDs from list/search results before reading, replying, marking read, or archiving.
- Never claim an email was sent, drafted, scheduled, or changed unless the MCP result confirms it.
- Do not permanently delete email.
- Keep inbox lists concise and show at most 10 messages unless the user asks for more.
"""


CALENDAR_SYSTEM_PROMPT = """
# Google Calendar Planner Agent

You create and manage Google Calendar meetings exclusively through Calendar MCP tools.

Rules:
- An explicit request to schedule, book, or create a meeting is authorization to create it immediately.
- A created meeting must include a fresh Google Meet link and send Calendar invitations to all attendees.
- Resolve relative dates and times using the current datetime supplied by the client.
- Never invent an attendee email address. Use exact addresses from the request or recent compatible context.
- If the date, time, or attendee email is genuinely missing or ambiguous, ask one concise clarification question.
- If duration is omitted, use 30 minutes. Convert the subject into a short title and preserve useful context in the description.
- Use list_calendar_events to identify an event before cancellation. If several events match, ask the user to choose.
- Never claim a meeting was created or cancelled unless the MCP result confirms it.
- In the final response include the title, date/time, attendee list, and Google Meet URL returned by the tool.
"""

WELLNESS_SYSTEM_PROMPT = """You manage private wellness tracking entirely through conversation; never direct the user to a form.

When the user starts wellness, first call get_wellness_profile. If no profile exists, run a calm guided onboarding and collect the baseline in small conversational steps: age, biological sex (allow "prefer not to say"), height, current weight, primary goal, measurable milestone, activity level, diet preferences or restrictions, relevant physical restrictions, motivation, and preferred morning/evening reminder times. Ask only one concise question at a time. Accept several answers at once when volunteered and do not ask for information already provided in the conversation. Save the profile only after the baseline is complete.

Immediately after saving the baseline, do not ask the user to choose a tracking category. Instead, explain how the feature works: they can naturally tell you about meals and hydration, workouts and activity, sleep/mood/energy, or body measurements whenever relevant. Explain that the stored insights include consistency, goal proximity, active minutes and steps, sleep and mood averages, and weight trends when those inputs exist. Tell them the top wellness heart button opens visual graphs and summaries.

For an existing profile, a request to start or open wellness should give that same short usage guide and invite the user to share an update naturally. Log diet, workouts, measurements, and daily journals through tools. Infer the log kind from the user's words instead of making them select it. Nutrition values are estimates unless user supplied. Never diagnose, prescribe medication, extreme diets, or injury treatment; recommend professional care for medical needs. Reports must summarize consistency, trailing trends, and goal proximity concisely."""


FINANCE_SYSTEM_PROMPT = """You manage the user's stock watchlist entirely through natural conversation. Never direct the user to a settings form or ask them to configure a widget manually.

Add, remove, list, and report on stocks only through the finance tools. Resolve company names to exchange-qualified symbols; for Reliance Industries in India use RELIANCE.NS. When the user sets an alert, preserve whether they mean a price threshold or percentage movement and whether the direction is above, below, up, down, or either-direction deviation. If wording such as 'over 500' does not make clear whether 500 is a currency price or 500 percent, ask one concise clarification question before calling a tool. Do not silently reinterpret units. A request like 'moves more than 5%' means percent_deviation. A request like 'goes above ₹500' means price_above.

Tell users that the watchlist widget is read-only and all configuration happens here in chat. The assistant produces an in-app watchlist summary at 9:15 AM Asia/Kolkata showing gainers and losers, and threshold notifications while the app is running. Market data may be delayed. Do not provide individualized buy, sell, or investment recommendations; present tracking facts only."""


def _parse_briefing_time(value: str) -> time | None:
    """Parse concise 12-hour or 24-hour briefing times."""
    text = value.strip().lower().replace(".", "")
    match = re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b", text)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        return time(hour=hour, minute=int(match.group(2) or 0))
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if match:
        return time(hour=int(match.group(1)), minute=int(match.group(2)))
    return None


def _format_briefing_time(value: time) -> str:
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {suffix}"


async def planner_node(state: GraphState):
    intent = state.get("intent")
    debug("AGENT", "start", agent="planner", intent=intent,
          conversation_id=state.get("conversation_id"), user_id=state.get("user_id"))
    recent_context = context_instructions(state.get("working_context", []))
    replay_message = replay_protection_message(
        intent, state.get("user_input", ""), state.get("working_context", [])
    )
    if replay_message:
        return {
            "planner_result": {"status": "success", "intent": intent, "result": replay_message},
            "execution_plan": [{
                "id": 1,
                "description": "Prevent replay of a completed external action",
                "tool": "replay_protection",
                "inputs": {"request": state.get("user_input", "")},
                "status": "completed",
            }],
            "current_step": 1,
            "tool_results": {"events": []},
        }
    if intent == "whatsapp_messaging":
        try:
            result = await whatsapp_client.execute(
                conversation_id=state.get("conversation_id", "default"),
                user_input=state["user_input"],
                system_prompt=WHATSAPP_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"WhatsApp is currently unavailable: {exc}"
        tool_name = "whatsapp_mcp"
        description = "Resolve the WhatsApp contact and execute the requested messaging action"
    elif intent == "reminder_management":
        try:
            result = await reminder_client.execute(
                user_id=state.get("user_id") or DEFAULT_USER_ID,
                user_input=state["user_input"],
                system_prompt=REMINDER_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Reminders are currently unavailable: {exc}"
        tool_name = "reminder_mcp"
        description = "Resolve the reminder schedule and persist it in PostgreSQL"
    elif intent == "task_management":
        try:
            result = await tasks_client.execute(
                user_id=state.get("user_id") or DEFAULT_USER_ID,
                user_input=state["user_input"],
                system_prompt=TASK_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Tasks are currently unavailable: {exc}"
        tool_name = "tasks_mcp"
        description = "Resolve and persist the requested task lifecycle action"
    elif intent == "email_management":
        try:
            result = await gmail_client.execute(
                user_id=state.get("user_id") or DEFAULT_USER_ID,
                user_input=state["user_input"],
                system_prompt=GMAIL_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Gmail is currently unavailable: {exc}"
        tool_name = "gmail_mcp"
        description = "Read, draft, send, reply to, or schedule Gmail messages"
    elif intent == "calendar_management":
        try:
            result = await calendar_client.execute(
                user_input=state["user_input"],
                system_prompt=CALENDAR_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
                recent_events=state.get("working_context", []),
            )
        except Exception as exc:
            result = f"Google Calendar is currently unavailable: {exc}"
        tool_name = "calendar_mcp"
        description = "Create, list, or cancel Google Calendar meetings with Google Meet"
    elif intent == "wellness_management":
        try:
            result = await wellness_client.execute(user_id=state.get("user_id") or DEFAULT_USER_ID,user_input=state["user_input"],system_prompt=WELLNESS_SYSTEM_PROMPT + recent_context,messages=state.get("messages", []))
        except Exception as exc:
            result = f"Wellness is currently unavailable: {exc}"
        tool_name = "wellness_tools"
        description = "Set up goals, log wellness activity, or generate a progress report"
    elif intent == "finance_watchlist":
        try:
            result = await finance_client.execute(
                user_id=state.get("user_id") or DEFAULT_USER_ID,
                user_input=state["user_input"],
                system_prompt=FINANCE_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Finance is currently unavailable: {exc}"
        tool_name = "finance_tools"
        description = "Configure or report on the natural-language stock watchlist and alerts"
    elif intent == "daily_briefing":
        try:
            briefing = await generate_daily_briefing(
                user_id=state.get("user_id") or DEFAULT_USER_ID,
                force=True,
            )
            result = ToolExecutionResult(
                text=briefing["text"],
                events=[build_tool_event(
                    integration="briefing",
                    tool_name="generate_daily_briefing",
                    arguments={"user_id": state.get("user_id") or DEFAULT_USER_ID, "force": True},
                    output={"briefing_date": briefing["briefing_date"], "summary": briefing["text"]},
                )],
            )
        except Exception as exc:
            result = f"Daily briefing is currently unavailable: {exc}"
        tool_name = "daily_briefing"
        description = "Aggregate today's tasks, reminders, WhatsApp items, and budget state"
    elif intent == "daily_briefing_schedule":
        briefing_time = _parse_briefing_time(state.get("user_input", ""))
        if briefing_time is None:
            result = "What time in the morning would you like the daily briefing to be triggered?"
        elif briefing_time.hour >= 12:
            result = "Daily briefings are morning-only. What morning time would you like?"
        else:
            user_id = state.get("user_id") or DEFAULT_USER_ID
            try:
                saved = await asyncio.to_thread(
                    set_daily_briefing_preference,
                    user_id=user_id,
                    briefing_time=briefing_time,
                )
                display_time = _format_briefing_time(saved["briefing_time"])
                result = ToolExecutionResult(
                    text=f"Your daily briefing is scheduled for {display_time} every morning.",
                    events=[build_tool_event(
                        integration="briefing",
                        tool_name="schedule_daily_briefing",
                        arguments={"user_id": user_id, "time": briefing_time.strftime("%H:%M")},
                        output={"enabled": True, "scheduled_time": briefing_time.strftime("%H:%M")},
                    )],
                )
            except Exception as exc:
                result = f"Daily briefing scheduling is currently unavailable: {exc}"
        tool_name = "schedule_daily_briefing"
        description = "Save the automatic morning daily briefing time"
    else:
        result = "This planner does not yet support that action."
        tool_name = "unsupported"
        description = "Unsupported planner action"

    if isinstance(result, ToolExecutionResult):
        events = result.events
        result = result.text
    else:
        events = []

    debug("AGENT", "complete", agent="planner", intent=intent, tool=tool_name,
          error_count=len(state.get("errors", [])), result_type=type(result).__name__,
          response_chars=len(str(result)), event_count=len(events))
    return {
        "planner_result": {
            "status": "failed" if "currently unavailable" in result else "success",
            "intent": state.get("intent", ""),
            "result": result,
        },
        "execution_plan": [
            {
                "id": 1,
                "description": description,
                "tool": tool_name,
                "inputs": {"request": state.get("user_input", "")},
                "status": "failed" if "currently unavailable" in result else "completed",
            }
        ],
        "current_step": 1,
        "tool_results": {"events": events},
    }
