"""
Prompt loader for versioned templates.

Templates live in the ``app.services.ai.prompts`` package as modules named
``{name}_{version}``.
"""

from __future__ import annotations

import importlib
from typing import Any


def get_prompt(name: str, version: str = "v1", **kwargs: Any) -> tuple[str, str, str]:
    """
    Load a prompt template and format the user half.

    Args:
        name: Logical prompt name (e.g. ``research`` loads ``research_v1``).
        version: Version tag, e.g. ``v1``.
        **kwargs: Placeholders for the user template ``str.format``.

    Returns:
        Tuple of ``(system_prompt, user_prompt, version_string)``.
    """
    module_path = f"app.services.ai.prompts.{name}_{version}"
    module = importlib.import_module(module_path)
    system_prompt = str(module.__dict__["SYSTEM"])
    user_template = str(module.__dict__["USER_TEMPLATE"])
    user_prompt = user_template.format(**kwargs)
    version_string = f"{name}_{version}"
    return system_prompt, user_prompt, version_string
