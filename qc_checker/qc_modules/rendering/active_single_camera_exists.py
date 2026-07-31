# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Active Single Camera Exists"
DESCRIPTION = (
    "Checks that the scene contains exactly one Camera object and that "
    "the same camera is assigned as the active render camera."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks that:

        1. At least one Camera object exists.
        2. Only one Camera object exists.
        3. The camera is assigned to scene.camera.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "failed_settings": dict,
            "camera_status": dict,
        }
    """
    scene = bpy.context.scene
    status = get_camera_status(scene)

    issues = []
    failed_objects = {}
    failed_settings = {}

    camera_count = status["camera_count"]
    active_camera_name = status["active_camera_name"]

    # ------------------------------------------------------------------
    # No camera exists
    # ------------------------------------------------------------------

    if camera_count == 0:
        issues.append(
            "Failed: No Camera exists in the scene."
        )

        failed_settings["camera_exists"] = {
            "current": False,
            "expected": True,
            "camera_count": 0,
        }

    # ------------------------------------------------------------------
    # More than one camera exists
    # ------------------------------------------------------------------

    elif camera_count > 1:
        issues.append(
            (
                "Failed: {} Camera objects exist in the scene; "
                "exactly one is expected."
            ).format(camera_count)
        )

        failed_settings["single_camera"] = {
            "current_camera_count": camera_count,
            "expected_camera_count": 1,
            "active_camera": active_camera_name,
        }

        # Include every camera so the artist can select and inspect them.
        for camera_obj in status["camera_objects"]:
            failed_objects[camera_obj.name] = {
                "issue": "Multiple Camera objects exist in the scene.",
                "is_active_render_camera": (
                    camera_obj == scene.camera
                ),
                "camera_count": camera_count,
            }

    # ------------------------------------------------------------------
    # Exactly one camera exists, but it is not active
    # ------------------------------------------------------------------

    if camera_count == 1 and scene.camera is None:
        camera_obj = status["camera_objects"][0]

        issues.append(
            (
                'Failed: Camera "{}" exists but is not assigned as '
                "the active render camera."
            ).format(camera_obj.name)
        )

        failed_settings["active_camera"] = {
            "current": None,
            "expected": camera_obj.name,
            "camera_count": 1,
        }

        failed_objects[camera_obj.name] = {
            "issue": "The only Camera object is not the active render camera.",
            "is_active_render_camera": False,
            "camera_count": 1,
            "can_auto_fix": True,
        }

    # ------------------------------------------------------------------
    # Multiple cameras and no active camera
    # ------------------------------------------------------------------

    elif camera_count > 1 and scene.camera is None:
        issues.append(
            (
                "Failed: No active render camera is assigned, and the scene "
                "contains multiple cameras, so the correct camera is ambiguous."
            )
        )

        failed_settings["active_camera"] = {
            "current": None,
            "expected": "One of the scene cameras",
            "camera_count": camera_count,
            "can_auto_fix": False,
        }

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "failed_settings": failed_settings,
        "camera_status": {
            "camera_count": camera_count,
            "camera_names": status["camera_names"],
            "active_camera_name": active_camera_name,
            "has_camera": status["has_camera"],
            "has_single_camera": status["has_single_camera"],
            "active_camera_assigned": status["active_camera_assigned"],
            "passes": not issues,
        },
    }


def fix(result_data=None):
    """
    Assigns the active render camera only when exactly one Camera object
    exists and scene.camera is not already assigned.

    The function intentionally does not:

        - Create a camera when none exists.
        - Delete extra cameras.
        - Guess which camera should be active when several exist.

    Args:
        result_data (dict | None):
            Result returned by main(). Included for QC framework compatibility.

    Returns:
        dict:
        {
            "issues": list[str],
            "fixed_objects": dict,
            "fixed_settings": dict,
        }
    """
    scene = bpy.context.scene
    status = get_camera_status(scene)
    camera_objects = status["camera_objects"]

    if len(camera_objects) == 0:
        return {
            "issues": [
                "Could not auto-fix: no Camera object exists in the scene."
            ],
            "fixed_objects": {},
            "fixed_settings": {},
        }

    if len(camera_objects) > 1:
        return {
            "issues": [
                (
                    "Could not auto-fix: {} Camera objects exist, so choosing "
                    "or deleting cameras requires an artist decision."
                ).format(len(camera_objects))
            ],
            "fixed_objects": {},
            "fixed_settings": {},
        }

    camera_obj = camera_objects[0]

    if scene.camera == camera_obj:
        return {
            "issues": [],
            "fixed_objects": {},
            "fixed_settings": {},
        }

    previous_camera = (
        scene.camera.name
        if scene.camera is not None
        else None
    )

    try:
        scene.camera = camera_obj
    except Exception as error:
        return {
            "issues": [
                'Could not assign Camera "{}" as the active render camera: {}'.format(
                    camera_obj.name,
                    error,
                )
            ],
            "fixed_objects": {},
            "fixed_settings": {},
        }

    return {
        "issues": [],
        "fixed_objects": {
            camera_obj.name: {
                "active_render_camera_assigned": True,
            },
        },
        "fixed_settings": {
            "active_camera": {
                "previous": previous_camera,
                "current": camera_obj.name,
            },
        },
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_camera_status(scene=None):
    """
    Returns the scene's camera state.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect. Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "has_camera": bool,
            "has_single_camera": bool,
            "active_camera_assigned": bool,
            "active_camera_name": str | None,
            "camera_count": int,
            "camera_names": list[str],
            "camera_objects": list[bpy.types.Object],
        }
    """
    if scene is None:
        scene = bpy.context.scene

    camera_objects = [
        obj
        for obj in scene.objects
        if obj.type == "CAMERA"
    ]

    active_camera = scene.camera

    return {
        "has_camera": bool(camera_objects),
        "has_single_camera": len(camera_objects) == 1,
        "active_camera_assigned": active_camera is not None,
        "active_camera_name": (
            active_camera.name
            if active_camera is not None
            else None
        ),
        "camera_count": len(camera_objects),
        "camera_names": [
            camera_obj.name
            for camera_obj in camera_objects
        ],
        "camera_objects": camera_objects,
    }
