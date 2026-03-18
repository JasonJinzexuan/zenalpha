"""Prompt version management for LLM reasoning layer agents.

Each agent's system prompt is stored as a Markdown file under
``chanquant/prompt_versions/<agent_name>/``.  This module provides:

- Loading the latest (or a specific) version of a prompt
- Listing available versions
- Recording prompt change metadata
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompt_versions"


@dataclass(frozen=True)
class PromptVersion:
    """Metadata for a single prompt version."""

    agent_name: str
    version: str
    filename: str
    content: str


@dataclass(frozen=True)
class PromptChangeRecord:
    """Audit record for a prompt change (mirrors PRD §2 Prompt versioning)."""

    version: str
    agent: str
    date: date
    change_summary: str
    trigger: str = ""
    old_accuracy: float | None = None
    new_accuracy: float | None = None
    sample_size: int | None = None
    p_value: float | None = None
    approved_by: str = ""


def list_versions(agent_name: str) -> list[PromptVersion]:
    """List all available prompt versions for an agent, sorted ascending."""
    agent_dir = _PROMPT_DIR / agent_name
    if not agent_dir.is_dir():
        return []

    versions: list[PromptVersion] = []
    for f in sorted(agent_dir.iterdir()):
        if f.suffix == ".md":
            ver = f.stem.split("_")[0] if "_" in f.stem else f.stem
            content = f.read_text(encoding="utf-8")
            versions.append(
                PromptVersion(
                    agent_name=agent_name,
                    version=ver,
                    filename=f.name,
                    content=content,
                )
            )
    return versions


def load_prompt(agent_name: str, version: str | None = None) -> str:
    """Load a prompt for the given agent.

    Args:
        agent_name: Directory name under prompt_versions/.
        version: Specific version prefix (e.g. "v1.0.0"). If None, loads
                 the latest (last sorted) version.

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: If no prompts exist for this agent.
    """
    versions = list_versions(agent_name)
    if not versions:
        raise FileNotFoundError(
            f"No prompts found for agent '{agent_name}' in {_PROMPT_DIR}"
        )

    if version is None:
        return versions[-1].content

    for v in versions:
        if v.version == version:
            return v.content

    raise FileNotFoundError(
        f"Prompt version '{version}' not found for agent '{agent_name}'. "
        f"Available: {[v.version for v in versions]}"
    )


def get_prompt_dir() -> Path:
    """Return the root prompt_versions directory path."""
    return _PROMPT_DIR
