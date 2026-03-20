"""Agentic tool-use execution loop.

Runs an LLM agent with tools: invoke → execute tool calls → feed results → repeat.
Supports Claude's native tool_use via ChatBedrock.bind_tools().
"""

from __future__ import annotations

import json
from typing import Any

from chanquant.agents.tool_defs import execute_tool, get_langchain_tools


_MAX_ITERATIONS = 8  # prevent infinite loops


def run_agent_with_tools(
    model: Any,
    system_prompt: str,
    user_message: str,
    max_iterations: int = _MAX_ITERATIONS,
) -> dict[str, Any]:
    """Run an agentic loop with tool use.

    Args:
        model: ChatBedrock model instance (will be bound to tools).
        system_prompt: System prompt for the agent.
        user_message: Initial user message.
        max_iterations: Max tool-use rounds.

    Returns:
        {"response": str, "tool_calls": list[dict], "iterations": int}
    """
    tools = get_langchain_tools()
    model_with_tools = model.bind_tools(tools)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tool_call_log: list[dict[str, Any]] = []

    for iteration in range(max_iterations):
        response = model_with_tools.invoke(messages)

        # Check for tool calls
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            # No more tool calls — agent is done
            content = response.content if hasattr(response, "content") else str(response)
            return {
                "response": content,
                "tool_calls": tool_call_log,
                "iterations": iteration + 1,
            }

        # Process each tool call
        messages.append(response)  # Add assistant message with tool_calls

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            # Execute the tool
            result = execute_tool(tool_name, tool_args)

            tool_call_log.append({
                "iteration": iteration,
                "tool": tool_name,
                "args": tool_args,
                "result_summary": _summarize_result(result),
            })

            # Feed result back as tool message
            from langchain_core.messages import ToolMessage
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=tool_call["id"],
                )
            )

    # Hit max iterations
    final_content = ""
    if messages:
        last = messages[-1]
        if hasattr(last, "content"):
            final_content = last.content
    return {
        "response": final_content,
        "tool_calls": tool_call_log,
        "iterations": max_iterations,
    }


def _summarize_result(result: dict) -> dict:
    """Create a concise summary of tool result for logging."""
    summary: dict[str, Any] = {}
    if "error" in result:
        summary["error"] = result["error"]
    if "instrument" in result:
        summary["instrument"] = result["instrument"]
    if "timeframe" in result:
        summary["timeframe"] = result["timeframe"]
    if "signals" in result:
        summary["signal_count"] = len(result["signals"])
        summary["signals"] = [s.get("signal_type") for s in result["signals"]]
    if "trend" in result and result["trend"]:
        summary["trend"] = result["trend"].get("classification")
    if "bar_count" in result:
        summary["bar_count"] = result["bar_count"]
    return summary
