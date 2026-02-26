<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
  <img src="https://img.shields.io/badge/ZeroMQ-26.0-DF0000?logo=zeromq&logoColor=white" alt="ZMQ" />
  <img src="https://img.shields.io/badge/Three.js-r170-black?logo=three.js" alt="Three.js" />
</p>

<h1 align="center">🧬 Open Virtual Agent Framework — Server</h1>

<p align="center">
  <strong>A modular, research-oriented server for driving embodied virtual agents in XR environments, with real-time AI orchestration, multi-provider LLM/TTS support, and a built-in Wizard-of-Oz console.</strong>
</p>

<p align="center">
  <em>Part of the <a href="https://github.com/AURAxLab">AURAxLab</a> research initiative</em>
</p>

---

## ✨ What is OAF?

The **Open Virtual Agent Framework (OAF)** is a server that sits between AI providers (OpenAI, Google Gemini) and XR client applications (Unity, Unreal, Web) to orchestrate the behavior of embodied virtual agents. It provides:

- 🧠 **Multi-provider LLM** — Hot-swap between OpenAI and Gemini mid-conversation
- 🔊 **Multi-provider TTS** — Auto-matched to active LLM (OpenAI voices + Gemini voices)
- 🎙️ **STT** — Speech-to-text transcription from XR client audio
- 🧑 **3D Avatar** — Lip-synced, emotion-reactive embodied agent rendered in-browser
- 🎮 **Wizard-of-Oz Console** — Full web dashboard for researchers to monitor and control experiments
- 📡 **Dual Transport** — ZeroMQ (low-latency XR) + WebSocket (web clients)
- 📊 **Telemetry & Logging** — Structured event capture with CSV export

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  XR Client (Unity / Unreal)                                     │
│  ───────────────────────                                        │
│  • Sends audio/text via ZMQ                                     │
│  • Receives TTS audio + action commands                         │
└────────────────────┬────────────────────────────────────────────┘
                     │ ZeroMQ (TCP 5555/5556)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  OAF Server (FastAPI + Uvicorn)                                 │
│  ───────────────────────────────                                │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Router   │──│ Orchestrator │──│  Providers   │             │
│  │           │  │              │  │              │             │
│  │ • Validate│  │ • STT → LLM │  │ • OpenAI LLM │             │
│  │ • Route   │  │ • LLM → TTS │  │ • Gemini LLM │             │
│  │ • Broadcast│ │ • History    │  │ • OpenAI TTS │             │
│  │           │  │ • Actions    │  │ • Gemini TTS │             │
│  └───────────┘  └──────────────┘  │ • OpenAI STT │             │
│                                    └──────────────┘             │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ ZMQ Layer │  │  WS Layer    │  │  Telemetry   │             │
│  │ (XR apps) │  │  (Web/WoZ)   │  │  (CSV/JSON)  │             │
│  └───────────┘  └──────────────┘  └──────────────┘             │
└────────────────────┬────────────────────────────────────────────┘
                     │ WebSocket (HTTP :8000)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  WoZ Console (Browser)                                          │
