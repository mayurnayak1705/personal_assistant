# Working-context integration contract

Working context is a short-lived record of successful tool activity. It is
separate from durable user facts and conversation history.

Any MCP client can participate without adding tool-specific database columns.
For each MCP call made on behalf of the user:

```python
from app.memory.working_context import ToolExecutionResult, build_tool_event

events.append(
    build_tool_event(
        integration="calendar",
        tool_name=tool_call.name,
        arguments=arguments,
        output=tool_output,
        is_error=is_error,
    )
)

return ToolExecutionResult(text=response_text, events=events)
```

The planner or memory node places `execution.events` in
`state["tool_results"]["events"]`. The API boundary persists successful events
after the graph finishes. On the next turn, recent unexpired events are loaded
into `state["working_context"]` before orchestration.

The same successful event is also stored permanently in
`assistant_action_history`. Its durable record contains the action type,
entity type and ID, readable summary, timestamp, and an optional follow-up
suggestion. Tool integrations do not need separate history persistence code.

Entity extraction is schema-independent. Nested objects containing `id`,
`phone_number`, or `email`, and arguments named `*_id`, automatically become
references. Tools should therefore return stable IDs and useful labels such as
`title`, `name`, `status`, `due_date`, or `category` in their normal result.

Working-context failures must not fail the underlying user action. Context is
bounded to 30 events per conversation and expires according to
`WORKING_CONTEXT_TTL_MINUTES` (six hours by default).

Use conventional tool verb names (`create_`, `update_`, `complete_`, `delete_`,
`send_`, `list_`, and so on) so action history can classify future tools
automatically. Register integration-specific suggestions in
`app/memory/follow_up_suggestions.py`; the API will choose at most one for each turn.
