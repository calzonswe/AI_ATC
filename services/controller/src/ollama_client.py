from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .prompt_engine import (
    LlmOutput,
    PromptContext,
    PromptEngine,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────

class OllamaError(Exception):
    """Base exception for all Ollama client errors."""


class OllamaConnectionError(OllamaError):
    """Failed to connect to the Ollama server."""


class OllamaTimeoutError(OllamaError):
    """Request to Ollama timed out."""


class OllamaResponseError(OllamaError):
    """Ollama returned an unexpected or malformed response."""


class OllamaModelError(OllamaError):
    """The requested model is not available on the Ollama server."""


# ──────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────

DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 2
RETRY_BACKOFF_S = [1.0, 2.0, 4.0]

CHAT_ENDPOINT = "/api/chat"
HEALTH_ENDPOINT = "/api/tags"


@dataclass
class OllamaResponse:
    raw_content: str
    llm_output: LlmOutput
    model: str
    total_duration_ns: Optional[int] = None


class OllamaClient:
    """Async HTTP client for the Ollama LLM API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:30b",
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        prompt_engine: Optional[PromptEngine] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._engine = prompt_engine or PromptEngine()
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ──

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OllamaClient:
        await self._get_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── Health ──

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(HEALTH_ENDPOINT)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                available = [m.get("name", "") for m in models]
                if self.model not in available:
                    logger.warning(
                        "Model %s not in available models: %s",
                        self.model, available,
                    )
                return True
            return False
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False

    # ── Primary API ──

    async def chat(
        self,
        context: PromptContext,
        system_override: Optional[str] = None,
    ) -> OllamaResponse:
        messages = self._build_messages(context, system_override)
        raw_response = await self._post_with_retry(messages)
        return self._parse_ollama_response(raw_response)

    # ── Internal ──

    def _build_messages(
        self,
        context: PromptContext,
        system_override: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        system = system_override or self._engine.build_system_prompt(
            self._engine._get_position(context.controller),  # noqa: SLF001
        )
        prompt = self._engine.build_radio_call_prompt(context)
        user_content = prompt.context_prompt or prompt.full_prompt

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    async def _post_with_retry(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self._post(messages)
            except (OllamaConnectionError, OllamaTimeoutError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)]
                    logger.warning(
                        "Ollama request failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        attempt + 1, self.max_retries + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Ollama request failed after %d attempts: %s",
                        self.max_retries + 1, exc,
                    )
            except OllamaError:
                raise
            except Exception as exc:
                last_error = exc
                logger.error("Unexpected error in Ollama request: %s", exc)
                break

        if last_error:
            raise last_error
        raise OllamaConnectionError(
            f"Request failed after {self.max_retries + 1} attempts"
        )

    async def _post(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        client = await self._get_client()
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            resp = await client.post(CHAT_ENDPOINT, json=payload)
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Request to Ollama timed out after {self.timeout}s: {exc}"
            ) from exc

        if resp.status_code == 404:
            detail = self._extract_error_detail(resp)
            raise OllamaModelError(
                f"Model '{self.model}' not found at {self.base_url}: {detail}"
            )
        if resp.status_code == 413:
            raise OllamaResponseError(
                f"Prompt exceeds model context window (413 Payload Too Large)"
            )
        if resp.status_code >= 500:
            detail = self._extract_error_detail(resp)
            raise OllamaConnectionError(
                f"Ollama server error ({resp.status_code}): {detail}"
            )
        if resp.status_code >= 400:
            detail = self._extract_error_detail(resp)
            raise OllamaResponseError(
                f"Ollama returned {resp.status_code}: {detail}"
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"Non-JSON response from Ollama: {resp.text[:500]}"
            ) from exc

        if "error" in data:
            raise OllamaResponseError(f"Ollama error in response: {data['error']}")

        return data

    def _parse_ollama_response(
        self,
        raw: Dict[str, Any],
    ) -> OllamaResponse:
        try:
            message = raw["message"]
            content = message["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaResponseError(
                f"Missing 'message.content' in Ollama response: {json.dumps(raw, default=str)[:500]}"
            ) from exc

        llm_output = self._engine.parse_llm_response(content)
        errors = self._engine.validate_output(llm_output)
        if errors:
            logger.warning("LLM output validation warnings: %s", errors)

        return OllamaResponse(
            raw_content=content,
            llm_output=llm_output,
            model=raw.get("model", self.model),
            total_duration_ns=raw.get("total_duration"),
        )

    @staticmethod
    def _extract_error_detail(resp: httpx.Response) -> str:
        try:
            body = resp.json()
            return body.get("error", resp.reason_phrase or str(resp.status_code))
        except Exception:
            return resp.text[:300] or resp.reason_phrase or str(resp.status_code)
