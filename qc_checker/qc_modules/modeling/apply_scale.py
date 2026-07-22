# Standard python imports
from math import isclose
from mathutils import Matrix

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
    failed_objects = get_objects_scale()

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
    fixed = fix_objects_scale(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_scale(
        objects=None,
        exclude_types=None
    ):
    """
    Returns a dictionary of objects whose transforms are not at defaults.

    Defaults:
        Scale    = (1,1,1)

    Args:
        objects (list): List of Blender objects.
                        Defaults to bpy.data.objects.
        tolerance (float): Floating point comparison tolerance.
        exclude_types (list): Object type to exclude.

    Returns:
        dict:
        {
            "Cube": {
                "scale": (1.0, 2.0, 1.0),
                "issues": [
                    "Scale"
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
        # Scale
        # -------------------------
        scale_bad = any(
            not isclose(v, 1.0, abs_tol=TOLERANCE)
            for v in obj.scale
        )

        if scale_bad:
            issues.append("Scale")

        # -------------------------
        if issues:
            results[obj.name] = {
                "scale": tuple(obj.scale),
                "issues": issues,
            }

    return results


# -------------------------
# Fix
# -------------------------

def fix_objects_scale(result_data=None):
    """
    Applies rotation and scale to mesh objects while preserving:

        - World-space appearance
        - Object location
        - Parenting

    After applying:
        Scale    -> 1

    Args:
        result_data (dict):
            Result returned by main()

    Returns:
        dict:
        {
            "fixed_objects": {
                "Character_Body": {
                    "scale_applied": True,
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

        scale = obj.scale

        needs_fix = any(
            abs(value - 1.0) > TOLERANCE
            for value in scale
        )

        if not needs_fix:
            continue

        try:
            # Copy shared mesh data before modifying it.
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            scale_matrix = Matrix.Diagonal((
                obj.scale.x,
                obj.scale.y,
                obj.scale.z,
                1.0,
            ))

            obj.data.transform(scale_matrix)

            obj.scale = (1.0, 1.0, 1.0)

            obj.data.update()

            fixed_objects[obj.name] = {
                "scale_applied": True,
            }

        except Exception as error:
            issues.append(
                "Could not apply scale to {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
