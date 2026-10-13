"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__, provider="anthropic")


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider (Claude 3.5, Claude 3, etc.)."""

    provider_name = "anthropic"

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize the async Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            settings = get_settings()
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using the Anthropic Messages API."""
        settings = get_settings()
        model = model or settings.anthropic_model
        client = self._get_client()

        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        start = time.perf_counter()
        response = await client.messages.create(**create_kwargs, **kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        result = LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=self.calculate_cost(model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            metadata={"stop_reason": response.stop_reason},
        )

        self.record_metrics(result)
        logger.info(
            "Anthropic generation complete",
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
        """Generate a streaming completion using the Anthropic API."""
        settings = get_settings()
        model = model or settings.anthropic_model
        client = self._get_client()

        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        async with client.messages.stream(**create_kwargs, **kwargs) as stream:
            async for text in stream.text_stream:
                yield text
