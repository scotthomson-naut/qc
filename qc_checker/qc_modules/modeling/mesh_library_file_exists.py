# Standard python imports
import os

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "Mesh Library File Exists"
DESCRIPTION = (
    "Checks if linked Mesh datablocks can still reach their source "
    "library file"
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
    failed_objects = get_objects_with_missing_library()

    return {
        "issues": [
            "Failed object: {} - Linked to a missing library file: {}".format(
                object_name,
                data["library_filepath"],
            )
            for object_name, data in failed_objects.items()
        ],
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# A missing library file needs an artist to relink the datablock to
# the correct path, or track down where the source file moved to -
# nothing here is safe to resolve automatically. Same convention as
# mesh_missing_datablock.py: no fix() defined, so the tool shows no
# Fix button for this row.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_missing_library(objects=None):
    """
    Finds Mesh objects whose datablock is linked from another .blend
    file, where that source file can no longer be found on disk.

    Note:
        A linked datablock keeps working off Blender's cached copy
        for the current session even after its source file is moved,
        renamed, or deleted - this check exists to surface that
        before it becomes a surprise on a fresh machine or after a
        file reload.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "library_filepath": "//../assets/props.blend",
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

        library = obj.data.library

        if library is None:
            continue

        filepath = bpy.path.abspath(library.filepath)

        if not os.path.exists(filepath):
            failed_objects[obj.name] = {
                "library_filepath": library.filepath,
            }

    return failed_objects
