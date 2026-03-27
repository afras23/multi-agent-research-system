"""
Helpers to parse JSON from LLM responses (including fenced blocks).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_json_text(raw: str) -> str:
    """Strip markdown fences and return JSON text for parsing."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    return text


def parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a single JSON object from model output."""
    text = extract_json_text(raw)
    if not text:
        return {}
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse JSON object from LLM output",
            extra={"preview": raw[:200]},
        )
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def parse_json_array(raw: str) -> list[Any]:
    """Parse a JSON array from model output."""
    text = extract_json_text(raw)
    if not text:
        return []
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse JSON array from LLM output",
            extra={"preview": raw[:200]},
        )
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def parse_model_list(raw: str, model_type: type[T]) -> list[T]:
    """Parse and validate a list of Pydantic models from JSON array text."""
    items = parse_json_array(raw)
    validated: list[T] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        try:
            validated.append(model_type.model_validate(entry))
        except ValidationError:
            logger.warning(
                "Model list item validation failed",
                extra={"model": model_type.__name__, "preview": raw[:200]},
            )
    return validated
