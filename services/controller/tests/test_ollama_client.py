import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ground import GroundController
from ollama_client import (
    DEFAULT_TIMEOUT_S,
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaModelError,
    OllamaResponse,
    OllamaResponseError,
    OllamaTimeoutError,
)
from prompt_engine import LlmOutput, PromptContext


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_ollama_response(
    content: str,
    model: str = "qwen3:30b",
    total_duration_ns: int = 1_000_000_000,
    status_code: int = 200,
    error: bool = False,
) -> httpx.Response:
    body: dict = {
        "model": model,
        "created_at": "2025-01-01T00:00:00Z",
        "message": {
            "role": "assistant",
            "content": content,
        },
        "done": True,
        "total_duration": total_duration_ns,
    }
    if error:
        body = {"error": content}
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "/api/chat"),
    )


def _make_valid_json_content() -> str:
    return json.dumps({
        "readback_correct": True,
        "phraseology_text": "SAS901, TAXI TO RUNWAY 01L VIA A B C",
        "issued_clearance": {
            "type": "taxi",
            "route": ["A", "B", "C"],
            "runway": "01L",
        },
    })


@pytest.fixture
def ground():
    return GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")


@pytest.fixture
def context(ground):
    return PromptContext(controller=ground)


@pytest.fixture
def client(ground):
    return OllamaClient(
        base_url="http://test-ollama:11434",
        model="qwen3:30b",
        timeout=5.0,
        max_retries=1,
    )


# ──────────────────────────────────────────────
# Client initialization
# ──────────────────────────────────────────────

class TestInit:
    def test_default_values(self):
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "qwen3:30b"
        assert client.timeout == DEFAULT_TIMEOUT_S
        assert client.max_retries == 2

    def test_custom_values(self):
        client = OllamaClient(
            base_url="http://custom:11434",
            model="llama3:8b",
            timeout=30.0,
            max_retries=3,
        )
        assert client.base_url == "http://custom:11434"
        assert client.model == "llama3:8b"
        assert client.max_retries == 3

    def test_base_url_trailing_slash_stripped(self):
        client = OllamaClient(base_url="http://test:11434/")
        assert client.base_url == "http://test:11434"

    def test_engine_not_provided_creates_default(self):
        client = OllamaClient()
        assert client._engine is not None


# ──────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager_creates_and_closes_client(self):
        async with OllamaClient(base_url="http://test:11434") as client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        client = OllamaClient(base_url="http://test:11434")
        await client.close()
        await client.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_instance(self):
        client = OllamaClient(base_url="http://test:11434")
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2
        await client.close()


# ──────────────────────────────────────────────
# _build_messages
# ──────────────────────────────────────────────

class TestBuildMessages:
    def test_returns_system_and_user(self, client, context):
        messages = client._build_messages(context)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Ground Controller" in messages[0]["content"]
        assert "ESSA_GND" in messages[1]["content"]

    def test_system_override(self, client, context):
        messages = client._build_messages(context, system_override="You are a test.")
        assert messages[0]["content"] == "You are a test."


# ──────────────────────────────────────────────
# Successful chat
# ──────────────────────────────────────────────

class TestChatSuccess:
    @pytest.mark.asyncio
    async def test_chat_returns_ollama_response(self, client, context):
        valid = _make_valid_json_content()

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(valid).json()

            result = await client.chat(context)

        assert isinstance(result, OllamaResponse)
        assert isinstance(result.llm_output, LlmOutput)
        assert result.llm_output.readback_correct is True
        assert "TAXI" in result.llm_output.phraseology_text
        assert result.llm_output.issued_clearance is not None
        assert result.llm_output.issued_clearance.type == "taxi"
        assert result.model == "qwen3:30b"
        assert result.total_duration_ns == 1_000_000_000

    @pytest.mark.asyncio
    async def test_chat_with_system_override(self, client, context):
        valid = _make_valid_json_content()

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(valid).json()

            messages = client._build_messages(context, system_override="Custom")
            _ = await client.chat(context, system_override="Custom")

        # Verify the messages passed to _post
        call_args = mock_post.await_args
        assert call_args is not None
        sent_messages = call_args.args[0]
        assert sent_messages[0]["content"] == "Custom"

    @pytest.mark.asyncio
    async def test_chat_parses_malformed_content_gracefully(self, client, context):
        bad_content = "not valid json at all"

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(bad_content).json()

            result = await client.chat(context)

        assert isinstance(result, OllamaResponse)
        assert result.raw_content == bad_content
        # parse_llm_response should fall back to readback_correct=False
        assert result.llm_output.readback_correct is False
        assert result.llm_output.phraseology_text == bad_content

    @pytest.mark.asyncio
    async def test_chat_extracts_markdown_json(self, client, context):
        md_content = '```json\n{"readback_correct": true, "phraseology_text": "HOLD SHORT"}\n```'

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(md_content).json()

            result = await client.chat(context)
        assert result.llm_output.readback_correct is True
        assert result.llm_output.phraseology_text == "HOLD SHORT"


