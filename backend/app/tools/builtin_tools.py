"""Built-in enterprise tools for AI agent use.

These tools are automatically registered in the global ToolRegistry
when this module is imported.
"""

from __future__ import annotations

import json
try:
    from datetime import UTC, datetime, timezone
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc  # type: ignore[assignment]
from typing import Any

from app.core.constants import Permission
from app.tools.registry import tool


@tool(
    name="calculator",
    description=(
        "Perform mathematical calculations. Accepts a mathematical expression "
        "as a string and returns the computed result. Supports addition, "
        "subtraction, multiplication, division, exponents, and parentheses."
    ),
    category="utility",
    parameters_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '(42 * 3) + 17')",
            }
        },
        "required": ["expression"],
    },
)
async def calculator(expression: str) -> str:
    """Safely evaluate a mathematical expression.

    Uses a restricted evaluator that only allows mathematical operations
    (no builtins, no imports, no attribute access).
    """
    import ast
    import operator

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            op = OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree)
        return f"Result: {result}"
    except Exception as exc:
        return f"Calculation error: {exc}"


@tool(
    name="get_current_datetime",
    description="Get the current date and time in ISO 8601 format.",
    category="utility",
    parameters_schema={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name (default: UTC)",
                "default": "UTC",
            }
        },
    },
)
async def get_current_datetime(timezone: str = "UTC") -> str:
    """Return the current datetime."""
    now = datetime.now(UTC)
    return json.dumps({
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": timezone,
    })


@tool(
    name="text_summarizer",
    description=(
        "Summarize a piece of text into a concise summary. "
        "Useful for condensing long documents, articles, or meeting notes."
    ),
    category="text_processing",
    parameters_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to summarize",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum summary length in words",
                "default": 100,
            },
        },
        "required": ["text"],
    },
)
async def text_summarizer(text: str, max_length: int = 100) -> str:
    """Summarize text using the configured LLM."""
    from app.llm.factory import get_llm_service

    llm = get_llm_service()
    response = await llm.generate(
        prompt=f"Summarize the following text in no more than {max_length} words:\n\n{text}",
        system_prompt="You are a concise text summarizer. Output only the summary.",
        temperature=0.3,
        max_tokens=max_length * 2,
    )
    return response.content


@tool(
    name="json_formatter",
    description="Format, validate, and pretty-print JSON data.",
    category="utility",
    parameters_schema={
        "type": "object",
        "properties": {
            "json_string": {
                "type": "string",
                "description": "Raw JSON string to format",
            }
        },
        "required": ["json_string"],
    },
)
async def json_formatter(json_string: str) -> str:
    """Parse and pretty-print JSON."""
    try:
        parsed = json.loads(json_string)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"
