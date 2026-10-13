"""OpenAI LLM provider implementation."""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__, provider="openai")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider (GPT-4o, GPT-4o-mini, etc.)."""

    provider_name = "openai"

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize the async OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI

            settings = get_settings()
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
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
        """Generate a completion using the OpenAI API.

        Args:
            prompt: User message.
            system_prompt: System message for behavior guidance.
            model: Model name override.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            Standardized LLMResponse.
        """
        settings = get_settings()
        model = model or settings.openai_model
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        result = LLMResponse(
            content=response.choices[0].message.content or "",
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=self.calculate_cost(model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            metadata={"finish_reason": response.choices[0].finish_reason},
        )

        self.record_metrics(result)
        logger.info(
            "OpenAI generation complete",
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
        """Generate a streaming completion using the OpenAI API.

        Yields:
            Content chunks as they arrive from the API.
        """
        settings = get_settings()
        model = model or settings.openai_model
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
