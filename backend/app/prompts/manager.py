"""Prompt template management using Jinja2.

Loads prompt templates from the ``prompts/`` directory and renders
them with context variables. Templates support inheritance, macros,
and conditional logic via Jinja2.

Usage::

    from app.prompts.manager import prompt_manager

    rendered = prompt_manager.render(
        "supervisor",
        user_message="Summarize Q3 revenue",
        available_tools=["sql_query", "calculator"],
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.core.logging import get_logger

logger = get_logger(__name__)

# Prompt templates directory (relative to backend root)
PROMPTS_DIR = Path(__file__).parent / "templates"


class PromptManager:
    """Manages and renders Jinja2 prompt templates.

    Templates are loaded from the filesystem and cached by Jinja2's
    built-in loader cache for performance.
    """

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or PROMPTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(self._dir)),
            autoescape=False,  # No HTML escaping for prompts
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a prompt template with the given context.

        Args:
            template_name: Template filename (without extension, or with .j2).
            **context: Variables to pass to the template.

        Returns:
            The rendered prompt string.

        Raises:
            TemplateNotFound: If the template file doesn't exist.
        """
        # Try with .j2 extension first, then without
        for name in [f"{template_name}.j2", template_name]:
            try:
                template = self._env.get_template(name)
                rendered = template.render(**context)
                return rendered.strip()
            except TemplateNotFound:
                continue

        raise TemplateNotFound(template_name)

    def list_templates(self) -> list[str]:
        """List all available template names.

        Returns:
            List of template filenames.
        """
        return self._env.list_templates(extensions=["j2", "txt", "md"])


# Global singleton
prompt_manager = PromptManager()
