"""Scriptronaut QC Checks internal module."""

import os
import traceback

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator

from .. import constants
from ..core.context import QCContext
from ..core import *
from ..properties import SCRIPTRONAUT_PG_CheckSetting
from ..utils import *


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def force_qc_redraw(
        context,
    ):
    """
    Forces Blender to redraw the UI so progress changes are visible
    during synchronous fix operations.

    Blender can redraw between fixes, but not while an individual fix
    is blocking the main thread.
    """
    if context.screen is not None:
        for area in context.screen.areas:
            area.tag_redraw()

    try:
        bpy.ops.wm.redraw_timer(
            type="DRAW_WIN_SWAP",
            iterations=1,
        )
    except RuntimeError:
        pass


def get_post_fix_status(
        context,
        item,
    ):
    """
    Inspects a QC check after it has been rerun following an
    automatic fix.

    This does not assume that an object being outside the current
    View Layer is the reason the check still fails. It only reports
    that the object cannot currently be accessed/selected there.

    Returns:
        dict:
        {
            "remaining_count": int,
            "remaining_objects": list[str],
            "unavailable_objects": list[str],
            "message": str,
            "guidance": str,
        }
    """
    result_data = (
        result_data_from_json(
            item.result_data
        )
    )

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        failed_objects = {}

    remaining_objects = list(
        failed_objects.keys()
    )

    unavailable_objects = []

    for object_name in remaining_objects:

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            continue

        if (
            context.view_layer.objects.get(
                object_name
            )
            is None
        ):
            unavailable_objects.append(
                object_name
            )

    remaining_count = len(
        remaining_objects
    )

    message = ""
    guidance = ""

    if remaining_count:

        message = (
            "Automatic fix completed, but {} object{} "
            "still fail this check."
        ).format(
            remaining_count,
            ""
            if remaining_count == 1
            else "s",
        )

        if unavailable_objects:

            unavailable_names = ", ".join(
                unavailable_objects
            )

            guidance = (
                "{} object{} cannot currently be accessed "
                "from View Layer '{}': {}. "
                "Switch to a View Layer containing the object{}, "
                "or enable the collection containing {}. "
                "Then rerun the check."
            ).format(
                len(unavailable_objects),
                ""
                if len(unavailable_objects) == 1
                else "s",
                context.view_layer.name,
                unavailable_names,
                ""
                if len(unavailable_objects) == 1
                else "s",
                "it"
                if len(unavailable_objects) == 1
                else "them",
            )

    return {
        "remaining_count":
            remaining_count,

        "remaining_objects":
            remaining_objects,

        "unavailable_objects":
            unavailable_objects,

        "message":
            message,

        "guidance":
            guidance,
    }


def report_post_fix_status(
        operator,
        context,
        item,
    ):
    """
    Reports unresolved failures after an automatic fix and rerun.

    Returns:
        bool:
            True if failures remain.
    """
    status = get_post_fix_status(
        context,
        item,
    )

    if not status[
        "remaining_count"
    ]:
        return False

    messages = []

    if status["message"]:
        messages.append(
            status["message"]
        )

    if status["guidance"]:
        messages.append(
            status["guidance"]
        )

    message = "\n".join(
        messages
    )

    if message:
        item.issues = message

        operator.report(
            {"WARNING"},
            " ".join(messages),
        )

    return True


