# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "Active Render Camera"
DESCRIPTION = (
    "Checks if the scene has an active render camera assigned "
    "(scene.camera). Distinct from checking whether any camera "
    "object exists at all - a scene can have several cameras and "
    "still have none of them set as active, which blocks rendering "
    "exactly like having no camera at all."
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
    status = get_active_camera_status()

    failed_objects = {}
    issues = []

    if not status["active_camera_assigned"]:
        failed_objects["No Active Render Camera"] = {
            "issue": "No active render camera assigned to the scene.",
            "camera_count": status["camera_count"],
        }
        issues.append(
            "Failed: No active render camera assigned to the scene "
            "({} camera object(s) exist in the scene)".format(
                status["camera_count"]
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Args:
        result_data (dict): Result returned by main().
    Returns:
        dict: Fix result.
    """
    # Call Function
    fix_result = fix_missing_active_camera(result_data)

    return fix_result

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_active_camera_status(scene=None):
    """
    Checks whether the scene has an active render camera assigned.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "active_camera_assigned": bool,
            "camera_count": int,
        }
    """
    if scene is None:
        scene = bpy.context.scene

    camera_count = sum(
        1 for obj in scene.objects if obj.type == "CAMERA"
    )

    return {
        "active_camera_assigned": scene.camera is not None,
        "camera_count": camera_count,
    }


# -------------------------
# Fix
# -------------------------

def fix_missing_active_camera(result_data):
    """
    Assigns the scene's active render camera, but only when it's
    unambiguous - specifically, when exactly one camera object exists
    in the scene. With zero cameras there's nothing to assign, and
    with more than one, picking on the artist's behalf would be a
    content decision, not a safe repair.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if "No Active Render Camera" not in failed_objects:
        return {
            "issues": [],
            "fixed_objects": {},
        }

    scene = bpy.context.scene

    camera_objects = [
        obj for obj in scene.objects if obj.type == "CAMERA"
    ]

    if len(camera_objects) != 1:
        return {
            "issues": [
                "Could not auto-fix: {} camera object(s) exist, "
                "so the choice of active camera is ambiguous. "
                "Assign one manually.".format(len(camera_objects))
            ],
            "fixed_objects": {},
        }

    scene.camera = camera_objects[0]

    return {
        "issues": [],
        "fixed_objects": {
            "No Active Render Camera": {
                "assigned_camera": camera_objects[0].name,
            },
        },
    }