"""
Central tool registry for Orch-xarc.

Collects all tools from the four namespaces and exposes them as lists
that can be bound to LangGraph agents.

Usage::

    from src.tools.registry import ToolRegistry

    registry = ToolRegistry()
    parent_tools = registry.get_all_tools()       # 53 tools
    subagent_tools = registry.get_math_tools()     # 14 tools (scoped)
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from src.tools.polymarket.tools import POLYMARKET_TOOLS
from src.tools.kalshi.tools import KALSHI_TOOLS
from src.tools.math_logic.tools import MATH_LOGIC_TOOLS
from src.tools.ops.tools import OPS_TOOLS


class ToolRegistry:
    """Namespace-aware tool registry."""

    def __init__(self) -> None:
        self._namespaces: dict[str, list[BaseTool]] = {
            "polymarket": list(POLYMARKET_TOOLS),
            "kalshi": list(KALSHI_TOOLS),
            "math_logic": list(MATH_LOGIC_TOOLS),
            "ops": list(OPS_TOOLS),
        }

    # ── Queries ─────────────────────────────────────────────

    def get_all_tools(self) -> list[BaseTool]:
        """Return every registered tool (for the parent agent)."""
        tools: list[BaseTool] = []
        for ns_tools in self._namespaces.values():
            tools.extend(ns_tools)
        return tools

    def get_namespace_tools(self, namespace: str) -> list[BaseTool]:
        """Return tools for a single namespace."""
        return list(self._namespaces.get(namespace, []))

    def get_math_tools(self) -> list[BaseTool]:
        """Scoped tool set for the arbitrage subagent."""
        return self.get_namespace_tools("math_logic")

    def get_parent_tools(self) -> list[BaseTool]:
        """All tools except math_logic (parent gathers, subagent analyses)."""
        tools: list[BaseTool] = []
        for ns, ns_tools in self._namespaces.items():
            tools.extend(ns_tools)
        return tools

    # ── Introspection ───────────────────────────────────────

    @property
    def tool_count(self) -> int:
        return sum(len(t) for t in self._namespaces.values())

    @property
    def namespace_count(self) -> int:
        return len(self._namespaces)

    def manifest(self) -> list[dict[str, str]]:
        """Return a serializable manifest of all tools for the /tools endpoint."""
        result = []
        for ns, ns_tools in self._namespaces.items():
            for tool in ns_tools:
                result.append({
                    "name": tool.name,
                    "namespace": ns,
                    "description": tool.description or "",
                })
        return result
