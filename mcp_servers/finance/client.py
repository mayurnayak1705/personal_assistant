"""LLM tool client for natural-language-only finance configuration."""
from __future__ import annotations

import json
from typing import Any, Iterable

from app.features.finance.store import add_stock, list_stocks, remove_stock, set_alert, watchlist_report
from app.core.models import configured_model, create_async_responses_client
from app.memory.working_context import ToolExecutionResult, build_tool_event


TOOLS = [
    {"type":"function","name":"add_stock","description":"Resolve and add a company or ticker to the user's stock watchlist, optionally with an alert","parameters":{"type":"object","properties":{"query":{"type":"string"},"alert_kind":{"type":"string","enum":["percent_up","percent_down","percent_deviation","price_above","price_below"]},"alert_value":{"type":"number"}},"required":["query"]}},
    {"type":"function","name":"list_stocks","description":"List the configured stock watchlist","parameters":{"type":"object","properties":{}}},
    {"type":"function","name":"remove_stock","description":"Remove one stock from the watchlist","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"type":"function","name":"set_stock_alert","description":"Set, change, or clear an alert on a watchlist stock; omit alert_kind and alert_value to clear it","parameters":{"type":"object","properties":{"query":{"type":"string"},"alert_kind":{"type":"string","enum":["percent_up","percent_down","percent_deviation","price_above","price_below"]},"alert_value":{"type":"number"}},"required":["query"]}},
    {"type":"function","name":"get_watchlist_report","description":"Fetch current prices and daily movement for all watchlist stocks","parameters":{"type":"object","properties":{}}},
]


class FinanceClient:
    def __init__(self):
        self.model = configured_model("gpt-4o-mini")
        self.llm = create_async_responses_client()

    async def execute(self, *, user_id: str, user_input: str, system_prompt: str,
                      messages: Iterable[Any] = ()) -> ToolExecutionResult:
        conversation = []
        for message in messages:
            kind = getattr(message, "type", "")
            if kind in {"human", "ai"}:
                conversation.append({"role":"user" if kind == "human" else "assistant", "content":str(getattr(message, "content", ""))})
        if not conversation or conversation[-1]["content"] != user_input:
            conversation.append({"role":"user", "content":user_input})
        response = await self.llm.responses.create(model=self.model, input=[{"role":"system","content":system_prompt}, *conversation], tools=TOOLS)
        events = []
        for _ in range(6):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return ToolExecutionResult(response.output_text or "Tell me which stock you want to track.", events)
            outputs = []
            for call in calls:
                args = json.loads(call.arguments or "{}")
                try:
                    if call.name == "add_stock": result = add_stock(user_id, args["query"], args.get("alert_kind"), args.get("alert_value"))
                    elif call.name == "list_stocks": result = list_stocks(user_id)
                    elif call.name == "remove_stock": result = remove_stock(user_id, args["query"])
                    elif call.name == "set_stock_alert": result = set_alert(user_id, args["query"], args.get("alert_kind"), args.get("alert_value"))
                    elif call.name == "get_watchlist_report": result = watchlist_report(user_id)
                    else: raise ValueError("Unknown finance tool")
                    output, is_error = json.dumps(result, default=str), False
                except Exception as exc:
                    output, is_error = str(exc), True
                events.append(build_tool_event(integration="finance", tool_name=call.name, arguments=args, output=output, is_error=is_error))
                if is_error:
                    return ToolExecutionResult(f"Finance could not complete the request: {output}", events)
                outputs.append({"type":"function_call_output", "call_id":call.call_id, "output":output})
            response = await self.llm.responses.create(model=self.model, previous_response_id=response.id, input=outputs, tools=TOOLS)
        return ToolExecutionResult("I could not complete the finance request.", events)


finance_client = FinanceClient()
