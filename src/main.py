import asyncio
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load .env BEFORE anything tries to read API keys
load_dotenv()
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from structlog import get_logger

from src.core.config import config_manager
from src.core.router import router
from src.core.orchestrator import DialogOrchestrator
from src.transport.zmq_layer import ZMQTransport
from src.transport.ws_layer import WebSocketTransport
from src.core.telemetry import telemetry

# Using OpenAI as the default fully functional provider for the MVP
from src.providers.openai_provider import OpenAISTTProvider, OpenAILLMProvider, OpenAITTSProvider
from src.providers.gemini_provider import GeminiLLMProvider
from pydantic import BaseModel

logger = get_logger()

# 1. Initialize Configuration
config_manager.load_config()

# 2. Setup Transports
zmq_transport = ZMQTransport(pub_port=5555, sub_port=5556)
ws_transport = WebSocketTransport()

# Bind both to the router so messages flow bidirectionally everywhere
router.add_transport(zmq_transport)
router.add_transport(ws_transport)

# 3. Setup AI Orchestrator
# (Requires API Keys in .env to function fully)
stt_provider = OpenAISTTProvider()
llm_providers = {
    "openai": OpenAILLMProvider(),
    "gemini": GeminiLLMProvider()
}
tts_provider = OpenAITTSProvider()

orchestrator = DialogOrchestrator(
    stt_provider=stt_provider,
    llm_providers=llm_providers,
    tts_provider=tts_provider,
    default_llm="openai"
)

# Pipe the Router to the Orchestrator so audio commands trigger AI responses
router.set_orchestrator(orchestrator)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI to start and stop background resources."""
    logger.info("Starting OpenVirtualAgentFramework Server...", experiment=config_manager.config.experiment.name)
    
    # Start all registered transports
    await zmq_transport.start()
    await ws_transport.start()
    
    yield
    
    # Shutdown gracefully
    await zmq_transport.stop()
    await ws_transport.stop()
    logger.info("OAF Server fully stopped.")

# 3. Initialize FastAPI App
app = FastAPI(
    title="OAF Server (Wizard of Oz & Gateway)",
    description="OpenVirtualAgentFramework Routing Server",
    version=config_manager.config.experiment.version,
    lifespan=lifespan
)

# 4. HTTP and WebSocket Mounts
@app.get("/api/config")
async def get_config():
    """Returns the current loaded topology directly from config.yaml"""
    return config_manager.config.model_dump()

class LLMConfigUpdate(BaseModel):
    provider_id: str | None = None
    system_prompt: str | None = None

@app.get("/api/llm/config")
async def get_llm_config():
    """Returns the current active LLM state"""
    return {
        "active_provider": orchestrator.active_llm_id,
        "available_providers": list(orchestrator.llm_providers.keys()),
        "system_prompt": orchestrator.system_prompt
    }

@app.post("/api/llm/config")
async def set_llm_config(update: LLMConfigUpdate):
    """Dynamically updates the Orchestrator without restarting"""
    if update.provider_id:
        orchestrator.set_active_llm(update.provider_id)
    if update.system_prompt:
        orchestrator.set_system_prompt(update.system_prompt)
        
    return {
        "active_provider": orchestrator.active_llm_id,
        "system_prompt": orchestrator.system_prompt,
        "tts_enabled": orchestrator.tts_enabled
    }

@app.post("/api/llm/tts")
async def toggle_tts():
    """Toggles TTS audio generation on/off"""
    orchestrator.tts_enabled = not orchestrator.tts_enabled
    return {"tts_enabled": orchestrator.tts_enabled}

@app.post("/api/llm/history/clear")
async def clear_history():
    """Clears the conversation memory"""
    orchestrator.clear_history()
    return {"status": "ok", "message": "Conversation history cleared"}

@app.get("/api/export")
async def export_telemetry():
    """Exports the current session JSONL into a structured CSV file for analysis"""
    csv_path = telemetry.export_to_csv()
    if csv_path and csv_path.exists():
        return FileResponse(path=csv_path, filename=csv_path.name, media_type='text/csv')
    return {"error": "Failed to generate CSV export."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Client entrypoint for the Wizard of Oz panel or Web Agents.
    Hands the connection over to the WS Transport Layer.
    """
    await ws_transport.connect(websocket)
    # Block and listen to this specific socket
    await ws_transport.handle_incoming(websocket)

# --- System Logs Streamer ---

log_subscribers = []

@app.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    """
    Dedicated endpoint for streaming server logs to the WoZ console UI.
    """
    await websocket.accept()
    log_subscribers.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        log_subscribers.remove(websocket)

class WebsocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            if not log_subscribers:
                return
            log_entry = self.format(record)
            payload = json.dumps({"level": record.levelname, "name": record.name, "message": log_entry})
            loop = asyncio.get_running_loop()
            for conn in list(log_subscribers):
                try:
                    loop.create_task(conn.send_text(payload))
                except Exception:
                    pass
        except Exception:
            pass

ws_logger = WebsocketLogHandler()
ws_logger.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))

# --- File Logging ---
# Write all logs to a rotating log file for future review
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "oaf_server.log")

file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))
file_handler.setLevel(logging.DEBUG)

# Register with root and all relevant loggers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(ws_logger)
root_logger.addHandler(file_handler)

# Register our custom OAF loggers (oaf.router, oaf.orchestrator, oaf.gemini)
oaf_logger = logging.getLogger("oaf")
oaf_logger.setLevel(logging.DEBUG)
oaf_logger.addHandler(ws_logger)
oaf_logger.addHandler(file_handler)
oaf_logger.propagate = False  # Prevent duplicate messages from root logger

logging.getLogger("uvicorn.access").addHandler(ws_logger)
logging.getLogger("uvicorn.access").addHandler(file_handler)
logging.getLogger("uvicorn.error").addHandler(ws_logger)
logging.getLogger("uvicorn.error").addHandler(file_handler)
logging.getLogger("fastapi").addHandler(ws_logger)
logging.getLogger("fastapi").addHandler(file_handler)

# --------------------------

# Mount the static WoZ panel to the root URL
# This allows researchers to visit http://localhost:8000 and immediately see the control panel
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:
    logger.warning("Static directory not found. WoZ Panel will not be available.", path=static_path)
