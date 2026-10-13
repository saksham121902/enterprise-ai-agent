"""Ollama local LLM provider implementation."""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__, provider="ollama")


class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider (Llama 3, Mistral, CodeGemma, etc.)."""

    provider_name = "ollama"

    def __init__(self) -> None:
        self._base_url: str | None = None

    def _get_base_url(self) -> str:
        """Get the Ollama server base URL from config."""
        if self._base_url is None:
            settings = get_settings()
            self._base_url = settings.ollama_base_url.rstrip("/")
        return self._base_url

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using the Ollama REST API."""
        settings = get_settings()
        model = model or settings.ollama_model
        base_url = self._get_base_url()

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - start) * 1000)

        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        result = LLMResponse(
            content=data.get("response", ""),
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=0.0,  # Local models have no cost
            latency_ms=latency_ms,
        )

        self.record_metrics(result)
        logger.info(
            "Ollama generation complete",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        return result

    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming completion using the Ollama API."""
        settings = get_settings()
        model = model or settings.ollama_model
        base_url = self._get_base_url()

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()
                import json

                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("response"):
                            yield data["response"]
