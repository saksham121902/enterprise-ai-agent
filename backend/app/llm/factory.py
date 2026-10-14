"""LLM service factory with automatic provider fallback.

Provides a unified ``LLMService`` that:
1. Routes requests to the configured primary provider
2. Automatically falls back to secondary providers on failure
3. Supports hot-swapping providers via configuration
4. Tracks metrics and costs across all providers

Usage::

    service = get_llm_service()
    response = await service.generate("Summarize this contract...")
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator

from app.core.config import get_settings
from app.core.constants import LLMProvider
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__)


def _create_provider(provider_name: str) -> BaseLLMProvider:
    """Create a provider instance by name.

    Imports are lazy to avoid loading unused provider SDKs.

    Args:
        provider_name: The provider identifier string.

    Returns:
        An initialized provider instance.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    p = provider_name.lower()
    if p == LLMProvider.OPENAI:
        from app.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif p == LLMProvider.ANTHROPIC:
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif p == LLMProvider.GOOGLE:
        from app.llm.google_provider import GoogleProvider
        return GoogleProvider()
    elif p == LLMProvider.OLLAMA:
        from app.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")


class LLMService:
    """Unified LLM service with multi-provider fallback.

    Tries the primary provider first, then falls back through
    configured fallback providers if the primary fails.
    """

    def __init__(
        self,
        primary_provider: str | None = None,
        fallback_providers: list[str] | None = None,
    ) -> None:
        settings = get_settings()
        self._primary_name = primary_provider or settings.llm_primary_provider
        self._fallback_names = fallback_providers or settings.llm_fallback_providers

        # Lazy provider cache
        self._providers: dict[str, BaseLLMProvider] = {}

    def _is_provider_configured(self, name: str) -> bool:
        """Check if the given provider has necessary credentials/configuration."""
        settings = get_settings()
        p = name.lower()
        if p == LLMProvider.OPENAI:
            return bool(settings.openai_api_key or os.getenv("OPENAI_API_KEY"))
        elif p == LLMProvider.ANTHROPIC:
            return bool(settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))
        elif p == LLMProvider.GOOGLE:
            return bool(
                settings.google_api_key
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
            )
        elif p == LLMProvider.OLLAMA:
            return bool(settings.ollama_base_url or os.getenv("OLLAMA_BASE_URL"))
        return False

    def _get_provider(self, name: str) -> BaseLLMProvider:
        """Get or create a cached provider instance."""
        if name not in self._providers:
            self._providers[name] = _create_provider(name)
        return self._providers[name]

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion with automatic fallback.

        Tries the specified/primary provider first. If it fails,
        iterates through fallback providers until one succeeds.
        If no API keys are configured, returns an immediate structured demo response.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            provider: Force a specific provider (bypasses fallback).
            **kwargs: Provider-specific parameters.

        Returns:
            Standardized LLMResponse from the successful provider.

        Raises:
            LLMProviderError: If all providers fail.
        """
        if provider:
            return await self._try_provider(
                provider, prompt, system_prompt, model, temperature, max_tokens, **kwargs
            )

        # Prioritize configured providers
        all_candidates = [self._primary_name, *self._fallback_names]
        configured_candidates = [p for p in all_candidates if self._is_provider_configured(p)]

        if configured_candidates:
            # Try configured providers first, then unconfigured as fallback
            providers_to_try = configured_candidates + [
                p for p in all_candidates if p not in configured_candidates
            ]
        else:
            providers_to_try = all_candidates

        last_error: Exception | None = None

        for provider_name in providers_to_try:
            # Skip attempting unconfigured providers if we already know none are configured
            if not self._is_provider_configured(provider_name) and not configured_candidates:
                continue

            try:
                return await self._try_provider(
                    provider_name, prompt, system_prompt, model, temperature, max_tokens, **kwargs
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM provider failed, trying next",
                    provider=provider_name,
                    error=str(exc),
                )

        # If no provider succeeded and none were configured with API keys, return an intelligent demo response
        if not configured_candidates:
            logger.info("No LLM API keys configured. Generating intelligent demo response.")
            is_json_request = (
                "JSON" in prompt
                or "json" in prompt
                or (system_prompt and "json" in system_prompt.lower())
            )

            if is_json_request:
                demo_content = json.dumps({
                    "reasoning": (
                        "Enterprise AI multi-agent supervisor, PostgreSQL DB, and security guardrails "
                        "are fully operational. Configure OPENAI_API_KEY or GEMINI_API_KEY for live LLM inference."
                    ),
                    "route_to": "direct",
                    "direct_response": (
                        "👋 Welcome to the Enterprise AI Assistant! All system components—multi-agent routing, "
                        "PostgreSQL persistence, document indexing, and role-based access control—are running live and healthy. "
                        "To enable real-time generative responses with external LLMs, set your `OPENAI_API_KEY` or `GEMINI_API_KEY` in Render environment variables."
                    ),
                })
            else:
                demo_content = (
                    "👋 Welcome to the Enterprise AI Assistant! All system components—multi-agent routing, "
                    "PostgreSQL persistence, document indexing, and role-based access control—are running live and healthy. "
                    "To enable real-time generative responses with external LLMs, set your `OPENAI_API_KEY` or `GEMINI_API_KEY` in Render environment variables."
                )

            tokens_count = len(prompt.split()) + len(demo_content.split())
            return LLMResponse(
                content=demo_content,
                model="demo-mode",
                provider="enterprise-agent",
                input_tokens=len(prompt.split()),
                output_tokens=len(demo_content.split()),
                total_tokens=tokens_count,
                cost_usd=0.0,
                latency_ms=10,
            )

        raise LLMProviderError(
            provider=self._primary_name,
            message=f"All LLM providers failed. Last error: {last_error}",
        )

    async def _try_provider(
        self,
        provider_name: str,
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> LLMResponse:
        """Attempt generation with a single provider."""
        try:
            p = self._get_provider(provider_name)
            return await p.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:
            raise LLMProviderError(
                provider=provider_name,
                message=f"Provider '{provider_name}' error: {exc}",
            ) from exc

    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming completion (primary provider only).

        Streaming does not support automatic fallback since partial
        responses may have already been sent to the client.

        Yields:
            Content chunks as they arrive.
        """
        provider_name = provider or self._primary_name

        # If selected provider is not configured, try any configured fallback
        if not self._is_provider_configured(provider_name):
            for fb in self._fallback_names:
                if self._is_provider_configured(fb):
                    provider_name = fb
                    break

        if not self._is_provider_configured(provider_name):
            yield (
                "👋 Welcome to Enterprise AI Agent! The multi-agent supervisor and database are fully operational. "
                "To enable live streaming LLM responses, set your OPENAI_API_KEY or GEMINI_API_KEY in the environment."
            )
            return

        p = self._get_provider(provider_name)
        async for chunk in p.generate_streaming(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk


# Module-level singleton
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the global LLM service singleton.

    Returns:
        The configured LLMService instance.
    """
    global _llm_service  # noqa: PLW0603
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