# ──────────────────────────────────────────────
# Retry mechanism
# ──────────────────────────────────────────────

class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, client, context):
        valid = _make_valid_json_content()

        call_count = 0

        async def _mock_post(messages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OllamaConnectionError("Connection refused")
            return _make_ollama_response(valid).json()

        with patch.object(client, "_post", new=_mock_post):
            result = await client.chat(context)

        assert call_count == 2
        assert result.llm_output.readback_correct is True

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self, client, context):
        valid = _make_valid_json_content()

        call_count = 0

        async def _mock_post(messages):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OllamaTimeoutError("Timed out")
            return _make_ollama_response(valid).json()

        client.max_retries = 2

        with patch.object(client, "_post", new=_mock_post):
            result = await client.chat(context)

        assert call_count == 3
        assert result.llm_output.readback_correct is True

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises(self, client, context):
        call_count = 0

        async def _mock_post(messages):
            nonlocal call_count
            call_count += 1
            raise OllamaConnectionError("Down")

        with patch.object(client, "_post", new=_mock_post):
            with pytest.raises(OllamaConnectionError, match="Down"):
                await client.chat(context)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self, client, context):
        call_count = 0

        async def _mock_post(messages):
            nonlocal call_count
            call_count += 1
            raise OllamaResponseError("Bad request")

        with patch.object(client, "_post", new=_mock_post):
            with pytest.raises(OllamaResponseError):
                await client.chat(context)

        assert call_count == 1


# ──────────────────────────────────────────────
# HTTP error codes
# ──────────────────────────────────────────────

class TestHttpErrors:
    @pytest.mark.asyncio
    async def test_404_model_not_found(self, client, context):
        resp = httpx.Response(
            status_code=404,
            json={"error": 'model "qwen3:30b" not found'},
            request=httpx.Request("POST", "/api/chat"),
        )

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=resp)):
            with pytest.raises(OllamaModelError, match="not found"):
                await client.chat(context)

    @pytest.mark.asyncio
    async def test_413_payload_too_large(self, client, context):
        resp = httpx.Response(
            status_code=413,
            json={},
            request=httpx.Request("POST", "/api/chat"),
        )

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=resp)):
            with pytest.raises(OllamaResponseError, match="exceeds model context"):
                await client.chat(context)

    @pytest.mark.asyncio
    async def test_500_server_error_retried_then_raises(self, client, context):
        resp = httpx.Response(
            status_code=500,
            json={"error": "internal error"},
            request=httpx.Request("POST", "/api/chat"),
        )

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=resp)):
            with pytest.raises(OllamaConnectionError, match="500"):
                await client.chat(context)

    @pytest.mark.asyncio
    async def test_400_bad_request(self, client, context):
        resp = httpx.Response(
            status_code=400,
            json={"error": "bad parameters"},
            request=httpx.Request("POST", "/api/chat"),
        )

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=resp)):
            with pytest.raises(OllamaResponseError, match="400"):
                await client.chat(context)


# ──────────────────────────────────────────────
# Network errors
# ──────────────────────────────────────────────