│  ─────────────────────                                          │
│  • LLM Playground with chat                                     │
│  • 3D Avatar with lip sync + emotions (Three.js + VRM)          │
│  • Real-time system logs                                        │
│  • Remote XR control panel                                      │
│  • Telemetry export                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- An API key for at least one provider:
  - [OpenAI API Key](https://platform.openai.com/api-keys) — for LLM + TTS + STT
  - [Google Gemini API Key](https://aistudio.google.com/apikey) — for LLM + TTS

### Installation

```bash
# Clone the repository
git clone https://github.com/AURAxLab/OpenVirtualAgentFramework-Server.git
cd OpenVirtualAgentFramework-Server

# Create and activate virtual environment
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install google-genai   # For Gemini provider

# Configure API keys
cp .env.example .env
# Edit .env and fill in your API keys
```

### Run the Server

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the **Wizard-of-Oz Console** at: [http://localhost:8000](http://localhost:8000)

---

## 🎮 WoZ Console Features

The built-in web console provides a full research interface with three tabs:

### 🕹️ Remote XR Control
Send commands directly to connected XR devices — trigger emotions, actions, gaze targets, and direct TTS messages in real time.

### 💬 LLM Playground
Interactive chat interface for testing the AI pipeline:
- **Hot-swap LLM providers** — Switch between OpenAI and Gemini mid-conversation
- **System prompt editor** — Customize the agent's personality in real time
- **TTS toggle** — Enable/disable voice synthesis
- **Auto-matched TTS** — When using Gemini LLM → Gemini TTS voice; when using OpenAI → OpenAI voice
- **Persistent state** — Chat history, config, and avatar selection survive page reloads

### 🧑 Embodied Agent
A 3D avatar rendered with **Three.js + three-vrm** that:
- 👄 **Lip-syncs** with TTS audio via Web Audio API `AnalyserNode`
- 😊 **Displays emotions** from LLM action calls (happy, sad, angry, surprised)
- 👀 **Blinks** naturally at random intervals
- 🫁 **Breathes** with subtle spine movement
- 🔄 **Sways** gently for lifelike idle behavior
- 📂 **Upload custom VRM models** — Drag-and-drop avatar replacement

### 📋 System Logs & Errors
Real-time streaming logs from all server components with color-coded severity.

---

## ⚙️ Configuration

### `config.yaml` — Experiment Setup

The config file defines your experiment's structure. The LLM uses these as tool schemas, so it can trigger actions, emotions, and gaze targets autonomously.

```yaml
experiment:
  name: "My Study"

agents:
  - id: "agent_alpha"
    name: "Alpha"

custom_commands:
  emotions:
    description: "Agent emotional states"
    values: ["neutral", "happy", "sad", "angry", "surprised"]

  actions:
    description: "Physical actions the agent can perform"
    values: ["wave", "nod", "shake_head", "point_left"]

  looks:
    description: "Gaze targets"
    values: ["user", "away", "agent_beta"]
```

> **💡 Tip:** Adding a new value to `custom_commands` automatically makes it available to the LLM as a tool call option — no code changes needed.

### `.env` — API Keys

```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
```

---

## 📡 Transport Protocols

### ZeroMQ (XR Clients)

Low-latency bidirectional communication for Unity/Unreal clients.

| Socket | Port | Direction | Purpose |
|--------|------|-----------|---------|
| PUB    | 5555 | Server → Client | Commands, TTS audio |
| SUB    | 5556 | Client → Server | Audio, text messages |

### WebSocket (Web Clients)

Full-duplex communication on `/ws` endpoint.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.type: "message" | "action" | "audio"
    // data.command: "llm_reply" | "execute_state" | "tts_chunk" | "tts_complete"
};
```

---

## 📁 Project Structure

```
OpenVirtualAgentFramework-Server/
├── config.yaml                  # Experiment configuration
├── requirements.txt             # Python dependencies
├── .env.example                 # API key template
│
├── src/
│   ├── main.py                  # FastAPI app, routes, startup
│   │
│   ├── core/
│   │   ├── orchestrator.py      # AI pipeline: STT → LLM → TTS → Router
│   │   ├── router.py            # Command validation & transport routing
│   │   ├── config.py            # YAML config loader
│   │   ├── schemas.py           # Pydantic models for commands
│   │   └── telemetry.py         # Event capture & CSV export
│   │
│   ├── providers/
│   │   ├── base.py              # Abstract base classes (STT, LLM, TTS)
│   │   ├── openai_provider.py   # OpenAI STT + LLM + TTS
│   │   └── gemini_provider.py   # Gemini LLM + TTS
│   │
│   ├── transport/
│   │   ├── base.py              # Transport base class
│   │   ├── zmq_layer.py         # ZeroMQ PUB/SUB transport
│   │   └── ws_layer.py          # WebSocket transport
│   │
│   └── static/
│       ├── index.html           # WoZ Console (single-page app)
│       ├── avatar.js            # 3D avatar engine (Three.js + VRM)
│       └── models/              # VRM avatar models
│           └── default_avatar.vrm
│
├── scripts/
│   └── mock_xr_client.py       # ZMQ test client for development
│
├── tests/
│   └── test_schemas.py         # Pydantic schema tests
│
└── data/                       # Experiment data storage
```

---

## 🔌 Adding a New AI Provider

OAF uses abstract base classes to make it easy to add new providers. Implement any combination of STT, LLM, or TTS:

```python
from src.providers.base import BaseLLMProvider, BaseTTSProvider

class MyLLMProvider(BaseLLMProvider):
    async def generate_response(self, prompt, system_prompt=None):
        yield "Hello from my custom LLM!"

    async def generate_response_with_actions(self, prompt, system_prompt=None, history=None):
        return "Hello!", {"emotions": "happy", "actions": "wave"}

class MyTTSProvider(BaseTTSProvider):
    async def synthesize_stream(self, text):
        audio_bytes = my_tts_api(text)
        yield audio_bytes
```

Then register in `main.py`:
```python
llm_providers = {
    "openai": OpenAILLMProvider(),
    "gemini": GeminiLLMProvider(),
    "custom": MyLLMProvider(),       # ← Add here
}
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🎯 Roadmap

- [ ] Streaming TTS for lower latency
- [ ] Multi-agent conversations
- [ ] ElevenLabs TTS provider
- [ ] User avatar upload persistence (server-side)
- [ ] Voice activity detection (VAD) for natural turn-taking
- [ ] Session recording and replay

---

## � Author

**Alexander Barquero Elizondo, Ph.D.**
📧 [alexander.barqueroelizondo@ucr.ac.cr](mailto:alexander.barqueroelizondo@ucr.ac.cr)
Profesor e Investigador — ECCI / CITIC
[Universidad de Costa Rica (UCR)](https://www.ucr.ac.cr)

---

## �📜 License

[MIT License](LICENSE) © 2026 [AURAxLab](https://github.com/AURAxLab)
