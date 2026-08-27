"""Shared helpers for resolving QC check settings."""

from typing import Any
from ..core import preferences


def resolve_settings(
    settings_schema: dict[str, dict[str, Any]] | None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Merge user preferences over a QC check's default settings.

    Args:
        settings_schema:
            The check module's SETTINGS dictionary.

        preferences:
            User-configured values for the check.

    Returns:
        Resolved setting values.

    Example:
        SETTINGS = {
            "threshold": {
                "type": "float",
                "default": 0.001,
            },
        }

        settings = resolve_settings(
            SETTINGS,
            preferences,
        )
    """
    if not isinstance(settings_schema, dict):
        return {}

    resolved: dict[str, Any] = {}

    for setting_name, definition in settings_schema.items():
        if not isinstance(definition, dict):
            continue

        resolved[setting_name] = definition.get(
            "default"
        )

    if isinstance(preferences, dict):
        for setting_name, value in preferences.items():
            if setting_name in resolved:
                resolved[setting_name] = value

    return resolved
