"""Scriptronaut QC Checks internal module."""

import os
import traceback
from typing import Any

import bpy

from ..constants import COMMON_CATEGORY
from .discovery import discover_check_scripts, get_categories, get_scripts
from .preferences import get_check_preference_id, module_has_settings
from .execution import call_check_main
from .results import normalize_check_result, get_issues_from_result
from .availability import evaluate_check_availability
from ..utils.json_io import (
    load_check_list,
    result_data_from_json,
    result_data_to_json,
    result_summary_from_json,
)
from ..utils.module_loader import load_module_from_path


def refresh_issues_display(context):
    """
    Updates the Issues display based on the currently selected QC check.

    Args:
        context (bpy.types.Context): Blender context.
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    checks = scene.scriptronaut_qc_checks

    if settings.check_index < 0 or settings.check_index >= len(checks):
        settings.issues_display = ""
        return

    item = checks[settings.check_index]

    if item.issues:
        settings.issues_display = item.issues
    else:
        settings.issues_display = "No issues found."


def load_qc_category(context):
    """
    Loads all QC scripts for the currently selected category.

    Also reads optional module metadata:

        LABEL
        DESCRIPTION
        fix()

    Returns:
        tuple:
            (success, message)
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    checks = scene.scriptronaut_qc_checks

    old_index = settings.check_index

    checks.clear()
    settings.issues_display = ""

    folder_path = settings.folder_path
    category = settings.category

    scripts = get_scripts(
        folder_path,
        category,
        use_json=settings.use_check_settings,
    )

    for script_data in scripts:
        item = checks.add()

        # -----------------------------------------------------
        # Basic script data
        # -----------------------------------------------------

        item.name = script_data["name"]

        item.display_name = script_data["name"]

        item.script_path = (
            script_data["script_path"]
        )

        item.source_category = (
            script_data["source_category"]
        )

        item.pack_id = script_data.get(
            "pack_id",
            "legacy",
        )

        item.selected = True
        item.status = "NOT_RUN"
        item.has_fix = False
        item.description = ""
        item.issues = "Not run yet."
        item.result_data = "{}"
        item.check_id = get_check_preference_id(
            category,
            item.name,
        )
        item.has_settings = False

        item.is_available = True
        item.unavailable_reason = ""

        # -----------------------------------------------------
        # Load optional module metadata
        # -----------------------------------------------------

        try:
            module = load_module_from_path(
                "qc_info_{}".format(
                    item.name
                ),
                item.script_path,
            )

            # Optional friendly UI name.
            item.display_name = getattr(
                module,
                "LABEL",
                item.name,
            )

            # Optional tooltip.
            item.description = getattr(
                module,
                "DESCRIPTION",
                "",
            )

            # Severity.
            severity = getattr(
                module,
                "SEVERITY",
                "warning",
            ).lower()

            if severity not in {
                "critical",
                "warning",
                "info",
            }:
                severity = "warning"

            item.severity = severity

            # Determine whether automatic fix exists.
            item.has_fix = callable(
                getattr(
                    module,
                    "fix",
                    None,
                )
            )

            item.has_settings = module_has_settings(
                module
            )

            item.is_available, item.unavailable_reason = (
                evaluate_check_availability(
                    module
                )
            )

            if not item.is_available:
                item.selected = False

        except Exception:
            print(
                "Could not load QC metadata for '{}':".format(
                    item.name
                )
            )

            print(
                traceback.format_exc()
            )

            # Do NOT stop loading the remaining checks.
            item.display_name = item.name
            item.description = ""
            item.has_fix = False
            item.has_settings = False

    # ---------------------------------------------------------
    # Restore selected index
    # ---------------------------------------------------------

    if len(checks) > 0:
        settings.check_index = min(
            old_index,
            len(checks) - 1,
        )

    else:
        settings.check_index = 0

    refresh_issues_display(
        context
    )

    return True, ""


def qc_category_items(self, context):
    """
    Returns the EnumProperty items for the QC category dropdown.

    Args:
        context (bpy.types.Context): Blender context.

    Returns:
        list[tuple]: EnumProperty item list.
    """
    categories = get_categories(
        self.folder_path,
        use_json=self.use_check_settings,
    )

    if not categories:
        return [("NONE", "No Categories Found", "")]

    return [(category, category, "") for category in categories]


