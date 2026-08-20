"""Scriptronaut QC Checks internal module."""

from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from ..constants import CHECKS_DIR
from ..core.callbacks import update_qc_category, update_qc_check_index, update_use_check_settings
from ..core.categories import qc_category_items, qc_editor_category_items, refresh_object_failed_checks


class SCRIPTRONAUT_QC_Settings(PropertyGroup):
    """
    Stores addon settings shared across the QC panel.

    Includes the QC modules folder, selected category,
    active check index, and displayed issue text.
    """
    folder_path: StringProperty(
        name="QC Folder",
        subtype="DIR_PATH",
        default=str(CHECKS_DIR),
    )

    last_run_time: StringProperty(
        name="Last QC Run Time",
        default="",
    )

    scene_modified_since_qc: BoolProperty(
        name="Scene Modified Since QC",
        default=False,
    )

    use_check_settings: BoolProperty(
        name="Use Check Settings",
        description=(
            "Use CHECK_SETTINGS_FILE to determine which checks belong "
            "to each category"
        ),
        default=False,
        update=update_use_check_settings,
    )

    mode: EnumProperty(
        name="Mode",
        description="Choose how QC results are viewed and fixed",
        items=[
            (
                "CHECKS",
                "Checks",
                "View checks and fix all failed objects for a check",
                "CHECKMARK",
                0,
            ),
            (
                "OBJECTS",
                "Objects",
                "View failed objects and the checks each object failed",
                "CUBE",
                1,
            ),
        ],
        default="CHECKS",
    )

    failed_object_index: IntProperty(
        name="Failed Object Index",
        default=0,
        update=lambda self, context: refresh_object_failed_checks(context),
    )

    object_check_index: IntProperty(
        name="Object Check Index",
        default=0,
    )

    editor_category: EnumProperty(
        name="Category",
        description="Category to edit",
        items=qc_editor_category_items,
    )

    editor_new_category: StringProperty(
        name="New Category",
        description="Optional new category name",
        default="",
    )

    editor_index: IntProperty(name="Editor Index", default=0)

    category: EnumProperty(
        name="Category",
        description="QC category folder",
        items=qc_category_items,
        update=update_qc_category,
    )

    check_index: IntProperty(
        default=0,
        update=update_qc_check_index,
    )

    issues_display: StringProperty(
        name="Issues",
        default="",
    )

    is_running: BoolProperty(
        name="QC Is Running",
        default=False,
    )

    run_progress: FloatProperty(
        name="QC Run Progress",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )


class SCRIPTRONAUT_PG_CheckSetting(
        PropertyGroup
    ):

    setting_name: StringProperty()
    label: StringProperty()
    description: StringProperty()
    setting_type: EnumProperty(
        items=(
            ("bool", "Boolean", ""),
            ("int", "Integer", ""),
            ("float", "Float", ""),
            ("string", "Text", ""),
            ("enum", "List", ""),
        ),
        default="string",
    )
    bool_value: BoolProperty()
    int_value: IntProperty()
    float_value: FloatProperty(
        default=0.0,
        precision=6,
    )
    string_value: StringProperty()
    enum_value: StringProperty()
    default_bool: BoolProperty()
    default_int: IntProperty()
    default_float: FloatProperty()
    default_string: StringProperty()

    minimum: FloatProperty(
        default=-1000000000.0,
    )

    maximum: FloatProperty(
        default=1000000000.0,
    )

    precision: IntProperty(
        default=6,
    )


CLASSES = (
    SCRIPTRONAUT_QC_Settings,
    SCRIPTRONAUT_PG_CheckSetting
)
