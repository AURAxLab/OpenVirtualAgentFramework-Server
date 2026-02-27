import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import os
import json

# Setup environment variable for tests
os.environ["OAF_TESTING"] = "1"

# Import app after setting env vars
from src.main import app
from src.core.config import config_manager, OAFConfig
from unittest.mock import PropertyMock

@pytest.fixture
def mock_config():
    """Provides a mocked OAFConfig for testing."""
    data = {
        "experiment": {
            "name": "Test Experiment",
            "description": "desc",
            "version": "1.0.0"
        },
        "devices": [
            {"id": "vr_headset", "name": "Quest 3", "type": "xr"}
        ],
        "agents": [
            {"id": "agent_test", "name": "Test Agent", "description": "desc"},
            {"id": "agent_alpha", "name": "Alpha Agent", "description": "desc"}
        ],
        "custom_commands": {
            "emotions": {"description": "desc", "values": ["happy", "sad"]},
            "actions": {"description": "desc", "values": ["wave", "nod"]}
        }
    }
    return OAFConfig(**data)

@pytest.fixture(autouse=True)
def patch_config_manager(mocker, mock_config):
    """Automatically patches the global config_manager to return our mock OAFConfig."""
    # We patch the property 'config' on the ConfigManager class
    mocker.patch("src.core.config.ConfigManager.config", new_callable=PropertyMock, return_value=mock_config)
    return config_manager

@pytest_asyncio.fixture
async def async_client():
    """Provides an AsyncClient bound to the FastAPI app for HTTP/WS testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
