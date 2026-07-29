# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "warning"
LABEL = "Objects Outside Collections"
DESCRIPTION = (
    "Checks if objects are linked directly to the Scene Collection "
    "root, bypassing every named collection. Distinct from an object "
    "sitting inside a collection that still has Blender's default "
    "'Collection' name - that's still organized, just possibly "
    "poorly named. This check is about objects with no organization "
    "at all."
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
    failed_objects = get_objects_in_scene_root()

    issues = [
        "Failed object: {} - Linked directly to the Scene Collection "
        "root, not inside any named collection".format(
            object_name
        )
        for object_name in failed_objects
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Moving an object into "a" collection to resolve this requires
# deciding which collection it belongs in - that's a real content
# decision only an artist can make, not something safe to guess at
# automatically.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_in_scene_root(scene=None):
    """
    Finds objects linked directly to the Scene Collection root.

    Note:
        scene.collection is the scene's hidden root collection - not
        a real, named collection you interact with in the Outliner.
        scene.collection.objects lists only objects linked directly
        to that root, not objects that are inside a named
        sub-collection (even the default-named "Collection").

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "Cube": {
                "issue": "Linked directly to the Scene Collection root.",
            },
            ...
        }
    """
    if scene is None:
        scene = bpy.context.scene

    failed_objects = {}

    for obj in scene.collection.objects:
        failed_objects[obj.name] = {
            "issue": "Linked directly to the Scene Collection root.",
        }

    return failed_objects