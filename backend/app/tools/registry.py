"""Dynamic Tool Registry for AI agent tool execution.

Tools are registered declaratively and discovered automatically.
The registry provides:
- Dynamic tool registration with metadata
- Permission-based access control
- Input validation via JSON schema
- Execution with timeout and error handling
- Prometheus metrics for tool usage

Usage::

    from app.tools.registry import tool_registry, tool

    @tool(
        name="calculator",
        description="Perform mathematical calculations",
        category="utility",
        permissions=[Permission.CHAT_CREATE],
    )
    async def calculator(expression: str) -> str:
        return str(eval(expression))  # simplified example

    # Agent discovers and executes tools:
    result = await tool_registry.execute("calculator", {"expression": "2 + 2"})
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from app.core.constants import Permission
from app.core.exceptions import ToolExecutionError
from app.core.logging import get_logger
from app.core.telemetry import TOOL_EXECUTIONS_TOTAL, TOOL_EXECUTION_DURATION

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    """Metadata and callable for a registered tool.

    Contains everything the AI agent needs to understand and invoke
    the tool, including its description (for LLM function calling),
    input schema (for validation), and required permissions.
    """

    name: str
    description: str
    category: str = "general"
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    required_permissions: list[Permission] = field(default_factory=list)
    is_dangerous: bool = False  # Requires human approval
    timeout_seconds: int = 30
    func: Callable[..., Coroutine[Any, Any, Any]] | None = None

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format.

        Returns:
            Dict compatible with OpenAI's tool/function calling API.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema or {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    def to_langchain_tool(self) -> dict[str, Any]:
        """Convert to LangChain tool format.

        Returns:
            Dict for LangChain's StructuredTool.
        """
        return {
            "name": self.name,
            "description": self.description,
            "args_schema": self.parameters_schema,
        }


class ToolRegistry:
    """Central registry for all available tools.

    Tools can be registered via decorator (``@tool``) or
    programmatically via ``register()``. The registry supports
    discovery, permission checking, and execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        """Register a tool in the registry.

        Args:
            definition: The complete tool definition with callable.

        Raises:
            ValueError: If a tool with the same name already exists.
        """
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._tools[definition.name] = definition
        logger.info(
            "Tool registered",
            tool_name=definition.name,
            category=definition.category,
        )

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry.

        Args:
            name: The tool name to remove.
        """
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name.

        Args:
            name: The tool name.

        Returns:
            The tool definition, or None if not found.
        """
        return self._tools.get(name)

    def list_tools(
        self,
        category: str | None = None,
        user_permissions: set[Permission] | None = None,
    ) -> list[ToolDefinition]:
        """List available tools, optionally filtered.

        Args:
            category: Filter by tool category.
            user_permissions: If provided, only return tools the user
                has permission to use.

        Returns:
            List of matching tool definitions.
        """
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if user_permissions is not None:
            tools = [
                t for t in tools
                if not t.required_permissions
                or all(p in user_permissions for p in t.required_permissions)
            ]

        return tools

    def get_openai_functions(
        self, user_permissions: set[Permission] | None = None
    ) -> list[dict[str, Any]]:
        """Get all tools in OpenAI function calling format.

        Args:
            user_permissions: Optional permission filter.

        Returns:
            List of OpenAI-formatted function definitions.
        """
        tools = self.list_tools(user_permissions=user_permissions)
        return [t.to_openai_function() for t in tools]

    def check_permission(
        self, tool_name: str, user_permissions: set[Permission]
    ) -> bool:
        """Check if a user has permission to execute a tool.

        Args:
            tool_name: The tool to check.
            user_permissions: The user's permissions.

        Returns:
            True if the user can execute the tool.
        """
        tool_def = self._tools.get(tool_name)
        if not tool_def:
            return False
        if not tool_def.required_permissions:
            return True
        return all(p in user_permissions for p in tool_def.required_permissions)

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a registered tool by name.

        Includes timeout enforcement, error handling, and metrics.

        Args:
            name: The tool name to execute.
            arguments: The tool input arguments.

        Returns:
            The tool's return value.

        Raises:
            ToolExecutionError: If the tool is not found, times out,
                or raises an exception.
        """
        tool_def = self._tools.get(name)
        if not tool_def:
            raise ToolExecutionError(tool=name, message=f"Tool '{name}' not found")
        if not tool_def.func:
            raise ToolExecutionError(tool=name, message=f"Tool '{name}' has no callable")

        max_retries = 3
        backoff_delay = 0.1
        last_error: Exception | None = None
        start = time.perf_counter()

        for attempt in range(1, max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool_def.func(**(arguments or {})),
                    timeout=tool_def.timeout_seconds,
                )
                duration = time.perf_counter() - start

                TOOL_EXECUTIONS_TOTAL.labels(tool_name=name, status="success").inc()
                TOOL_EXECUTION_DURATION.labels(tool_name=name).observe(duration)

                logger.info(
                    "Tool executed successfully",
                    tool_name=name,
                    attempt=attempt,
                    duration_ms=int(duration * 1000),
                )
                return result

            except asyncio.TimeoutError:
                last_error = ToolExecutionError(
                    tool=name,
                    message=f"Tool '{name}' timed out after {tool_def.timeout_seconds}s (attempt {attempt}/{max_retries})",
                )
                logger.warning("Tool execution timed out, retrying", tool_name=name, attempt=attempt)
            except Exception as exc:
                last_error = exc
                logger.warning("Tool execution failed, retrying with backoff", tool_name=name, attempt=attempt, error=str(exc))

            if attempt < max_retries:
                await asyncio.sleep(backoff_delay * (2 ** (attempt - 1)))

        duration = time.perf_counter() - start
        TOOL_EXECUTIONS_TOTAL.labels(tool_name=name, status="error").inc()
        TOOL_EXECUTION_DURATION.labels(tool_name=name).observe(duration)

        raise ToolExecutionError(
            tool=name,
            message=f"Tool '{name}' failed after {max_retries} attempts: {last_error}",
        ) from last_error

    @property
    def tool_count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    @property
    def categories(self) -> set[str]:
        """Unique categories across all registered tools."""
        return {t.category for t in self._tools.values()}


# Global registry singleton
tool_registry = ToolRegistry()


def tool(
    name: str,
    description: str,
    category: str = "general",
    parameters_schema: dict[str, Any] | None = None,
    required_permissions: list[Permission] | None = None,
    is_dangerous: bool = False,
    timeout_seconds: int = 30,
):
    """Decorator to register a function as a tool.

    Args:
        name: Unique tool name.
        description: Human-readable description (shown to LLM).
        category: Tool category for organization.
        parameters_schema: JSON Schema for input validation.
        required_permissions: Permissions needed to execute.
        is_dangerous: Whether this tool requires human approval.
        timeout_seconds: Maximum execution time.

    Usage::

        @tool(name="web_search", description="Search the web")
        async def web_search(query: str) -> str:
            ...
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        definition = ToolDefinition(
            name=name,
            description=description,
            category=category,
            parameters_schema=parameters_schema or {},
            required_permissions=required_permissions or [],
            is_dangerous=is_dangerous,
            timeout_seconds=timeout_seconds,
            func=func,
        )
        tool_registry.register(definition)
        return func

    return decorator
