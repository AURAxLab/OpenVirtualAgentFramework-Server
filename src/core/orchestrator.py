import asyncio
import base64
import logging
from typing import Optional
from structlog import get_logger

from src.providers.base import BaseSTTProvider, BaseLLMProvider, BaseTTSProvider
from src.core.schemas import BaseCommand
from src.core.router import router

logger = get_logger()
std_log = logging.getLogger("oaf.orchestrator")

class DialogOrchestrator:
    """
    Manages the core AI Pipeline for the Framework:
    1. STT: Binary Audio -> Text
    2. LLM: Text -> Response Text + JSON Actions
    3. TTS: Response Text -> Binary Audio Stream
    4. Routing: Dispatch Actions and TTS Audio back to XR
    """
    MAX_HISTORY_TURNS = 20  # Keep last N messages to prevent token overflow

    def __init__(self, 
                 stt_provider: BaseSTTProvider,
                 llm_providers: dict[str, BaseLLMProvider], 
                 tts_provider: BaseTTSProvider,
                 default_llm: str = "openai"):
                     
        self.stt = stt_provider
        self.llm_providers = llm_providers
        self.active_llm_id = default_llm
        self.tts = tts_provider
        self.tts_enabled = True  # Toggle from UI
        self.conversation_history: list[dict[str, str]] = []
        
        # This will be overridden by the config or UI
        self.system_prompt = (
            "You are an embodied virtual agent in an XR environment. "
            "Be concise and reply in natural spoken language. "
            "Pay close attention to the user's emotional state and respond empathetically. "
            "If the user expresses frustration, sadness, or excitement, reflect that in your emotion choice. "
            "Always call the update_agent_state function with your spoken reply and appropriate state."
        )

    def clear_history(self):
        """Clears conversation memory."""
        self.conversation_history.clear()
        std_log.info("🗑️ Orchestrator: Conversation history cleared")

    @property
    def llm(self) -> BaseLLMProvider:
        """Returns the currently active LLM provider instance."""
        provider = self.llm_providers.get(self.active_llm_id)
        if not provider:
            logger.error(f"Active LLM Provider '{self.active_llm_id}' not found. Falling back to first available.")
            return next(iter(self.llm_providers.values()))
        return provider

    def set_active_llm(self, provider_id: str):
        if provider_id in self.llm_providers:
            self.active_llm_id = provider_id
            logger.info("Orchestrator: LLM Provider Swapped", new_provider=provider_id)
            return True
        logger.warning("Orchestrator: Ignored request to swap to unknown provider", unknown_id=provider_id)
        return False
        
    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt
        logger.info("Orchestrator: System Prompt Updated")
        
    async def process_audio_interaction(self, audio_bytes: bytes, target_device: str, target_agent: str):
        """Full pipeline from raw audio bytes out to TTS playback."""
        logger.info("Orchestrator: Starting STT...")
        user_text = await self.stt.transcribe(audio_bytes)
        
        if not user_text.strip():
            logger.info("Orchestrator: STT returned empty transcription. Aborting.")
            return
            
        logger.info("Orchestrator: STT Result", text=user_text)
        await self.process_text_interaction(user_text, target_device, target_agent)

    async def process_text_interaction(self, text: str, target_device: str, target_agent: str):
        """Pipeline starting from parsed Text (Useful for WoZ injection or direct Web chat)."""
        try:
            # Append user message to conversation history
            self.conversation_history.append({"role": "user", "content": text})
            
            std_log.info(f"🧠 Orchestrator: Starting LLM call | provider={self.active_llm_id} | prompt=\"{text[:80]}\" | history_turns={len(self.conversation_history)}")
            logger.info("Orchestrator: Asking LLM...", prompt=text)
            
            spoken_reply, actions = await self.llm.generate_response_with_actions(
                prompt=text,
                system_prompt=self.system_prompt,
                history=self.conversation_history[:-1]  # Everything except current msg (already in prompt)
            )
            
            # Append assistant reply to conversation history
            if spoken_reply:
                self.conversation_history.append({"role": "assistant", "content": spoken_reply})
            
            # Trim history to prevent token overflow
            if len(self.conversation_history) > self.MAX_HISTORY_TURNS:
                self.conversation_history = self.conversation_history[-self.MAX_HISTORY_TURNS:]
            
            std_log.info(f"✅ Orchestrator: LLM responded | reply=\"{str(spoken_reply)[:120]}\" | actions={actions}")
            logger.info("Orchestrator: LLM Reply", text=spoken_reply, actions=actions)
            
            # 0. Broadcast the raw text so the Web UI Chat window can display what the Bot is thinking
            if spoken_reply:
                std_log.info(f"📡 Orchestrator: Broadcasting llm_reply to all transports")
                text_cmd = BaseCommand(
                    sender="server_orchestrator",
                    target_device="all", # Send to UI
                    target_agent=target_agent,
                    command_type="message",
                    command="llm_reply",
                    subcommand={
                        "text": spoken_reply,
                        "provider": self.active_llm_id,
                        "model": self.llm.model,
                        "agent": target_agent
                    }
                )
                await router.route_command(text_cmd)
                std_log.info(f"✅ Orchestrator: llm_reply broadcast complete")
            else:
                std_log.warning(f"⚠️ Orchestrator: LLM returned empty spoken_reply")
            
            # 1. Dispatch the chosen actions (Emotions/Transformations) FIRST
            if actions:
                await self._dispatch_actions(actions, target_device, target_agent)
                
            # 2. Dispatch the TTS Audio Stream (only if enabled)
            if spoken_reply and self.tts_enabled:
                 await self._dispatch_tts(spoken_reply, target_device, target_agent)
            elif spoken_reply and not self.tts_enabled:
                std_log.info("🔇 Orchestrator: TTS disabled, skipping audio generation")
        except Exception as e:
            std_log.error(f"💥 Orchestrator: CRITICAL ERROR in process_text_interaction | {type(e).__name__}: {str(e)}")
            logger.error("Orchestrator pipeline crashed", error=str(e))

    async def _dispatch_actions(self, actions_dict: dict, target_device: str, target_agent: str):
        """Packages LLM JSON actions into a valid BaseCommand and pushes it to Router."""
        try:
            std_log.info(f"⚡ Orchestrator: Dispatching actions | {actions_dict}")
            cmd = BaseCommand(
                sender="server_orchestrator",
                target_device=target_device,
                target_agent=target_agent,
                command_type="action",
                command="execute_state",
                subcommand=actions_dict
            )
            # Route back out to ZMQ/WS
            await router.route_command(cmd)
            
        except Exception as e:
            std_log.error(f"❌ Orchestrator: Failed to dispatch actions | {str(e)}")
            logger.error("Failed to parse and route LLM actions", error=str(e), actions=actions_dict)

    async def _dispatch_tts(self, text: str, target_device: str, target_agent: str):
        """Starts TTS generation and streams audio chunks through the router as they arrive."""
        try:
            audio_generator = self.tts.synthesize_stream(text)
            
            async for audio_chunk in audio_generator:
                # We encode the raw bytes into base64 to transport inside the JSON command via ZMQ
                b64_chunk = base64.b64encode(audio_chunk).decode("utf-8")
                
                cmd = BaseCommand(
                    sender="server_orchestrator",
                    target_device=target_device,
                    target_agent=target_agent,
                    command_type="audio",
                    command="tts_chunk",
                    subcommand={"audio_base64": b64_chunk}
                )
                await router.route_command(cmd)
                
            # Optional: Send a final 'tts_complete' flag 
            end_cmd = BaseCommand(
                sender="server_orchestrator",
                target_device=target_device,
                target_agent=target_agent,
                command_type="audio",
                command="tts_complete"
            )
            await router.route_command(end_cmd)
            
        except Exception as e:
            logger.error("TTS Streaming failed", error=str(e))
