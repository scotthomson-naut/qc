"""Reports local object datablocks that are not linked to any scene."""

import bpy


SEVERITY = "warning"
LABEL = "Unlinked Object Datablocks"
DESCRIPTION = (
    "Checks for local object datablocks that exist in the Blender file "
    "but are not linked to any scene."
)
WHY = (
    "Unlinked objects can be reported by checks that scan all file data, "
    "but they cannot be selected or safely fixed through a scene context."
)


def main():
    """Return every local object datablock with no scene users."""
    failed_objects = find_unlinked_object_datablocks()

    return {
        "issues": [
            (
                'Object "{}" exists in the file but is not linked '
                "to any scene."
            ).format(object_name)
            for object_name in failed_objects
        ],
        "failed_objects": failed_objects,
        "can_auto_fix": False,
    }


def find_unlinked_object_datablocks(objects=None):
    """
    Find local objects that have no scene users.

    This check intentionally scans bpy.data.objects instead of using
    get_qc_objects(). Its purpose is to diagnose objects outside normal QC
    scene scope. Linked library objects are excluded because this file does
    not own them and cannot safely clean them up.
    """
    if objects is None:
        objects = bpy.data.objects

    failed_objects = {}

    for obj in objects:
        if obj is None:
            continue

        if getattr(obj, "library", None) is not None:
            continue

        if tuple(getattr(obj, "users_scene", ())) :
            continue

        failed_objects[obj.name] = {
            "issue": "Object datablock is not linked to any scene.",
        }

    return failed_objects


# No automatic fix is provided. Linking the object to a scene or deleting it
# is a content decision that must be made by the user.
