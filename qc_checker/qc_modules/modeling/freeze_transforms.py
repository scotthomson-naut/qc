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
    failed_objects = []

    failed_objects = get_objects_with_non_default_transforms()

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
    failed_objects = result_data.get("failed_objects", {})

    object_names = list(failed_objects.keys())

    fixed = fix_objects_with_non_default_transforms(object_names)

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

def get_objects_with_non_default_transforms(
        objects=None,
        tolerance=1e-5,
        exclude_types=None
    ):
    """
    Returns a dictionary of objects whose transforms are not at defaults.

    Defaults:
        Location = (0,0,0)
        Rotation = (0,0,0)
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
                "location": (1.0, 0.0, 0.0),
                "rotation": (0.0, 0.5, 0.0),
                "scale": (1.0, 2.0, 1.0),
                "issues": [
                    "Location",
                    "Rotation",
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
        # Location
        # -------------------------
        location_bad = any(
            not isclose(v, 0.0, abs_tol=tolerance)
            for v in obj.location
        )

        if location_bad:
            issues.append("Location")

        # -------------------------
        # Rotation
        # -------------------------
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
            rotation_bad = not isclose(rotation[0], 0.0, abs_tol=tolerance)

        else:
            rotation = tuple(obj.rotation_euler)
            rotation_bad = any(
                not isclose(v, 0.0, abs_tol=tolerance)
                for v in rotation
            )

        if rotation_bad:
            issues.append("Rotation")

        # -------------------------
        # Scale
        # -------------------------
        scale_bad = any(
            not isclose(v, 1.0, abs_tol=tolerance)
            for v in obj.scale
        )

        if scale_bad:
            issues.append("Scale")

        # -------------------------
        if issues:
            results[obj.name] = {
                "location": tuple(obj.location),
                "rotation": rotation,
                "scale": tuple(obj.scale),
                "issues": issues,
            }

    return results


# -------------------------
# Fix
# -------------------------

def fix_objects_with_non_default_transforms(objects=None):
    """
    Fixes objects whose transforms are not at defaults.

    Args:
        objects (list): List of Blender objects.
                        Defaults to bpy.data.objects.

    Returns:
        dict:
        {
            "Cube": ["Location", "Rotation", "Scale"]
            ...
        }
    """
    if objects is None:
        objects = bpy.data.objects

    # Convert object names to real Blender objects
    if objects and isinstance(objects[0], str):
        objects = [
            bpy.data.objects[name]
            for name in objects
            if name in bpy.data.objects
        ]

    fixed = {}
    for obj in objects:
        fixed_issues = []

        obj.location = (0.0, 0.0, 0.0)
        fixed_issues.append("Location")

        if obj.rotation_mode == 'QUATERNION':
            obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        elif obj.rotation_mode == 'AXIS_ANGLE':
            obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        else:
            obj.rotation_euler = (0.0, 0.0, 0.0)

        fixed_issues.append("Rotation")

        obj.scale = (1.0, 1.0, 1.0)
        fixed_issues.append("Scale")

        fixed[obj.name] = fixed_issues

    bpy.context.view_layer.update()

    return fixed
