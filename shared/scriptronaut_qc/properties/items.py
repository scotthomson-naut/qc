"""Scriptronaut QC Checks internal module."""

from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from ..constants import CHECKS_DIR


class SCRIPTRONAUT_QC_CheckItem(PropertyGroup):
    """
    """
    name: StringProperty(
        default=""
    )

    display_name: StringProperty(
        name="Display Name",
        default="",
    )

    description: StringProperty(
        name="Description",
        default="",
    )

    severity: EnumProperty(
        name="Severity",
        items=[
            (
                "critical",
                "Critical",
                "Critical QC issue",
            ),
            (
                "warning",
                "Warning",
                "QC warning",
            ),
            (
                "info",
                "Info",
                "Informational QC check",
            ),
        ],
        default="warning",
    )

    script_path: StringProperty(
        default=""
    )

    selected: BoolProperty(
        default=True
    )

    status: EnumProperty(
        name="Status",
        items=[
            (
                "NOT_RUN",
                "Not Run",
                "",
            ),
            (
                "PASS",
                "Pass",
                "",
            ),
            (
                "FAIL",
                "Fail",
                "",
            ),
            (
                "RUNNING",
                "Running",
                "",
            ),
            (
                "FIXING",
                "Fixing",
                "",
            ),
        ],
        default="NOT_RUN",
    )

    source_category: StringProperty(
        name="Source Category",
        default="",
    )

    pack_id: StringProperty(
        name="Pack ID",
        default="",
    )

    has_fix: BoolProperty(
        default=False
    )

    can_auto_fix: BoolProperty(
        name="Can Auto Fix",
        description=(
            "Whether the current failure can be fixed automatically"
        ),
        default=True,
    )

    issues: StringProperty(
        default=""
    )

    result_data: StringProperty(
        default="{}"
    )

    result_summary: StringProperty(
        default="{}"
    )

    check_id: StringProperty(
        default=""
    )

    has_settings: BoolProperty(
        default=False
    )

    # alpha
    is_available: BoolProperty(
        name="Available",
        default=True,
    )
    unavailable_reason: StringProperty(
        name="Unavailable Reason",
        default="",
    )


class SCRIPTRONAUT_QC_FailedObjectItem(PropertyGroup):
    """
    Represents an object that failed one or more QC checks.
    """
    name: StringProperty(default="")
    failed_check_count: IntProperty(default=0)


class SCRIPTRONAUT_QC_ObjectCheckItem(PropertyGroup):
    """
    Represents a QC check failed by the currently selected object.
    """
    name: StringProperty(default="")
    script_path: StringProperty(default="")
    has_fix: BoolProperty(default=False)
    can_auto_fix: BoolProperty(default=True)
    has_settings: BoolProperty(default=False)
    check_id: StringProperty(default="")

    check_index: IntProperty(
        default=-1,
    )

    display_name: StringProperty(default="")
    severity: StringProperty(default="warning")
    description: StringProperty(default="")

CLASSES = (
    SCRIPTRONAUT_QC_CheckItem,
    SCRIPTRONAUT_QC_FailedObjectItem,
    SCRIPTRONAUT_QC_ObjectCheckItem,
)