def qc_editor_category_items(self, context):
    """
    Returns categories stored in CHECK_SETTINGS_FILE for the editor.
    """
    if context is None or context.scene is None:
        return [("NONE", "No Categories", "")]

    settings = context.scene.scriptronaut_qc_settings
    check_list = load_check_list(settings.folder_path)
    categories = sorted(
        category
        for category, script_names in check_list.items()
        if isinstance(category, str) and isinstance(script_names, list)
    )

    if not categories:
        return [("NONE", "No Categories", "")]

    return [
        (category, category.replace("_", " ").title(), "")
        for category in categories
    ]


def populate_qc_editor(context, category=None):
    """
    Populates the editor with all discovered scripts.
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    editor_items = scene.scriptronaut_qc_editor_items
    editor_items.clear()

    registry, duplicate_names = discover_check_scripts(
        settings.folder_path,
        registered=False,
    )
    if duplicate_names:
        lines = []
        for script_name, paths in duplicate_names.items():
            lines.append("{}: {}".format(script_name, ", ".join(paths)))
        return False, "Duplicate script names found:\n{}".format("\n".join(lines))

    check_list = load_check_list(settings.folder_path)
    if category is None:
        category = settings.editor_category

    assigned_names = set(
        check_list.get(category, [])
        if category and category != "NONE"
        else []
    )

    for script_name in sorted(registry):
        script_data = registry[script_name]
        item = editor_items.add()
        item.name = script_name
        item.script_path = script_data["script_path"]
        item.source_category = script_data["source_category"]
        item.pack_id = script_data.get("pack_id", "legacy")
        item.selected = script_name in assigned_names

    settings.editor_index = 0
    return True, ""


def rebuild_failed_objects(context):
    """
    Builds a unique list of objects that failed any QC check.

    Each object stores how many checks it failed.
    """
    scene = context.scene
    checks = scene.scriptronaut_qc_checks
    failed_items = scene.scriptronaut_qc_failed_objects
    settings = scene.scriptronaut_qc_settings

    previous_name = None

    if (
        failed_items
        and 0 <= settings.failed_object_index < len(failed_items)
    ):
        previous_name = (
            failed_items[
                settings.failed_object_index
            ].name
        )

    failed_items.clear()

    object_failures = {}

    for check_index, check_item in enumerate(checks):
        if check_item.status != "FAIL":
            continue

        result_summary = result_summary_from_json(
            check_item.result_summary
        )

        failed_objects = result_summary.get(
            "failed_objects",
            {},
        )

        if not isinstance(
            failed_objects,
            dict,
        ):
            continue

        for object_name in failed_objects:
            object_failures.setdefault(
                object_name,
                [],
            ).append(
                check_index
            )

    for object_name in sorted(
        object_failures
    ):
        item = failed_items.add()
        item.name = object_name
        item.failed_check_count = len(
            object_failures[
                object_name
            ]
        )

    # Restore selection when possible.
    settings.failed_object_index = 0

    if previous_name:
        for index, item in enumerate(
            failed_items
        ):
            if item.name == previous_name:
                settings.failed_object_index = (
                    index
                )
                break

    refresh_object_failed_checks(
        context
    )


def refresh_object_failed_checks(context):
    """
    Populates the failed-check list for the currently
    selected object in Object Mode.
    """
    if (
        context is None
        or context.scene is None
    ):
        return

    scene = context.scene

    settings = (
        scene.scriptronaut_qc_settings
    )

    failed_objects = (
        scene.scriptronaut_qc_failed_objects
    )

    object_checks = (
        scene.scriptronaut_qc_object_checks
    )

    checks = (
        scene.scriptronaut_qc_checks
    )

    object_checks.clear()

    if (
        settings.failed_object_index < 0
        or
        settings.failed_object_index
        >= len(failed_objects)
    ):
        return

    object_name = failed_objects[
        settings.failed_object_index
    ].name

    for check_index, check_item in enumerate(
        checks
    ):
        if check_item.status != "FAIL":
            continue

        result_summary = result_summary_from_json(
            check_item.result_summary
        )

        check_failed_objects = (
            result_summary.get(
                "failed_objects",
                {},
            )
        )

        if not isinstance(
            check_failed_objects,
            dict,
        ):
            continue

        if object_name not in check_failed_objects:
            continue

        item = object_checks.add()
        item.name = check_item.name
        item.script_path = check_item.script_path
        item.has_fix = check_item.has_fix
        item.has_settings = check_item.has_settings
        item.check_id = check_item.check_id
        item.check_index = check_index
        item.display_name = (
            check_item.display_name
            if check_item.display_name
            else check_item.name
        )
        item.severity = check_item.severity
        item.description = check_item.description

    settings.object_check_index = 0
