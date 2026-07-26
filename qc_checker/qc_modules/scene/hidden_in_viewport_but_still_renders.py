# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Hidden In Viewport But Still Renders"
DESCRIPTION = (
    "Checks if objects are hidden in the viewport (Monitor OFF) but "
    "will still render (Camera ON). Common, often intentional pattern "
    "for heavy geometry kept out of the way during layout - surfaced "
    "here so it isn't a surprise at render time."
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
    failed_objects = get_hidden_viewport_visible_render_objects()

    issues = [
        "Failed object: {} - Hidden in viewport but will still "
        "render".format(
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
# This is a common, often intentional pattern (heavy geometry kept
# hidden from the viewport during layout, while still meant to
# render) - not safe to assume it's a mistake and auto-toggle it.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_hidden_viewport_visible_render_objects(objects=None):
    """
    Finds objects that are hidden in the viewport (Monitor OFF) but
    will still render (Camera ON).

    Note:
        Unlike most of the other visibility checks, this one doesn't
        need to iterate per view layer - hide_viewport and hide_render
        are both global flags on the object, the same in every view
        layer. The per-view-layer eye icon isn't part of this
        particular check at all.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "issue": "Hidden in viewport but will still render.",
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

        if obj.hide_viewport and not obj.hide_render:
            failed_objects[obj.name] = {
                "issue": "Hidden in viewport but will still render.",
            }

    return failed_objects
