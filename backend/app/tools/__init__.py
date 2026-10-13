"""Tools package — tool registry and built-in tools.

Importing this package registers all built-in tools.
"""

# Auto-register built-in tools on import
from app.tools import builtin_tools as _builtin  # noqa: F401
from app.tools.registry import ToolDefinition, ToolRegistry, tool, tool_registry

__all__ = ["ToolDefinition", "ToolRegistry", "tool", "tool_registry"]
