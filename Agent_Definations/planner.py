"""Planner agent for action-oriented requests."""

from graph_state import GraphState
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client


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


async def planner_node(state: GraphState):
    print("========== PLANNER NODE ==========")

    intent = state.get("intent")
    if intent == "whatsapp_messaging":
        try:
            result = await whatsapp_client.execute(
                conversation_id=state.get("conversation_id", "default"),
                user_input=state["user_input"],
                system_prompt=WHATSAPP_SYSTEM_PROMPT,
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
                system_prompt=REMINDER_SYSTEM_PROMPT,
                messages=state.get("messages", []),
            )
        except Exception as exc:
            result = f"Reminders are currently unavailable: {exc}"
        tool_name = "reminder_mcp"
        description = "Resolve the reminder schedule and persist it in PostgreSQL"
    else:
        result = "This planner does not yet support that action."
        tool_name = "unsupported"
        description = "Unsupported planner action"

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
    }