class TestNetworkErrors:
    @pytest.mark.asyncio
    async def test_connection_refused(self, client, context):
        with patch.object(
            httpx.AsyncClient, "post",
            new=AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(OllamaConnectionError, match="Cannot connect"):
                await client.chat(context)

    @pytest.mark.asyncio
    async def test_timeout(self, client, context):
        with patch.object(
            httpx.AsyncClient, "post",
            new=AsyncMock(side_effect=httpx.TimeoutException("Timed out")),
        ):
            with pytest.raises(OllamaTimeoutError, match="timed out"):
                await client.chat(context)


# ──────────────────────────────────────────────
# Response parsing
# ──────────────────────────────────────────────

class TestResponseParsing:
    def test_parse_valid_response(self, client):
        raw = _make_ollama_response(_make_valid_json_content()).json()
        result = client._parse_ollama_response(raw)
        assert result.llm_output.readback_correct is True
        assert result.raw_content == _make_valid_json_content()
        assert result.total_duration_ns == 1_000_000_000

    def test_parse_missing_message_key(self, client):
        raw = {"model": "test"}
        with pytest.raises(OllamaResponseError, match="Missing.*message"):
            client._parse_ollama_response(raw)

    def test_parse_missing_content_key(self, client):
        raw = {"model": "test", "message": {}}
        with pytest.raises(OllamaResponseError, match="Missing.*content"):
            client._parse_ollama_response(raw)

    def test_parse_non_dict_message(self, client):
        raw = {"model": "test", "message": "not a dict"}
        with pytest.raises(OllamaResponseError, match="Missing.*content"):
            client._parse_ollama_response(raw)

    def test_orchestration_response_format(self, client):
        raw = _make_ollama_response(_make_valid_json_content()).json()
        result = client._parse_ollama_response(raw)
        assert raw["total_duration"] == result.total_duration_ns


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        resp = httpx.Response(
            status_code=200,
            json={"models": [{"name": "qwen3:30b"}]},
            request=httpx.Request("GET", "/api/tags"),
        )

        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=resp)):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self, client):
        with patch.object(
            httpx.AsyncClient, "get",
            new=AsyncMock(side_effect=httpx.ConnectError("Down")),
        ):
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, client):
        with patch.object(
            httpx.AsyncClient, "get",
            new=AsyncMock(side_effect=httpx.TimeoutException("Timed out")),
        ):
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_non_200(self, client):
        resp = httpx.Response(
            status_code=503,
            request=httpx.Request("GET", "/api/tags"),
        )

        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=resp)):
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_model_not_available_logs_warning(self, client, caplog):
        resp = httpx.Response(
            status_code=200,
            json={"models": [{"name": "llama3:8b"}]},
            request=httpx.Request("GET", "/api/tags"),
        )

        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=resp)):
            result = await client.health_check()

        assert result is True
        assert "qwen3:30b not in available" in caplog.text


# ──────────────────────────────────────────────
# Error extraction
# ──────────────────────────────────────────────

class TestExtractErrorDetail:
    def test_json_error_body(self):
        resp = httpx.Response(
            status_code=404,
            json={"error": "model not found"},
            request=httpx.Request("POST", "/api/chat"),
        )
        detail = OllamaClient._extract_error_detail(resp)
        assert detail == "model not found"

    def test_non_json_body(self):
        resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "/api/chat"),
        )
        detail = OllamaClient._extract_error_detail(resp)
        assert "Internal Server Error" in detail


# ──────────────────────────────────────────────
# Integration: end-to-end with real PromptEngine
# ──────────────────────────────────────────────

class TestIntegration:
    @pytest.mark.asyncio
    async def test_chat_with_real_prompt_engine(self, ground):
        context = PromptContext(controller=ground)
        client = OllamaClient(
            base_url="http://test:11434",
            model="qwen3:30b",
            timeout=5.0,
            max_retries=0,
        )
        valid = _make_valid_json_content()

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(valid).json()

            result = await client.chat(context)

        assert result.llm_output.readback_correct is True
        assert result.llm_output.issued_clearance is not None

    @pytest.mark.asyncio
    async def test_chat_uses_correct_endpoint(self, context):
        client = OllamaClient(
            base_url="http://test:11434",
            model="qwen3:30b",
            timeout=5.0,
            max_retries=0,
        )

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(
                _make_valid_json_content()
            )
            await client.chat(context)

        call_kwargs = mock_post.await_args
        assert call_kwargs is not None
        url_path = str(call_kwargs.args[0]) if call_kwargs.args else ""
        assert "/api/chat" in url_path or url_path.endswith("/api/chat")

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client, context):
        valid = _make_valid_json_content()

        with patch.object(client, "_post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _make_ollama_response(valid).json()

            results = await asyncio.gather(
                client.chat(context),
                client.chat(context),
                client.chat(context),
            )

        assert len(results) == 3
        for r in results:
            assert r.llm_output.readback_correct is True


import asyncio  # noqa: E402
