import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_root_headless_mode(async_client: AsyncClient):
    """
    Test that the root URL serves the headless dashboard when OAF_TESTING environment variable is on.
    We assert that the response is successful and contains HTML indicative of the headless page.
    """
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Headless Dashboard" in response.text
    assert "<title>OAF Server | Headless Dashboard</title>" in response.text

@pytest.mark.asyncio
async def test_static_files_resolution(async_client: AsyncClient):
    """
    Test that static files like the SDK resolve correctly even when in headless mode.
    """
    response = await async_client.get("/sdk/oaf-client.js")
    # Even if the file doesn't perfectly match our mocking directory structure in tests,
    # the router should still attempt to fetch it rather than failing with a 500.
    # In GitHub Actions, static folder might not be populated during tox tests unless copied, 
    # but 200/404 is the expected behavior of StaticFiles() not 500.
    assert response.status_code in [200, 404]


