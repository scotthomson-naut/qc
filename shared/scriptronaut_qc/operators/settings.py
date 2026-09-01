"""Scriptronaut QC Checks internal module."""

import json
import os
import traceback

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty
from bpy.types import Operator

from .. import constants
from ..core.context import QCContext
from ..core import *
from ..properties import (
    SCRIPTRONAUT_PG_CheckSetting,
    get_check_setting_enum_identifiers,
)
from ..utils import *
from ..ui import draw_wrapped_text



def normalize_enum_items(
        definition,
    ):
    """
    Converts SETTINGS["items"] into JSON-safe enum triples.

    Supported schema:

        "items": [
            ("IDENTIFIER", "Label", "Description"),
            ...
        ]
    """
    raw_items = definition.get(
        "items",
        [],
    )

    if not isinstance(
        raw_items,
        (list, tuple),
    ):
        return []

    items = []

    for raw_item in raw_items:

        if not isinstance(
            raw_item,
            (list, tuple),
        ):
            continue

        if len(
            raw_item
        ) < 2:
            continue

        items.append(
            [
                str(
                    raw_item[
                        0
                    ]
                ),
                str(
                    raw_item[
                        1
                    ]
                ),
                (
                    str(
                        raw_item[
                            2
                        ]
                    )
                    if len(
                        raw_item
                    ) >= 3
                    else ""
                ),
            ]
        )

    return items


def set_check_setting_enum_value(
        item,
        value,
    ):
    """
    Assigns a valid enum identifier.

    Saved preferences may contain an old identifier after a check changes its
    enum choices. Fall back to the current default, then the first choice.
    """
    identifiers = (
        get_check_setting_enum_identifiers(
            item
        )
    )

    if not identifiers:
        return

    value = str(
        value
        if value is not None
        else ""
    )

    if value not in identifiers:

        default_value = str(
            item.default_string
            or ""
        )

        if default_value in identifiers:
            value = default_value

        else:
            value = identifiers[
                0
            ]

    try:
        item.enum_value = (
            value
        )

    except TypeError:
        # Blender can query a new dynamic EnumProperty one UI cycle after its
        # backing item data changes. Defer the assignment until draw().
        item[
            "_pending_enum_value"
        ] = value

def reset_check_settings_dialog(self, context):
    """Restore the settings shown in the dialog to module defaults."""
    if not self.reset_to_defaults:
        return

    for item in self.settings:
        if item.setting_type == "bool":
            item.bool_value = item.default_bool
        elif item.setting_type == "int":
            item.int_value = item.default_int
        elif item.setting_type == "float":
            item.float_value = item.default_float
        elif item.setting_type == "enum":
            set_check_setting_enum_value(
                item,
                item.default_string,
            )
        else:
            item.string_value = item.default_string

    # Return the toggle to its unpressed state without recursively
    # running the reset logic again.
    self["reset_to_defaults"] = False

    if context is not None and context.area is not None:
        context.area.tag_redraw()


