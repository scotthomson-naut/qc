# Standard python imports
from math import isclose

# Blender imports
import bpy

# Company imports


# Constants
TOLERANCE=1e-5

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = []
    failed_objects = get_objects_rotation()

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
    fixed = fix_objects_rotation(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_rotation(
        objects=None,
        exclude_types=None
    ):
    """
    Returns a dictionary of objects whose transforms are not at defaults.

    Defaults:
        Rotation = (0,0,0)

    Args:
        objects (list): List of Blender objects.
                        Defaults to bpy.data.objects.
        exclude_types (list): Object type to exclude.

    Returns:
        dict:
        {
            "Cube": {
                "rotation": (0.0, 0.5, 0.0),
                "issues": [
                    "Rotation",
                ]
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.data.objects

    if exclude_types is None:
        # Skip cameras and lights
        exclude_types = {'CAMERA', 'LIGHT'}

    results = {}

    for obj in objects:
        if obj.type in exclude_types:
            continue

        issues = []

        # -------------------------
        # Rotation
        # -------------------------
        if obj.rotation_mode == 'QUATERNION':
            rotation = tuple(obj.rotation_quaternion)
            rotation_bad = (
                not isclose(rotation[0], 1.0, abs_tol=TOLERANCE)
                or any(
                    not isclose(v, 0.0, abs_tol=TOLERANCE)
                    for v in rotation[1:]
                )
            )

        elif obj.rotation_mode == 'AXIS_ANGLE':
            rotation = tuple(obj.rotation_axis_angle)
            rotation_bad = not isclose(rotation[0], 0.0, abs_tol=TOLERANCE)

        else:
            rotation = tuple(obj.rotation_euler)
            rotation_bad = any(
                not isclose(v, 0.0, abs_tol=TOLERANCE)
                for v in rotation
            )

        if rotation_bad:
            issues.append("Rotation")

        # -------------------------
        if issues:
            results[obj.name] = {
                "rotation": rotation,
                "issues": issues,
            }

    return results


# -------------------------
# Fix
# -------------------------

def fix_objects_rotation(result_data=None):
    """
    Applies rotation mesh objects while preserving:

        - World-space appearance
        - Object location
        - Parenting
        - Rotation mode

    After applying:
        Rotation -> 0

    Args:
        result_data (dict):
            Result returned by main()

    Returns:
        dict:
        {
            "fixed_objects": {
                "Character_Body": {
                    "rotation_applied": True,
                }
            },
            "issues": [...]
        }
    """
    failed_objects = result_data.get("failed_objects", {})
    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj.type != "MESH":
            continue

        rotation = obj.rotation_euler

        needs_fix = any(
            abs(value) > TOLERANCE
            for value in rotation
        )

        if not needs_fix:
            continue

        try:
            # Copy shared mesh data before modifying it.
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            rotation_matrix = (
                obj.rotation_euler.to_matrix().to_4x4()
            )

            obj.data.transform(rotation_matrix)
            obj.rotation_euler = (0.0, 0.0, 0.0)
            obj.data.update()

            fixed_objects[obj.name] = {
                "rotation_applied": True,
            }

        except Exception as error:
            issues.append(
                "Could not apply rotation to {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
