# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "View Layer Render Single Disabled"
DESCRIPTION = (
    "Checks if 'Render Single Layer' is enabled while more than one "
    "view layer exists. This scene-wide override skips every view "
    "layer except the active one at render time, regardless of each "
    "layer's own 'Use for Rendering' setting - usually left on "
    "accidentally after fast-iterating on one layer. With only one "
    "view layer in the scene, this setting is inert and not flagged."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Note:
        Uses scene.render.use_single_layer, based on the "Render
        Single Layer" checkbox found just under "Use for Rendering"
        in the View Layer Properties tab. This property name has not
        been confirmed against a live Blender console check - verify
        with bpy.context.scene.render.use_single_layer before
        trusting this in production.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    status = get_render_single_layer_status()

    failed_objects = {}
    issues = []

    if status["applies"]:
        failed_objects["Render Single Layer"] = {
            "issue": (
                "'Render Single Layer' is enabled with {} view "
                "layers in the scene - only the active one will "
                "render.".format(status["view_layer_count"])
            ),
        }
        issues.append(
            "Failed: 'Render Single Layer' is enabled with {} view "
            "layers in the scene".format(status["view_layer_count"])
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Same reasoning as view_layer_use_for_rendering.py - this is a
# manual-only check, period. This setting is usually a leftover from
# fast iteration, but that's not certain enough to auto-disable it on
# an artist's behalf.

# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_render_single_layer_status(scene=None):
    """
    Checks whether 'Render Single Layer' is enabled while more than
    one view layer exists in the scene.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "single_layer_enabled": bool,
            "view_layer_count": int,
            "applies": bool,
        }
    """
    if scene is None:
        scene = bpy.context.scene

    single_layer_enabled = scene.render.use_single_layer
    view_layer_count = len(scene.view_layers)

    return {
        "single_layer_enabled": single_layer_enabled,
        "view_layer_count": view_layer_count,
        "applies": single_layer_enabled and view_layer_count > 1,
    }