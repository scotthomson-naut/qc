"""QC Pro-only check-settings operators."""

from bpy.types import Operator

from ..scriptronaut_qc.core.categories import load_qc_category
from ..scriptronaut_qc.core.discovery import (
    get_categories,
    validate_check_configuration,
)
from ..scriptronaut_qc.utils.json_io import (
    load_check_list,
    save_check_list,
)
from ..scriptronaut_qc.utils.naming import sanitize_category_name

from .support import populate_qc_editor


def save_current_category(
        context,
    ):
    """
    Saves the currently edited Pro category to check_settings.json.

    Returns:
        tuple:
            success, message, category, selected_count
    """
    scene = context.scene

    core_settings = (
        scene.scriptronaut_qc_settings
    )

    settings = (
        scene.scriptronaut_qc_pro_settings
    )

    editor_items = (
        scene.scriptronaut_qc_pro_editor_items
    )

    new_category = (
        settings.editor_new_category.strip()
    )

    category = (
        sanitize_category_name(
            new_category
        )
        if new_category
        else settings.editor_category
    )

    if (
        not category
        or category == "NONE"
    ):
        return (
            False,
            "Enter or select a category.",
            "",
            0,
        )

    selected_scripts = [
        item.name
        for item in editor_items
        if item.selected
    ]

    check_list = load_check_list(
        core_settings.folder_path
    )

    check_list[
        category
    ] = selected_scripts

    success, message = save_check_list(
        core_settings.folder_path,
        check_list,
    )

    if not success:
        return (
            False,
            message,
            category,
            len(
                selected_scripts
            ),
        )

    if new_category:
        settings.editor_new_category = ""

        try:
            settings.editor_category = category
        except TypeError:
            pass

    if core_settings.category == category:
        load_qc_category(
            context
        )

    return (
        True,
        "",
        category,
        len(
            selected_scripts
        ),
    )


