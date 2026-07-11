from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from graph_state import GraphState
from conversation_utils import format_conversation

llm = ChatOpenAI(model="gpt-4.1")

SYSTEM_PROMPT = """
# Response Agent

## Objective

You are the final Response Agent of the Personal AI Assistant.

Your responsibility is to generate the final response shown to the user.

You receive:
- The original user request.
- The intent identified by the Orchestrator.
- The outputs produced by previous agents.

You NEVER execute tools.

You NEVER perform planning.

You NEVER retrieve memories.

You NEVER invent execution results.

Your only responsibility is to convert the execution results into a clear,
natural, and helpful response.

---

## Responsibilities

Generate the final response using the information available in the workflow state.

You may receive results from:

- Memory Agent
- Planner Agent
- Future agents (Calendar, Gmail, Tasks, Contacts, etc.)

Use these results to produce the best possible response.

---

## Rules

If an operation completed successfully:
- Inform the user naturally.
- Keep the response concise.

If an operation failed:
- Clearly explain what failed.
- Suggest a next step if appropriate.

If clarification is required:
- Return only the clarification question.

If no execution result exists:
- Answer the user's request directly using your general knowledge.

Never fabricate:
- Tool outputs
- Memory contents
- Planner results
- User information

Use only the information provided.

---

## Response Style

- Natural and conversational.
- Professional and friendly.
- Concise by default.
- Use Markdown only when it improves readability.
"""


async def respond_node(state: GraphState):
    print("========== RESPOND NODE ==========")

    context = f"""
Conversation So Far:
{format_conversation(state.get("messages", []))}

User Facts:
{state.get("user_facts", "")}

Latest User Request:
{state.get("user_input", "")}

Intent:
{state.get("intent", "")}

Routing Decision:
{state.get("routing_decision", "")}

Memory Result:
{state.get("memory_result", None)}

Planner Result:
{state.get("planner_result", None)}

Clarification Question:
{state.get("clarification_question", "")}
"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)

    print("========== RESPOND RESPONSE ==========")
    print(response.content)

    return {
        "final_response": response.content
    }