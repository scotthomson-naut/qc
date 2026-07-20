# Standard python imports
from math import isclose

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_non_default_rotation_scale()

    return {
        "issues": [
            "Failed object: {}".format(name)
            for name in failed_objects
        ],
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_objects_with_non_default_rotation_scale(result_data)

    return {
        "issues": [],
        "fixed_objects": fixed,
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------

def get_objects_with_non_default_rotation_scale(
        objects=None,
        tolerance=1e-5,
    ):
    """
    Finds mesh objects whose Rotation or Scale are not at their
    default values.

    Defaults:
        Rotation = (0, 0, 0)
        Scale    = (1, 1, 1)

    Supports:
        - Euler Rotation
        - Quaternion Rotation
        - Axis-Angle Rotation

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Floating point comparison tolerance.

    Returns:
        dict:
        {
            "Cube":
            {
                "rotation": (...),
                "scale": (...),
                "issues": [
                    "Rotation",
                    "Scale",
                ],
            },
            ...
        }
    """

    if objects is None:
        objects = bpy.context.scene.objects

    results = {}

    for obj in objects:

        if obj.type != 'MESH':
            continue

        issues = []

        # --------------------------------------------------
        # Rotation
        # --------------------------------------------------

        if obj.rotation_mode == 'QUATERNION':

            rotation = tuple(obj.rotation_quaternion)

            rotation_bad = (
                not isclose(rotation[0], 1.0, abs_tol=tolerance)
                or any(
                    not isclose(v, 0.0, abs_tol=tolerance)
                    for v in rotation[1:]
                )
            )

        elif obj.rotation_mode == 'AXIS_ANGLE':

            rotation = tuple(obj.rotation_axis_angle)

            rotation_bad = (
                not isclose(rotation[0], 0.0, abs_tol=tolerance)
            )

        else:

            rotation = tuple(obj.rotation_euler)

            rotation_bad = any(
                not isclose(v, 0.0, abs_tol=tolerance)
                for v in rotation
            )

        if rotation_bad:
            issues.append("Rotation")

        # --------------------------------------------------
        # Scale
        # --------------------------------------------------

        scale = tuple(obj.scale)

        scale_bad = any(
            not isclose(v, 1.0, abs_tol=tolerance)
            for v in scale
        )

        if scale_bad:
            issues.append("Scale")

        # --------------------------------------------------

        if issues:
            results[obj.name] = {
                "rotation": rotation,
                "scale": scale,
                "issues": issues,
            }

    return results


# -------------------------
# Fix
# -------------------------

def fix_objects_with_non_default_rotation_scale(result_data=None):
    """
    Resets Rotation and Scale.
    """
    failed_objects = result_data.get("failed_objects", {})

    for object_name in failed_objects.keys():

        obj = bpy.data.objects.get(object_name)

        if obj is None:
            continue

        if obj.rotation_mode == 'QUATERNION':
            obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)

        elif obj.rotation_mode == 'AXIS_ANGLE':
            obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)

        else:
            obj.rotation_euler = (0.0, 0.0, 0.0)

        obj.scale = (1.0, 1.0, 1.0)

    bpy.context.view_layer.update()

    return {
        "issues": []
    }
