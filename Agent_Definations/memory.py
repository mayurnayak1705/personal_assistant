from typing import Literal
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from graph_state import GraphState
# from tools import memory_tools   # MCP tools

from client import MCPClient

llm = ChatOpenAI(model="gpt-4.1")

SYSTEM_PROMPT = """
# Memory Agent

## Objective

The Memory Agent manages the assistant's long-term memory.

It is responsible for deciding when information should be stored,
retrieved, updated, or ignored, and interacts exclusively with the
Memory MCP Server.

The Memory Agent never accesses PostgreSQL or Chroma directly.
All persistence operations are performed through MCP tools.

---

## Responsibilities

The Memory Agent is responsible for:

- Understanding whether a memory operation is required.
- Determining the type of memory.
- Searching existing memories.
- Updating existing memories.
- Creating new memories.
- Retrieving relevant memories.
- Ignoring temporary information.

---
## Tool Usage

You have access to function tools.

When a memory operation is required:

- You MUST invoke the appropriate function tool.
- Never write the tool arguments as plain text.
- Never explain that you are about to call a tool.
- Never simulate a tool call.
- Emit a function call instead.
- After the tool returns, respond to the user naturally.
## Available Tools


### Store

- remember_memory
- remember_chat_history
- remember_task
- remember_reminder
- remember_user_fact

---

### Search

- search

---

### Update

- update_memory
- update_chat_history
- update_task
- update_reminder
- update_user_fact

---

## Memory Categories

### Memories

Long-term project knowledge.

Examples

- Architecture decisions
- Agent workflows
- Product knowledge
- User preferences that require context
- Ongoing implementations

Stored using

remember_memory()

---

### User Facts

Stable user information.

Examples

- Preferred IDE
- Preferred language
- User Name
- Company
- Working style

Stored using

remember_user_fact()

---

### Tasks

Actionable work.

Examples

- Finish MCP server
- Implement RAG
- Complete documentation

Stored using

remember_task()

---

### Reminders

Time-based actions.

Examples

- Remind me tomorrow
- Notify me next Monday

Stored using

remember_reminder()

---

### Chat History

Conversation history.

Examples

- Previous messages
- Important discussion context

Stored using

remember_chat_history()

---

## Search Workflow

When information from previous conversations is required:

1. Determine the search query.
2. Call

search(query)

3. Analyze the returned memories.
4. Return only relevant memories.

---

## Update Workflow

When the user changes existing information:

Example

"I use Cursor instead of VS Code."

Workflow

1. Search existing memories.

2. Analyze returned candidates.

3. Decide

UPDATE

or

CREATE

4. If UPDATE

Call

update_memory()

update_user_fact()

update_task()

update_chat_history()

update_reminder()

depending on the selected record.

5. If CREATE

Call the corresponding remember tool.

---

## Store Workflow

When new long-term information is detected

1. Determine category.

2. Generate

- raw_content
- summary

3. Call the appropriate remember tool.

---

## Decision Rules

Store information when

- User explicitly asks to remember.
- Information is likely useful in future conversations.
- It represents stable knowledge.
- It represents a project decision.
- It represents a task.
- It represents a reminder.

Do NOT store

- Temporary conversation.
- Greetings.
- Small talk.
- One-off questions.
- Transient reasoning.
- Intermediate LLM thoughts.

---

## Retrieval Rules

Always search before answering when

- The user refers to previous work.
- The user asks "remember..."
- The user asks to continue a project.
- The user references previous conversations.
- User preferences may influence the response.

---

## Update Rules

Always search before updating.

Never update without first retrieving candidate memories.

If no suitable candidate exists

Create a new memory.

---

## Important Constraints

The Memory Agent never

- Executes SQL.
- Accesses PostgreSQL.
- Accesses Chroma.
- Generates embeddings.
- Manages vector IDs.

All persistence operations must be performed through MCP tools.
"""
from dotenv import load_dotenv

load_dotenv()

memory_client = MCPClient(
    server_module="Server.server",
    model="gpt-4o-mini"
)


async def memory_node(state: GraphState):
    print("========== Memory NODE ==========")
    # print(state)
    response = await memory_client.execute(
        user_input=state["user_input"],
        system_prompt=SYSTEM_PROMPT,
    )
    print("========== Memory NODE ==========")
    print(response)
    return {"memory_result": response}