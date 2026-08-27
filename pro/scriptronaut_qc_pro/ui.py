"""QC Pro-only UI."""

from bpy.types import UIList


class SCRIPTRONAUT_UL_QC_PRO_EditorScripts(UIList):

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

        row.prop(
            item,
            "selected",
            text="",
        )

        split = row.split(
            factor=0.65,
            align=True,
        )

        split.label(
            text=item.name,
            icon="FILE_SCRIPT",
        )

        split.label(
            text=item.source_category,
        )


def draw_check_settings_feature(
        layout,
        context,
    ):
    scene = context.scene

    if not hasattr(
        scene,
        "scriptronaut_qc_pro_settings",
    ):
        return

    settings = (
        scene.scriptronaut_qc_pro_settings
    )

    settings_box = layout.box()

    settings_box.label(
        text="Settings",
        icon="PREFERENCES",
    )

    settings_row = settings_box.row(
        align=True
    )

    settings_row.prop(
        settings,
        "use_check_settings",
        text="Use Check Settings",
    )

    editor_row = settings_row.row(
        align=True
    )

    editor_row.enabled = (
        settings.use_check_settings
    )

    editor_row.operator(
        "scriptronaut.qc_open_json_editor",
        text="Edit Check Settings",
        icon="GREASEPENCIL",
    )


class SCRIPTRONAUT_UL_QC_PRO_IgnoredCollections(UIList):

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

        if item.collection is None:
            row.label(
                text="No Collection",
                icon="ERROR",
            )
        else:
            row.label(
                text=item.collection.name,
                icon="OUTLINER_COLLECTION",
            )

        if item.scope == "CATEGORY":
            row.label(
                text="Category: {}".format(
                    item.category.replace(
                        "_",
                        " ",
                    ).title()
                    if item.category
                    else "None"
                )
            )

        else:
            row.label(
                text="Check: {}".format(
                    item.check_id
                    if item.check_id
                    else "None"
                )
            )


def draw_ignored_collections_feature(
        layout,
        context,
    ):
    """
    Adds the Pro ignored-collections editor to the Settings area.
    """
    scene = context.scene

    if not hasattr(
        scene,
        "scriptronaut_qc_pro_ignored_collections",
    ):
        return

    settings_box = layout.box()

    settings_box.label(
        text="Ignored Collections",
        icon="OUTLINER_COLLECTION",
    )

    row = settings_box.row(
        align=True
    )

    row.label(
        text="{} rule(s)".format(
            len(
                scene.scriptronaut_qc_pro_ignored_collections
            )
        )
    )

    row.operator(
        "scriptronaut.qc_edit_ignored_collections",
        text="Edit Ignored Collections",
        icon="GREASEPENCIL",
    )


CLASSES = (
    SCRIPTRONAUT_UL_QC_PRO_EditorScripts,
    SCRIPTRONAUT_UL_QC_PRO_IgnoredCollections,
)
