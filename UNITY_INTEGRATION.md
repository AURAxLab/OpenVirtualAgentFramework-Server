# Unity Integration Guide: Open Virtual Agent Framework (OAF)

This manual provides all the necessary information for a Unity Developer to connect a 3D XR application (PCVR, Meta Quest, WebGL) to the OAF Server.

OAF acts as the "brain," handling Speech-to-Text (STT), Large Language Model (LLM) processing, and Text-to-Speech (TTS) synthesis. Unity acts as the "body," handling user microphone input, 3D rendering, avatar lip-sync, and animations.

---

## 1. Connection Protocols

The OAF Server supports two concurrent protocols. You only need to implement **one**.

### Option A: WebSockets (Recommended)
Best for Meta Quest, WebGL, and mobile builds.
- **URL**: `ws://<server_ip>:8000/ws/client/<your_client_id>`
  - *Example*: `ws://192.68.1.100:8000/ws/client/quest_vr_01`
- **Unity Package**: We recommend [NativeWebSocket](https://github.com/endel/NativeWebSocket) or Unity's native `System.Net.WebSockets.ClientWebSocket`.

### Option B: ZeroMQ (Local/PCVR)
Best for low-latency desktop VR (PCVR) running on the same network or local machine.
- **PUB/SUB Port**: `tcp://<server_ip>:5555` (Subscribe to receive commands from the server).
- **REQ/REP Port**: `tcp://<server_ip>:5556` (Send requests to the server).
- **Unity Package**: [NetMQ](https://github.com/zeromq/netmq) via NuGet.

---

## 2. Universal Payload Structure

Every message sent to or received from the OAF Server uses a strict JSON schema called `BaseCommand`.

```json
{
  "sender": "quest_vr_01",         // Your Device ID 
  "target_device": "server",       // Who the message is for
  "target_agent": "agent_alpha",   // The specific Avatar/Agent ID
  "command_type": "audio",         // Can be: "audio", "message", "action", "scene_change", "system"
  "command": "stt_request",        // The specific action
  "subcommand": {                  // Optional: Data payload
    "key": "value"
  }
}
```

> **Important Configuration Note**: 
> The values for `sender`, `target_device`, and `target_agent` MUST match the IDs declared in the server's `config.yaml`. Default IDs are:
> - Devices: `quest_vr_01`, `quest_vr_02`, `woz_console`
> - Agents: `agent_alpha`, `agent_beta`

---

## 3. Core Workflows

### A. Sending Voice (Microphone to STT)
When the user speaks, record the microphone data in Unity, convert it to a `.WAV` byte array, encode it in Base64, and send it to the server.

**Unity -> Server (JSON Payload)**:
```json
{
  "sender": "quest_vr_01",
  "target_device": "server",
  "target_agent": "agent_alpha",
  "command_type": "audio",
  "command": "stt_request",
  "subcommand": {
    "audio_base64": "UklGR...<base64 string>..."
  }
}
```

### B. Sending Text (Direct LLM Request)
If you have a virtual keyboard or a debug UI, you can skip the STT and send text directly to the LLM.

**Unity -> Server (JSON Payload)**:
```json
{
  "sender": "quest_vr_01",
  "target_device": "server",
  "target_agent": "agent_alpha",
  "command_type": "message",
  "command": "llm_request",
  "subcommand": {
    "text": "Hello, how are you today?"
  }
}
```

### C. Receiving Agent Audio Responses (TTS)
When the LLM finishes thinking, the server generates audio and streams it down in base64 chunks. You must capture these chunks, decode them into byte arrays, and buffer them into a Unity `AudioClip` for the avatar to speak.

**Server -> Unity  (Incoming JSON)**:
```json
{
  "sender": "server",
  "target_device": "quest_vr_01",
  "target_agent": "agent_alpha",
  "command_type": "audio",
  "command": "tts_chunk",
  "subcommand": {
    "audio_base64": "UklGR..." // Part of the continuous WAV audio
  }
}
```
*Note: Depending on the provider (OpenAI vs Gemini), the audio will be either MP3 or WAV format.*

When the agent finishes talking, the server sends a completion signal:
```json
{
  "sender": "server",
  "target_device": "quest_vr_01",
  "target_agent": "agent_alpha",
  "command_type": "audio",
  "command": "tts_complete"
}
```

### D. Receiving Agent Actions (Emotions & Body Language)
The LLM can decide what emotion to show or what animation to play alongside its voice. This is sent dynamically.

**Server -> Unity (Incoming JSON)**:
```json
{
  "sender": "server",
  "target_device": "quest_vr_01",
  "target_agent": "agent_alpha",
  "command_type": "action",
  "command": "agent_action",
  "subcommand": {
    "emotion": "joy",       // Values: neutral, joy, sorrow, angry, fun, surprised
    "animation": "wave"     // Custom values defined in config.yaml
  }
}
```
In Unity, parse the `subcommand`, look for `emotion` or `animation`, and trigger the corresponding BlendShapes or Animator triggers on your VRM/3D Model.

---

## 4. Implementation Steps for Unity Dev

1. **Connect**: Open a standard WebSocket connection to `ws://server_ip:8000/ws/client/quest_vr_01`.
2. **Handle OnMessage**: Parse incoming text as JSON. Switch based on `command_type` and `command`.
3. **Audio Playback**: Use `Convert.FromBase64String()` on the incoming `tts_chunk` payloads. Pipe the byte arrays into a Unity AudioClip or use the Meta MR Utility Kit's audio streaming tools.
4. **Lip Sync**: Attach a script (like Oculus OVRLipSync) to the AudioSource playing the TTS so the avatar's mouth moves automatically with the audio.
5. **Mic Recording**: Use `Microphone.Start()` in Unity. Ensure you trim silence, package the clip as a WAV byte array, Base64 encode it, and construct the `stt_request` JSON to send over the socket.
