# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Hidden Via Eye Icon But Still Renders"
DESCRIPTION = (
    "Checks if objects are hidden in the viewport via the per-view-"
    "layer Eye icon (hide_get()) but will still render (Camera ON). "
    "This is Blender's 'temporary' hide, scoped to one view layer - "
    "distinct from the Monitor icon, which is global. Common when an "
    "object was eye-hidden to isolate something while working and "
    "never switched back."
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
    failed_objects = get_eye_hidden_visible_render_objects()

    issues = []

    for object_name, object_data in failed_objects.items():
        issues.append(
            "Failed object: {} - Hidden via Eye icon but will still "
            "render, in view layer(s): {}".format(
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
# Eye-hiding an object is often a deliberate, temporary choice made
# while working (isolating something to focus on other geometry) -
# not safe to assume it's a leftover mistake and auto-unhide it.
# Needs an artist to confirm intent.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_eye_hidden_visible_render_objects(objects=None, view_layers=None):
    """
    Finds objects hidden via the per-view-layer Eye icon
    (hide_get()) that will still render (hide_render is False).

    Note:
        Unlike visibility_hidden_viewport_visible_render.py, this
        check must iterate per view layer, since the Eye icon's state
        is stored independently for each one - the same object can be
        eye-hidden in one view layer and visible in another.

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

            if eye_hidden and not obj.hide_render:
                object_data = failed_objects.setdefault(
                    obj.name,
                    {"view_layers": []},
                )

                object_data["view_layers"].append(view_layer.name)

    return failed_objects