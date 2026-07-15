"""Planner agent for action-oriented requests."""

from graph_state import GraphState
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client
from mcp_servers.tasks.client import tasks_client
from mcp_servers.gmail.client import gmail_client
from working_context import ToolExecutionResult, context_instructions


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
- The configured From address is mayurnayak1705@gmail.com. Never invent or substitute another sender.
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


async def planner_node(state: GraphState):
    print("========== PLANNER NODE ==========")

    intent = state.get("intent")
    recent_context = context_instructions(state.get("working_context", []))
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
                user_id=state.get("user_id", "mayur"),
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
                user_id=state.get("user_id", "mayur"),
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
                user_id=state.get("user_id", "mayur"),
                user_input=state["user_input"],
                system_prompt=GMAIL_SYSTEM_PROMPT + recent_context,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Gmail is currently unavailable: {exc}"
        tool_name = "gmail_mcp"
        description = "Read, draft, send, reply to, or schedule Gmail messages"
    else:
        result = "This planner does not yet support that action."
        tool_name = "unsupported"
        description = "Unsupported planner action"

    if isinstance(result, ToolExecutionResult):
        events = result.events
        result = result.text
    else:
        events = []

    print("========== PLANNER RESPONSE ==========")
    print(result)
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
