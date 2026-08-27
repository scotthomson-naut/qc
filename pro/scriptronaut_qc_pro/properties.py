"""QC Pro-only property definitions."""

from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Collection, PropertyGroup

from .support import (
    ignored_rule_category_items,
    ignored_rule_check_items,
    qc_editor_category_items,
    update_editor_category,
    update_use_check_settings,
)


class SCRIPTRONAUT_QC_PRO_Settings(PropertyGroup):
    use_check_settings: BoolProperty(
        name="Use Check Settings",
        description=(
            "Use check_settings.json to determine which checks belong "
            "to each category"
        ),
        default=False,
        update=update_use_check_settings,
    )

    editor_category: EnumProperty(
        name="Category",
        description="Category to edit",
        items=qc_editor_category_items,
        update=update_editor_category,
    )

    editor_new_category: StringProperty(
        name="New Category",
        description="Optional new category name",
        default="",
    )

    editor_index: IntProperty(
        name="Editor Index",
        default=0,
    )

    ignored_collection_index: IntProperty(
        name="Ignored Collection Rule Index",
        default=0,
    )


class SCRIPTRONAUT_QC_PRO_EditorItem(PropertyGroup):
    name: StringProperty(
        name="Script Name",
        default="",
    )

    script_path: StringProperty(
        name="Script Path",
        default="",
    )

    source_category: StringProperty(
        name="Source Folder",
        default="",
    )

    pack_id: StringProperty(
        name="Pack ID",
        default="",
    )

    selected: BoolProperty(
        name="Enabled",
        default=False,
    )


class SCRIPTRONAUT_QC_PRO_IgnoredCollectionRule(PropertyGroup):
    """
    Scene-specific rule for excluding a collection from one category/check.
    """

    collection: PointerProperty(
        name="Collection",
        type=Collection,
    )

    scope: EnumProperty(
        name="Applies To",
        items=(
            (
                "CATEGORY",
                "Category",
                "Ignore this collection for every check in one category",
            ),
            (
                "CHECK",
                "Check",
                "Ignore this collection for one specific QC check",
            ),
        ),
        default="CATEGORY",
    )

    category: EnumProperty(
        name="Category",
        items=ignored_rule_category_items,
    )

    check_id: EnumProperty(
        name="Check",
        items=ignored_rule_check_items,
    )


CLASSES = (
    SCRIPTRONAUT_QC_PRO_Settings,
    SCRIPTRONAUT_QC_PRO_EditorItem,
    SCRIPTRONAUT_QC_PRO_IgnoredCollectionRule,
)
