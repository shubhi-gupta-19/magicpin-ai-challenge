import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.context_store import context_store
from app.suppression import suppression_manager
from app.conversation_manager import conversation_manager

@pytest.fixture
def client():
    # Fresh state per test session/function if needed
    context_store.clear()
    suppression_manager.clear()
    conversation_manager.clear()
    with TestClient(app) as c:
        yield c