# -------------------------------------------------------------------------
# Fix All
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_FixAll(
    Operator
):
    """
    Runs fix() for every failed QC check that provides an automatic fix.
    """

    bl_idname = (
        "scriptronaut.qc_fix_all"
    )

    bl_label = (
        "Fix All"
    )

    bl_description = (
        "Fix all failed QC checks that have an automatic fix"
    )

    def execute(
        self,
        context,
    ):
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        checks = (
            scene.scriptronaut_qc_checks
        )

        # ---------------------------------------------------------
        # Collect fixable and manual checks
        # ---------------------------------------------------------

        fixable_items = [
            item
            for item in checks
            if (
                item.status == "FAIL"
                and item.has_fix
                and item.can_auto_fix
            )
        ]

        skipped_manual = [
            item.display_name or item.name
            for item in checks
            if (
                item.status == "FAIL"
                and (
                    not item.has_fix
                    or not item.can_auto_fix
                )
            )
        ]

        total_fix_count = len(
            fixable_items
        )

        if total_fix_count == 0:
            self.report(
                {"INFO"},
                "No automatic fixes are currently available.",
            )
            return {"FINISHED"}

        fixed_any = False
        failed_fixes = []
        unresolved_checks = []

        # ---------------------------------------------------------
        # Start progress
        # ---------------------------------------------------------

        constants.QC_IS_RUNNING = True
        settings.is_running = True
        settings.run_progress = 0.0

        force_qc_redraw(
            context
        )

        try:
            for fix_index, item in enumerate(
                fixable_items,
                start=1,
            ):
                try:
                    if not os.path.isfile(
                        item.script_path
                    ):
                        failed_fixes.append(
                            "{}: script not found".format(
                                item.display_name
                                or item.name
                            )
                        )
                        continue

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
                        continue

                    result_data = (
                        result_data_from_json(
                            item.result_data
                        )
                    )

                    # Show which check is currently being fixed.
                    item.status = "FIXING"
                    item.issues = "Fixing..."

                    force_qc_redraw(
                        context
                    )

                    call_check_fix(
                        module,
                        get_check_id_for_item(
                            item
                        ),
                        result_data=result_data,
                    )

                    fixed_any = True

                    # ---------------------------------------------
                    # Re-run after fix so the row immediately
                    # reflects PASS/FAIL.
                    # ---------------------------------------------

                    rerun_success = (
                        rerun_qc_check_item(
                            item
                        )
                    )

                    if not rerun_success:
                        failed_fixes.append(
                            (
                                "{}: fix ran but the check "
                                "could not be rerun"
                            ).format(
                                item.display_name
                                or item.name
                            )
                        )
                        continue

                    post_status = (
                        get_post_fix_status(
                            context,
                            item,
                        )
                    )

                    if post_status[
                        "remaining_count"
                    ]:
                        unresolved_checks.append(
                            item.display_name
                            or item.name
                        )

                        report_post_fix_status(
                            self,
                            context,
                            item,
                        )

                except Exception:
                    failed_fixes.append(
                        "{}:\n{}".format(
                            item.display_name
                            or item.name,
                            traceback.format_exc(),
                        )
                    )

                finally:
                    # ---------------------------------------------
                    # Advance progress after each complete
                    # fix + rerun cycle.
                    # ---------------------------------------------

                    settings.run_progress = (
                        fix_index
                        / total_fix_count
                    )

                    force_qc_redraw(
                        context
                    )

        finally:
            constants.QC_IS_RUNNING = False
            settings.is_running = False

            if total_fix_count:
                settings.run_progress = 1.0

            force_qc_redraw(
                context
            )

        # ---------------------------------------------------------
        # Scene state
        # ---------------------------------------------------------

        if (
            fixed_any
            and settings.last_run_time
        ):
            settings.scene_modified_since_qc = (
                True
            )

        # ---------------------------------------------------------
        # Refresh
        # ---------------------------------------------------------

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        # ---------------------------------------------------------
        # Report
        # ---------------------------------------------------------

        if failed_fixes:
            for error in failed_fixes:
                print(
                    "QC Fix All error:\n{}".format(
                        error
                    )
                )

            self.report(
                {"WARNING"},
                (
                    "Some automatic fixes failed. "
                    "See system console."
                ),
            )

        elif unresolved_checks:
            self.report(
                {"WARNING"},
                (
                    "Automatic fixes completed, but {} check{} "
                    "still contain unresolved failures."
                ).format(
                    len(unresolved_checks),
                    ""
                    if len(unresolved_checks) == 1
                    else "s",
                ),
            )

        elif fixed_any:
            if skipped_manual:
                self.report(
                    {"INFO"},
                    (
                        "Automatic fixes completed. "
                        "{} check(s) require manual fixing."
                    ).format(
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


# -------------------------------------------------------------------------
# Fix Check Inline
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_FixCheckInline(
    Operator
):
    """
    Fixes one specific QC check directly from its UIList row.
    """

    bl_idname = (
        "scriptronaut.qc_fix_check_inline"
    )

    bl_label = (
        "Fix QC Check"
    )

    bl_description = (
        "Fix this QC check"
    )

    check_index: IntProperty(
        name="Check Index",
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

        checks = (
            scene.scriptronaut_qc_checks
        )

        if (
            self.check_index < 0
            or
            self.check_index
            >= len(checks)
        ):
            return {"CANCELLED"}

        item = checks[
            self.check_index
        ]

        if (
            item.status != "FAIL"
            or not item.has_fix
            or not item.can_auto_fix
        ):
            self.report(
                {"WARNING"},
                (
                    "This check has no available "
                    "automatic fix."
                ),
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

            if not callable(
                fix_function
            ):
                item.has_fix = False

                self.report(
                    {"ERROR"},
                    "Missing fix() function.",
                )

                return {"CANCELLED"}

            result_data = (
                result_data_from_json(
                    item.result_data
                )
            )

            # -----------------------------------------------------
            # Execute fix
            # -----------------------------------------------------

            item.status = "FIXING"
            item.issues = "Fixing..."

            force_qc_redraw(
                context
            )

            call_check_fix(
                module,
                get_check_id_for_item(
                    item
                ),
                result_data=result_data,
            )

            # -----------------------------------------------------
            # Re-run after fix
            # -----------------------------------------------------

            rerun_success = (
                rerun_qc_check_item(
                    item
                )
            )

            if not rerun_success:

                self.report(
                    {"WARNING"},
                    (
                        "The automatic fix ran, but the "
                        "QC check could not be rerun."
                    ),
                )

            else:

                unresolved = (
                    report_post_fix_status(
                        self,
                        context,
                        item,
                    )
                )

                if not unresolved:
                    self.report(
                        {"INFO"},
                        (
                            'Fixed "{}".'
                        ).format(
                            item.display_name
                            or item.name
                        ),
                    )

            # -----------------------------------------------------
            # Current selection
            # -----------------------------------------------------

            settings.check_index = (
                self.check_index
            )

            # -----------------------------------------------------
            # Refresh
            # -----------------------------------------------------

            refresh_issues_display(
                context
            )

            rebuild_failed_objects(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = (
                    True
                )

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


# -------------------------------------------------------------------------
# Fix Object Inline
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_FixObjectInline(
    Operator
):
    """
    Fixes one specific failed check for the currently selected
    failed object.
    """

    bl_idname = (
        "scriptronaut.qc_fix_object_inline"
    )

    bl_label = (
        "Fix Check On Object"
    )

    bl_description = (
        "Fix this check only on this object"
    )

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
            or
            settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # ---------------------------------------------------------
        # Validate check
        # ---------------------------------------------------------

        if (
            self.object_check_index < 0
            or
            self.object_check_index
            >= len(object_checks)
        ):
            return {"CANCELLED"}

        object_check = object_checks[
            self.object_check_index
        ]

        if (
            not object_check.has_fix
            or not object_check.can_auto_fix
        ):
            self.report(
                {"WARNING"},
                (
                    "This check must be fixed "
                    "manually."
                ),
            )

            return {"CANCELLED"}

        check_index = (
            object_check.check_index
        )

        if (
            check_index < 0
            or
            check_index >= len(checks)
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
            # Filter original result to this object
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

            # -----------------------------------------------------
            # Execute object-specific fix
            # -----------------------------------------------------

            try:

                check_item.status = "FIXING"
                check_item.issues = "Fixing..."

                force_qc_redraw(
                    context
                )

                call_check_fix(
                    module,
                    get_check_id_for_item(
                        check_item
                    ),
                    result_data=filtered_result,
                    require_result_data=True,
                )

            except TypeError as error:

                self.report(
                    {"ERROR"},
                    str(error),
                )

                return {"CANCELLED"}

            # -----------------------------------------------------
            # Re-run affected check
            # -----------------------------------------------------

            rerun_success = (
                rerun_qc_check_item(
                    check_item
                )
            )

            unresolved = False

            if not rerun_success:

                self.report(
                    {"WARNING"},
                    (
                        "The fix ran, but the affected "
                        "QC check could not be rerun."
                    ),
                )

            else:

                unresolved = (
                    report_post_fix_status(
                        self,
                        context,
                        check_item,
                    )
                )

            # -----------------------------------------------------
            # Refresh
            # -----------------------------------------------------

            rebuild_failed_objects(
                context
            )

            refresh_issues_display(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = (
                    True
                )

        except Exception:

            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                (
                    "Could not fix {} on {}."
                ).format(
                    check_item.name,
                    object_name,
                ),
            )

            return {"CANCELLED"}

        if not unresolved:

            self.report(
                {"INFO"},
                'Fixed "{}" on "{}".'.format(
                    check_item.display_name
                    or check_item.name,
                    object_name,
                ),
            )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Fix All Checks On Object
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_FixAllObjectChecks(
    Operator
):
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
    def poll(
        cls,
        context,
    ):
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
            (
                item.has_fix
                and item.can_auto_fix
            )
            for item in object_checks
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
        # Snapshot fixable check indices
        # -----------------------------------------------------

        check_indices = [
            item.check_index
            for item in object_checks
            if (
                item.has_fix
                and item.can_auto_fix
                and item.check_index >= 0
                and item.check_index < len(checks)
            )
        ]

        if not check_indices:
            self.report(
                {"INFO"},
                (
                    "No automatic fixes are available "
                    "for this object."
                ),
            )
            return {"CANCELLED"}

        fixed_checks = []
        failed_fixes = []
        unresolved_checks = []

        # Two phases are included in progress:
        #   1. applying each fix
        #   2. rerunning each affected check
        total_steps = len(
            check_indices
        ) * 2
        completed_steps = 0

        constants.QC_IS_RUNNING = True
        settings.is_running = True
        settings.run_progress = 0.0

        force_qc_redraw(
            context
        )

        try:
            # -------------------------------------------------
            # Execute fixes
            # -------------------------------------------------

            for check_index in check_indices:
                check_item = checks[
                    check_index
                ]

                try:
                    if check_item.status != "FAIL":
                        continue

                    if (
                        not check_item.has_fix
                        or not check_item.can_auto_fix
                    ):
                        continue

                    if not os.path.isfile(
                        check_item.script_path
                    ):
                        failed_fixes.append(
                            (
                                "{}: script does not exist"
                            ).format(
                                check_item.display_name
                                or check_item.name
                            )
                        )
                        continue

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
                        continue

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

                    try:

                        check_item.status = "FIXING"
                        check_item.issues = "Fixing..."

                        force_qc_redraw(
                            context
                        )

                        call_check_fix(
                            module,
                            get_check_id_for_item(
                                check_item
                            ),
                            result_data=filtered_result,
                            require_result_data=True,
                        )
                    except TypeError as error:
                        failed_fixes.append(
                            "{}: {}".format(
                                check_item.display_name
                                or check_item.name,
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

                finally:
                    completed_steps += 1
                    settings.run_progress = (
                        completed_steps
                        / total_steps
                    )

                    force_qc_redraw(
                        context
                    )

            # -------------------------------------------------
            # Re-run affected checks
            # -------------------------------------------------

            for check_index in check_indices:
                check_item = checks[
                    check_index
                ]

                try:
                    rerun_success = (
                        rerun_qc_check_item(
                            check_item
                        )
                    )

                    if not rerun_success:
                        failed_fixes.append(
                            (
                                "{}: fix ran but the check "
                                "could not be rerun"
                            ).format(
                                check_item.display_name
                                or check_item.name
                            )
                        )
                        continue

                    post_status = (
                        get_post_fix_status(
                            context,
                            check_item,
                        )
                    )

                    if post_status[
                        "remaining_count"
                    ]:
                        unresolved_checks.append(
                            check_item.display_name
                            or check_item.name
                        )

                        report_post_fix_status(
                            self,
                            context,
                            check_item,
                        )

                finally:
                    completed_steps += 1
                    settings.run_progress = (
                        completed_steps
                        / total_steps
                    )

                    force_qc_redraw(
                        context
                    )

        finally:
            constants.QC_IS_RUNNING = False
            settings.is_running = False
            settings.run_progress = 1.0

            force_qc_redraw(
                context
            )

        # -----------------------------------------------------
        # Refresh
        # -----------------------------------------------------

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        if (
            fixed_checks
            and settings.last_run_time
        ):
            settings.scene_modified_since_qc = (
                True
            )

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

        elif unresolved_checks:
            self.report(
                {"WARNING"},
                (
                    "Automatic fixes ran on '{}', but {} "
                    "check{} still contain unresolved failures."
                ).format(
                    object_name,
                    len(unresolved_checks),
                    ""
                    if len(unresolved_checks) == 1
                    else "s",
                ),
            )

        elif fixed_checks:
            self.report(
                {"INFO"},
                (
                    "Fixed {} check(s) on '{}'."
                ).format(
                    len(fixed_checks),
                    object_name,
                ),
            )

        else:
            self.report(
                {"INFO"},
                (
                    "No checks were fixed on '{}'."
                ).format(
                    object_name
                ),
            )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------

CLASSES = (
    SCRIPTRONAUT_OT_QC_FixAll,
    SCRIPTRONAUT_OT_QC_FixCheckInline,
    SCRIPTRONAUT_OT_QC_FixObjectInline,
    SCRIPTRONAUT_OT_QC_FixAllObjectChecks,
)
