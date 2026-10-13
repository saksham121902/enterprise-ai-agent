"""Evaluation package for Enterprise AI Operations Agent.

Provides benchmark datasets, evaluation runners, and metric reporting for:
1. RAG retrieval hit-rate, answer correctness, and citation accuracy
2. Text-to-SQL execution accuracy and safety guardrail enforcement
3. Supervisor multi-agent intent classification and routing accuracy
4. Latency profiling (p50/p95) and token cost estimation
"""

from __future__ import annotations

__version__ = "1.0.0"
