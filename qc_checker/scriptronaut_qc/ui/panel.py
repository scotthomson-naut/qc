"""Scriptronaut QC Checks internal module."""

import time

from bpy.types import Panel, UIList

from ..constants import COMMON_CATEGORY, TIER
from ..core import (
    get_qc_elapsed_text,
    get_severity_icon,
    notify_window_scene_changed,
)
from ..utils.json_io import result_summary_from_json
from .helpers import draw_wrapped_text
from ..icons import get_icon_id


QC_PANEL_PROFILE = True
QC_PANEL_PROFILE_THRESHOLD = 0.020


def _qc_profile_print(
        label,
        elapsed,
        extra="",
    ):
    """
    Prints only panel operations that exceed the profiling threshold.
    """
    if not QC_PANEL_PROFILE:
        return

    if elapsed < QC_PANEL_PROFILE_THRESHOLD:
        return

    suffix = (
        " | {}".format(extra)
        if extra
        else ""
    )

    print(
        "QC Panel {:<28} {:7.3f} sec{}".format(
            label,
            elapsed,
            suffix,
        )
    )


class SCRIPTRONAUT_PT_QC_Checks(Panel):
    """
    Main QC Checks panel displayed in the 3D Viewport sidebar.

    Provides two display modes:

        CHECKS
            View QC checks.
            Run selected checks.
            View all failed objects for the selected check.
            Fix all failed objects for the selected check.

        OBJECTS
            View objects that failed one or more checks.
            View all failed checks for the selected object.
            Fix only the selected check on the selected object.
    """

    bl_label = "QC Checker"
    bl_idname = "SCRIPTRONAUT_PT_QC_Checks"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scriptronaut"

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        checks = (
            scene.scriptronaut_qc_checks
        )

        # ---------------------------------------------------------
        # New Scene initialization
        # ---------------------------------------------------------
        #
        # QC check collections are stored per Scene. Blender creates a
        # brand-new Scene with an empty collection, but the Category enum
        # can already display its default value without firing the enum's
        # update callback.
        #
        # Scene-change/depsgraph notifications are not guaranteed for every
        # way Blender creates an empty Scene. The panel redraw, however, is
        # guaranteed because Blender is displaying the new Scene.
        #
        # Request a deferred initialization here. The timer performs the
        # actual collection mutation after draw() has finished, avoiding
        # RNA changes from inside the panel draw callback itself.
        if len(checks) == 0:
            notify_window_scene_changed()

        # ---------------------------------------------------------
        # Tier-level settings
        # ---------------------------------------------------------

        if TIER in [
            "Pro",
            "Studio",
        ]:
            settings_box = layout.box()
            settings_box.label(
                text="Settings",
                icon="PREFERENCES",
            )

            settings_row = settings_box.row(
                align=True
            )

            # ---------------------------------------------------------
            # Left side - checkbox
            # ---------------------------------------------------------

            use_settings_row = settings_row.row(
                align=True
            )

            use_settings_row.prop(
                settings,
                "use_check_settings",
                text="Use Check Settings",
            )

            # ---------------------------------------------------------
            # Right side - edit button
            # ---------------------------------------------------------

            editor_row = settings_row.row(
                align=True
            )

            editor_row.enabled = (
                settings.use_check_settings
            )

            editor_row.operator(
                "scriptronaut.qc_open_json_editor",
                text="Edit Check Settings",
                icon="GREASEPENCIL",
            )

        # ---------------------------------------------------------
        # Mode
        # ---------------------------------------------------------

        mode_box = layout.box()

        mode_box.label(
            text="Mode",
            icon="OPTIONS",
        )

        mode_row =  mode_box.row()
        mode_row.prop(
            settings,
            "mode",
            expand=True,
        )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        status_box = layout.box()
        status_box.label(
            text="Status",
            icon="INFO",
        )

        elapsed_text = get_qc_elapsed_text(settings)
        status_row = status_box.row()

        if not settings.last_run_time:
            status_row.label(
                text="Last Run: Not Run Yet",
                icon="QUESTION",
            )

        elif settings.scene_modified_since_qc:
            status_row.alert = True
            status_row.label(
                text="Last Run: {}".format(elapsed_text),
                icon="TIME",
            )
            status_row.label(
                text="Scene Modified Since Last Run",
                icon="ERROR",
            )

        else:
            status_row.label(
                text="Last Run: {}".format(elapsed_text),
                icon="TIME",
            )
            status_row.label(
                text="Scene Has Not Changed",
                icon="CHECKMARK",
            )

        # ---------------------------------------------------------
        # Failure Severity Summary
        # ---------------------------------------------------------

        critical_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "critical"
            )
        )

        warning_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "warning"
            )
        )

        info_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "info"
            )
        )

        severity_row = layout.row(
            align=True
        )

        critical_col = severity_row.column(
            align=True
        )

        warning_col = severity_row.column(
            align=True
        )

        info_col = severity_row.column(
            align=True
        )

        critical_col.label(
            text="Critical: {}".format(
                critical_count
            ),
            icon_value=get_icon_id(
                "severity_critical"
            ),
        )

        warning_col.label(
            text="Warning: {}".format(
                warning_count
            ),
            icon_value=get_icon_id(
                "severity_warning"
            ),
        )

        info_col.label(
            text="Info: {}".format(
                info_count
            ),
            icon_value=get_icon_id(
                "severity_info"
            ),
        )


        # ---------------------------------------------------------
        # CHECK MODE
        # ---------------------------------------------------------

        if settings.mode == "CHECKS":

            profile_start = time.perf_counter()

            self.draw_checks_mode(
                context,
                layout,
                settings,
                checks,
            )

            _qc_profile_print(
                "draw_checks_mode",
                time.perf_counter() - profile_start,
                "category={}".format(
                    settings.category
                ),
            )

        # ---------------------------------------------------------
        # OBJECT MODE
        # ---------------------------------------------------------

        elif settings.mode == "OBJECTS":

            profile_start = time.perf_counter()

            self.draw_objects_mode(
                context,
                layout,
                settings,
                checks,
            )

            _qc_profile_print(
                "draw_objects_mode",
                time.perf_counter() - profile_start,
            )

    # ---------------------------------------------------------------------
    # Progress
    # ---------------------------------------------------------------------

    def draw_progress_bar(
        self,
        layout,
        settings,
    ):
        """
        Draws the shared progress bar used by check runs and bulk fixes.
        """
        if not settings.is_running:
            return

        progress_row = layout.row()
        progress_row.scale_y = 0.5

        progress_row.progress(
            factor=settings.run_progress,
            type="BAR",
            text="{:.0f}%".format(
                settings.run_progress * 100
            ),
        )


    # ---------------------------------------------------------------------
    # CHECK MODE
    # ---------------------------------------------------------------------

    def draw_checks_mode(
        self,
        context,
        layout,
        settings,
        checks,
    ):
        """
        Draws the traditional check-oriented QC interface.
        """
        scene = context.scene

        # ---------------------------------------------------------
        # Category
        # ---------------------------------------------------------

        layout.prop(
            settings,
            "category",
            text="Category",
        )

        # ---------------------------------------------------------
        # Select All / Critical / Invert / None
        # ---------------------------------------------------------

        row = layout.row(align=True)

        row.operator(
            "scriptronaut.qc_select_all",
            icon="CHECKBOX_HLT",
            text="Select All",
        )

        row.separator()

        row.operator(
            "scriptronaut.qc_select_critical",
            icon_value=get_icon_id(
                "severity_critical"
            ),
            text="",
        )

        row.separator()

        row.operator(
            "scriptronaut.qc_select_invert",
            icon_value=get_icon_id(
                "select_invert"
            ),
            text="",
        )

        row.separator()

        row.operator(
            "scriptronaut.qc_select_none",
            icon="CHECKBOX_DEHLT",
            text="Select None",
        )

        # ---------------------------------------------------------
        # Check list
        # ---------------------------------------------------------

        profile_start = time.perf_counter()

        layout.template_list(
            "SCRIPTRONAUT_UL_QC_Checks",
            "",
            scene,
            "scriptronaut_qc_checks",
            settings,
            "check_index",
            rows=8,
        )

        _qc_profile_print(
            "checks template_list",
            time.perf_counter() - profile_start,
            "checks={}".format(
                len(checks)
            ),
        )

        # ---------------------------------------------------------
        # Run / Fix Progress
        # ---------------------------------------------------------

        self.draw_progress_bar(
            layout,
            settings,
        )

        # ---------------------------------------------------------
        # Run selected
        # ---------------------------------------------------------

        selected_check_count = sum(
            1
            for item in checks
            if item.selected
        )

        run_row = layout.row()
        run_row.scale_y = 1.5

        run_row.enabled = (
            selected_check_count > 0
        )

        if selected_check_count == 0:
            run_button_text = (
                "No Checks Selected"
            )
        else:
            run_button_text = (
                "Run ({}) Selected Check{}".format(
                    selected_check_count,
                    ""
                    if selected_check_count == 1
                    else "s",
                )
            )

        run_row.operator(
            "scriptronaut.qc_run_selected",
            icon="PLAY",
            text=run_button_text,
        )

        # ---------------------------------------------------------
        # Current check
        # ---------------------------------------------------------

        current_item = None
        if (
            checks
            and
            0
            <= settings.check_index
            < len(checks)
        ):
            current_item = checks[
                settings.check_index
            ]

        # ---------------------------------------------------------
        # Fix All
        # ---------------------------------------------------------

        fixable_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.has_fix
                and item.can_auto_fix
            )
        )

        fix_all_row = layout.row()
        fix_all_row.scale_y = 1.1
        fix_all_row.enabled = (
            fixable_count > 0
        )

        if fixable_count > 0:
            fix_all_text = (
                "Fix All ({}) Fixable Checks".format(
                    fixable_count
                )
            )
        else:
            fix_all_text = (
                "No Automatic Fixes Available"
            )

        fix_all_row.operator(
            "scriptronaut.qc_fix_all",
            icon="TOOL_SETTINGS",
            text=fix_all_text,
        )

        # ---------------------------------------------------------
        # Issues
        # ---------------------------------------------------------

        issues_box = layout.box()

        issues_box.label(
            text="Issues:",
            icon="INFO",
        )

        if current_item is None:
            issues_box.label(
                text="No check selected.",
            )
            return

        profile_start = time.perf_counter()

        result_summary = result_summary_from_json(
            current_item.result_summary
        )

        _qc_profile_print(
            "result summary decode",
            time.perf_counter() - profile_start,
            "check={} summary={:.2f} KB".format(
                current_item.name,
                len(
                    current_item.result_summary
                ) / 1024.0,
            ),
        )

        failed_objects = result_summary.get(
            "failed_objects",
            {},
        )

        # ---------------------------------------------------------
        # Failed objects
        # ---------------------------------------------------------

        if (
            isinstance(failed_objects, dict)
            and failed_objects
        ):
            profile_start = time.perf_counter()

            failed_object_count = len(
                failed_objects
            )

            for object_name, object_data in failed_objects.items():

                row = issues_box.row(
                    align=True
                )

                row.alert = True

                selection_mode = ""

                if isinstance(
                    object_data,
                    dict,
                ):
                    selection_mode = str(
                        object_data.get(
                            "selection_mode",
                            "",
                        )
                    ).upper()

                # -------------------------------------------------
                # Selection button
                # -------------------------------------------------

                if selection_mode:

                    if selection_mode == "FACE":
                        button_icon = "FACESEL"

                    elif selection_mode == "EDGE":
                        button_icon = "EDGESEL"

                    elif selection_mode == "VERT":
                        button_icon = "VERTEXSEL"

                    else:
                        button_icon = "EDITMODE_HLT"

                    button_text = (
                        "Select Failed Components: {}".format(
                            object_name
                        )
                    )

                else:
                    button_icon = "OBJECT_DATA"

                    button_text = (
                        "Select Failed Object: {}".format(
                            object_name
                        )
                    )

                select_operator = row.operator(
                    "scriptronaut.qc_select_object",
                    text=button_text,
                    icon=button_icon,
                )

                select_operator.object_name = (
                    object_name
                )

                # Required so the operator can retrieve this
                # check's stored component-selection data.
                select_operator.check_index = (
                    settings.check_index
                )

                # -------------------------------------------------
                # Details button
                # -------------------------------------------------

                details_operator = row.operator(
                    "scriptronaut.qc_object_details",
                    text="",
                    icon="TEXT",
                )

                details_operator.check_index = (
                    settings.check_index
                )

                details_operator.object_name = (
                    object_name
                )

            _qc_profile_print(
                "failed object rows",
                time.perf_counter() - profile_start,
                "check={} objects={}".format(
                    current_item.name,
                    failed_object_count,
                ),
            )

        # ---------------------------------------------------------
        # Non-object issue messages
        # ---------------------------------------------------------

        elif settings.issues_display:

            for line in (
                settings.issues_display
                .splitlines()
            ):
                draw_wrapped_text(
                    issues_box,
                    line,
                    width=80,
                )

        else:
            issues_box.label(
                text="No issues found.",
                icon="CHECKMARK",
            )

    # ---------------------------------------------------------------------
    # OBJECT MODE
    # ---------------------------------------------------------------------

    def draw_objects_mode(
        self,
        context,
        layout,
        settings,
        checks,
    ):
        """
        Draws QC results organized by failed object.
        """
        scene = context.scene

        failed_objects = (
            scene.scriptronaut_qc_failed_objects
        )

        object_checks = (
            scene.scriptronaut_qc_object_checks
        )

        # ---------------------------------------------------------
        # No results yet
        # ---------------------------------------------------------

        if not checks:
            box = layout.box()
            box.label(
                text="No QC results available.",
                icon="INFO",
            )
            box.label(
                text="Run checks in Checks mode first."
            )

            return

        # ---------------------------------------------------------
        # Failed objects
        # ---------------------------------------------------------

        object_box = layout.box()

        object_box.label(
            text="Failed Objects ({})".format(
                len(failed_objects)
            ),
            icon="OBJECT_DATA",
        )

        if not failed_objects:
            object_box.label(
                text="No failed objects.",
                icon="CHECKMARK",
            )

            return

        profile_start = time.perf_counter()

        object_box.template_list(
            "SCRIPTRONAUT_UL_QC_FailedObjects",
            "",
            scene,
            "scriptronaut_qc_failed_objects",
            settings,
            "failed_object_index",
            rows=6,
        )

        _qc_profile_print(
            "failed objects template",
            time.perf_counter() - profile_start,
            "objects={}".format(
                len(failed_objects)
            ),
        )

        # ---------------------------------------------------------
        # Selected object
        # ---------------------------------------------------------

        current_object_item = None

        if (
            0
            <= settings.failed_object_index
            < len(failed_objects)
        ):
            current_object_item = (
                failed_objects[
                    settings.failed_object_index
                ]
            )

        if current_object_item:
            info_row = object_box.row()
            info_row.label(
                text="Selected: {}".format(
                    current_object_item.name
                ),
                icon="RESTRICT_SELECT_OFF",
            )

            object_box.operator(
                "scriptronaut.qc_select_current_failed_object",
                text="Select Object",
                icon="RESTRICT_SELECT_OFF",
            )

        # ---------------------------------------------------------
        # Failed checks for selected object
        # ---------------------------------------------------------

        check_box = layout.box()

        check_box.label(
            text="Failed Checks",
            icon="ERROR",
        )

        if not object_checks:
            check_box.label(
                text="No failed checks for this object.",
                icon="CHECKMARK",
            )

            return

        profile_start = time.perf_counter()

        check_box.template_list(
            "SCRIPTRONAUT_UL_QC_ObjectChecks",
            "",
            scene,
            "scriptronaut_qc_object_checks",
            settings,
            "object_check_index",
            rows=6,
        )

        _qc_profile_print(
            "object checks template",
            time.perf_counter() - profile_start,
            "checks={}".format(
                len(object_checks)
            ),
        )

        # ---------------------------------------------------------
        # Fix Progress
        # ---------------------------------------------------------

        self.draw_progress_bar(
            layout,
            settings,
        )

        # ---------------------------------------------------------
        # Current failed check
        # ---------------------------------------------------------

        current_object_check = None

        if (
            0
            <= settings.object_check_index
            < len(object_checks)
        ):
            current_object_check = (
                object_checks[
                    settings.object_check_index
                ]
            )

        if current_object_check is None:
            return

        # ---------------------------------------------------------
        # Fix all failed checks for the selected object
        # ---------------------------------------------------------

        fixable_object_check_count = sum(
            1
            for item in object_checks
            if (
                item.has_fix
                and item.can_auto_fix
            )
        )

        fix_all_object_row = layout.row()
        fix_all_object_row.scale_y = 1.4

        fix_all_object_row.enabled = (
            fixable_object_check_count > 0
        )

        if fixable_object_check_count > 0:
            button_text = (
                "Fix All Checks on This Object ({})".format(
                    fixable_object_check_count
                )
            )

        else:
            button_text = (
                "No Automatic Fixes Available"
            )

        fix_all_object_row.operator(
            "scriptronaut.qc_fix_all_object_checks",
            text=button_text,
            icon="TOOL_SETTINGS",
        )

        # ---------------------------------------------------------
        # Optional check information
        # ---------------------------------------------------------

        details_box = layout.box()

        details_box.label(
            text="Selected Check:",
            icon="INFO",
        )

        details_box.label(
            text=current_object_check.name
        )

        if current_object_check.has_fix:
            details_box.label(
                text="Automatic fix available.",
                icon="TOOL_SETTINGS",
            )

        else:
            details_box.label(
                text="Manual fix required.",
                icon="INFO",
            )

CLASSES = (SCRIPTRONAUT_PT_QC_Checks,)
