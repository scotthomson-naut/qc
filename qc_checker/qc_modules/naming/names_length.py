# Standard python imports
import re

# Blender imports
import bpy

# Company imports

# Constants
MAX_LENGTH = 64


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_objects_with_long_names(
        max_length=MAX_LENGTH,
    )
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Name is {} characters "
            "(maximum is {})".format(
                object_name,
                data["name_length"],
                data["max_length"],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_long_names(
        objects=None,
        max_length=64,
    ):
    """
    Finds objects whose names are longer than the allowed length.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        max_length (int):
            Maximum allowed number of characters.
            Defaults to 64.

    Returns:
        dict:
        {
            "Very_Long_Object_Name...": {
                "name_length": 72,
                "max_length": 64,
                "characters_over": 8,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        name_length = len(obj.name)

        if name_length <= max_length:
            continue

        failed_objects[obj.name] = {
            "name_length": name_length,
            "max_length": max_length,
            "characters_over": name_length - max_length,
        }

    return failed_objects
