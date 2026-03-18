"""Bedrock model factory for Agent LLM integration.

Provides a unified interface to create Claude models via AWS Bedrock.
Falls back gracefully when langchain-aws is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelTier(str, Enum):
    """Model tiers mapped to specific Claude models on Bedrock."""

    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


_MODEL_IDS: dict[ModelTier, str] = {
    ModelTier.OPUS: "anthropic.claude-opus-4-6-20250610-v1:0",
    ModelTier.SONNET: "anthropic.claude-sonnet-4-6-20250514-v1:0",
    ModelTier.HAIKU: "anthropic.claude-haiku-4-5-20251001-v1:0",
}

_DEFAULT_REGION = "us-east-1"


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a Bedrock model instance."""

    tier: ModelTier
    temperature: float = 0.0
    max_tokens: int = 4096
    region: str = _DEFAULT_REGION


# Agent-to-model mapping per PRD §3.3
AGENT_MODEL_MAP: dict[str, ModelConfig] = {
    "orchestrator": ModelConfig(tier=ModelTier.OPUS),
    "scanner": ModelConfig(tier=ModelTier.HAIKU),  # deterministic, LLM rarely used
    "nester": ModelConfig(tier=ModelTier.SONNET),
    "research": ModelConfig(tier=ModelTier.SONNET),
    "backtester": ModelConfig(tier=ModelTier.HAIKU, max_tokens=2048),
    "alerter": ModelConfig(tier=ModelTier.HAIKU, max_tokens=2048),
    "report": ModelConfig(tier=ModelTier.SONNET),
    "signal-reviewer": ModelConfig(tier=ModelTier.SONNET),
    # Per-layer LLM agents
    "segment-agent": ModelConfig(tier=ModelTier.HAIKU),
    "structure-agent": ModelConfig(tier=ModelTier.HAIKU),
    "divergence-agent": ModelConfig(tier=ModelTier.SONNET),
    "signal-agent": ModelConfig(tier=ModelTier.SONNET),
    "nesting-agent": ModelConfig(tier=ModelTier.SONNET),
}


def create_model(agent_name: str, config: ModelConfig | None = None) -> Any:
    """Create a ChatBedrock model for the given agent.

    Args:
        agent_name: Agent identifier (must be in AGENT_MODEL_MAP or config provided).
        config: Optional override config.

    Returns:
        A ChatBedrock instance, or a stub if langchain-aws is not installed.

    Raises:
        ValueError: If agent_name not found and no config provided.
    """
    cfg = config or AGENT_MODEL_MAP.get(agent_name)
    if cfg is None:
        raise ValueError(
            f"Unknown agent '{agent_name}'. "
            f"Available: {list(AGENT_MODEL_MAP.keys())}"
        )

    model_id = _MODEL_IDS[cfg.tier]

    try:
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=model_id,
            region_name=cfg.region,
            model_kwargs={
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
    except ImportError:
        return _StubModel(model_id=model_id, agent_name=agent_name)


class _StubModel:
    """Stub returned when langchain-aws is not installed.

    Raises a clear error when invoked, allowing import-time success
    but runtime failure with a helpful message.
    """

    def __init__(self, model_id: str, agent_name: str) -> None:
        self.model_id = model_id
        self.agent_name = agent_name

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            f"Cannot invoke model for agent '{self.agent_name}' "
            f"(model_id={self.model_id}). "
            "Install langchain-aws: pip install langchain-aws"
        )

    def __repr__(self) -> str:
        return f"StubModel(agent={self.agent_name}, model={self.model_id})"
