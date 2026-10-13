"""Google Gemini LLM provider implementation."""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__, provider="google")


class GoogleProvider(BaseLLMProvider):
    """Google Generative AI provider (Gemini 2.0, 1.5 Pro, etc.)."""

    provider_name = "google"

    def __init__(self) -> None:
        self._configured = False

    def _configure(self) -> None:
        """Configure the Google Generative AI SDK with API key."""
        if not self._configured:
            import os
            import google.generativeai as genai

            settings = get_settings()
            api_key = (
                settings.google_api_key
                or os.getenv("GEMINI_API_KEY", "")
                or os.getenv("GOOGLE_API_KEY", "")
            )
            genai.configure(api_key=api_key)
            self._configured = True

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using the Google Generative AI API."""
        import google.generativeai as genai

        self._configure()
        settings = get_settings()
        model_name = model or settings.google_model

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
            generation_config=generation_config,
        )

        start = time.perf_counter()
        response = await model_instance.generate_content_async(prompt, **kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = response.text if response.text else ""

        # Extract token counts from usage metadata
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        result = LLMResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=self.calculate_cost(model_name, input_tokens, output_tokens),
            latency_ms=latency_ms,
        )

        self.record_metrics(result)
        logger.info(
            "Google generation complete",
            model=model_name,
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
        """Generate a streaming completion using the Google API."""
        import google.generativeai as genai

        self._configure()
        settings = get_settings()
        model_name = model or settings.google_model

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
            generation_config=generation_config,
        )

        response = await model_instance.generate_content_async(
            prompt, stream=True, **kwargs
        )

        async for chunk in response:
            if chunk.text:
                yield chunk.text
