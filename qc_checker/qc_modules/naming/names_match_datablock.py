# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue
    """
    failed_objects = get_objects_with_mismatched_mesh_names()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Mesh datablock is named '{}'".format(
                object_name,
                data["mesh_name"],
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
    fixed = fix_objects_with_mismatched_mesh_names(result_data)

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

def get_objects_with_mismatched_mesh_names(objects=None):
    """
    Finds mesh objects whose object name does not match
    their mesh datablock name.

    Example:
        Object name: "Character_Body"
        Mesh name:   "Cube"
        -> FAIL

        Object name: "Character_Body"
        Mesh name:   "Character_Body"
        -> PASS

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Character_Body": {
                "object_name": "Character_Body",
                "mesh_name": "Cube",
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        # Only check mesh objects.
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        object_name = obj.name
        mesh_name = obj.data.name

        if object_name == mesh_name:
            continue

        failed_objects[object_name] = {
            "object_name": object_name,
            "mesh_name": mesh_name,
        }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_with_mismatched_mesh_names(result_data):
    """
    Renames mesh datablocks to match their object names.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:

        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        if obj.type != "MESH" or obj.data is None:
            continue

        old_mesh_name = obj.data.name

        obj.data.name = obj.name

        fixed_objects[obj.name] = {
            "old_mesh_name": old_mesh_name,
            "new_mesh_name": obj.data.name,
        }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }
