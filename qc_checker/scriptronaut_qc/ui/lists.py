"""Scriptronaut QC Checks internal module."""

from bpy.types import Panel, UIList

from ..constants import COMMON_CATEGORY, TIER
from ..core import get_qc_elapsed_text, get_severity_icon
from ..utils.json_io import result_data_from_json


class SCRIPTRONAUT_UL_QC_Checks(UIList):
    """
    Displays QC checks with:

        - Selection checkbox
        - Status icon
        - Check label
        - Description tooltip
        - Status
        - Inline Fix button when available
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):

        row = layout.row(align=True)

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        # Safe defaults.
        icon_name = "VIEWZOOM"
        status_text = "Not Run"

        if not item.is_available:
            icon_name = "LOCKED"
            status_text = "Disabled"

        elif item.status == "PASS":
            icon_name = "CHECKMARK"
            status_text = "Pass"

        elif item.status == "FAIL":
            icon_name = "CANCEL"
            status_text = "Fail"
            row.alert = True

        elif item.status == "RUNNING":
            icon_name = "SOLO_ON"
            status_text = "Running"

        elif item.status == "FIXING":
            icon_name = "MODIFIER"
            status_text = "Fixing"

        # ---------------------------------------------------------
        # Enabled checkbox
        # ---------------------------------------------------------

        select_row = row.row(
            align=True
        )

        select_row.enabled = (
            item.is_available
        )

        select_row.prop(
            item,
            "selected",
            text="",
        )

        # ---------------------------------------------------------
        # Severity icon
        # ---------------------------------------------------------

        severity_names = {
            "critical": "Critical",
            "warning": "Warning",
            "info": "Info",
        }

        severity_info = row.operator(
            "scriptronaut.qc_check_info",
            text="",
            icon_value=get_severity_icon(
                item.severity
            ),
            emboss=False,
        )

        severity_info.tooltip_text = (
            "Severity: {}".format(
                severity_names.get(
                    item.severity,
                    "Warning",
                )
            )
        )

        # ---------------------------------------------------------
        # Main columns
        #
        # Name         ~70%
        # Status       ~15%
        # Fix button   remaining
        # ---------------------------------------------------------

        main_split = row.split(
            factor=0.7,
            align=True,
        )

        name_column = main_split.row(
            align=True
        )

        right_side = main_split.row(
            align=True
        )

        status_split = right_side.split(
            factor=0.50,
            align=True,
        )

        status_column = status_split.row(
            align=True
        )

        action_column = status_split.row(
            align=True
        )

        # ---------------------------------------------------------
        # Display name
        # ---------------------------------------------------------

        display_name = (
            item.display_name
            if item.display_name
            else item.name
        )

        if (
            item.source_category
            == COMMON_CATEGORY
        ):
            display_name = (
                "[Common] {}".format(
                    display_name
                )
            )

        # Keep this a label so selecting the UIList row
        # continues to work correctly.
        name_column.label(
            text=display_name,
            icon=icon_name,
        )

        # ---------------------------------------------------------
        # Description tooltip
        # ---------------------------------------------------------

        if item.description:
            info_operator = (
                name_column.operator(
                    "scriptronaut.qc_check_info",
                    text="",
                    icon="INFO",
                    emboss=False,
                )
            )

            description = (
                item.description
            )

            if not item.is_available:
                description = (
                    "{}\n\n{}".format(
                        description,
                        item.unavailable_reason,
                    )
                    if description
                    else item.unavailable_reason
                )

            info_operator.tooltip_text = (
                description
            )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        status_column.label(
            text=status_text,
        )

        # ---------------------------------------------------------
        # Inline Settings / Fix
        # ---------------------------------------------------------

        if item.has_settings:
            settings_operator = action_column.operator(
                "scriptronaut.qc_check_settings",
                text="",
                icon="GREASEPENCIL",
            )
            settings_operator.check_id = item.check_id
            settings_operator.script_path = item.script_path

        if (
            item.status == "FAIL"
            and item.has_fix
            and item.can_auto_fix
        ):
            fix_operator = action_column.operator(
                "scriptronaut.qc_fix_check_inline",
                text="",
                icon="TOOL_SETTINGS",
            )

            fix_operator.check_index = (
                index
            )

        elif not item.has_settings:
            action_column.label(text="")


class SCRIPTRONAUT_UL_QC_EditorScripts(UIList):
    """
    Displays discovered QC scripts with selection checkboxes.
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(align=True)
        selection_row = row.row(
            align=True
        )

        selection_row.enabled = (
            item.is_available
        )

        split = row.split(factor=0.65, align=True)
        split.label(text=item.name, icon="FILE_SCRIPT")
        split.label(text=item.source_category)