class SCRIPTRONAUT_OT_QC_OpenJsonEditor(Operator):
    """
    Opens the QC JSON category editor.
    """
    bl_idname = "scriptronaut.qc_open_json_editor"
    bl_label = "Edit Check Categories"
    bl_description = "Assign QC scripts to JSON categories"

    def invoke(self, context, event):
        core_settings = context.scene.scriptronaut_qc_settings
        settings = context.scene.scriptronaut_qc_pro_settings
        if not settings.use_check_settings:
            self.report({"WARNING"}, "Enable Use Check Settings first.")
            return {"CANCELLED"}

        check_list = load_check_list(core_settings.folder_path)
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
        core_settings = scene.scriptronaut_qc_settings
        settings = scene.scriptronaut_qc_pro_settings

        category_box = layout.box()
        category_box.label(text="Category", icon="FILE_FOLDER")
        category_box.prop(settings, "editor_category", text="Existing")
        category_box.prop(settings, "editor_new_category", text="New")

        row = layout.row(
            align=True
        )

        row.operator(
            "scriptronaut.qc_editor_update_category",
            text="Update Category Checks",
            icon="FILE_TICK",
        )

        delete_row = layout.row(
            align=True
        )

        delete_row.operator(
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
            "SCRIPTRONAUT_UL_QC_PRO_EditorScripts",
            "",
            scene,
            "scriptronaut_qc_pro_editor_items",
            settings,
            "editor_index",
            rows=14,
        )

        selected_count = sum(
            1 for item in scene.scriptronaut_qc_pro_editor_items if item.selected
        )
        layout.label(
            text="{} script(s) selected".format(selected_count),
            icon="INFO",
        )

    def execute(self, context):
        success, message, category, selected_count = (
            save_current_category(
                context
            )
        )

        if not success:
            if message:
                print(
                    message
                )

            self.report(
                {"ERROR"},
                (
                    message
                    or "Could not update category checks."
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            'Updated "{}": {} check(s).'.format(
                category,
                selected_count,
            ),
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorUpdateCategory(Operator):
    """
    Saves the currently edited category and keeps the dialog open.
    """

    bl_idname = "scriptronaut.qc_editor_update_category"
    bl_label = "Update Category Checks"

    def execute(self, context):
        success, message, category, selected_count = (
            save_current_category(
                context
            )
        )

        if not success:
            if message:
                print(
                    message
                )

            self.report(
                {"ERROR"},
                (
                    message
                    or "Could not update category checks."
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            'Updated "{}": {} check(s).'.format(
                category,
                selected_count,
            ),
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectAll(Operator):
    bl_idname = "scriptronaut.qc_editor_select_all"
    bl_label = "Select All Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_pro_editor_items:
            item.selected = True
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectNone(Operator):
    bl_idname = "scriptronaut.qc_editor_select_none"
    bl_label = "Select No Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_pro_editor_items:
            item.selected = False
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorDeleteCategory(Operator):
    bl_idname = "scriptronaut.qc_editor_delete_category"
    bl_label = "Delete QC Category"

    def execute(self, context):
        core_settings = context.scene.scriptronaut_qc_settings
        settings = context.scene.scriptronaut_qc_pro_settings
        category = settings.editor_category
        if not category or category == "NONE":
            self.report({"WARNING"}, "No category selected.")
            return {"CANCELLED"}

        check_list = load_check_list(core_settings.folder_path)
        if category not in check_list:
            self.report({"WARNING"}, "Category was not found.")
            return {"CANCELLED"}

        del check_list[category]
        success, message = save_check_list(core_settings.folder_path, check_list)
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
            context.scene.scriptronaut_qc_pro_editor_items.clear()

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
        core_settings = scene.scriptronaut_qc_settings
        settings = scene.scriptronaut_qc_pro_settings

        categories = get_categories(
            core_settings.folder_path,
            use_json=settings.use_check_settings,
        )

        validation = validate_check_configuration(
            core_settings.folder_path,
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

        if core_settings.category == "NONE" or core_settings.category not in categories:
            core_settings.category = categories[0]

        success, message = load_qc_category(context)

        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditIgnoredCollections(Operator):
    """
    Opens scene-specific ignored collection rules.
    """

    bl_idname = "scriptronaut.qc_edit_ignored_collections"
    bl_label = "Edit Ignored Collections"
    bl_description = (
        "Exclude objects in selected collections from a QC category or check"
    )

    def invoke(
            self,
            context,
            event,
        ):
        return context.window_manager.invoke_props_dialog(
            self,
            width=700,
        )

    def draw(
            self,
            context,
        ):
        layout = self.layout
        scene = context.scene
        settings = scene.scriptronaut_qc_pro_settings
        rules = scene.scriptronaut_qc_pro_ignored_collections

        top_row = layout.row(
            align=True
        )

        top_row.operator(
            "scriptronaut.qc_ignored_collection_add",
            text="Add Rule",
            icon="ADD",
        )

        remove_row = top_row.row(
            align=True
        )

        remove_row.enabled = bool(
            rules
        )

        remove_row.operator(
            "scriptronaut.qc_ignored_collection_remove",
            text="Remove Rule",
            icon="REMOVE",
        )

        layout.template_list(
            "SCRIPTRONAUT_UL_QC_PRO_IgnoredCollections",
            "",
            scene,
            "scriptronaut_qc_pro_ignored_collections",
            settings,
            "ignored_collection_index",
            rows=6,
        )

        if not rules:
            layout.label(
                text="No ignored collection rules.",
                icon="INFO",
            )
            return

        index = min(
            max(
                settings.ignored_collection_index,
                0,
            ),
            len(
                rules
            ) - 1,
        )

        rule = rules[
            index
        ]

        box = layout.box()

        box.label(
            text="Rule",
            icon="OUTLINER_COLLECTION",
        )

        box.prop(
            rule,
            "collection",
            text="Collection",
        )

        box.prop(
            rule,
            "scope",
            text="Applies To",
        )

        if rule.scope == "CATEGORY":
            box.prop(
                rule,
                "category",
                text="Category",
            )

        else:
            box.prop(
                rule,
                "check_id",
                text="Check",
            )

        box.label(
            text=(
                "Child collections are included automatically."
            ),
            icon="INFO",
        )

    def execute(
            self,
            context,
        ):
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_IgnoredCollectionAdd(Operator):
    bl_idname = "scriptronaut.qc_ignored_collection_add"
    bl_label = "Add Ignored Collection Rule"

    def execute(
            self,
            context,
        ):
        scene = context.scene
        settings = scene.scriptronaut_qc_pro_settings
        rules = scene.scriptronaut_qc_pro_ignored_collections

        rule = rules.add()

        rule.scope = "CATEGORY"

        core_settings = scene.scriptronaut_qc_settings

        categories = get_categories(
            core_settings.folder_path,
            use_json=settings.use_check_settings,
        )

        if categories:
            try:
                rule.category = categories[0]
            except TypeError:
                pass

        settings.ignored_collection_index = (
            len(
                rules
            ) - 1
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_IgnoredCollectionRemove(Operator):
    bl_idname = "scriptronaut.qc_ignored_collection_remove"
    bl_label = "Remove Ignored Collection Rule"

    def execute(
            self,
            context,
        ):
        scene = context.scene
        settings = scene.scriptronaut_qc_pro_settings
        rules = scene.scriptronaut_qc_pro_ignored_collections

        if not rules:
            return {"CANCELLED"}

        index = min(
            max(
                settings.ignored_collection_index,
                0,
            ),
            len(
                rules
            ) - 1,
        )

        rules.remove(
            index
        )

        settings.ignored_collection_index = min(
            index,
            max(
                len(
                    rules
                ) - 1,
                0,
            ),
        )

        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_OpenJsonEditor,
    SCRIPTRONAUT_OT_QC_EditIgnoredCollections,
    SCRIPTRONAUT_OT_QC_IgnoredCollectionAdd,
    SCRIPTRONAUT_OT_QC_IgnoredCollectionRemove,
    SCRIPTRONAUT_OT_QC_EditorUpdateCategory,
    SCRIPTRONAUT_OT_QC_EditorSelectAll,
    SCRIPTRONAUT_OT_QC_EditorSelectNone,
    SCRIPTRONAUT_OT_QC_EditorDeleteCategory,
    SCRIPTRONAUT_OT_QC_RefreshCategories,
)
