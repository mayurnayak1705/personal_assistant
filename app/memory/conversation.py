from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


def format_conversation(messages: list[BaseMessage], max_turns: int = 10) -> str:
    """
    Renders the last `max_turns` user/assistant turns as a plain-text
    transcript, e.g.:

        User: Add an expense for travel, 100 rupees
        Assistant: Done — logged ₹100 for travel.
        User: Actually make that 150

    max_turns counts turns (user+assistant pairs), not individual messages,
    so it slices the last (max_turns * 2) messages.
    """
    trimmed = messages[-max_turns * 2:] if max_turns else messages

    lines = []
    for m in trimmed:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            lines.append(f"Assistant: {m.content}")

    return "\n".join(lines) if lines else "(no prior conversation)"
