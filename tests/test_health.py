"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient

from llm_adapter_claw import __version__
from llm_adapter_claw.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__

    def test_readiness_check(self, client: TestClient) -> None:
        """Test readiness check endpoint."""
        response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_metrics_endpoint(self, client: TestClient) -> None:
        """Test metrics endpoint."""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "requests_total" in data
