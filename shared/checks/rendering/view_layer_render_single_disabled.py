# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "View Layer Render Single Disabled"
DESCRIPTION = (
    "Checks if 'Render Single Layer' is enabled while more than one "
    "view layer exists."
)
WHY = (
    "Without this checked, Blender defaults to rendering every single "
    "view layer in your scene sequentially, which wastes time if you only "
    "want to test or output one specific layer."
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

        This is a scene-level setting, not tied to any selectable
        object - like aov_denoising.py, this only ever returns
        "failed_settings", never "failed_objects". A placeholder key
        in failed_objects (e.g. "Render Single Layer", which isn't a
        real Blender object) was previously enough to make the panel
        show a "Select Failed Objects" button that had nothing valid
        to select.

    Returns:
        dict: {issues (list(str)), failed_settings(dict)}
    """
    status = get_render_single_layer_status()

    issues = []
    failed_settings = {}

    if status["applies"]:
        issues.append(
            "Failed: 'Render Single Layer' is enabled with {} view "
            "layers in the scene".format(status["view_layer_count"])
        )

        failed_settings["use_single_layer"] = {
            "current": True,
            "expected": False,
            "view_layer_count": status["view_layer_count"],
        }

    return {
        "issues": issues,
        "failed_settings": failed_settings,
    }


def fix(result_data=None):
    """
    Fix for issue.

    Note:
        Same reasoning as the reversal on
        view_layer_use_for_rendering.py's fix() - this button is only
        ever triggered by an artist choosing to click it, not run
        automatically. This setting is usually a leftover from fast
        iteration rather than a deliberate final choice, and clicking
        Fix is itself the artist's confirmation that this instance
        was unintentional.

    Args:
        result_data (dict | None): Result returned by main().
    Returns:
        dict: Fix result.
    """
    return fix_render_single_layer(result_data)

# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_render_single_layer(result_data=None):
    """
    Disables 'Render Single Layer'.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed_settings = result_data.get(
        "failed_settings",
        {},
    )

    if "use_single_layer" not in failed_settings:
        return {
            "issues": [],
            "fixed_settings": {},
        }

    scene = bpy.context.scene
    previous = scene.render.use_single_layer
    scene.render.use_single_layer = False

    return {
        "issues": [],
        "fixed_settings": {
            "use_single_layer": {
                "previous": previous,
                "current": False,
            },
        },
    }

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