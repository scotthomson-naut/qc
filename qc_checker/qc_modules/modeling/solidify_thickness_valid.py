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
    failed_objects = get_objects_with_negative_solidify_thickness()
    issues = []

    for object_name, data in failed_objects.items():
        for modifier_data in data["modifiers"]:
            issues.append(
                "Failed object: {} - Solidify modifier '{}' "
                "has negative thickness: {}".format(
                    object_name,
                    modifier_data["name"],
                    modifier_data["thickness"],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_objects_with_negative_solidify_thickness(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_negative_solidify_thickness(objects=None):
    """
    Finds mesh objects with Solidify modifiers that use negative thickness.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Wall": {
                "modifiers": [
                    {
                        "name": "Solidify",
                        "thickness": -0.02,
                    }
                ]
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        failed_modifiers = []

        for modifier in obj.modifiers:

            if modifier.type != "SOLIDIFY":
                continue

            if modifier.thickness >= 0.0:
                continue

            failed_modifiers.append({
                "name": modifier.name,
                "thickness": modifier.thickness,
            })

        if failed_modifiers:
            failed_objects[obj.name] = {
                "modifiers": failed_modifiers,
            }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_with_negative_solidify_thickness(result_data=None):
    """
    Converts negative Solidify thickness values to positive values.

    Args:
        result_data (dict):
            Result returned by main()

    Returns:
        dict:
        {
            "fixed_objects": {
                "Character_Body": {
                    "fixed_modifiers": [],
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

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        fixed_modifiers = []

        for modifier_data in object_data.get(
            "modifiers",
            [],
        ):

            modifier = obj.modifiers.get(
                modifier_data["name"]
            )

            if (
                modifier is None
                or modifier.type != "SOLIDIFY"
            ):
                continue

            modifier_offset = modifier.offset
            if modifier.thickness < 0.0:
                modifier.thickness = abs(
                    modifier.thickness
                )

                modifier.offset = (
                    modifier_offset * -1
                )

                fixed_modifiers.append(
                    modifier.name
                )

        if fixed_modifiers:
            fixed_objects[object_name] = {
                "fixed_modifiers": fixed_modifiers,
            }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }
