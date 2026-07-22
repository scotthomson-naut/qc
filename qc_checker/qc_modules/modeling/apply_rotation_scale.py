# Standard python imports
from math import isclose
from mathutils import Matrix

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

    failed_objects = get_objects_rotation_and_scale()

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
    fixed = fix_objects_rotation_and_scale(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_rotation_and_scale(
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
                "rotation": (0.0, 0.5, 0.0),
                "scale": (1.0, 2.0, 1.0),
                "issues": [
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

def fix_objects_rotation_and_scale(result_data=None):
    """
    Applies rotation and scale to mesh objects while preserving:

        - World-space appearance
        - Object location
        - Parenting
        - Rotation mode

    After applying:
        Rotation -> 0
        Scale    -> 1

    Args:
        result_data (dict):
            Result returned by main(), containing:

            {
                "failed_objects": {
                    "ObjectName": {
                        "missing_start": ["location[0]", ...],
                        "missing_end": ["location[1]", ...],
                    }
                }
            }


    Returns:
        dict:
        {
            "fixed_objects": {
                "Character_Body": {
                    "rotation_applied": True,
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

        # Linked data cannot safely be modified.
        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(obj.name)
            )
            continue

        mesh = obj.data

        if mesh is None:
            continue

        # Shared mesh data would also affect other objects.
        if mesh.users > 1:
            mesh = mesh.copy()
            obj.data = mesh

        old_scale = obj.scale.copy()
        old_rotation = obj.rotation_euler.copy()

        rotation_applied = any(
            abs(value) > 1e-6
            for value in old_rotation
        )

        scale_applied = any(
            abs(value - 1.0) > 1e-6
            for value in old_scale
        )

        if not rotation_applied and not scale_applied:
            continue

        try:
            # Build transform containing rotation and scale,
            # but not translation.
            transform_matrix = (
                obj.rotation_euler.to_matrix().to_4x4()
                @ Matrix.Diagonal((
                    obj.scale.x,
                    obj.scale.y,
                    obj.scale.z,
                    1.0,
                ))
            )

            # Bake rotation and scale into mesh vertices.
            mesh.transform(transform_matrix)

            # Reset object transforms.
            obj.rotation_euler = (0.0, 0.0, 0.0)
            obj.scale = (1.0, 1.0, 1.0)

            mesh.update()

            fixed_objects[obj.name] = {
                "rotation_applied": rotation_applied,
                "scale_applied": scale_applied,
            }

        except Exception as error:
            issues.append(
                "Could not apply transforms to {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
