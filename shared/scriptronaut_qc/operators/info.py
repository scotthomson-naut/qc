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

from ..core.icons import get_severity_icon

from ..core.results import (
    get_issues_from_result
)

from ..utils.formatting import (
    draw_qc_result_dictionary,
    draw_wrapped_qc_text,
    get_matching_object_issues,
)


class SCRIPTRONAUT_OT_QC_CheckInfo(Operator):
    """
    UI-only operator used to provide a tooltip
    for a QC check in the list.
    """
    bl_idname = "scriptronaut.qc_check_info"
    bl_label = "QC Check"
    tooltip_text: StringProperty(
        default=""
    )

    @classmethod
    def description(
        cls,
        context,
        properties,
    ):
        return (
            properties.tooltip_text
            or
            "No description available."
        )

    def execute(
        self,
        context,
    ):
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_ObjectDetails(
    Operator
):
    """
    Displays detailed result information for one failed object.
    """

    bl_idname = (
        "scriptronaut.qc_object_details"
    )

    bl_label = (
        "QC Failure Details"
    )

    bl_description = (
        "Display detailed information about this QC failure"
    )

    check_index: IntProperty(
        name="Check Index",
        default=-1,
    )

    object_name: StringProperty(
        name="Object Name",
        default="",
    )

    def invoke(
        self,
        context,
        event,
    ):
        checks = (
            context.scene
            .scriptronaut_qc_checks
        )

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            self.report(
                {"ERROR"},
                "The QC check is no longer available.",
            )

            return {"CANCELLED"}

        check_item = checks[
            self.check_index
        ]

        result_data = (
            result_data_from_json(
                check_item.result_data
            )
        )

        failed_objects = (
            result_data.get(
                "failed_objects",
                {},
            )
        )

        if (
            not isinstance(
                failed_objects,
                dict,
            )
            or self.object_name
            not in failed_objects
        ):
            self.report(
                {"WARNING"},
                (
                    'No stored failure information was found for "{}".'
                ).format(
                    self.object_name
                ),
            )

            return {"CANCELLED"}

        return (
            context.window_manager
            .invoke_props_dialog(
                self,
                width=650,
            )
        )

    def draw(self, context):
        """
        Draw the stored issue messages and structured failure data for the
        selected object.
        """
        layout = self.layout

        scene = context.scene
        checks = scene.scriptronaut_qc_checks

        # ---------------------------------------------------------
        # Validate check index
        # ---------------------------------------------------------

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            layout.label(
                text="The QC check is no longer available.",
                icon="ERROR",
            )
            return

        check_item = checks[
            self.check_index
        ]

        result_data = result_data_from_json(
            check_item.result_data
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

        object_data = failed_objects.get(
            self.object_name
        )

        # ---------------------------------------------------------
        # Header
        # ---------------------------------------------------------

        header_box = layout.box()

        header_box.label(
            text=(
                check_item.display_name
                or check_item.name
            ),
            icon_value=get_severity_icon(
                check_item.severity
            ),
        )

        header_box.label(
            text=self.object_name,
            icon="OBJECT_DATA",
        )

        # ---------------------------------------------------------
        # Issue messages
        # ---------------------------------------------------------

        issue_box = layout.box()

        issue_box.label(
            text="Issue Messages",
            icon="ERROR",
        )

        matching_issues = get_matching_object_issues(
            result_data,
            self.object_name,
        )

        if not matching_issues:
            all_issues = get_issues_from_result(
                result_data
            )

            # Show one general issue when the check only returned one.
            if len(all_issues) == 1:
                matching_issues = all_issues

        if matching_issues:
            for issue_index, issue in enumerate(
                matching_issues
            ):
                if issue_index:
                    issue_box.separator()

                draw_wrapped_qc_text(
                    issue_box,
                    issue,
                    icon="ERROR",
                    width=85,
                )

        else:
            issue_box.label(
                text=(
                    "No object-specific issue message "
                    "was returned by this check."
                ),
                icon="INFO",
            )

        # ---------------------------------------------------------
        # Structured failure data
        # ---------------------------------------------------------

        result_box = layout.box()

        result_box.label(
            text="Failure Data",
            icon="PROPERTIES",
        )

        if object_data is None:
            result_box.label(
                text=(
                    'No failed_objects data was found for "{}".'
                ).format(
                    self.object_name
                ),
                icon="INFO",
            )

        elif isinstance(
            object_data,
            dict,
        ):
            if object_data:
                draw_qc_result_dictionary(
                    result_box,
                    object_data,
                )
            else:
                result_box.label(
                    text="The object failure dictionary is empty.",
                    icon="INFO",
                )

        else:
            draw_wrapped_qc_text(
                result_box,
                str(object_data),
                width=85,
            )

    def execute(
        self,
        context,
    ):
        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_CheckInfo,
    SCRIPTRONAUT_OT_QC_ObjectDetails,
)
