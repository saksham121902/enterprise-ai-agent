"""LLM provider abstraction layer.

Provides a unified interface for multiple LLM providers with:
- Automatic fallback between providers
- Token counting and cost tracking
- Prometheus metrics integration
- Structured logging for every call

Usage::

    from app.llm.factory import get_llm_service

    llm = get_llm_service()
    response = await llm.generate("Summarize this document: ...")
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import LLM_PRICING
from app.core.logging import get_logger
from app.core.telemetry import LLM_COST_DOLLARS, LLM_REQUEST_DURATION, LLM_TOKENS_TOTAL

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider.

    Provides a consistent interface regardless of which provider
    (OpenAI, Anthropic, Google, Ollama) generated the response.
    """

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Each provider implements ``generate`` and ``generate_streaming``
    with provider-specific API calls, while the base class handles
    metrics, logging, and cost calculation.
    """

    provider_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            prompt: The user prompt / message.
            system_prompt: Optional system prompt for behavior guidance.
            model: Model override (uses config default if None).
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens in the response.
            **kwargs: Provider-specific additional parameters.

        Returns:
            Standardized LLMResponse.
        """

    @abstractmethod
    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        """Generate a streaming completion from the LLM.

        Yields partial response chunks for real-time display.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            **kwargs: Provider-specific parameters.

        Yields:
            String chunks of the response.
        """

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate the USD cost for a request.

        Args:
            model: The model name.
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.

        Returns:
            Cost in USD.
        """
        pricing = LLM_PRICING.get(model, {})
        if not pricing:
            return 0.0
        input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
        return round(input_cost + output_cost, 6)

    def record_metrics(self, response: LLMResponse) -> None:
        """Record Prometheus metrics for the LLM call.

        Args:
            response: The LLM response with token/cost data.
        """
        LLM_TOKENS_TOTAL.labels(
            provider=response.provider,
            model=response.model,
            token_type="input",
        ).inc(response.input_tokens)

        LLM_TOKENS_TOTAL.labels(
            provider=response.provider,
            model=response.model,
            token_type="output",
        ).inc(response.output_tokens)

        LLM_COST_DOLLARS.labels(
            provider=response.provider,
            model=response.model,
        ).inc(response.cost_usd)

        LLM_REQUEST_DURATION.labels(
            provider=response.provider,
            model=response.model,
        ).observe(response.latency_ms / 1000.0)
