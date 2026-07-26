# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Hidden Everywhere (Local)"
DESCRIPTION = (
    "Checks if objects are hidden via the per-view-layer Eye icon "
    "and also disabled from render (Camera OFF). Scoped to one view "
    "layer at a time, distinct from the Monitor-icon version which "
    "is global. Likely intentional archive/reference geometry for "
    "this view layer specifically."
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

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_eye_hidden_and_render_disabled_objects()

    issues = []

    for object_name, object_data in failed_objects.items():
        issues.append(
            "Failed object: {} - Hidden via Eye icon and disabled "
            "from render, in view layer(s): {}".format(
                object_name,
                ", ".join(object_data["view_layers"]),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Likely intentional archive/reference state, not a mistake - not
# safe to assume otherwise and auto-toggle it.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_eye_hidden_and_render_disabled_objects(objects=None, view_layers=None):
    """
    Finds objects hidden via the per-view-layer Eye icon
    (hide_get()) that are also disabled from render (hide_render is
    True).

    Note:
        Must iterate per view layer, since the Eye icon's state is
        stored independently for each one. This is the per-view-layer
        counterpart to visibility_hidden_everywhere_global.py, which
        checks the equivalent global flags instead.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Defaults to all objects in the current scene.

        view_layers (iterable[bpy.types.ViewLayer] | None):
            Defaults to every view layer on the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "view_layers": ["ViewLayer_001"],
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

            if eye_hidden and obj.hide_render:
                object_data = failed_objects.setdefault(
                    obj.name,
                    {"view_layers": []},
                )

                object_data["view_layers"].append(view_layer.name)

    return failed_objects
