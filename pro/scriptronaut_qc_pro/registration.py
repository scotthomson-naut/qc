"""Registration for QC Pro-only features."""

import bpy
from bpy.props import CollectionProperty, PointerProperty

from ..scriptronaut_qc.core.features import (
    register_feature,
    unregister_feature,
)

from ..scriptronaut_qc.core.object_filter import (
    register_object_filter,
    unregister_object_filter,
)

from . import operators
from . import properties
from . import ui
from .support import (
    check_settings_enabled,
    ignored_collections_object_filter,
)

from .ui import (
    draw_check_settings_feature,
    draw_ignored_collections_feature,
)


CLASS_MODULES = (
    properties,
    ui,
    operators,
)


def _all_classes():
    classes = []

    for module in CLASS_MODULES:
        classes.extend(
            getattr(
                module,
                "CLASSES",
                (),
            )
        )

    return tuple(
        classes
    )


CLASSES = _all_classes()


def register():
    for cls in CLASSES:
        bpy.utils.register_class(
            cls
        )

    bpy.types.Scene.scriptronaut_qc_pro_settings = (
        PointerProperty(
            type=properties.SCRIPTRONAUT_QC_PRO_Settings
        )
    )

    bpy.types.Scene.scriptronaut_qc_pro_editor_items = (
        CollectionProperty(
            type=properties.SCRIPTRONAUT_QC_PRO_EditorItem
        )
    )

    bpy.types.Scene.scriptronaut_qc_pro_ignored_collections = (
        CollectionProperty(
            type=properties.SCRIPTRONAUT_QC_PRO_IgnoredCollectionRule
        )
    )

    register_feature(
        "check_settings",
        enabled_callback=check_settings_enabled,
        draw_callback=draw_check_settings_feature,
    )

    register_feature(
        "ignored_collections",
        draw_callback=draw_ignored_collections_feature,
    )

    register_object_filter(
        "pro_ignored_collections",
        ignored_collections_object_filter,
        priority=100,
    )


def unregister():
    unregister_object_filter(
        "pro_ignored_collections"
    )

    unregister_feature(
        "ignored_collections"
    )

    unregister_feature(
        "check_settings"
    )

    if hasattr(
        bpy.types.Scene,
        "scriptronaut_qc_pro_ignored_collections",
    ):
        del bpy.types.Scene.scriptronaut_qc_pro_ignored_collections

    if hasattr(
        bpy.types.Scene,
        "scriptronaut_qc_pro_editor_items",
    ):
        del bpy.types.Scene.scriptronaut_qc_pro_editor_items

    if hasattr(
        bpy.types.Scene,
        "scriptronaut_qc_pro_settings",
    ):
        del bpy.types.Scene.scriptronaut_qc_pro_settings

    for cls in reversed(
        CLASSES
    ):
        bpy.utils.unregister_class(
            cls
        )
