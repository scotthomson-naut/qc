# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Mesh Datablock Exists"
DESCRIPTION = (
    "Checks if Mesh objects have a mesh datablock assigned"
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
    failed_objects = get_objects_missing_datablock()

    return {
        "issues": [
            "Failed object: {} - Mesh object has no datablock assigned".format(
                object_name
            )
            for object_name in failed_objects
        ],
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# A mesh object with no datablock assigned can't be resolved
# automatically - there's no way to guess which mesh the artist
# intended to assign, or whether the object itself is no longer
# needed and should just be deleted. Requires manual review, so this
# module omits fix() entirely, same as ngon_detection.py and
# names_no_defaults.py do for their own manual-only checks. No fix()
# defined means the tool shows no Fix button for this row.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_missing_datablock(objects=None):
    """
    Finds Mesh-type objects that have no mesh datablock assigned.

    Note:
        This is a defensive check against file-level corruption (a
        mangled .blend, a bad import/export round-trip, or a tool
        writing to Blender's low-level data structures directly). It
        is not straightforward to reproduce through a live Blender/
        Python session: Object.type is derived from Object.data, so
        setting obj.data = None converts the object to an EMPTY
        rather than leaving a MESH object with no data assigned.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "issue": "Mesh object has no datablock assigned.",
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
            failed_objects[obj.name] = {
                "issue": "Mesh object has no datablock assigned.",
            }

    return failed_objects
