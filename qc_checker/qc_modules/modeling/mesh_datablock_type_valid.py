# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Mesh Datablock Type Valid"
DESCRIPTION = (
    "Checks if Mesh objects' datablock is actually a valid Mesh type"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_invalid_datablock_type()

    return {
        "issues": [
            "Failed object: {} - Datablock '{}' is not a valid Mesh type".format(
                object_name,
                data["datablock"],
            )
            for object_name, data in failed_objects.items()
        ],
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# A MESH-type object pointing at a datablock that isn't actually a
# Mesh is a sign of genuine file-level corruption - there's no safe
# automatic action to take (reassigning or deleting the object's data
# is a real content decision, not a repair). No fix() defined, so the
# tool shows no Fix button for this row.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_invalid_datablock_type(objects=None):
    """
    Finds Mesh-type objects whose datablock isn't actually a
    bpy.types.Mesh.

    Note:
        This is a defensive check against genuine file-level
        corruption, and, like mesh_missing_datablock.py, is not
        straightforward to reproduce through a live Blender/Python
        session: Object.data's setter validates that an assigned ID
        matches the object's type, so assigning e.g. a Camera
        datablock to a MESH-type object should be rejected by the API
        itself rather than accepted silently. Treat this one as
        verified by code review rather than a live repro, unless you
        have a deliberately corrupted .blend file to test against.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "datablock": "<repr of the offending datablock>",
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        if not isinstance(obj.data, bpy.types.Mesh):
            failed_objects[obj.name] = {
                "datablock": repr(obj.data),
            }

    return failed_objects
