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

        # Try primary provider
        providers_to_try = [self._primary_name, *self._fallback_names]
        last_error: Exception | None = None

        for provider_name in providers_to_try:
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
