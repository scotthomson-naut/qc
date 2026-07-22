# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """

    # Call
    failed_objects = get_objects_with_keyframes()

    return {
        "issues": [
            "Failed object: {}".format(name)
            for name in failed_objects
        ],
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Args:
        result_data (list[str]): List of object names.
    Returns:
        dict: Issues
    """
    failed_objects = result_data.get("failed_objects", [])

    # Call Function
    remove_keyframes_from_objects(failed_objects)

    return {
        "issues": []
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------


def get_objects_with_keyframes():
    """
    Gets object with key frames.

    Returns:
        dict:
        {
            "Cube": {"haskeys": True},
            ...
        }
    """
    keyed_objects = {}

    for obj in bpy.data.objects:
        if object_has_keyframes(obj):
            keyed_objects[obj.name] = {"haskeys": True}

    return keyed_objects


def object_has_keyframes(obj):
    """
    Check if object has keyframes.

    Args:
        obj (object): List of object names.
    Returns:
        bool: True or False
    """
    anim_data = obj.animation_data

    if not anim_data or not anim_data.action:
        return False

    action = anim_data.action

    # Old action system
    if hasattr(action, "fcurves"):
        if len(action.fcurves) > 0:
            return True

    # Blender 5.0 layered action system
    if hasattr(action, "layers"):
        action_slot = getattr(anim_data, "action_slot", None)

        for layer in action.layers:
            for strip in layer.strips:
                # In Blender 5, channelbag is a function
                if hasattr(strip, "channelbag") and action_slot:
                    channelbag = strip.channelbag(action_slot)
                    if channelbag and hasattr(channelbag, "fcurves"):
                        if len(channelbag.fcurves) > 0:
                            return True

    return False


# -------------------------
# Fix
# -------------------------

def remove_keyframes_from_objects(object_names):
    """
    Remove all keyframes from the specified objects.

    Args:
        object_names (list[str]): List of object names.
    Returns:
        list[str]: Names of objects that were successfully processed.
    """
    removed = []

    for name in object_names:
        obj = bpy.data.objects.get(name)

        if obj is None:
            print(f"Object not found: {name}")
            continue

        if obj.animation_data:
            obj.animation_data_clear()
            removed.append(name)
            print(f"Removed animation from: {name}")

    return removed
