# Terminal debug logging

Debug logging is enabled by default and written to stderr so it remains visible
without corrupting MCP servers that reserve stdout for JSON-RPC.

Log prefixes identify the boundary being traced:

- `[DEBUG][AGENT]` agent start, completion and orchestrator routing
- `[DEBUG][TOOL]` MCP tool name, integration, parameters and result status
- `[DEBUG][DB]` database engine, database path/name, SQL and bound parameters
- `[DEBUG][API]` HTTP path, query parameters, status and duration

Secrets and large message content are not printed. Passwords, OAuth tokens,
authorization values, email/message bodies, user input and system prompts are
redacted. Tool results are represented by success status and character count.

Disable all debug output when needed:

```bash
DEEP_THOUGHT_DEBUG=0 uvicorn main:app --reload
```

Enable it explicitly:

```bash
DEEP_THOUGHT_DEBUG=1 uvicorn main:app --reload
```
