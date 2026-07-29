# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "warning"
LABEL = "Single Camera"
DESCRIPTION = (
    "Checks if more than one Camera object exists in the scene. "
    "Unlike a missing active camera, this doesn't block rendering at "
    "all - Blender just quietly renders through whichever camera is "
    "active and ignores the rest. That's exactly the risk: someone "
    "switches to review through a second camera, forgets to switch "
    "back, and the file renders successfully from the wrong one with "
    "nothing announcing the mistake."
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
    failed_objects = get_extra_cameras()

    issues = [
        "Failed object: {} - Multiple cameras exist in the scene "
        "({})".format(
            camera_name,
            "active" if data["is_active"] else "inactive",
        )
        for camera_name, data in failed_objects.items()
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Deciding which camera is "the" correct one, and whether the extras
# should be deleted, renamed, or just left as reference/alternate
# angles, is entirely a content decision - not something safe to
# guess at or auto-delete.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_extra_cameras(scene=None):
    """
    Finds all camera objects in the scene, when more than one exists.

    Note:
        Every camera is included when this fires, not just the extra
        ones - including the active camera lets an artist click
        through each one in the tool to review which is genuinely
        intended.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "Camera": {
                "is_active": True,
            },
            "Camera.001": {
                "is_active": False,
            },
        }
    """
    if scene is None:
        scene = bpy.context.scene

    camera_objects = [
        obj for obj in scene.objects if obj.type == "CAMERA"
    ]

    if len(camera_objects) <= 1:
        return {}

    failed_objects = {}

    for camera_obj in camera_objects:
        failed_objects[camera_obj.name] = {
            "is_active": camera_obj == scene.camera,
        }

    return failed_objects