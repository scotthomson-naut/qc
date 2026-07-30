"""Scriptronaut QC Checks internal module."""

import os
import traceback

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty
from bpy.types import Operator

from .. import constants
from ..core.context import QCContext
from ..core import *
from ..properties import SCRIPTRONAUT_PG_CheckSetting
from ..utils import *

class SCRIPTRONAUT_OT_QC_FixAll(Operator):
    """
    Runs fix() for every failed QC check that provides an automatic fix.
    """

    bl_idname = "scriptronaut.qc_fix_all"
    bl_label = "Fix All"
    bl_description = "Fix all failed QC checks that have an automatic fix"

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        fixed_any = False
        skipped_manual = []
        failed_fixes = []

        for item in checks:
            # Only fix failed checks.
            if item.status != "FAIL":
                continue

            # Skip checks without an automatic fix.
            if not item.has_fix:
                skipped_manual.append(
                    item.name
                )
                continue

            if not os.path.isfile(
                item.script_path
            ):
                failed_fixes.append(
                    "{}: script not found".format(
                        item.name
                    )
                )
                continue

            try:
                module = load_module_from_path(
                    "qc_fix_all_{}".format(
                        item.name
                    ),
                    item.script_path,
                )

                fix_function = getattr(
                    module,
                    "fix",
                    None,
                )

                if not callable(
                    fix_function
                ):
                    item.has_fix = False

                    skipped_manual.append(
                        item.name
                    )

                    continue

                result_data = (
                    result_data_from_json(
                        item.result_data
                    )
                )

                call_check_fix(
                    module,
                    get_check_id_for_item(item),
                    result_data=result_data,
                )

                fixed_any = True

                # Re-run this check after fixing so its
                # status/result data are accurate.
                rerun_qc_check_item(
                    item
                )

            except Exception:
                failed_fixes.append(
                    "{}:\n{}".format(
                        item.name,
                        traceback.format_exc(),
                    )
                )

        if fixed_any and settings.last_run_time:
            settings.scene_modified_since_qc = True

        # Refresh both QC views after all fixes.
        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        if failed_fixes:
            for error in failed_fixes:
                print(
                    "QC Fix All error:\n{}".format(
                        error
                    )
                )

            self.report(
                {"WARNING"},
                "Some automatic fixes failed. See system console.",
            )

        elif fixed_any:
            if skipped_manual:

                self.report(
                    {"INFO"},
                    "Automatic fixes completed. {} check(s) require manual fixing.".format(
                        len(skipped_manual)
                    ),
                )

            else:
                self.report(
                    {"INFO"},
                    "All available fixes completed.",
                )

        else:
            self.report(
                {"INFO"},
                "No automatic fixes are currently available.",
            )

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_FixCheckInline(Operator):
    """
    Fixes one specific QC check directly from its UIList row.
    """

    bl_idname = "scriptronaut.qc_fix_check_inline"
    bl_label = "Fix QC Check"
    bl_description = "Fix this QC check"

    check_index: IntProperty(
        name="Check Index",
        default=-1,
    )

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            return {"CANCELLED"}

        item = checks[
            self.check_index
        ]

        if (
            item.status != "FAIL"
            or not item.has_fix
        ):
            self.report(
                {"WARNING"},
                "This check has no available automatic fix.",
            )
            return {"CANCELLED"}

        try:
            module = load_module_from_path(
                "qc_inline_fix_{}_{}".format(
                    item.name,
                    self.check_index,
                ),
                item.script_path,
            )

            fix_function = getattr(
                module,
                "fix",
                None,
            )

            if not callable(fix_function):
                item.has_fix = False
                self.report(
                    {"ERROR"},
                    "Missing fix() function.",
                )

                return {"CANCELLED"}

            result_data = result_data_from_json(
                item.result_data
            )

            call_check_fix(
                module,
                get_check_id_for_item(item),
                result_data=result_data,
            )

            # Re-run this specific QC check after the fix.
            rerun_qc_check_item(
                item
            )

            # Make this the currently selected check so the
            # Issues panel immediately displays its new result.
            settings.check_index = (
                self.check_index
            )

            refresh_issues_display(
                context
            )

            rebuild_failed_objects(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = True

        except Exception:
            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                'Could not fix "{}".'.format(
                    item.name
                ),
            )

            return {"CANCELLED"}

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_FixObjectInline(Operator):
    """
    Fixes one specific failed check for the currently selected
    failed object.
    """

    bl_idname = "scriptronaut.qc_fix_object_inline"
    bl_label = "Fix Check On Object"
    bl_description = "Fix this check only on this object"

    object_check_index: IntProperty(
        name="Object Check Index",
        default=-1,
    )

    def execute(
        self,
        context,
    ):
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

        # ---------------------------------------------------------
        # Validate selected object
        # ---------------------------------------------------------

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # ---------------------------------------------------------
        # Validate inline check
        # ---------------------------------------------------------

        if (
            self.object_check_index < 0
            or self.object_check_index
            >= len(object_checks)
        ):
            return {"CANCELLED"}

        object_check = object_checks[
            self.object_check_index
        ]

        if not object_check.has_fix:
            self.report(
                {"WARNING"},
                "This check must be fixed manually.",
            )

            return {"CANCELLED"}

        check_index = (
            object_check.check_index
        )

        if (
            check_index < 0
            or check_index >= len(checks)
        ):
            return {"CANCELLED"}

        check_item = checks[
            check_index
        ]

        try:
            module = load_module_from_path(
                "qc_object_inline_fix_{}_{}".format(
                    check_item.name,
                    self.object_check_index,
                ),
                check_item.script_path,
            )

            fix_function = getattr(
                module,
                "fix",
                None,
            )

            if not callable(
                fix_function
            ):
                check_item.has_fix = False
                self.report(
                    {"ERROR"},
                    "Missing fix() function.",
                )

                return {"CANCELLED"}

            # -----------------------------------------------------
            # Filter original result to ONLY this object
            # -----------------------------------------------------

            result_data = (
                result_data_from_json(
                    check_item.result_data
                )
            )

            filtered_result = (
                get_filtered_result_for_object(
                    result_data,
                    object_name,
                )
            )

            # Object-specific fixes must accept result data so only
            # the selected object can be changed safely.
            try:
                call_check_fix(
                    module,
                    get_check_id_for_item(check_item),
                    result_data=filtered_result,
                    require_result_data=True,
                )
            except TypeError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

            # -----------------------------------------------------
            # Re-run affected check
            # -----------------------------------------------------

            rerun_qc_check_item(
                check_item
            )

            # Rebuild Object mode after result changed.
            rebuild_failed_objects(
                context
            )

            refresh_issues_display(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = True

        except Exception:
            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                "Could not fix {} on {}.".format(
                    check_item.name,
                    object_name,
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            'Fixed "{}" on "{}".'.format(
                check_item.name,
                object_name,
            ),
        )

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_FixAllObjectChecks(Operator):
    """
    Fixes every automatically fixable failed check for the
    currently selected failed object.
    """

    bl_idname = (
        "scriptronaut.qc_fix_all_object_checks"
    )

    bl_label = (
        "Fix All Checks on This Object"
    )

    bl_description = (
        "Run all available automatic fixes for the "
        "currently selected failed object"
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(
            context,
            "scene",
            None,
        )

        if scene is None:
            return False

        settings = getattr(
            scene,
            "scriptronaut_qc_settings",
            None,
        )

        failed_objects = getattr(
            scene,
            "scriptronaut_qc_failed_objects",
            None,
        )

        object_checks = getattr(
            scene,
            "scriptronaut_qc_object_checks",
            None,
        )

        if (
            settings is None
            or failed_objects is None
            or object_checks is None
        ):
            return False

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            return False

        return any(
            item.has_fix
            for item in object_checks
        )

    def execute(self, context):
        
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

        # -----------------------------------------------------
        # Validate selected failed object
        # -----------------------------------------------------

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            self.report(
                {"WARNING"},
                "No failed object selected.",
            )

            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # -----------------------------------------------------
        # Snapshot check indices
        #
        # Do not iterate the collection while rebuilding it.
        # -----------------------------------------------------

        check_indices = [
            item.check_index
            for item in object_checks
            if (
                item.has_fix
                and item.check_index >= 0
                and item.check_index < len(checks)
            )
        ]

        if not check_indices:
            self.report(
                {"INFO"},
                "No automatic fixes are available for this object.",
            )

            return {"CANCELLED"}

        fixed_checks = []
        failed_fixes = []
        skipped_checks = []

        constants.QC_IS_RUNNING = True

        try:
            for check_index in check_indices:

                check_item = checks[
                    check_index
                ]

                if check_item.status != "FAIL":
                    continue

                if not check_item.has_fix:
                    skipped_checks.append(
                        check_item.display_name
                        or check_item.name
                    )
                    continue

                if not os.path.isfile(
                    check_item.script_path
                ):
                    failed_fixes.append(
                        "{}: script does not exist".format(
                            check_item.display_name
                            or check_item.name
                        )
                    )
                    continue

                try:
                    module = load_module_from_path(
                        "qc_fix_all_object_{}_{}".format(
                            check_item.name,
                            check_index,
                        ),
                        check_item.script_path,
                    )

                    fix_function = getattr(
                        module,
                        "fix",
                        None,
                    )

                    if not callable(
                        fix_function
                    ):
                        check_item.has_fix = False

                        skipped_checks.append(
                            check_item.display_name
                            or check_item.name
                        )

                        continue

                    # -----------------------------------------
                    # Filter this check's result so only the
                    # selected object is passed to fix().
                    # -----------------------------------------

                    result_data = (
                        result_data_from_json(
                            check_item.result_data
                        )
                    )

                    filtered_result = (
                        get_filtered_result_for_object(
                            result_data,
                            object_name,
                        )
                    )

                    filtered_objects = (
                        filtered_result.get(
                            "failed_objects",
                            {},
                        )
                    )

                    if not filtered_objects:
                        continue

                    # Object-specific fixing must accept result data.
                    try:
                        call_check_fix(
                            module,
                            get_check_id_for_item(check_item),
                            result_data=filtered_result,
                            require_result_data=True,
                        )
                    except TypeError as error:
                        failed_fixes.append(
                            "{}: {}".format(
                                check_item.display_name or check_item.name,
                                error,
                            )
                        )
                        continue

                    fixed_checks.append(
                        check_item.display_name
                        or check_item.name
                    )

                except Exception:
                    failed_fixes.append(
                        "{}:\n{}".format(
                            check_item.display_name
                            or check_item.name,
                            traceback.format_exc(),
                        )
                    )

            # -------------------------------------------------
            # Re-run affected checks after all fixes
            # -------------------------------------------------

            for check_index in check_indices:
                if (
                    check_index >= 0
                    and check_index < len(checks)
                ):
                    rerun_qc_check_item(
                        checks[check_index]
                    )

        finally:
            constants.QC_IS_RUNNING = False

        # -----------------------------------------------------
        # Refresh both UI modes once
        # -----------------------------------------------------

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        if fixed_checks and settings.last_run_time:
            settings.scene_modified_since_qc = True

        # -----------------------------------------------------
        # Report
        # -----------------------------------------------------

        if failed_fixes:
            for error in failed_fixes:
                print(
                    "QC object fix error:\n{}".format(
                        error
                    )
                )

            self.report(
                {"WARNING"},
                (
                    "Fixed {} check(s) on '{}'. "
                    "{} fix(es) failed."
                ).format(
                    len(fixed_checks),
                    object_name,
                    len(failed_fixes),
                ),
            )

        elif fixed_checks:
            self.report(
                {"INFO"},
                "Fixed {} check(s) on '{}'.".format(
                    len(fixed_checks),
                    object_name,
                ),
            )

        else:
            self.report(
                {"INFO"},
                "No checks were fixed on '{}'.".format(
                    object_name
                ),
            )

        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_FixAll,
    SCRIPTRONAUT_OT_QC_FixCheckInline,
    SCRIPTRONAUT_OT_QC_FixObjectInline,
    SCRIPTRONAUT_OT_QC_FixAllObjectChecks,
)
