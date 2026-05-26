"""Integration test for the health check endpoint."""

import pytest


@pytest.mark.integration
async def test_health_returns_healthy(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}
