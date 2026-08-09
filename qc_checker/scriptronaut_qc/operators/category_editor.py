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


class SCRIPTRONAUT_OT_QC_OpenJsonEditor(Operator):
    """
    Opens the QC JSON category editor.
    """
    bl_idname = "scriptronaut.qc_open_json_editor"
    bl_label = "Edit Check Categories"
    bl_description = "Assign QC scripts to JSON categories"

    def invoke(self, context, event):
        settings = context.scene.scriptronaut_qc_settings
        if not settings.use_check_settings:
            self.report({"WARNING"}, "Enable Use Check Settings first.")
            return {"CANCELLED"}

        check_list = load_check_list(settings.folder_path)
        categories = sorted(check_list.keys())
        if categories:
            try:
                settings.editor_category = categories[0]
            except TypeError:
                pass

        settings.editor_new_category = ""
        success, message = populate_qc_editor(
            context,
            category=settings.editor_category,
        )
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self, width=620)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.scriptronaut_qc_settings

        category_box = layout.box()
        category_box.label(text="Category", icon="FILE_FOLDER")
        category_box.prop(settings, "editor_category", text="Existing")
        category_box.prop(settings, "editor_new_category", text="New")

        row = layout.row(align=True)
        row.operator(
            "scriptronaut.qc_editor_load_category",
            text="Load Category",
            icon="FILE_REFRESH",
        )
        row.operator(
            "scriptronaut.qc_editor_delete_category",
            text="Delete Category",
            icon="TRASH",
        )

        select_row = layout.row(align=True)
        select_row.operator(
            "scriptronaut.qc_editor_select_all",
            text="Select All",
            icon="CHECKBOX_HLT",
        )
        select_row.operator(
            "scriptronaut.qc_editor_select_none",
            text="Select None",
            icon="CHECKBOX_DEHLT",
        )

        layout.template_list(
            "SCRIPTRONAUT_UL_QC_EditorScripts",
            "",
            scene,
            "scriptronaut_qc_editor_items",
            settings,
            "editor_index",
            rows=14,
        )

        selected_count = sum(
            1 for item in scene.scriptronaut_qc_editor_items if item.selected
        )
        layout.label(
            text="{} script(s) selected".format(selected_count),
            icon="INFO",
        )

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        editor_items = scene.scriptronaut_qc_editor_items

        new_category = settings.editor_new_category.strip()
        category = (
            sanitize_category_name(new_category)
            if new_category
            else settings.editor_category
        )

        if not category or category == "NONE":
            self.report({"ERROR"}, "Enter or select a category.")
            return {"CANCELLED"}

        selected_scripts = [
            item.name for item in editor_items if item.selected
        ]

        check_list = load_check_list(settings.folder_path)
        check_list[category] = selected_scripts
        success, message = save_check_list(settings.folder_path, check_list)
        if not success:
            print(message)
            self.report({"ERROR"}, "Could not save CHECK_SETTINGS_FILE.")
            return {"CANCELLED"}

        categories = get_categories(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )
        if category in categories:
            try:
                settings.category = category
            except TypeError:
                pass

        load_qc_category(context)
        self.report(
            {"INFO"},
            'Saved {} check(s) to category "{}".'.format(
                len(selected_scripts), category
            ),
        )
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorLoadCategory(Operator):
    bl_idname = "scriptronaut.qc_editor_load_category"
    bl_label = "Load Category"

    def execute(self, context):
        settings = context.scene.scriptronaut_qc_settings
        success, message = populate_qc_editor(
            context,
            category=settings.editor_category,
        )
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        settings.editor_new_category = ""
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectAll(Operator):
    bl_idname = "scriptronaut.qc_editor_select_all"
    bl_label = "Select All Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_editor_items:
            item.selected = True
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectNone(Operator):
    bl_idname = "scriptronaut.qc_editor_select_none"
    bl_label = "Select No Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_editor_items:
            item.selected = False
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorDeleteCategory(Operator):
    bl_idname = "scriptronaut.qc_editor_delete_category"
    bl_label = "Delete QC Category"

    def execute(self, context):
        settings = context.scene.scriptronaut_qc_settings
        category = settings.editor_category
        if not category or category == "NONE":
            self.report({"WARNING"}, "No category selected.")
            return {"CANCELLED"}

        check_list = load_check_list(settings.folder_path)
        if category not in check_list:
            self.report({"WARNING"}, "Category was not found.")
            return {"CANCELLED"}

        del check_list[category]
        success, message = save_check_list(settings.folder_path, check_list)
        if not success:
            print(message)
            self.report({"ERROR"}, "Could not update JSON file.")
            return {"CANCELLED"}

        remaining = sorted(check_list.keys())
        if remaining:
            try:
                settings.editor_category = remaining[0]
            except TypeError:
                pass
            populate_qc_editor(context, remaining[0])
        else:
            context.scene.scriptronaut_qc_editor_items.clear()

        self.report({"INFO"}, 'Deleted category "{}".'.format(category))
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_RefreshCategories(Operator):
    """
    Reloads the available QC categories and scripts from disk.
    """
    bl_idname = "scriptronaut.qc_refresh_categories"
    bl_label = "Refresh QC Categories"

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings

        categories = get_categories(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )

        validation = validate_check_configuration(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )

        for warning in validation["warnings"]:
            print("QC warning: {}".format(warning))

        if not validation["valid"]:
            for error in validation["errors"]:
                print("QC error: {}".format(error))

            scene.scriptronaut_qc_checks.clear()
            settings.issues_display = (
                "QC configuration contains errors. "
                "See the system console."
            )

            self.report(
                {"ERROR"},
                "QC configuration contains errors.",
            )
            return {"CANCELLED"}

        if not categories:
            scene.scriptronaut_qc_checks.clear()
            settings.issues_display = ""
            self.report({"ERROR"}, "No QC categories found.")
            return {"CANCELLED"}

        if settings.category == "NONE" or settings.category not in categories:
            settings.category = categories[0]

        success, message = load_qc_category(context)

        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_OpenJsonEditor,
    SCRIPTRONAUT_OT_QC_EditorLoadCategory,
    SCRIPTRONAUT_OT_QC_EditorSelectAll,
    SCRIPTRONAUT_OT_QC_EditorSelectNone,
    SCRIPTRONAUT_OT_QC_EditorDeleteCategory,
    SCRIPTRONAUT_OT_QC_RefreshCategories,
)
