"""Central registration assembled from module-level CLASSES tuples."""

import bpy
from bpy.props import CollectionProperty, PointerProperty

from .constants import CHECKS_DIR
from .core.packs import (
    register_check_pack,
    unregister_check_pack,
)

from .core.runtime import (
    initialize_new_scene_qc,
    initialize_qc_checks_after_load,
    initialize_qc_checks_timer,
    mark_scene_modified_after_qc,
    redraw_qc_status_timer,
    register_scene_change_listener,
    unregister_scene_change_listener,
)
from .properties import items as property_items
from .properties import settings as property_settings
from .operators import category_editor, fix, info, run, selection, settings as settings_ops
from .ui import lists, panel
from .icons import (
    register_icons,
    unregister_icons,
)
from .properties import (
    SCRIPTRONAUT_QC_CheckItem, SCRIPTRONAUT_QC_EditorItem,
    SCRIPTRONAUT_QC_FailedObjectItem, SCRIPTRONAUT_QC_ObjectCheckItem,
    SCRIPTRONAUT_QC_Settings,
)

CLASS_MODULES = (
    property_items, property_settings, lists, category_editor, run, selection,
    fix, info, settings_ops, panel,
)


def _all_classes():
    classes = []
    for module in CLASS_MODULES:
        classes.extend(getattr(module, "CLASSES", ()))
    return tuple(classes)

CLASSES = _all_classes()
SCENE_PROPERTIES = (
    "scriptronaut_qc_settings", "scriptronaut_qc_checks",
    "scriptronaut_qc_editor_items", "scriptronaut_qc_failed_objects",
    "scriptronaut_qc_object_checks",
)


def register():
    # Core is itself a registered check pack. Discovery never needs to know
    # that these checks happen to ship beside the framework.
    register_check_pack(
        pack_id="scriptronaut_core",
        name="Scriptronaut QC Core",
        checks_path=CHECKS_DIR,
        version="0.1.0",
        priority=0,
    )

    register_icons()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scriptronaut_qc_settings = PointerProperty(type=SCRIPTRONAUT_QC_Settings)
    bpy.types.Scene.scriptronaut_qc_checks = CollectionProperty(type=SCRIPTRONAUT_QC_CheckItem)
    bpy.types.Scene.scriptronaut_qc_editor_items = CollectionProperty(type=SCRIPTRONAUT_QC_EditorItem)
    bpy.types.Scene.scriptronaut_qc_failed_objects = CollectionProperty(type=SCRIPTRONAUT_QC_FailedObjectItem)
    bpy.types.Scene.scriptronaut_qc_object_checks = CollectionProperty(type=SCRIPTRONAUT_QC_ObjectCheckItem)
    if initialize_qc_checks_after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(initialize_qc_checks_after_load)

    register_scene_change_listener()

    if initialize_new_scene_qc not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(initialize_new_scene_qc)

    if mark_scene_modified_after_qc not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(mark_scene_modified_after_qc)
    if not bpy.app.timers.is_registered(initialize_qc_checks_timer):
        bpy.app.timers.register(initialize_qc_checks_timer, first_interval=0.1)
    if not bpy.app.timers.is_registered(redraw_qc_status_timer):
        bpy.app.timers.register(redraw_qc_status_timer, first_interval=30.0, persistent=True)


def unregister():
    unregister_check_pack(
        "scriptronaut_core"
    )

    if initialize_qc_checks_after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(initialize_qc_checks_after_load)

    unregister_scene_change_listener()

    if initialize_new_scene_qc in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(initialize_new_scene_qc)

    if mark_scene_modified_after_qc in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(mark_scene_modified_after_qc)
    if bpy.app.timers.is_registered(initialize_qc_checks_timer):
        bpy.app.timers.unregister(initialize_qc_checks_timer)
    if bpy.app.timers.is_registered(redraw_qc_status_timer):
        bpy.app.timers.unregister(redraw_qc_status_timer)
    for name in reversed(SCENE_PROPERTIES):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    unregister_icons()
