# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "Deliverable Visible In Viewport But Render Disabled"
DESCRIPTION = (
    "Checks if objects inside a hero/deliverable collection are "
    "visible in the viewport (Eye ON, Monitor ON) but disabled from "
    "render (Camera OFF). Same flag pattern as 'Visible In Viewport "
    "But Render Disabled', escalated to Critical here because the "
    "object sits in a collection meant to be part of final output. "
    "Skips control-type objects (Empty/Armature/Lattice, CTRL_/REF_ "
    "naming, or rig_controls/guides collections), since this is their "
    "normal designed state regardless of which collection they're in."
)

# Object types this check evaluates. Cameras/lights/speakers etc.
# don't meaningfully participate in the visibility cascade.
RELEVANT_OBJECT_TYPES = {
    "MESH",
    "CURVE",
    "SURFACE",
    "META",
    "FONT",
    "EMPTY",
    "ARMATURE",
    "LATTICE",
    "VOLUME",
    "GPENCIL",
}

CONTROL_OBJECT_TYPES = {
    "EMPTY",
    "ARMATURE",
    "LATTICE",
}

CONTROL_NAME_PREFIXES = (
    "CTRL_",
    "REF_",
)

CONTROL_COLLECTION_KEYWORDS = (
    "rig_controls",
    "guides",
)

DELIVERABLE_COLLECTION_KEYWORDS = (
    "hero",
    "deliverable",
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_deliverable_render_disabled_objects()

    issues = [
        "Failed object: {} - In a hero/deliverable collection, "
        "visible in viewport but disabled from render, in view "
        "layer(s): {}".format(
            object_name,
            ", ".join(object_data["view_layers"]),
        )
        for object_name, object_data in failed_objects.items()
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Same reasoning as visibility_render_disabled_visible_viewport.py -
# this flag combination can be an intentional pattern (reference/proxy
# geo), so it isn't safe to assume it's a mistake and auto-toggle it.
# Needs an artist to confirm intent, and doing so here matters even
# more given the deliverable-collection context.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Role-aware classifier
# -------------------------
#
# Duplicated in visibility_render_disabled_visible_viewport.py
# (module 2a) by design choice - this framework doesn't currently
# share code between check modules, so if these rules ever change
# (e.g. adding a new control-name prefix), both files need to be
# updated by hand.

def is_control_object(obj):
    """
    Args:
        obj (bpy.types.Object): Object to classify.

    Returns:
        bool: True if this looks like a control/rig object rather
            than renderable deliverable geometry.
    """
    if obj.type in CONTROL_OBJECT_TYPES:
        return True

    for prefix in CONTROL_NAME_PREFIXES:
        if obj.name.startswith(prefix):
            return True

    for collection in obj.users_collection:
        if is_control_collection(collection):
            return True

    return False


def is_control_collection(collection):
    """
    Args:
        collection (bpy.types.Collection): Collection to classify.

    Returns:
        bool: True if the collection's name matches a known
            control/rig role.
    """
    name_lower = collection.name.lower()

    return any(
        keyword in name_lower for keyword in CONTROL_COLLECTION_KEYWORDS
    )


def is_object_in_deliverable_collection(obj):
    """
    Args:
        obj (bpy.types.Object): Object to check.

    Returns:
        bool: True if the object sits in a collection whose name
            matches a known hero/deliverable pattern.
    """
    for collection in obj.users_collection:
        name_lower = collection.name.lower()

        if any(
            keyword in name_lower
            for keyword in DELIVERABLE_COLLECTION_KEYWORDS
        ):
            return True

    return False


# -------------------------
# Find
# -------------------------

def get_deliverable_render_disabled_objects(
        objects=None,
        view_layers=None,
    ):
    """
    Finds objects in a hero/deliverable collection that are visible
    in the viewport but disabled from render, excluding control-type
    objects.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Defaults to all objects in the current scene.

        view_layers (iterable[bpy.types.ViewLayer] | None):
            Defaults to every view layer on the current scene. Needed
            because the eye icon (hide_get()) is per-view-layer, even
            though Monitor/Camera are global.

    Returns:
        dict:
        {
            "Cube": {
                "view_layers": ["ViewLayer", "ViewLayer_001"],
            },
            ...
        }
    """
    scene = bpy.context.scene

    if objects is None:
        objects = scene.objects

    if view_layers is None:
        view_layers = scene.view_layers

    failed_objects = {}

    for view_layer in view_layers:
        for obj in objects:
            if obj.type not in RELEVANT_OBJECT_TYPES:
                continue

            eye_hidden = obj.hide_get(view_layer=view_layer)
            viewport_disabled = obj.hide_viewport
            render_disabled = obj.hide_render

            if eye_hidden or viewport_disabled or not render_disabled:
                # Not actually "visible in viewport but disabled from
                # render" in this view layer - nothing to flag.
                continue

            if is_control_object(obj):
                # Normal designed state, regardless of collection -
                # takes priority over the deliverable escalation.
                continue

            if not is_object_in_deliverable_collection(obj):
                # Ordinary case, covered by the separate
                # Warning-severity check instead, not this one.
                continue

            object_data = failed_objects.setdefault(
                obj.name,
                {"view_layers": []},
            )

            object_data["view_layers"].append(view_layer.name)

    return failed_objects