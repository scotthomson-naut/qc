# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    result = check_system_unit()

    issues = []

    if not result["is_valid"]:
        issues.append(
            "Scene unit system is set to None."
        )

    return {
        "issues": issues,
        "unit_settings": result,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def check_system_unit(scene=None):
    """
    Checks whether the Blender scene has a unit system configured.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect.
            Defaults to the current scene.

    Returns:
        dict:
        {
            "is_valid": bool,
            "unit_system": str,
            "scale_length": float,
        }
    """
    if scene is None:
        scene = bpy.context.scene

    unit_settings = scene.unit_settings
    unit_system = unit_settings.system

    return {
        "is_valid": unit_system != "NONE",
        "unit_system": unit_system,
        "scale_length": unit_settings.scale_length,
    }
