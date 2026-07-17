import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes import router
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client
from mcp_servers.tasks.client import tasks_client
from mcp_servers.gmail.client import gmail_client
from mcp_servers.calendar.client import calendar_client
from action_history_store import init_action_history_schema
from daily_briefing_store import init_daily_briefing_schema
from working_context_store import init_working_context_schema
from debug_log import debug, install_sqlite_tracing

install_sqlite_tracing()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep WhatsApp connected for the whole web-app lifetime so incoming
    # events continue to reach the MCP message log even between chat requests.
    services = {
        "WhatsApp": whatsapp_client.start_if_enabled(),
        "Reminder": reminder_client.start(),
        "Tasks": tasks_client.start(),
        "Gmail": gmail_client.start(),
        "Calendar": calendar_client.start(),
        "Working context": asyncio.to_thread(init_working_context_schema),
        "Action history": asyncio.to_thread(init_action_history_schema),
        "Daily briefing": asyncio.to_thread(init_daily_briefing_schema),
    }
    results = await asyncio.gather(*services.values(), return_exceptions=True)
    for service_name, result in zip(services, results):
        if isinstance(result, Exception):
            logger.warning("%s MCP did not start: %s", service_name, result)
            debug("TOOL", "service_start", service=service_name, success=False, error=str(result))
        else:
            debug("TOOL", "service_start", service=service_name, success=True)
    yield
    await asyncio.gather(
        whatsapp_client.stop(),
        reminder_client.stop(),
        tasks_client.stop(),
        gmail_client.stop(),
        calendar_client.stop(),
        return_exceptions=True,
    )

app = FastAPI(
    title="Personal Assistant",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def debug_requests(request: Request, call_next):
    started = time.perf_counter()
    debug("API", "request", method=request.method, path=request.url.path,
          query=dict(request.query_params))
    try:
        response = await call_next(request)
    except Exception as exc:
        debug("API", "response", method=request.method, path=request.url.path,
              success=False, error=type(exc).__name__, duration_ms=round((time.perf_counter() - started) * 1000, 1))
        raise
    debug("API", "response", method=request.method, path=request.url.path,
          status=response.status_code, duration_ms=round((time.perf_counter() - started) * 1000, 1))
    return response

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# HTML Templates
templates = Jinja2Templates(directory="templates")

# API
app.include_router(router, prefix="/api")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )
