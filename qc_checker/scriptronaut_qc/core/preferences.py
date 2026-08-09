"""Scriptronaut QC Checks internal module."""

import inspect
from typing import Any
from ..utils import json_io
from ..utils.naming import sanitize_category_name


def load_all_check_preferences():
    return json_io.load_all_check_preferences()


def save_all_check_preferences(data):
    return json_io.save_all_check_preferences(data)


def get_check_preference_id(category_name, module_name):
    """
    """
    category_name = (
        str(category_name)
        .strip()
        .lower()
        .replace(" ", "_")
    )

    module_name = (
        str(module_name)
        .strip()
        .lower()
    )

    if module_name.endswith(".py"):
        module_name = module_name[:-3]

    return "{}.{}".format(
        category_name,
        module_name,
    )


def get_check_preferences(
        check_id,
        module,
    ):
    """
    Returns settings for one check with user values
    merged over module defaults.
    """
    schema = getattr(
        module,
        "SETTINGS",
        {},
    )

    if not isinstance(schema, dict):
        return {}

    resolved = {}

    for setting_name, definition in schema.items():
        if not isinstance(
            definition,
            dict,
        ):
            continue

        resolved[setting_name] = (
            definition.get("default")
        )

    all_preferences = (
        load_all_check_preferences()
    )

    user_preferences = (
        all_preferences.get(
            check_id,
            {},
        )
    )

    if isinstance(
        user_preferences,
        dict,
    ):
        for setting_name, value in user_preferences.items():
            if setting_name in resolved:
                resolved[setting_name] = value

    return resolved


def get_check_id_for_item(item):
    """
    Returns the stable preference identifier stored on a check item.
    """
    if getattr(item, "check_id", ""):
        return item.check_id

    return get_check_preference_id(
        getattr(item, "source_category", ""),
        getattr(item, "name", ""),
    )


def module_has_settings(module):
    """
    Returns True when a check module declares a non-empty SETTINGS map.
    """
    schema = getattr(module, "SETTINGS", {})
    return isinstance(schema, dict) and bool(schema)