class SCRIPTRONAUT_UL_QC_FailedObjects(UIList):
    """
    Displays objects that failed one or more QC checks.
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(
            align=True
        )

        split = row.split(
            factor=0.75,
            align=True,
        )

        split.label(
            text=item.name,
            icon="OBJECT_DATA",
        )

        split.label(
            text="{} Fail{}".format(
                item.failed_check_count,
                ""
                if item.failed_check_count == 1
                else "s",
            )
        )


class SCRIPTRONAUT_UL_QC_ObjectChecks(UIList):
    """
    Displays checks failed by the selected object.

    Keeps the visual style consistent with Checks Mode:
        - Severity icon
        - Fail X icon
        - Friendly display name
        - Inline Fix button
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):

        row = layout.row(
            align=True
        )

        # This list only contains failed checks.
        row.alert = True

        scene = context.scene
        checks = scene.scriptronaut_qc_checks

        # ---------------------------------------------------------
        # Resolve original check item
        # ---------------------------------------------------------

        source_check = None

        if (
            item.check_index >= 0
            and item.check_index < len(checks)
        ):
            source_check = checks[
                item.check_index
            ]

        # ---------------------------------------------------------
        # Severity
        # ---------------------------------------------------------

        if source_check is not None:

            severity_icon = get_severity_icon(
                source_check.severity
            )

            display_name = (
                source_check.display_name
                if source_check.display_name
                else source_check.name
            )

        else:

            severity_icon = get_severity_icon(
                "warning"
            )

            display_name = (
                item.name
            )

        # ---------------------------------------------------------
        # Layout
        # ---------------------------------------------------------

        split = row.split(
            factor=0.88,
            align=True,
        )

        name_column = split.row(
            align=True
        )

        action_column = split.row(
            align=True
        )

        # ---------------------------------------------------------
        # Severity icon
        # ---------------------------------------------------------

        name_column.label(
            text="",
            icon_value=severity_icon,
        )

        # ---------------------------------------------------------
        # Status icon
        # ---------------------------------------------------------

        status_icon = "CANCEL"

        if source_check is not None:

            if source_check.status == "FIXING":
                status_icon = "MODIFIER"

            elif source_check.status == "RUNNING":
                status_icon = "SOLO_ON"

            elif source_check.status == "PASS":
                status_icon = "CHECKMARK"

            elif source_check.status == "FAIL":
                status_icon = "CANCEL"

        name_column.label(
            text="",
            icon=status_icon,
        )

        # ---------------------------------------------------------
        # Friendly display name
        # ---------------------------------------------------------

        name_column.label(
            text=display_name,
        )

        # ---------------------------------------------------------
        # Settings / Fix
        # ---------------------------------------------------------

        if item.has_settings and source_check is not None:
            settings_operator = action_column.operator(
                "scriptronaut.qc_check_settings",
                text="",
                icon="GREASEPENCIL",
            )
            settings_operator.check_id = source_check.check_id
            settings_operator.script_path = source_check.script_path

        if (
            item.has_fix
            and item.can_auto_fix
        ):
            operator = (
                action_column.operator(
                    "scriptronaut.qc_fix_object_inline",
                    text="",
                    icon="TOOL_SETTINGS",
                )
            )

            operator.object_check_index = (
                index
            )

        else:
            manual_row = (
                action_column.row(
                    align=True
                )
            )

            manual_row.enabled = False

            manual_row.label(
                text="Manual"
            )

CLASSES = (
    SCRIPTRONAUT_UL_QC_Checks,
    SCRIPTRONAUT_UL_QC_EditorScripts,
    SCRIPTRONAUT_UL_QC_FailedObjects,
    SCRIPTRONAUT_UL_QC_ObjectChecks
)
