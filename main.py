import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes import router
from mcp_servers.whatsappmeow.client import whatsapp_client
from mcp_servers.reminder.client import reminder_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep WhatsApp connected for the whole web-app lifetime so incoming
    # events continue to reach the MCP message log even between chat requests.
    services = {
        "WhatsApp": whatsapp_client.start(),
        "Reminder": reminder_client.start(),
    }
    results = await asyncio.gather(*services.values(), return_exceptions=True)
    for service_name, result in zip(services, results):
        if isinstance(result, Exception):
            logger.warning("%s MCP did not start: %s", service_name, result)
    yield
    await asyncio.gather(
        whatsapp_client.stop(),
        reminder_client.stop(),
        return_exceptions=True,
    )

app = FastAPI(
    title="Personal Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

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
