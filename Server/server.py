from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from Server.remember import remember

from Server.models import (
    MemoryRecord,
    ChatHistoryRecord,
    TaskRecord,
    ReminderRecord,
    UserFactRecord,
)

mcp = FastMCP("Memory MCP Server")


@mcp.tool()
def remember_memory(
    raw_content: str,
    summary: str,
    record: MemoryRecord,
) -> str:
    """
    Store a new long-term memory.

    Use this tool ONLY when the user provides information that should be
    remembered across future conversations and does not fit into the
    User Fact, Task, Reminder, or Chat History categories.

    Examples:
    - Architecture decisions
    - Project knowledge
    - Workflow documentation
    - Design decisions
    - Technical implementation details
    - Long-term preferences that require context

    Do NOT use for:
    - Stable user profile information (use remember_user_fact)
    - Tasks (use remember_task)
    - Reminders (use remember_reminder)
    - Conversation transcripts (use remember_chat_history)

    Inputs:
    - raw_content: Original information to preserve.
    - summary: Short searchable summary.
    - record: Memory metadata.

    Returns:
    Confirmation that the memory has been stored.
    """

    return remember(
        raw_content=raw_content,
        summary=summary,
        table="memories",
        record=record.model_dump(),
    )


@mcp.tool()
def remember_chat_history(
    raw_content: str,
    summary: str,
    record: ChatHistoryRecord,
) -> str:
    """
    Store an important conversation in long-term chat history.

    Use this tool ONLY when preserving conversation context that may
    be useful in future discussions.

    Examples:
    - Important design discussions
    - Long technical conversations
    - Decisions reached during a discussion
    - Previous assistant responses worth remembering

    Do NOT use for:
    - User preferences
    - Project knowledge
    - Tasks
    - Reminders

    Inputs:
    - raw_content: Original conversation.
    - summary: Short searchable summary.
    - record: Conversation metadata.

    Returns:
    Confirmation that the chat history has been stored.
    """

    return remember(
        raw_content=raw_content,
        summary=summary,
        table="chat_history",
        record=record.model_dump(),
    )


@mcp.tool()
def remember_task(
    raw_content: str,
    summary: str,
    record: TaskRecord,
) -> str:
    """
    Create a new long-term task.

    Use this tool whenever the user requests work that should be tracked
    until completed.

    Examples:
    - Finish the MCP server
    - Build a RAG pipeline
    - Refactor memory architecture
    - Complete documentation

    Do NOT use for:
    - Calendar reminders
    - User preferences
    - Long-term knowledge
    - Conversation history

    Inputs:
    - raw_content: Original task description.
    - summary: Short task summary.
    - record: Task metadata including priority and status.

    Returns:
    Confirmation that the task has been stored.
    """
    return remember(
        raw_content=raw_content,
        summary=summary,
        table="tasks",
        record=record.model_dump(),
    )


@mcp.tool()
def remember_reminder(
    raw_content: str,
    summary: str,
    record: ReminderRecord,
) -> str:
    """
    Create a reminder for a future date or time.

    Use this tool whenever the user asks to be reminded at a specific
    time or according to a schedule.

    Examples:
    - Remind me tomorrow
    - Remind me every Monday
    - Notify me next week

    Do NOT use for:
    - General tasks without a reminder time
    - User preferences
    - Long-term knowledge

    Inputs:
    - raw_content: Original reminder request.
    - summary: Short reminder summary.
    - record: Reminder metadata including reminder time.

    Returns:
    Confirmation that the reminder has been stored.
    """
    return remember(
        raw_content=raw_content,
        summary=summary,
        table="reminders",
        record=record.model_dump(),
    )


@mcp.tool()
def remember_user_fact(
    raw_content: str,
    summary: str,
    record: UserFactRecord,
) -> str:
    """
    Store stable user profile information.

    Use this tool whenever the user explicitly asks the assistant to
    remember something about themselves or states information that will
    be useful in future conversations.

    Examples:
    - My favorite language is Python
    - I use Cursor as my IDE
    - I work at Radisys
    - I live in Bangalore
    - My preferred editor is VS Code
    - My name is John

    Always use this tool when the user says:
    - Remember that...
    - Save this...
    - From now on...
    - Keep in mind...

    Do NOT use for:
    - Temporary conversation
    - Current tasks
    - Reminders
    - Project documentation

    Inputs:
    - raw_content: Original user statement.
    - summary: Concise searchable summary.
    - record: User fact metadata.

    Returns:
    Confirmation that the user fact has been stored.
    """
    print(record)
    return remember(
        raw_content=raw_content,
        summary=summary,
        table="user_facts",
        record=record.model_dump(),
    )




