# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Active Single Camera Exists"
DESCRIPTION = (
    "Checks that the scene has at least one Camera object, that a "
    "camera is assigned as the active render camera, and (when the "
    "'Require Single Camera' setting is on) that exactly one Camera "
    "object exists."
)
WHY = (
    "Knows exactly which viewpoint to use for rendering and viewport "
    "framing. Without a designated active camera, rendering fails or "
    "captures the wrong angle."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "required": {
        "type": "bool",
        "label": "Require Single Camera",
        "description": (
            "If enabled, the check fails when more than one Camera "
            "object exists in the scene. Disable this if your "
            "project intentionally uses multiple cameras. Does not "
            "affect the 'no camera exists' or 'no active camera' "
            "checks, which always apply regardless of this setting."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks that:

        1. At least one Camera object exists. (always checked)
        2. The scene has an active render camera assigned.
           (always checked)
        3. Only one Camera object exists. (only checked when the
           'Require Single Camera' setting is enabled)

    Note:
        resolve_settings() is called here but not imported anywhere
        in this file - not confirmed how it reaches this module, best
        understanding is the QC framework injects it into each check
        module's namespace at runtime, same as how "preferences"
        arrives as an argument. Flag with your team if this errors as
        undefined.

    Args:
        preferences (dict | None):
            User-configured settings for this check, resolved against
            SETTINGS. Passed in by the QC framework.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "failed_settings": dict,
            "camera_status": dict,
        }
    """
    settings = resolve_settings(SETTINGS, preferences)

    scene = bpy.context.scene
    status = get_camera_status(scene)

    issues = []
    failed_objects = {}
    failed_settings = {}

    camera_count = status["camera_count"]
    active_camera_name = status["active_camera_name"]

    # ------------------------------------------------------------------
    # No camera exists - always checked, regardless of settings
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
    # More than one camera exists - only checked when
    # settings["required"] is True
    # ------------------------------------------------------------------

    elif camera_count > 1 and settings["required"]:
        failed_settings["single_camera"] = {
            "current_camera_count": camera_count,
            "expected_camera_count": 1,
            "active_camera": active_camera_name,
        }

        # One named message per camera, so the panel can match each
        # camera's own detail view to its issue text - a combined
        # count-only summary never names any specific camera, which
        # leaves the detail view with no message to show.
        for camera_obj in status["camera_objects"]:
            issues.append(
                (
                    'Failed: Camera "{}" - {} Camera objects exist in '
                    "the scene; exactly one is expected."
                ).format(camera_obj.name, camera_count)
            )

            failed_objects[camera_obj.name] = {
                "object_type": camera_obj.type,
                "is_active_render_camera": (
                    camera_obj == scene.camera
                ),
                "camera_count": camera_count,
                "can_auto_fix": False,
            }

    # ------------------------------------------------------------------
    # Exactly one camera exists, but it is not active - always
    # checked, regardless of settings
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
            "object_type": camera_obj.type,
            "is_active_render_camera": False,
            "camera_count": 1,
            "can_auto_fix": True,
        }

    # ------------------------------------------------------------------
    # Multiple cameras and no active camera - always checked,
    # regardless of settings. Even if multiple cameras are allowed,
    # SOME camera still has to be active for render to work at all.
    # ------------------------------------------------------------------

    elif camera_count > 1 and scene.camera is None:
        failed_settings["active_camera"] = {
            "current": None,
            "expected": "One of the scene cameras",
            "camera_count": camera_count,
            "can_auto_fix": False,
        }

        # Same reasoning as the branch above - name each camera so
        # the panel has a matching message for every detail view.
        # This branch previously never populated failed_objects at
        # all, leaving Failure Data empty on top of the missing
        # message.
        for camera_obj in status["camera_objects"]:
            issues.append(
                (
                    'Failed: Camera "{}" - No active render camera is '
                    "assigned, and the scene contains multiple "
                    "cameras, so the correct camera is ambiguous."
                ).format(camera_obj.name)
            )

            failed_objects.setdefault(
                camera_obj.name,
                {
                    "object_type": camera_obj.type,
                    "is_active_render_camera": False,
                    "camera_count": camera_count,
                    "can_auto_fix": False,
                },
            )

    can_auto_fix = (
        camera_count == 1
        and scene.camera is None
    )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "failed_settings": failed_settings,
        "can_auto_fix": can_auto_fix,
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


def fix(result_data=None, preferences=None):
    """
    Assigns the active render camera only when exactly one Camera object
    exists and scene.camera is not already assigned.

    The function intentionally does not:

        - Create a camera when none exists.
        - Delete extra cameras.
        - Guess which camera should be active when several exist.

    Note:
        Doesn't need "preferences" for its own logic - the only
        auto-fixable case (single camera, not active) is unconditional
        and doesn't depend on the "Require Single Camera" setting.
        Accepted here anyway for QC framework call-signature
        compatibility, matching cycle_denoising_enabled.py's fix().

    Args:
        result_data (dict | None):
            Result returned by main(). Included for QC framework compatibility.

        preferences (dict | None):
            Unused by this function - see note above.

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
        if (
            obj.type == "CAMERA"
            and obj.library is None
        )
    ]

    active_camera = scene.camera

    if (
        active_camera is not None
        and active_camera.library is not None
    ):
        active_camera = None

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
