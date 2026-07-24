# Standard python imports
import re

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "No Special Charcaters in Object Name"
DESCRIPTION = (
    "Checks if Object's Name has Special Charcaters"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_objects_with_invalid_characters()
    issues = []

    for object_name, data in failed_objects.items():

        issues.append(
            "Failed object: {} - Contains special character(s): {}".format(
                object_name,
                " ".join(data["invalid_characters"]),
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

def get_objects_with_invalid_characters(objects=None):
    """
    Finds objects containing characters outside the allowed naming set.

    Allowed:
        A-Z
        a-z
        0-9
        underscore _
        hyphen -
        period .
        space

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

    Returns:
        dict: Objects containing invalid characters.
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    pattern = re.compile(r"[^A-Za-z0-9_.\- ]")

    for obj in objects:

        invalid_characters = list(
            dict.fromkeys(
                pattern.findall(obj.name)
            )
        )

        if invalid_characters:

            failed_objects[obj.name] = {
                "invalid_characters": invalid_characters,
            }

    return failed_objects