from Server.search import search_memory

@mcp.tool()
def search(
    query: str,
    top_k: int = 5,
):
    """
    Search long-term memory using semantic search.

    Use this tool whenever information from previous conversations,
    stored memories, user preferences, tasks, reminders, or project
    knowledge may be needed.

    Always use before:
    - Updating a memory
    - Answering questions about previous conversations
    - Continuing an existing project
    - Looking up stored user preferences

    Examples:
    - What IDE do I use?
    - Continue my AI assistant project.
    - What did we discuss yesterday?
    - Update my favorite language.

    Inputs:
    - query: Natural language search query.
    - top_k: Maximum number of results.

    Returns:
    The most relevant stored memories with PostgreSQL identifiers.
    """

    return search_memory(
        query=query,
        top_k=top_k,
    )




from Server.search import search_memory
@mcp.tool()
def change_memory(
    search_query: str,
    raw_content: str,
    summary: str,
    record: MemoryRecord,
) -> dict:
    """
    Find candidate memories that may need updating.

    Always call this tool BEFORE modifying any long-term memory.

    Use this tool when the user changes previously stored information.

    Examples:
    - I switched from VS Code to Cursor.
    - My favorite language is now Rust.
    - Change my preferred editor.

    If no suitable memory is found,
    create a new memory using the appropriate remember_* tool.

    Inputs:
    - search_query: Query used to locate existing memory.
    - raw_content: New information.
    - summary: Updated summary.
    - record: Updated metadata.

    Returns:
    Candidate memories that should be updated.
    """

    return search_memory(
        query=search_query,
        top_k=5,
    )


from Server.update import update

@mcp.tool()
def update_memory(
    postgres_id: str,
    raw_content: str,
    summary: str,
    record: MemoryRecord,
):
    """
    Update an existing long-term memory.

    Use ONLY after an existing memory has been found using
    change_memory() or search().

    Never guess the PostgreSQL identifier.

    Inputs:
    - postgres_id: Existing memory identifier.
    - raw_content: Updated content.
    - summary: Updated summary.
    - record: Updated metadata.

    Returns:
    Confirmation that the memory has been updated.
    """

    return update(
        postgres_id=postgres_id,
        table="memories",
        raw_content=raw_content,
        summary=summary,
        record=record.model_dump(),
    )

@mcp.tool()
def update_chat_history(
    postgres_id: str,
    raw_content: str,
    summary: str,
    record: ChatHistoryRecord,
):
    """
    Update an existing chat history record.

    Use ONLY after locating the existing conversation record.

    Never create new chat history with this tool.

    Returns confirmation that the conversation history has been updated.
    """

    return update(
        postgres_id=postgres_id,
        table="chat_history",
        raw_content=raw_content,
        summary=summary,
        record=record.model_dump(),
    )


@mcp.tool()
def update_task(
    postgres_id: str,
    raw_content: str,
    summary: str,
    record: TaskRecord,
):
    """
    Update an existing task.

    Use when the task already exists and its status, title,
    priority, or other details have changed.

    Examples:
    - Mark task completed
    - Change priority
    - Rename task

    Returns confirmation that the task has been updated.
    """

    return update(
        postgres_id=postgres_id,
        table="tasks",
        raw_content=raw_content,
        summary=summary,
        record=record.model_dump(),
    )

@mcp.tool()
def update_reminder(
    postgres_id: str,
    raw_content: str,
    summary: str,
    record: ReminderRecord,
):
    """
    Update an existing reminder.

    Use when the reminder already exists and its schedule,
    status, or details need to change.

    Examples:
    - Move reminder to tomorrow
    - Change reminder time
    - Cancel reminder

    Returns confirmation that the reminder has been updated.
    """

    return update(
        postgres_id=postgres_id,
        table="reminders",
        raw_content=raw_content,
        summary=summary,
        record=record.model_dump(),
    )

@mcp.tool()
def update_user_fact(
    postgres_id: str,
    raw_content: str,
    summary: str,
    record: UserFactRecord,
):
    """
    Update an existing user fact.

    Always search for the existing user fact first.

    Use when the user changes stable personal information.

    Examples:
    - I now use Cursor instead of VS Code.
    - My favorite language is now Rust.
    - I moved to Hyderabad.

    Do NOT create a new user fact if an existing one should be updated.

    Returns confirmation that the user fact has been updated.
    """

    return update(
        postgres_id=postgres_id,
        table="user_facts",
        raw_content=raw_content,
        summary=summary,
        record=record.model_dump(),
    )

if __name__ == "__main__":
    mcp.run()
