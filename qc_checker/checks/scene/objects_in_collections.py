# Blender imports
import bpy



# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Objects in Collections"
DESCRIPTION = (
    "Checks if objects are linked directly to the Scene Collection "
    "root, bypassing every named collection."
)
WHY = (
    "Helps you keep your scene organized. It lets you manage large projects, "
    "hide or show groups of items at once, and apply changes to "
    "many objects easily."
)


# -------------------------------------------------------------------------
# Main
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
# Find
# -------------------------------------------------------------------------

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

        # Ignore externally linked/library objects. These are read-only
        # from the current file and should not fail local organization QC.
        if is_linked_object(
            obj
        ):
            continue

        failed_objects[obj.name] = {
            "issue": "Linked directly to the Scene Collection root.",
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def is_linked_object(
        obj,
    ):
    """
    Returns True when the object belongs to external linked/library data.

    Checks:
        - Directly linked objects.
        - Library Overrides.
        - Objects whose datablock comes from a linked library.
        - Collection-instance empties whose instance collection is linked.

    Args:
        obj (bpy.types.Object):
            Object to inspect.

    Returns:
        bool
    """
    if obj is None:
        return False

    if obj.library is not None:
        return True

    if getattr(
        obj,
        "override_library",
        None,
    ) is not None:
        return True

    # Collection instances are often local Empty objects whose
    # instance_collection points to a linked library collection.
    # In that case obj.library and obj.data are both local/None,
    # so we must explicitly inspect the instanced collection.
    instance_collection = getattr(
        obj,
        "instance_collection",
        None,
    )

    if (
        instance_collection is not None
        and getattr(
            instance_collection,
            "library",
            None,
        ) is not None
    ):
        return True

    data = getattr(
        obj,
        "data",
        None,
    )

    if (
        data is not None
        and getattr(
            data,
            "library",
            None,
        ) is not None
    ):
        return True

    return False
