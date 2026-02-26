import os
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from google import genai
from structlog import get_logger

from src.providers.base import BaseLLMProvider
from src.core.config import config_manager

logger = get_logger()
std_log = logging.getLogger("oaf.gemini")

class GeminiClientSingleton:
    """Manages the shared Gemini client instance."""
    _instance = None
    _client: genai.Client = None

    @classmethod
    def get_client(cls) -> genai.Client:
        if cls._client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                std_log.warning("⚠️ Gemini: GEMINI_API_KEY not found in environment. Provider will be disabled.")
                logger.warning("GEMINI_API_KEY environment variable not set.")
                return None
            
            try:
                cls._client = genai.Client(api_key=api_key)
                std_log.info(f"✅ Gemini: Client initialized successfully (key ends in ...{api_key[-4:]})")
            except ValueError as e:
                std_log.error(f"❌ Gemini: Failed to create client | {str(e)}")
                logger.error("Failed to create Gemini client", error=str(e))
                return None

        return cls._client

class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini Language Model utilizing Native Tool Calling for configuration actions."""
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model = model_name
        self.client = GeminiClientSingleton.get_client()

    def _build_tools_schema(self) -> list:
        """Dynamically build Gemini Tool Schema from the config_manager."""
        config = config_manager.config
        
        properties = {}
        required = []

        # Iterate all custom defined commands from YAML config (ex: emotions, actions)
        for cat_name, category in config.custom_commands.items():
            properties[cat_name] = {
                "type": "STRING",
                "enum": category.values,
                "description": category.description
            }
            required.append(cat_name)

        # Add spoken_response as a required param so the LLM always provides text
        properties["spoken_response"] = {
            "type": "STRING",
            "description": "Your spoken reply to the user. This is what the agent will say out loud."
        }
        required.append("spoken_response")

        # Gemini expects the JSON Schema format to be slightly different (OpenAPI 3.0 subset)
        # We define a function declaration
        tool_schema = {
            "function_declarations": [
                {
                    "name": "update_agent_state",
                    "description": "Always call this function with your spoken reply and the agent's updated state.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": properties,
                        "required": required
                    }
                }
            ]
        }
        return [tool_schema]

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        # Gemini Python SDK doesn't natively support AsyncGenerator out-of-the-box easily without workarounds
        # For the MVP we await the whole stream generation or loop through the blocking sync iterable
        
        config_kwargs = {}
        if system_prompt:
             config_kwargs["system_instruction"] = system_prompt

        response = self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(**config_kwargs)
        )
        
        # We yield as strings
        for chunk in response:
            if chunk.text:
                 yield chunk.text

    async def generate_response_with_actions(self, prompt: str, system_prompt: Optional[str] = None, history: Optional[list] = None) -> tuple[str, Dict[str, Any]]:
        """Non-streaming call that returns text and parallel tool arguments (JSON)."""
        if not self.client:
            std_log.error("❌ Gemini: Provider called but client is None (missing API key)")
            logger.error("Gemini Provider called but the client is not initialized (missing API key).")
            return "Server Error: Gemini Provider is unconfigured.", {}

        tools = self._build_tools_schema()
        
        config_kwargs = {
            "tools": tools,
            "temperature": 0.7,
        }
        if system_prompt:
             config_kwargs["system_instruction"] = system_prompt
        
        # Build multi-turn contents from history
        contents = []
        if history:
            for msg in history:
                role = "model" if msg["role"] == "assistant" else msg["role"]
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        std_log.info(f"🔄 Gemini: Calling API | model={self.model} | prompt=\"{prompt[:80]}\" | history_turns={len(contents)-1}")
             
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=contents,
                config=genai.types.GenerateContentConfig(**config_kwargs)
            )
        except Exception as e:
            std_log.error(f"❌ Gemini: API call FAILED | {type(e).__name__}: {str(e)}")
            logger.error("Gemini API call failed", error=str(e))
            return f"API Error: {str(e)}", {}
        
        spoken_text = ""
        actions = {}
        
        # Manually iterate parts to handle mixed text + function_call responses
        # The SDK's response.text property can fail or return empty when function_calls are present
        try:
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        spoken_text += part.text
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        std_log.info(f"⚡ Gemini: Function call detected | name={fc.name} args={fc.args}")
                        if fc.name == "update_agent_state":
                            args = dict(fc.args)
                            # Extract spoken_response from function args if text is empty
                            if not spoken_text and "spoken_response" in args:
                                spoken_text = args.pop("spoken_response")
                            else:
                                args.pop("spoken_response", None)
                            actions = args
            else:
                # Fallback to simple .text if no candidates structure
                spoken_text = response.text or ""
        except Exception as e:
            std_log.warning(f"⚠️ Gemini: Error parsing response parts | {str(e)}")
            try:
                spoken_text = response.text or ""
            except Exception:
                pass
                    
        std_log.info(f"✅ Gemini: Response complete | text=\"{spoken_text[:80]}\" | actions={actions}")
        return spoken_text, actions
