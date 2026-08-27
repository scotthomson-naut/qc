"""Scriptronaut QC Checks internal module."""

from typing import Any


def sanitize_category_name(category_name):
    """
    Converts a user-entered category into a safe JSON key.
    """
    category_name = category_name.strip().lower()
    category_name = category_name.replace("-", "_")
    category_name = "_".join(category_name.split())
    return "".join(
        character
        for character in category_name
        if character.isalnum() or character == "_"
    )
