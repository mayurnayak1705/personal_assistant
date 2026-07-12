# Personal AI Assistant

> A modular, agentic AI assistant built using **LangGraph**, **FastAPI**, **OpenAI**, and **MCP (Model Context Protocol)**.

The goal of this project is to build a **truly personal AI assistant** that can reason, remember, plan, and execute tasks using external tools while maintaining long-term memory.

Unlike traditional chatbots, this assistant separates **reasoning**, **memory**, and **execution** into independent agents, making the system highly extensible and easy to maintain.

---

# Features

- 🧠 Multi-Agent Architecture
- 💾 Persistent Memory
- 📋 Intelligent Task Planning
- 🔧 MCP Tool Integration
- 💰 Expense Tracking
- 🌐 FastAPI Web Interface
- 🔍 Long-Term User Memory
- 🗂 Conversation History
- ⚡ Extensible Tool Ecosystem

---

# Architecture


# Architecture

The assistant follows a **modular multi-agent architecture** where reasoning, planning, memory, and tool execution are cleanly separated. Each agent has a single responsibility, making the system easier to extend, maintain, and scale.

<p align="center">
  <img src="docs/images/architecture.png" alt="Personal AI Assistant Architecture" width="1000"/>
</p>

The architecture is built around three core principles:

- **Reasoning is performed by agents.**
- **Execution is performed by MCP tools.**
- **Workflow orchestration is managed by LangGraph.**

This separation allows new capabilities—such as Gmail, WhatsApp, Calendar, GitHub, or other integrations—to be added as independent MCP servers without modifying the core reasoning logic.



# Why MCP?

Every external capability is implemented as an independent MCP server.

This allows the assistant to remain modular and easily extensible.

Benefits include:

- Independent development of tools
- Language-agnostic servers
- Easy testing
- Plug-and-play integrations
- Clear separation between reasoning and execution

The Planner decides **what** to do, while MCP servers decide **how** to do it.

---

# Project Structure

```
## Project Structure

```text
personal_assistant/
│
├── Agent_Definations/
│   ├── orchestrator.py        # Intent detection & routing
│   ├── memory.py              # Memory retrieval agent
│   └── respond.py             # Direct response agent
│
├── api/
│   └── routes.py              # FastAPI API endpoints
│
├── Databases/
│   └── Chroma/                # Persistent vector database
│
├── Server/                    # Memory MCP Server
│   ├── server.py
│   ├── remember.py
│   ├── search.py
│   ├── update.py
│   ├── models.py
│   ├── postgre_insert.py
│   ├── postgre_search.py
│   ├── postgre_update.py
│   ├── vector_db_insert.py
│   ├── vector_db_search.py
│   └── vector_db_update.py
│
├── mcp_servers/
│   └── expense/               # Expense MCP Server
│
├── static/
│   ├── css/
│   └── js/
│
├── templates/
│   └── index.html
│
├── graph.py
├── graph_state.py
├── main.py
├── client.py
├── chroma_client.py
├── session_store.py
├── conversation_utils.py
├── token_utils.py
└── requirements.txt
```


---

# Agent Responsibilities

## 1. Orchestrator Agent

The Orchestrator is the entry point of the system.

Responsibilities

- Understand user intent
- Estimate confidence
- Decide routing
- Ask clarification when required

Possible routing decisions

- Planner
- Memory
- Planner + Memory
- Response
- Clarification

The Orchestrator never executes tools.

---

## 2. Planner Agent

The Planner converts natural language into executable actions.

Responsibilities

- Create execution plans
- Execute MCP tools
- Retry failures
- Handle tool responses
- Generate final outputs

Example

```
User:
Add ₹100 shopping expense today

↓

Planner

↓

Expense MCP Tool

↓

Database Updated

↓

Response Returned
```

---

## 3. Memory Agent

The Memory Agent manages long-term knowledge.

It is the only component allowed to communicate with storage.

Responsibilities

- Store memories
- Retrieve memories
- Search conversations
- Search documents
- Store user preferences
- Update memories
- Delete memories

---

## 4. Response Agent

Handles questions that require no planning or tool execution.

Example

```
Where is Japan?

↓

Response Agent

↓

Answer
```

---

# Memory Architecture

One of the core components of this assistant is its long-term memory system.

The memory layer is completely isolated from the Planner and Orchestrator.


---
                User Message
                      │
                      ▼
               Memory Agent
                      │
      ┌───────────────┴──────────────┐
      ▼                              ▼
Generate Summary              Generate Embedding
      │                              │
      ▼                              ▼
 Store in PostgreSQL          Store in ChromaDB
      │                              │
      └───────────────┬──────────────┘
                      ▼
                Memory Stored


## Why Two Databases?

The assistant separates **structured storage** from **semantic retrieval**.

### PostgreSQL

PostgreSQL acts as the source of truth.

It stores complete records including:

- User profile
- Conversations
- Notes
- Tasks
- Expenses
- Metadata

Every memory has a unique ID.

---

### ChromaDB

ChromaDB stores only the vector embeddings and lightweight metadata.

Instead of searching every conversation, semantic search first finds the most relevant memory IDs.

These IDs are then used to fetch the complete records from PostgreSQL.

This architecture combines:

- fast semantic search
- reliable relational storage
- efficient updates
- scalable retrieval

## Memory Flow

Saving memory

```
User says

