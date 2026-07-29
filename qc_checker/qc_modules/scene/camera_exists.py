# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "Camera Exists"
DESCRIPTION = (
    "Checks if at least one Camera object exists anywhere in the "
    "scene. Distinct from checking whether an active render camera "
    "is assigned (scene.camera) - this only checks that a camera "
    "object exists at all."
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
    status = get_camera_status()

    failed_objects = {}
    issues = []

    if not status["has_camera"]:
        failed_objects["No Camera In Scene"] = {
            "issue": "No camera object found in the scene.",
        }
        issues.append(
            "Failed: No camera object found in the scene."
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# A camera's placement, framing, and lens settings are creative
# decisions - there's no meaningful automatic placement to fall back
# on. Auto-creating a camera at the origin wouldn't actually resolve
# the underlying problem, it would just make the check pass without
# a usable camera.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_camera_status(scene=None):
    """
    Checks whether at least one Camera-type object exists in the
    scene.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "has_camera": bool,
            "camera_count": int,
        }
    """
    if scene is None:
        scene = bpy.context.scene

    camera_count = sum(
        1 for obj in scene.objects if obj.type == "CAMERA"
    )

    return {
        "has_camera": camera_count > 0,
        "camera_count": camera_count,
    }