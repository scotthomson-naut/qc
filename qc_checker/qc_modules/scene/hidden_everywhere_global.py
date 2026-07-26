# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Hidden Everywhere (Global)"
DESCRIPTION = (
    "Checks if objects are disabled from both viewport (Monitor OFF) "
    "and render (Camera OFF) globally, in every view layer. Likely "
    "intentional archive/reference geometry - surfaced for visibility "
    "rather than as a likely mistake."
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
    failed_objects = get_globally_hidden_objects()

    issues = [
        "Failed object: {} - Disabled from viewport and render "
        "globally (Monitor OFF, Camera OFF)".format(
            object_name
        )
        for object_name in failed_objects
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# This is commonly an intentional archive/reference state, not a
# mistake - not safe to assume otherwise and auto-toggle it.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_globally_hidden_objects(objects=None):
    """
    Finds objects disabled from both viewport and render, globally
    (Monitor OFF and Camera OFF).

    Note:
        Both flags checked here are global, the same in every view
        layer, so no per-view-layer iteration is needed - unlike the
        Eye-icon version of this same check
        (visibility_hidden_everywhere_eye.py), which is scoped per
        view layer instead.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "issue": "Disabled from viewport and render globally.",
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type not in RELEVANT_OBJECT_TYPES:
            continue

        if obj.hide_viewport and obj.hide_render:
            failed_objects[obj.name] = {
                "issue": "Disabled from viewport and render globally.",
            }

    return failed_objects