# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "View Layer Rendering Enabled"
DESCRIPTION = (
    "Checks if every view layer has 'Use for Rendering' enabled. A "
    "view layer with this disabled produces zero output when "
    "rendering, regardless of whether it's correctly wired into the "
    "compositor or has otherwise valid settings - nothing about it "
    "ever gets computed at all."
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Note:
        Uses ViewLayer.use, based on the "Use for Rendering" checkbox
        in the View Layer Properties tab. This property name has not
        been confirmed against a live Blender console check - verify
        with bpy.context.view_layer.use before trusting this in
        production.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_view_layers_not_used_for_rendering()

    issues = [
        "Failed view layer: {} - 'Use for Rendering' is disabled, "
        "this view layer will produce no output".format(
            view_layer_name
        )
        for view_layer_name in failed_objects
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# A view layer can be legitimately disabled from rendering on
# purpose - a WIP or reference layer someone doesn't want computed
# right now, for example. Not safe to assume it's a mistake and
# auto-enable it.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_view_layers_not_used_for_rendering(scene=None):
    """
    Finds view layers that have 'Use for Rendering' disabled.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "ViewLayer_001": {
                "issue": "'Use for Rendering' is disabled.",
            },
            ...
        }
    """
    if scene is None:
        scene = bpy.context.scene

    failed_objects = {}

    for view_layer in scene.view_layers:
        if not view_layer.use:
            failed_objects[view_layer.name] = {
                "issue": "'Use for Rendering' is disabled.",
            }

    return failed_objects