↓

Memory Agent

↓

Generate Summary

↓

Store Complete Record

↓

Generate Embedding

↓

Store Vector Metadata

↓

Done
```

---

Searching memory

```
User Query

↓

Embedding Generated

↓

Semantic Search

↓

Relevant IDs

↓

Fetch Full Records

↓

Planner
```

---

## Retrieved Memory

The Planner never queries databases directly.

Instead it receives

```python
class RetrievedMemory(TypedDict):

    profile: dict

    relevant_conversations: list

    relevant_documents: list

    notes: list

    preferences: dict
```

This keeps the Planner completely storage independent.

---

# Expense Tool

The first MCP tool integrated into the assistant is the Expense Tracker.

Example

```
Add ₹100 shopping expense on 12 July 2026
```

Flow

```
User

↓

Planner

↓

Expense MCP Tool

↓

Expense Server

↓

Database

↓

Response
```

Supported examples

```
Add ₹250 dinner expense

Spent ₹80 on coffee

Add ₹1000 shopping yesterday

Show expenses this month

How much did I spend on food?
```

The Planner only decides **what** should happen.

The Expense MCP Server decides **how** to execute it.

---

# MCP Integration

Every capability is exposed as an MCP server.

```
Planner

↓

MCP Client

↓

Expense Server

↓

Response
```

Adding new capabilities only requires adding another MCP server.

No planner logic needs to change.

---

# Current Features

- Expense Tracking
- Long-term Memory
- User Facts
- Conversation Memory
- Planner
- FastAPI Backend
- Modern Web UI

---

# Running Locally

## Clone

```bash
git clone https://github.com/<username>/personal-ai-assistant.git

cd personal-ai-assistant
```

---

## Create Virtual Environment

Mac/Linux

```bash
python3 -m venv .venv
```

Windows

```bash
python -m venv .venv
```

Activate

Mac/Linux

```bash
source .venv/bin/activate
```

Windows

```bash
.venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment

Create

```
.env
```

Example

```text
OPENAI_API_KEY=your_openai_api_key

DATABASE_URL=postgresql://...

CHROMA_PATH=./chroma_db
```

---

## Start MCP Servers

Example

```
python -m mcp.memory.server

python -m mcp.expense.server
```

---

## Run FastAPI

```
uvicorn main:app --reload
```

Visit

```
http://127.0.0.1:8000
```

---

# Example Queries

```
Remember that I like Python.

What is my favorite language?

Add ₹200 shopping expense.

How much did I spend this week?

Summarize my uploaded documents.

Continue working on my AI Assistant project.
```

---

# Future Roadmap

The assistant is designed around MCP, making it easy to integrate new capabilities without modifying the Planner.

## Productivity

- Gmail
- Google Calendar
- Google Drive
- Google Docs
- Google Sheets
- Notion
- Slack
- Discord

---

## Communication

- WhatsApp
- Telegram
- Signal
- SMS
- Phone Calls
- Microsoft Teams

---

## Development

- GitHub
- GitLab
- Docker
- Kubernetes
- Jira
- Linear
- VS Code

---

## Finance

- Bank Statements
- UPI Transactions
- Investments
- Budget Planning
- Monthly Reports
- Auto Expense Categorization

---

## Personal Assistant

- Daily Briefing
- Morning Routine
- Smart Notifications
- Shopping Lists
- Medicine Reminders
- Habit Tracking
- Goal Tracking

---

## AI Capabilities

- Autonomous Research
- Document Understanding
- Code Generation
- Report Generation
- Meeting Summaries
- Voice Conversations
- Multi-modal Understanding

---

# Towards a Truly Hands-Free AI Assistant

The long-term goal is to transform this project from a conversational assistant into a fully autonomous personal operating system.

Instead of waiting for instructions, the assistant should proactively understand context, monitor connected services, remember long-term information, and take actions on behalf of the user.

Imagine interactions such as:

- "Read my unread Gmail messages and summarize only the important ones."
- "Reply politely to emails requesting project updates."
- "If my manager messages me on WhatsApp during office hours, notify me immediately."
- "Schedule meetings automatically by checking everyone's availability."
- "Track my spending from UPI notifications without manual entry."
- "Generate a daily briefing every morning with weather, calendar, unread emails, pending GitHub PRs, and high-priority tasks."
- "Monitor my repositories and notify me if CI/CD pipelines fail."
- "Listen for voice commands and execute actions hands-free."
- "Maintain context across conversations, remembering preferences, ongoing projects, and past decisions."

By combining **long-term memory**, **reasoning agents**, **MCP-based tool execution**, and **voice interaction**, the assistant evolves into a proactive digital companion that can reason, act, and continuously assist with minimal user intervention.

---

# Contributing

Contributions are welcome.

Ideas include

- New MCP Servers
- Memory Improvements
- Planner Enhancements
- UI Improvements
- Voice Integration
- New Connectors
- Testing
- Documentation

---

# License

MIT License