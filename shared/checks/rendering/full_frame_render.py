# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Full Frame Render"
DESCRIPTION = (
    "Checks if Render Border or Crop to Render Region is enabled."
)
WHY = (
    "Leaving them enabled by accident can cause your final image to be "
    "unexpectedly cropped or missing large parts of your scene."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks whether the current scene has Render Border enabled.

    Returns:
        dict
    """
    return get_render_setting()


def fix(result_data=None):
    """
    Disables Render Border and Crop to Render Region.

    Args:
        result_data (dict |None)

    Returns:
        dict
    """
    return fix_render_setting()


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_render_setting():
    """
    Checks whether the current scene has Render Border enabled.

    Returns:
        dict
    """
    scene = bpy.context.scene
    render = scene.render

    issues = []
    failed_settings = {}

    if render.use_border:
        issues.append(
            "Render Border is enabled."
        )

        failed_settings["use_border"] = True

    if render.use_crop_to_border:
        issues.append(
            "Crop to Render Region is enabled."
        )

        failed_settings["use_crop_to_border"] = True

    return {
        "issues": issues,
        "failed_settings": failed_settings,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_render_setting():
    """
    Disables Render Border and Crop to Render Region.

    Args:
        result_data (dict |None)

    Returns:
        dict
    """
    scene = bpy.context.scene
    render = scene.render

    fixed_settings = {}

    if render.use_border:
        render.use_border = False
        fixed_settings["use_border"] = False

    if render.use_crop_to_border:
        render.use_crop_to_border = False
        fixed_settings["use_crop_to_border"] = False

    return {
        "fixed_settings": fixed_settings,
        "issues": [],
    }
