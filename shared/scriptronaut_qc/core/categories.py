"""Scriptronaut QC Checks internal module."""

import os
import traceback
from typing import Any
from types import SimpleNamespace

import bpy

from ..constants import COMMON_CATEGORY
from .discovery import get_categories, get_scripts
from .preferences import get_check_preference_id, module_has_settings
from .execution import call_check_main
from .results import normalize_check_result, get_issues_from_result
from .availability import evaluate_check_availability
from .features import is_feature_enabled
from ..utils.json_io import (
    result_data_from_json,
    result_data_to_json,
    result_summary_from_json,
)
from ..utils.module_loader import load_module_from_path
from ..utils.diagnostics import capture_current_traceback


# UI metadata cache. Category switching happens on Blender's main UI thread,
# so re-executing every check module here creates a visible pause. Cache only
# presentation/availability metadata; actual checks are still freshly loaded
# when they run or fix. The file signature automatically invalidates edited
# check scripts during development.
_QC_METADATA_CACHE = {}

# Incremental background pre-warm queue. Each timer tick loads only a small
# number of static check modules so Blender's UI remains responsive.
_QC_METADATA_PREWARM_QUEUE = []
_QC_METADATA_PREWARM_KEYS = set()
_QC_METADATA_PREWARM_BATCH_SIZE = 2


def clear_qc_metadata_cache():
    """Clears cached check metadata and any pending background pre-warm work."""
    _QC_METADATA_CACHE.clear()
    _QC_METADATA_PREWARM_QUEUE.clear()
    _QC_METADATA_PREWARM_KEYS.clear()


def _metadata_file_signature(script_path):
    """Returns a lightweight signature that changes when a check file changes."""
    stat = os.stat(script_path)
    return (
        os.path.abspath(script_path),
        stat.st_mtime_ns,
        stat.st_size,
    )


def _get_check_metadata(script_data):
    """Returns cached UI metadata for one QC script, loading it only when needed."""
    script_path = script_data["script_path"]
    signature = _metadata_file_signature(script_path)
    cached = _QC_METADATA_CACHE.get(script_path)

    if cached is not None and cached["signature"] == signature:
        return cached["metadata"]

    module = load_module_from_path(
        "qc_info_{}".format(script_data["name"]),
        script_path,
    )

    severity = getattr(module, "SEVERITY", "warning").lower()
    if severity not in {"critical", "warning", "info"}:
        severity = "warning"

    metadata = {
        "display_name": getattr(module, "LABEL", script_data["name"]),
        "description": getattr(module, "DESCRIPTION", ""),
        "severity": severity,
        "has_fix": callable(getattr(module, "fix", None)),
        "has_settings": module_has_settings(module),
        "max_scene_triangles": getattr(module, "MAX_SCENE_TRIANGLES", None),
    }
    _QC_METADATA_CACHE[script_path] = {
        "signature": signature,
        "metadata": metadata,
    }
    return metadata



def queue_qc_metadata_prewarm(context):
    """Queues uncached check metadata for all categories without blocking the UI."""
    if context is None or context.scene is None:
        return

    scene = context.scene
    if not hasattr(scene, "scriptronaut_qc_settings"):
        return

    settings = scene.scriptronaut_qc_settings
    use_json = is_feature_enabled("check_settings", context)

    categories = get_categories(
        settings.folder_path,
        use_json=use_json,
    )

    # Current category has already been populated synchronously. Queue the
    # remaining categories first, while de-duplicating common checks.
    ordered_categories = [
        category for category in categories
        if category != settings.category
    ]

    for category in ordered_categories:
        for script_data in get_scripts(
            settings.folder_path,
            category,
            use_json=use_json,
        ):
            script_path = script_data["script_path"]

            try:
                signature = _metadata_file_signature(script_path)
            except OSError:
                continue

            cached = _QC_METADATA_CACHE.get(script_path)
            if cached is not None and cached["signature"] == signature:
                continue

            queue_key = signature
            if queue_key in _QC_METADATA_PREWARM_KEYS:
                continue

            _QC_METADATA_PREWARM_KEYS.add(queue_key)
            _QC_METADATA_PREWARM_QUEUE.append(
                (queue_key, dict(script_data))
            )


def prewarm_qc_metadata_timer():
    """Loads a small batch of queued check metadata, then yields back to Blender."""
    processed = 0

    while (
        _QC_METADATA_PREWARM_QUEUE
        and processed < _QC_METADATA_PREWARM_BATCH_SIZE
    ):
        queue_key, script_data = _QC_METADATA_PREWARM_QUEUE.pop(0)
        _QC_METADATA_PREWARM_KEYS.discard(queue_key)

        try:
            _get_check_metadata(script_data)
        except Exception:
            print(
                "Could not pre-warm QC metadata for '{}':".format(
                    script_data.get("name", "unknown")
                )
            )
            print(capture_current_traceback())

        processed += 1

    if _QC_METADATA_PREWARM_QUEUE:
        # Short idle gap keeps category preloading responsive rather than
        # importing every module in one long main-thread operation.
        return 0.05

    return None


def schedule_qc_metadata_prewarm(context):
    """Builds the pre-warm queue and starts its Blender timer when needed."""
    queue_qc_metadata_prewarm(context)

    if (
        _QC_METADATA_PREWARM_QUEUE
        and not bpy.app.timers.is_registered(prewarm_qc_metadata_timer)
    ):
        bpy.app.timers.register(
            prewarm_qc_metadata_timer,
            first_interval=0.15,
        )

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
        use_json=is_feature_enabled("check_settings", context),
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
        # Load optional module metadata (cached)
        # -----------------------------------------------------

        try:
            metadata = _get_check_metadata(script_data)
            item.display_name = metadata["display_name"]
            item.description = metadata["description"]
            item.severity = metadata["severity"]
            item.has_fix = metadata["has_fix"]
            item.has_settings = metadata["has_settings"]

            # Availability can depend on the current scene, so keep this
            # live even though the module's static metadata is cached.
            availability_source = SimpleNamespace(
                MAX_SCENE_TRIANGLES=metadata["max_scene_triangles"]
            )
            item.is_available, item.unavailable_reason = (
                evaluate_check_availability(availability_source)
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
                capture_current_traceback()
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
        use_json=is_feature_enabled("check_settings", context),
    )

    if not categories:
        return [("NONE", "No Categories Found", "")]

    return [(category, category, "") for category in categories]


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

        object_failure_data = (
            check_failed_objects.get(
                object_name,
                {}
            )
        )

        # Start with the check-level capability for backward compatibility.
        # A check may then override it for this specific failed object by
        # returning:
        #
        #     failed_objects[object_name]["can_auto_fix"] = True / False
        #
        # This is important for partially-fixable checks such as Connected
        # Geometry, where loose verts/edges are fixable but face islands are
        # manual-review only.
        object_can_auto_fix = (
            check_item.has_fix
            and check_item.can_auto_fix
        )

        if isinstance(
            object_failure_data,
            dict,
        ):
            explicit_can_auto_fix = (
                object_failure_data.get(
                    "can_auto_fix",
                    None,
                )
            )

            if isinstance(
                explicit_can_auto_fix,
                bool,
            ):
                object_can_auto_fix = (
                    check_item.has_fix
                    and explicit_can_auto_fix
                )

        item = object_checks.add()
        item.name = check_item.name
        item.script_path = check_item.script_path
        item.has_fix = check_item.has_fix
        item.can_auto_fix = object_can_auto_fix
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
