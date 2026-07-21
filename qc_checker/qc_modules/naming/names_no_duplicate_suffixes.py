# Standard python imports
import re

# Blender imports
import bpy

# Company imports

# Constants
AUTO_INCREMENT_PATTERN = re.compile(r"^(.*)\.(\d{3})$")

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Detects Blender auto-incremented object names.
    """
    failed_objects = get_objects_with_auto_increment_names(
        exclude_types={"CAMERA", "LIGHT"},
    )

    return {
        "issues": [
            "Auto-incremented object name: {}".format(name)
            for name in failed_objects
        ],
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------

def get_objects_with_auto_increment_names(
        objects=None,
        exclude_types=None,
    ):
    """
    Finds objects whose names end with Blender's automatic numeric
    suffix (.001, .002, etc.).

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        exclude_types (set[str] | None):
            Object types to ignore.
            Example:
                {"CAMERA", "LIGHT"}

    Returns:
        dict:
        {
            "Cube.001": {
                "base_name": "Cube",
                "suffix": 1,
            },
            "Cylinder.015": {
                "base_name": "Cylinder",
                "suffix": 15,
            }
        }
    """
    if objects is None:
        objects = bpy.data.objects

    if exclude_types is None:
        exclude_types = set()

    failed_objects = {}

    for obj in objects:

        if obj.type in exclude_types:
            continue

        match = AUTO_INCREMENT_PATTERN.match(obj.name)

        if not match:
            continue

        failed_objects[obj.name] = {
            "base_name": match.group(1),
            "suffix": int(match.group(2)),
        }

    return failed_objects
