"""Tool-style wellness client for planner requests."""
from __future__ import annotations
import json
from datetime import date
from typing import Any, Iterable
from app.core.models import configured_model, create_async_responses_client
from app.features.wellness.store import add_log, get_profile, report, save_profile
from app.memory.working_context import ToolExecutionResult, build_tool_event

TOOLS=[
 {"type":"function","name":"get_wellness_profile","description":"Get wellness setup and goals","parameters":{"type":"object","properties":{}}},
 {"type":"function","name":"save_wellness_profile","description":"Create or update a wellness profile only after conversational onboarding has collected the complete baseline","parameters":{"type":"object","properties":{"data":{"type":"object"}},"required":["data"]}},
 {"type":"function","name":"log_wellness_entry","description":"Store a naturally described diet, workout, journal, or measurement update after inferring its kind","parameters":{"type":"object","properties":{"kind":{"type":"string","enum":["diet","workout","journal","measurement"]},"data":{"type":"object"},"notes":{"type":"string"},"log_date":{"type":"string"}},"required":["kind","data"]}},
 {"type":"function","name":"get_wellness_report","description":"Get complete wellness progress report and chart data","parameters":{"type":"object","properties":{"days":{"type":"integer"}}}},
]
class WellnessClient:
 def __init__(self): self.model=configured_model("gpt-4o-mini"); self.llm=create_async_responses_client()
 async def execute(self,*,user_id:str,user_input:str,system_prompt:str,messages:Iterable[Any]=())->ToolExecutionResult:
  conversation=[]
  for m in messages:
   kind=getattr(m,"type","")
   if kind in {"human","ai"}: conversation.append({"role":"user" if kind=="human" else "assistant","content":str(getattr(m,"content",""))})
  if not conversation or conversation[-1]["content"]!=user_input: conversation.append({"role":"user","content":user_input})
  response=await self.llm.responses.create(model=self.model,input=[{"role":"system","content":system_prompt},*conversation],tools=TOOLS); events=[]
  for _ in range(6):
   calls=[x for x in response.output if x.type=="function_call"]
   if not calls:return ToolExecutionResult(response.output_text or "Tell me what you would like to track.",events,artifact=report(user_id) if "report" in user_input.casefold() else None)
   outputs=[]
   for call in calls:
    args=json.loads(call.arguments or "{}"); error=False
    try:
     if call.name=="get_wellness_profile": result=get_profile(user_id)
     elif call.name=="save_wellness_profile": result=save_profile(user_id,args["data"])
     elif call.name=="log_wellness_entry": result=add_log(user_id,args["kind"],args["data"],args.get("notes", ""),date.fromisoformat(args["log_date"]) if args.get("log_date") else None)
     elif call.name=="get_wellness_report": result=report(user_id,args.get("days",30))
     else: raise ValueError("Unknown wellness tool")
     output=json.dumps(result,default=str)
    except Exception as exc: output=str(exc);error=True
    events.append(build_tool_event(integration="wellness",tool_name=call.name,arguments=args,output=output,is_error=error))
    if error:return ToolExecutionResult(f"Wellness could not complete the request: {output}",events)
    outputs.append({"type":"function_call_output","call_id":call.call_id,"output":output})
   response=await self.llm.responses.create(model=self.model,previous_response_id=response.id,input=outputs,tools=TOOLS)
  return ToolExecutionResult("I could not complete the wellness request.",events)
wellness_client=WellnessClient()
