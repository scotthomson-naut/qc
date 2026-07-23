# Standard python imports
import re

# Blender imports
import bpy

# Company imports

# Constants
DEFAULT_OBJECT_NAMES = {
    "Cube",
    "Plane",
    "Sphere",
    "Icosphere",
    "Cylinder",
    "Cone",
    "Torus",
    "Grid",
    "Suzanne",
    "Circle",
    "Empty",
    "Armature",
    "Text",
    "Curve",
    "BezierCurve",
    "Surface",
    "Metaball",
    "Volume",
    "GreasePencil",
}

# "Camera",
# "Light",

# Meta data
LABEL = "Default Names"
DESCRIPTION = (
    "Checks if objects have default names like Cube, Sphere .."
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_objects_with_default_names()
    issues = [
        "Failed object: {} - Uses default Blender name".format(
            object_name
        )
        for object_name in failed_objects
    ]

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

def get_objects_with_default_names(
        objects=None,
        default_names=None,
        include_numbered_suffixes=True,
    ):
    """
    Finds objects using Blender default or generic object names.

    Examples:
        Cube
        Cube.001
        Plane
        Sphere
        Icosphere.002
        Empty
        Empty.003
        Camera
        Light

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        default_names (set[str] | None):
            Names considered invalid/default.
            Defaults to DEFAULT_OBJECT_NAMES.

        include_numbered_suffixes (bool):
            If True, also detects Blender auto-incremented versions
            such as Cube.001 and Plane.002.

    Returns:
        dict:
        {
            "Cube": {
                "base_name": "Cube",
                "suffix": None,
            },
            "Plane.002": {
                "base_name": "Plane",
                "suffix": 2,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if default_names is None:
        default_names = DEFAULT_OBJECT_NAMES

    failed_objects = {}

    for obj in objects:
        object_name = obj.name

        base_name = object_name
        suffix = None

        if include_numbered_suffixes:
            match = re.match(
                r"^(.*)\.(\d{3})$",
                object_name,
            )

            if match:
                base_name = match.group(1)
                suffix = int(match.group(2))

        if base_name not in default_names:
            continue

        failed_objects[object_name] = {
            "base_name": base_name,
            "suffix": suffix,
        }

    return failed_objects
