"""Scriptronaut QC Checks internal module."""

from typing import Any

from .categories import load_qc_category, refresh_issues_display
from .discovery import get_categories
from .features import is_feature_enabled


def update_qc_folder_path(self, context):
    """
    Callback executed when the QC folder path changes.

    Reloads available categories and refreshes the QC check list.

    Args:
        context (bpy.types.Context): Blender context.
    """
    categories = get_categories(
        self.folder_path,
        use_json=is_feature_enabled("check_settings", context),
    )

    if categories:
        self.category = categories[0]
        load_qc_category(context)
    else:
        context.scene.scriptronaut_qc_checks.clear()
        self.category = "NONE"
        self.issues_display = ""


def update_qc_category(self, context):
    """
    Callback executed when the selected QC category changes.
    Loads the QC scripts contained in the selected category.

    Args:
        context (bpy.types.Context): Blender context.
    """
    if self.category != "NONE":
        load_qc_category(context)


def update_qc_check_index(self, context):
    """
    Callback executed when the selected QC check changes.
    Refreshes the displayed issues.

    Args:
        context (bpy.types.Context): Blender context.
    """
    refresh_issues_display(context)
