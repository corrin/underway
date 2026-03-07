"""Smoke test — verify the app starts and health endpoint works."""

from httpx import AsyncClient


async def test_health_endpoint(client: AsyncClient) -> None:
    """GET /api/health returns 200 with status ok."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
