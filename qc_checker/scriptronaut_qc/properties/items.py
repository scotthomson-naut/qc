"""Scriptronaut QC Checks internal module."""

from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from ..constants import CHECKS_DIR
from ..core.callbacks import update_qc_category, update_qc_check_index, update_use_check_settings
from ..core.categories import qc_category_items, qc_editor_category_items, refresh_object_failed_checks


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


class SCRIPTRONAUT_QC_EditorItem(PropertyGroup):
    """
    Represents one available QC script in the JSON editor.
    """
    name: StringProperty(name="Script Name", default="")
    script_path: StringProperty(name="Script Path", default="")
    source_category: StringProperty(name="Source Folder", default="")
    pack_id: StringProperty(name="Pack ID", default="")
    selected: BoolProperty(name="Enabled", default=False)


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
    SCRIPTRONAUT_QC_EditorItem,
    SCRIPTRONAUT_QC_FailedObjectItem,
    SCRIPTRONAUT_QC_ObjectCheckItem,
)
