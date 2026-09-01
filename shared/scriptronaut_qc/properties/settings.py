"""Scriptronaut QC Checks internal module."""

import json

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from ..constants import CHECKS_DIR
from ..core.callbacks import update_qc_category, update_qc_check_index
from ..core.categories import qc_category_items, refresh_object_failed_checks


# Dynamic EnumProperty callbacks must keep returned strings alive for as long
# as Blender may reference them. Cache the generated tuples by their serialized
# SETTINGS schema.
_CHECK_SETTING_ENUM_CACHE = {}


def _decode_check_setting_enum_items(
        raw_items,
    ):
    """
    Converts serialized enum item data into Blender EnumProperty items.

    The cache is important: Blender requires the strings returned from a
    dynamic EnumProperty callback to remain referenced by Python.
    """
    raw_items = str(
        raw_items
        or "[]"
    )

    cached_items = (
        _CHECK_SETTING_ENUM_CACHE.get(
            raw_items
        )
    )

    if cached_items is not None:
        return cached_items

    try:
        stored_items = json.loads(
            raw_items
        )

    except (
        TypeError,
        ValueError,
    ):
        stored_items = []

    enum_items = []

    if isinstance(
        stored_items,
        list,
    ):
        for stored_item in stored_items:

            if not isinstance(
                stored_item,
                (list, tuple),
            ):
                continue

            if len(
                stored_item
            ) < 2:
                continue

            identifier = str(
                stored_item[
                    0
                ]
            )

            label = str(
                stored_item[
                    1
                ]
            )

            description = (
                str(
                    stored_item[
                        2
                    ]
                )
                if len(
                    stored_item
                ) >= 3
                else ""
            )

            enum_items.append(
                (
                    identifier,
                    label,
                    description,
                )
            )

    if not enum_items:
        enum_items = [
            (
                "NONE",
                "None",
                "No enum choices are available.",
            ),
        ]

    enum_items = tuple(
        enum_items
    )

    _CHECK_SETTING_ENUM_CACHE[
        raw_items
    ] = enum_items

    return enum_items


def qc_check_setting_enum_items(
        self,
        context,
    ):
    """
    Dynamic item callback for one QC check enum setting.
    """
    return _decode_check_setting_enum_items(
        getattr(
            self,
            "enum_items_json",
            "[]",
        )
    )


def get_check_setting_enum_identifiers(
        item,
    ):
    """
    Returns enum identifiers in their original SETTINGS order.
    """
    return tuple(
        enum_item[
            0
        ]
        for enum_item in _decode_check_setting_enum_items(
            getattr(
                item,
                "enum_items_json",
                "[]",
            )
        )
        if enum_item[
            0
        ] != "NONE"
    )


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

    # Serialized copy of the enum choices defined by the active check's
    # SETTINGS entry. The generic dialog can therefore display a different
    # dropdown for every check without hardcoding choices in the framework.
    enum_items_json: StringProperty(
        default="[]",
    )

    enum_value: EnumProperty(
        name="Value",
        items=qc_check_setting_enum_items,
    )

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
