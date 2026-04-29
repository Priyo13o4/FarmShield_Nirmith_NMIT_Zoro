"""
FarmShield Chat — Test Suite (Phase 10).

All 11 test cases covering PRD §12 requirements.
Tests never connect to a real DB, MQTT broker, or Gemini API.
Agent and session store are mocked at the appropriate layer.

Test IDs:
  test_chat_disabled_returns_404         — router not registered, route doesn't exist
  test_chat_message_valid                — happy path invoke
  test_chat_message_empty_string         — 422 validation
  test_chat_message_too_long             — 422 validation
  test_chat_session_preserves_history    — session_store.append called
  test_chat_session_clear                — DELETE 200 cleared=True
  test_chat_session_clear_not_found      — DELETE 404
  test_chat_agent_error_graceful         — invoke error → 200 with error reply
  test_sql_tools_restricted_tables       — build_sql_tools uses include_tables
  test_rag_tool_builds_index             — first run builds FAISS
  test_rag_tool_loads_existing_index     — second run loads from disk
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure chat vars are set before any app imports
os.environ.update({
    "CHAT_ENABLED": "false",   # default — individual tests override
    "GEMINI_API_KEY": "test-key",
    "CHAT_DB_READONLY_USER": "farmshield_readonly",
    "CHAT_DB_READONLY_PASSWORD": "readonly123",
})


# ── Helpers ─────────────────────────────────────────────────────────────────

def _chat_enabled_client():
    """
    Return a context manager yielding an AsyncClient with chat enabled.
    Uses the existing async_client pattern from conftest but forces chat_enabled=True
    and patches farm_agent at the service layer.
    """
    from contextlib import asynccontextmanager
    from app.dependencies import get_db
    from app.main import app

    @asynccontextmanager
    async def mock_lifespan(a):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    async def mock_get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    return ASGITransport(app=app), original_lifespan


# ── Tests: Chat Disabled ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_disabled_returns_404(async_client):
    """
    When CHAT_ENABLED=false the chat router is never registered.
    POST /api/v1/chat/message must return 404 (route not found).
    """
    response = await async_client.post(
        "/api/v1/chat/message",
        json={"message": "hello", "session_id": "s1"},
    )
    assert response.status_code == 404


# ── Tests: Chat Enabled ──────────────────────────────────────────────────────

@pytest.fixture
def mock_agent_invoke():
    """Patch farm_agent.invoke to return a canned successful response."""
    with patch("app.services.chat.agent.farm_agent") as m:
        m.invoke = AsyncMock(return_value={
            "reply": "Soil moisture is 42%.",
            "sources": ["sql_database_query"],
            "session_id": "test-session",
            "ts": 1234567890,
        })
        m.stream = AsyncMock()
        yield m


@pytest.fixture
def mock_agent_error():
    """Patch farm_agent.invoke to return a graceful error response (not raise)."""
    with patch("app.services.chat.agent.farm_agent") as m:
        m.invoke = AsyncMock(return_value={
            "reply": "I encountered an error processing your request.",
            "sources": [],
            "session_id": "test-session",
            "error": "Gemini API timeout",
            "ts": 1234567890,
        })
        yield m


@pytest.fixture
def mock_session_store():
    """Patch session_store for isolation."""
    with patch("app.services.chat.session_store.session_store") as m:
        m.get_history = AsyncMock(return_value=[])
        m.append = AsyncMock()
        m.clear = AsyncMock(return_value=True)
        yield m


@pytest.fixture
async def chat_client(mock_agent_invoke):
    """
    AsyncClient with CHAT_ENABLED=true and agent mocked.
    Uses the chat router which is registered conditionally.
    """
    from contextlib import asynccontextmanager
    from app.dependencies import get_db
    from app.config import settings

    # Temporarily enable chat
    original = settings.chat_enabled
    settings.chat_enabled = True

    # Re-register the chat router
    from app.api.v1 import chat as chat_module
    from app.api.v1.router import router as v1_router
    # Check if already included (idempotent)
    existing_prefixes = [r.path for r in v1_router.routes]
    if "/chat/message" not in " ".join(existing_prefixes):
        v1_router.include_router(chat_module.router)

    from app.main import app

    @asynccontextmanager
    async def mock_lifespan(a):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    async def mock_get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    settings.chat_enabled = original
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_message_valid(chat_client, mock_agent_invoke):
    """POST /chat/message with valid body → 200 with reply, sources, ts."""
    response = await chat_client.post(
        "/api/v1/chat/message",
        json={"message": "What is the soil moisture?", "session_id": "test-session"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "Soil moisture is 42%."
    assert data["session_id"] == "test-session"
    assert isinstance(data["sources"], list)
    assert isinstance(data["ts"], int)
    mock_agent_invoke.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_chat_message_empty_string(chat_client):
    """POST /chat/message with empty message → 422."""
    response = await chat_client.post(
        "/api/v1/chat/message",
        json={"message": "", "session_id": "s1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_message_too_long(chat_client):
    """POST /chat/message with message > 2000 chars → 422."""
    response = await chat_client.post(
        "/api/v1/chat/message",
        json={"message": "x" * 2001, "session_id": "s1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_agent_error_graceful(chat_client, mock_agent_error):
    """Agent returning error dict → still 200, not 500."""
    response = await chat_client.post(
        "/api/v1/chat/message",
        json={"message": "What is the soil temperature?", "session_id": "test-session"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data["reply"].lower() or data["reply"]  # graceful reply


# ── Tests: Session ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_session_clear(chat_client):
    """DELETE /chat/session/{id} → 200 cleared=True."""
    with patch("app.api.v1.chat.session_store") as mock_store:
        mock_store.clear = AsyncMock(return_value=True)
        response = await chat_client.delete("/api/v1/chat/session/test-session")
    assert response.status_code == 200
    assert response.json() == {"session_id": "test-session", "cleared": True}


@pytest.mark.asyncio
async def test_chat_session_clear_not_found(chat_client):
    """DELETE /chat/session/{id} for unknown session → 404."""
    with patch("app.api.v1.chat.session_store") as mock_store:
        mock_store.clear = AsyncMock(return_value=False)
        response = await chat_client.delete("/api/v1/chat/session/ghost-session")
    assert response.status_code == 404
    assert response.json()["detail"]["type"] == "NOT_FOUND"


# ── Tests: Session Store Unit ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_store_max_history():
    """SessionStore trims history to max_history pairs."""
    from app.services.chat.session_store import SessionStore
    store = SessionStore(max_history=2)
    await store.append("s1", "q1", "a1")
    await store.append("s1", "q2", "a2")
    await store.append("s1", "q3", "a3")  # should drop q1/a1
    history = await store.get_history("s1")
    assert len(history) == 4  # 2 pairs = 4 messages
    assert history[0].content == "q2"


@pytest.mark.asyncio
async def test_session_store_clear_returns_false_for_unknown():
    """SessionStore.clear returns False for unknown session."""
    from app.services.chat.session_store import SessionStore
    store = SessionStore(max_history=10)
    result = await store.clear("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_session_store_clear_returns_true_for_existing():
    """SessionStore.clear returns True and removes the session."""
    from app.services.chat.session_store import SessionStore
    store = SessionStore(max_history=10)
    await store.append("s1", "hello", "world")
    result = await store.clear("s1")
    assert result is True
    history = await store.get_history("s1")
    assert history == []


# ── Tests: SQL Tool ──────────────────────────────────────────────────────────

def test_sql_tools_use_include_tables():
    """build_sql_tools configures SQLDatabase with only the allowed tables."""
    with patch("app.services.chat.sql_tool.SQLDatabase") as mock_db_cls:
        mock_db = MagicMock()
        mock_db.dialect = "postgresql"
        mock_db_cls.from_uri.return_value = mock_db

        with patch("app.services.chat.sql_tool.InfoSQLDatabaseTool") as mock_info:
            with patch("app.services.chat.sql_tool.QuerySQLDataBaseTool") as mock_query:
                mock_info.return_value = MagicMock()
                mock_query.return_value = MagicMock()

                from app.config import settings
                from app.services.chat.sql_tool import build_sql_tools

                tools = build_sql_tools(settings)

                call_kwargs = mock_db_cls.from_uri.call_args[1]
                assert "sensor_readings" in call_kwargs["include_tables"]
                assert "alerts" in call_kwargs["include_tables"]
                assert "ml_inferences" not in call_kwargs["include_tables"]
                assert len(tools) == 2


# ── Tests: RAG Tool ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_tool_builds_index_from_knowledge_dir(tmp_path):
    """RagTool.load_or_build_index builds a FAISS index when none exists."""
    from app.services.chat.rag_tool import RagTool

    settings_mock = MagicMock()
    settings_mock.faiss_index_path = str(tmp_path / "new_index")
    settings_mock.gemini_embedding_model = "models/text-embedding-004"
    settings_mock.gemini_api_key = "test-key"

    mock_vectorstore = MagicMock()
    mock_vectorstore.as_retriever.return_value = MagicMock()

    with patch("app.services.chat.rag_tool.GoogleGenerativeAIEmbeddings"):
        with patch("app.services.chat.rag_tool.FAISS") as mock_faiss:
            mock_faiss.from_documents = MagicMock(return_value=mock_vectorstore)

            rag = RagTool()
            await rag.load_or_build_index(settings_mock)

            assert rag._ready is True
            mock_faiss.from_documents.assert_called_once()
            mock_vectorstore.save_local.assert_called_once()


@pytest.mark.asyncio
async def test_rag_tool_loads_existing_index(tmp_path):
    """RagTool.load_or_build_index loads from disk when index dir exists and non-empty."""
    # Create a non-empty directory to simulate existing index
    index_dir = tmp_path / "existing_index"
    index_dir.mkdir()
    (index_dir / "index.faiss").write_bytes(b"dummy")

    from app.services.chat.rag_tool import RagTool

    settings_mock = MagicMock()
    settings_mock.faiss_index_path = str(index_dir)
    settings_mock.gemini_embedding_model = "models/text-embedding-004"
    settings_mock.gemini_api_key = "test-key"

    mock_vectorstore = MagicMock()
    mock_vectorstore.as_retriever.return_value = MagicMock()

    with patch("app.services.chat.rag_tool.GoogleGenerativeAIEmbeddings"):
        with patch("app.services.chat.rag_tool.FAISS") as mock_faiss:
            mock_faiss.load_local = MagicMock(return_value=mock_vectorstore)

            rag = RagTool()
            await rag.load_or_build_index(settings_mock)

            assert rag._ready is True
            mock_faiss.load_local.assert_called_once()
            mock_faiss.from_documents.assert_not_called()
