import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class DeviceConfig(BaseModel):
    id: str
    name: str
    type: str

class AgentConfig(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class CustomCommandCategory(BaseModel):
    description: str
    values: List[str]

class ExperimentConfig(BaseModel):
    name: str
    description: str
    version: str

class OAFConfig(BaseModel):
    experiment: ExperimentConfig
    devices: List[DeviceConfig]
    agents: List[AgentConfig]
    custom_commands: Dict[str, CustomCommandCategory]

class ConfigManager:
    """Singleton to load and manage the dynamic configuration throughout the server."""
    _instance = None
    _config: Optional[OAFConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def load_config(self, config_path: str | Path = "config.yaml") -> OAFConfig:
        """Loads and parses the YAML config file into Pydantic models."""
        p = Path(config_path)
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found at {p.absolute()}")
            
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        self._config = OAFConfig(**data)
        return self._config
        
    @property
    def config(self) -> OAFConfig:
        if self._config is None:
            raise ValueError("Config not loaded. Call load_config() first.")
        return self._config

    def get_valid_devices(self) -> List[str]:
        return [dev.id for dev in self.config.devices] + ["all"]
        
    def get_valid_agents(self) -> List[str]:
        return [agent.id for agent in self.config.agents] + ["all"]

# Global accessor
config_manager = ConfigManager()
