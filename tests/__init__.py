"""Test configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from llm_adapter_claw.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)
