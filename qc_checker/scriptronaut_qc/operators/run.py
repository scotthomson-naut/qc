"""Scriptronaut QC Checks internal module."""

import os
import time
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

from ..core.results import (
    result_can_auto_fix,
)

from ..utils.time_utils import (
    format_elapsed_time,
)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def force_qc_redraw(
        context,
    ):
    """
    Forces Blender to redraw the UI so QC status and progress changes
    become visible during a synchronous QC run.

    Note:
        Blender can redraw between checks, but not while an individual
        check is blocking the main thread.
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


# -------------------------------------------------------------------------
# Select All
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_SelectAll(Operator):
    """
    Selects all QC checks.
    """

    bl_idname = (
        "scriptronaut.qc_select_all"
    )

    bl_label = (
        "Select All Checks"
    )

    def execute(
        self,
        context,
    ):
        for item in (
            context.scene
            .scriptronaut_qc_checks
        ):
            item.selected = (
                item.is_available
            )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Select None
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_SelectNone(Operator):
    """
    Deselects all QC checks.
    """

    bl_idname = (
        "scriptronaut.qc_select_none"
    )

    bl_label = (
        "Select None"
    )

    def execute(
        self,
        context,
    ):
        for item in (
            context.scene
            .scriptronaut_qc_checks
        ):
            item.selected = False

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Select Critical
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_SelectCritical(Operator):
    """
    Select only Critical QC checks.
    """

    bl_idname = (
        "scriptronaut.qc_select_critical"
    )

    bl_label = (
        "Select Critical Checks"
    )

    bl_description = (
        "Select only Critical QC checks"
    )

    def execute(
        self,
        context,
    ):
        checks = (
            context.scene
            .scriptronaut_qc_checks
        )

        for item in checks:
            item.selected = (
                item.is_available
                and item.severity == "critical"
            )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Select Invert
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_SelectInvert(Operator):
    """
    Deselects all QC checks.
    """

    bl_idname = (
        "scriptronaut.qc_select_invert"
    )

    bl_label = (
        "Invert Selection"
    )

    bl_description = (
        "Inverts the Selected checks"
    )

    def execute(
        self,
        context,
    ):
        for item in (
            context.scene
            .scriptronaut_qc_checks
        ):
            item.selected = (
                not item.selected
            )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Run Selected
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_RunSelected(Operator):
    """
    Executes all selected QC scripts and stores the results.
    """

    bl_idname = (
        "scriptronaut.qc_run_selected"
    )

    bl_label = (
        "Run Selected Checks"
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
        # Collect selected checks
        # ---------------------------------------------------------

        selected_items = [
            item
            for item in checks
            if (
                item.selected
                and item.is_available
            )
        ]

        total_check_count = len(
            selected_items
        )

        if total_check_count == 0:
            self.report(
                {"WARNING"},
                "No checks selected.",
            )

            return {"CANCELLED"}

        # ---------------------------------------------------------
        # Start run
        # ---------------------------------------------------------

        run_start_time = (
            time.perf_counter()
        )

        executed_check_count = 0
        constants.QC_IS_RUNNING = True

        settings.is_running = True
        settings.run_progress = 0.0

        force_qc_redraw(context)

        try:

            # -----------------------------------------------------
            # Run checks from top to bottom
            # -----------------------------------------------------

            for item in selected_items:

                # -------------------------------------------------
                # Mark current check as running
                # -------------------------------------------------

                item.status = "RUNNING"

                item.issues = (
                    "Running..."
                )

                item.result_data = "{}"
                item.result_summary = "{}"

                # Force the panel to redraw BEFORE the check begins.
                # This is where the RUNNING/star icon becomes visible.
                force_qc_redraw(
                    context
                )

                script_path = (
                    item.script_path
                )

                try:

                    # ---------------------------------------------
                    # Script missing
                    # ---------------------------------------------

                    if not os.path.isfile(
                        script_path
                    ):
                        result_data = {
                            "issues": [
                                (
                                    "Script does not exist:\n{}"
                                ).format(
                                    script_path
                                )
                            ],

                            "script_path":
                                script_path,
                        }

                        item.status = "FAIL"

                        item.issues = "\n".join(
                            result_data[
                                "issues"
                            ]
                        )

                        item.result_data = (
                            result_data_to_json(
                                result_data
                            )
                        )

                        item.result_summary = (
                            result_summary_to_json(
                                result_data
                            )
                        )

                        item.has_fix = False
                        item.can_auto_fix = False

                    else:

                        # -----------------------------------------
                        # Load module
                        # -----------------------------------------

                        module = (
                            load_module_from_path(
                                "qc_{}".format(
                                    item.name
                                ),
                                script_path,
                            )
                        )

                        # -----------------------------------------
                        # Check availability BEFORE execution
                        # -----------------------------------------

                        is_available, unavailable_reason = (
                            evaluate_check_availability(
                                module
                            )
                        )

                        item.is_available = (
                            is_available
                        )

                        item.unavailable_reason = (
                            unavailable_reason
                        )

                        if not is_available:
                            item.selected = False
                            item.status = "NOT_RUN"
                            item.issues = (
                                unavailable_reason
                            )

                            skipped_result = {
                                "issues": [
                                    unavailable_reason
                                ],
                                "script_path":
                                    script_path,
                                "skipped": True,
                            }

                            item.result_data = (
                                result_data_to_json(
                                    skipped_result
                                )
                            )

                            item.result_summary = (
                                result_summary_to_json(
                                    skipped_result
                                )
                            )

                            continue

                        # -----------------------------------------
                        # main()
                        # -----------------------------------------

                        main_function = getattr(
                            module,
                            "main",
                            None,
                        )

                        # -----------------------------------------
                        # Missing main()
                        # -----------------------------------------

                        if not callable(
                            main_function
                        ):
                            result_data = {
                                "issues": [
                                    "Missing main() function."
                                ],

                                "script_path":
                                    script_path,
                            }

                            item.status = "FAIL"

                            item.issues = "\n".join(
                                result_data[
                                    "issues"
                                ]
                            )

                            item.result_data = (
                                result_data_to_json(
                                    result_data
                                )
                            )

                            item.result_summary = (
                                result_summary_to_json(
                                    result_data
                                )
                            )

                            item.has_fix = False
                            item.can_auto_fix = False

                        else:

                            # -------------------------------------
                            # Execute QC check
                            # -------------------------------------

                            raw_result = (
                                call_check_main(
                                    module,
                                    get_check_id_for_item(
                                        item
                                    ),
                                )
                            )

                            result_data = (
                                normalize_check_result(
                                    raw_result
                                )
                            )

                            result_data[
                                "check_name"
                            ] = item.name

                            result_data[
                                "script_path"
                            ] = script_path

                            issues = (
                                get_issues_from_result(
                                    result_data
                                )
                            )

                            item.result_data = (
                                result_data_to_json(
                                    result_data
                                )
                            )

                            item.result_summary = (
                                result_summary_to_json(
                                    result_data
                                )
                            )

                            # -------------------------------------
                            # Fix availability
                            # -------------------------------------

                            item.has_fix = callable(
                                getattr(
                                    module,
                                    "fix",
                                    None,
                                )
                            )

                            item.can_auto_fix = (
                                item.has_fix
                                and result_can_auto_fix(
                                    result_data,
                                    default=True,
                                )
                            )

                            # -------------------------------------
                            # Settings availability
                            # -------------------------------------

                            item.has_settings = (
                                module_has_settings(
                                    module
                                )
                            )

                            # -------------------------------------
                            # Result
                            # -------------------------------------

                            if issues:

                                item.status = (
                                    "FAIL"
                                )

                                item.issues = (
                                    "\n".join(
                                        str(issue)
                                        for issue
                                        in issues
                                    )
                                )

                            else:

                                item.status = (
                                    "PASS"
                                )

                                item.issues = (
                                    "No issues found."
                                )

                # -------------------------------------------------
                # Check execution error
                # -------------------------------------------------

                except Exception:

                    result_data = {
                        "issues": [
                            traceback.format_exc()
                        ],

                        "check_name":
                            item.name,

                        "script_path":
                            script_path,
                    }

                    item.status = "FAIL"

                    item.issues = "\n".join(
                        result_data[
                            "issues"
                        ]
                    )

                    item.result_data = (
                        result_data_to_json(
                            result_data
                        )
                    )

                    item.result_summary = (
                        result_summary_to_json(
                            result_data
                        )
                    )

                    item.can_auto_fix = False

                # -------------------------------------------------
                # Check completed
                # -------------------------------------------------

                finally:

                    executed_check_count += 1
                    settings.run_progress = (
                        executed_check_count
                        / total_check_count
                    )

                    # Redraw again after PASS/FAIL and progress change.
                    force_qc_redraw(
                        context
                    )

        finally:

            constants.QC_IS_RUNNING = False
            settings.is_running = False

            # Leave at 100%. Since the panel only shows the progress
            # bar while is_running is True, it disappears afterward.
            if executed_check_count:
                settings.run_progress = (
                    executed_check_count
                    / total_check_count
                )

            force_qc_redraw(
                context
            )

        # ---------------------------------------------------------
        # Total execution time
        # ---------------------------------------------------------

        total_elapsed = (
            time.perf_counter()
            - run_start_time
        )

        print("")

        print(
            "QC Run Complete: {} check{} in {}".format(
                executed_check_count,
                ""
                if executed_check_count == 1
                else "s",
                format_elapsed_time(
                    total_elapsed
                ),
            )
        )

        print("")

        # ---------------------------------------------------------
        # Refresh QC results
        # ---------------------------------------------------------

        set_qc_run_timestamp(
            context
        )

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        return {"FINISHED"}


CLASSES = (
    SCRIPTRONAUT_OT_QC_SelectAll,
    SCRIPTRONAUT_OT_QC_SelectNone,
    SCRIPTRONAUT_OT_QC_SelectCritical,
    SCRIPTRONAUT_OT_QC_SelectInvert,
    SCRIPTRONAUT_OT_QC_RunSelected,
)