class SCRIPTRONAUT_OT_QC_CheckSettings(Operator):
    """
    """
    bl_idname = "scriptronaut.qc_check_settings"
    bl_label = "Check Settings"
    bl_description = "Edit configurable values for this QC check"

    check_id: StringProperty()
    category_name: StringProperty()
    module_name: StringProperty()
    script_path: StringProperty(subtype="FILE_PATH")
    settings: CollectionProperty(type=SCRIPTRONAUT_PG_CheckSetting)
    reset_to_defaults: BoolProperty(
        name="Reset Values to Defaults",
        description=(
            "Restore the displayed settings to the defaults "
            "defined by this QC check"
        ),
        default=False,
        update=reset_check_settings_dialog,
    )

    def invoke(
            self,
            context,
            event,
        ):
        self.settings.clear()

        if not self.script_path or not os.path.isfile(self.script_path):
            self.report(
                {"ERROR"},
                "QC check script could not be found.",
            )
            return {"CANCELLED"}

        try:
            module = load_module_from_path(
                "qc_settings_{}".format(
                    abs(hash(self.script_path))
                ),
                self.script_path,
            )
        except Exception:
            print(traceback.format_exc())
            module = None

        if module is None:
            self.report(
                {"ERROR"},
                "Could not load the QC module.",
            )
            return {"CANCELLED"}

        schema = getattr(
            module,
            "SETTINGS",
            {},
        )

        if not isinstance(
            schema,
            dict,
        ) or not schema:
            self.report(
                {"INFO"},
                "This check has no configurable settings.",
            )
            return {"CANCELLED"}

        preferences = get_check_preferences(
            self.check_id,
            module,
        )

        for setting_name, definition in schema.items():
            if not isinstance(
                definition,
                dict,
            ):
                continue

            item = self.settings.add()

            item.setting_name = setting_name

            item.label = definition.get(
                "label",
                setting_name.replace(
                    "_",
                    " ",
                ).title(),
            )

            item.description = definition.get(
                "description",
                "",
            )

            item.setting_type = str(
                definition.get(
                    "type",
                    "string",
                )
            ).lower()

            value = preferences.get(
                setting_name,
                definition.get("default"),
            )

            default = definition.get(
                "default"
            )

            if item.setting_type == "bool":
                item.bool_value = bool(
                    value
                )

                item.default_bool = bool(
                    default
                )

            elif item.setting_type == "int":
                item.int_value = int(
                    value
                )

                item.default_int = int(
                    default
                )

                item.minimum = float(
                    definition.get(
                        "min",
                        -1000000000,
                    )
                )

                item.maximum = float(
                    definition.get(
                        "max",
                        1000000000,
                    )
                )

            elif item.setting_type == "float":
                item.float_value = float(
                    value
                )

                item.default_float = float(
                    default
                )

                item.minimum = float(
                    definition.get(
                        "min",
                        -1000000000.0,
                    )
                )

                item.maximum = float(
                    definition.get(
                        "max",
                        1000000000.0,
                    )
                )

            elif item.setting_type == "enum":

                enum_items = normalize_enum_items(
                    definition
                )

                item.enum_items_json = json.dumps(
                    enum_items,
                    separators=(
                        ",",
                        ":",
                    ),
                )

                item.default_string = str(
                    default
                    if default is not None
                    else ""
                )

                set_check_setting_enum_value(
                    item,
                    value,
                )

            else:
                item.string_value = str(
                    value
                    if value is not None
                    else ""
                )

                item.default_string = str(
                    default
                    if default is not None
                    else ""
                )

        return context.window_manager.invoke_props_dialog(
            self,
            width=500,
        )

    def draw(
            self,
            context,
        ):
        layout = self.layout

        layout.label(
            text="Check Settings",
            icon="GREASEPENCIL",
        )

        layout.label(
            text=self.check_id,
        )

        layout.separator()

        for item in self.settings:
            box = layout.box()
            row = box.row()

            if item.setting_type == "bool":
                row.prop(
                    item,
                    "bool_value",
                    text=item.label,
                )

            elif item.setting_type == "int":
                row.prop(
                    item,
                    "int_value",
                    text=item.label,
                )

            elif item.setting_type == "float":
                row.prop(
                    item,
                    "float_value",
                    text=item.label,
                )

            elif item.setting_type == "enum":

                pending_value = item.get(
                    "_pending_enum_value"
                )

                if pending_value:

                    try:
                        item.enum_value = (
                            pending_value
                        )

                        del item[
                            "_pending_enum_value"
                        ]

                    except TypeError:
                        pass

                row.prop(
                    item,
                    "enum_value",
                    text=item.label,
                )

            else:
                row.prop(
                    item,
                    "string_value",
                    text=item.label,
                )

            if item.description:
                draw_wrapped_text(
                    box,
                    item.description,
                )

        layout.separator()

        reset_row = layout.row(
            align=True
        )

        reset_row.prop(
            self,
            "reset_to_defaults",
            text="Reset Values to Defaults",
            icon="LOOP_BACK",
            toggle=True,
        )

    def execute(
            self,
            context,
        ):
        all_preferences = (
            load_all_check_preferences()
        )

        check_preferences = {}

        for item in self.settings:

            if item.setting_type == "bool":
                value = item.bool_value

            elif item.setting_type == "int":
                value = int(
                    max(
                        item.minimum,
                        min(
                            item.maximum,
                            item.int_value,
                        ),
                    )
                )

            elif item.setting_type == "float":
                value = float(
                    max(
                        item.minimum,
                        min(
                            item.maximum,
                            item.float_value,
                        ),
                    )
                )

            elif item.setting_type == "enum":
                value = item.enum_value

            else:
                value = item.string_value

            check_preferences[
                item.setting_name
            ] = value

        all_preferences[
            self.check_id
        ] = check_preferences

        try:
            save_all_check_preferences(
                all_preferences
            )

        except OSError as error:
            self.report(
                {"ERROR"},
                "Could not save settings: {}".format(
                    error
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            "Check settings saved.",
        )

        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_CheckSettings,
)
