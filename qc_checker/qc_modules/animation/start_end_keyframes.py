# Standard python imports
from math import isclose

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates - allo
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_objects_missing_start_end_keys()

    return {
        "issues": [
            "Failed object: {}".format(object_name)
            for object_name in failed_objects
        ],
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_objects_missing_start_end_keys(result_data)

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

def get_objects_missing_start_end_keys(
        objects=None,
        start_frame=None,
        end_frame=None,
        tolerance=1e-5,
    ):
    """
    Finds animated objects whose F-Curves do not contain keys at both
    the start and end of the timeline.

    Supports Blender 5.x layered/slotted Actions.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        start_frame (float | None):
            Required starting frame.
            Defaults to scene.frame_start.

        end_frame (float | None):
            Required ending frame.
            Defaults to scene.frame_end.

        tolerance (float):
            Frame comparison tolerance.

    Returns:
        dict:
        {
            "Cube": {
                "missing_start": [
                    "location[0]"
                ],
                "missing_end": [
                    "rotation_euler[2]"
                ],
                "animated_channels": 2,
            }
        }
    """
    scene = bpy.context.scene

    if objects is None:
        objects = scene.objects

    if start_frame is None:
        start_frame = scene.frame_start

    if end_frame is None:
        end_frame = scene.frame_end

    failed_objects = {}

    for obj in objects:
        animation_data = obj.animation_data

        if (
            animation_data is None
            or animation_data.action is None
        ):
            continue

        fcurves = get_action_fcurves(animation_data)

        if not fcurves:
            continue

        missing_start = []
        missing_end = []

        for fcurve in fcurves:
            channel_name = get_fcurve_channel_name(fcurve)

            has_start_key = any(
                abs(keyframe.co.x - start_frame) <= tolerance
                for keyframe in fcurve.keyframe_points
            )

            has_end_key = any(
                abs(keyframe.co.x - end_frame) <= tolerance
                for keyframe in fcurve.keyframe_points
            )

            if not has_start_key:
                missing_start.append(channel_name)

            if not has_end_key:
                missing_end.append(channel_name)

        if missing_start or missing_end:
            failed_objects[obj.name] = {
                "missing_start": missing_start,
                "missing_end": missing_end,
                "animated_channels": len(fcurves),
            }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_missing_start_end_keys(result_data=None):
    """
    Adds missing keys at the scene start and end frames.

    The inserted key value is evaluated from the existing F-Curve at
    that frame, preserving the curve's current animation behavior.

    Args:
        result_data (dict):
            Result returned by main(), containing:

            {
                "failed_objects": {
                    "ObjectName": {
                        "missing_start": ["location[0]", ...],
                        "missing_end": ["location[1]", ...],
                    }
                }
            }

    Returns:
        dict:
        {
            "issues": [],
            "fixed_objects": {
                "Cube": {
                    "start_keys_added": [...],
                    "end_keys_added": [...]
                }
            }
        }
    """
    scene = bpy.context.scene
    start_frame = scene.frame_start
    end_frame = scene.frame_end

    failed_objects = result_data.get("failed_objects", {})
    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(object_name)
            )
            continue

        animation_data = obj.animation_data

        if (
            animation_data is None
            or animation_data.action is None
        ):
            issues.append(
                "Object has no active action: {}".format(object_name)
            )
            continue

        action = animation_data.action

        missing_start = set(
            object_data.get("missing_start", [])
        )
        missing_end = set(
            object_data.get("missing_end", [])
        )

        start_keys_added = []
        end_keys_added = []

        fcurves = get_action_fcurves(animation_data)
        for fcurve in fcurves:
            channel_name = get_fcurve_channel_name(fcurve)

            if channel_name in missing_start:
                insert_fcurve_key(
                    fcurve=fcurve,
                    frame=start_frame,
                )
                start_keys_added.append(channel_name)

            if channel_name in missing_end:
                insert_fcurve_key(
                    fcurve=fcurve,
                    frame=end_frame,
                )
                end_keys_added.append(channel_name)

        if start_keys_added or end_keys_added:
            fixed_objects[object_name] = {
                "start_keys_added": start_keys_added,
                "end_keys_added": end_keys_added,
            }

    bpy.context.view_layer.update()

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }


# -------------------------
# Helpers
# -------------------------

def get_fcurve_channel_name(fcurve):
    """
    Returns a unique readable identifier for an F-Curve.

    Examples:
        location[0]
        rotation_euler[2]
        pose.bones["Hand.L"].rotation_quaternion[1]
    """
    return "{}[{}]".format(
        fcurve.data_path,
        fcurve.array_index,
    )


def insert_fcurve_key(fcurve, frame):
    """
    Inserts a keyframe into an F-Curve at the specified frame.

    The value is evaluated from the existing curve at that frame.

    Args:
        fcurve (bpy.types.FCurve): Target F-Curve.
        frame (float): Frame at which to insert the key.

    Returns:
        bpy.types.Keyframe: Newly inserted or existing keyframe.
    """
    value = fcurve.evaluate(frame)

    keyframe = fcurve.keyframe_points.insert(
        frame=frame,
        value=value,
        options={"FAST"},
    )

    # Preserve the curve shape as closely as possible.
    keyframe.interpolation = get_nearest_interpolation(
        fcurve,
        frame,
    )

    fcurve.update()

    return keyframe


def get_nearest_interpolation(fcurve, frame):
    """
    Gets interpolation from the nearest existing keyframe.

    Args:
        fcurve (bpy.types.FCurve): F-Curve being modified.
        frame (float): Frame where the new key is inserted.

    Returns:
        str: Blender keyframe interpolation identifier.
    """
    nearest_key = None
    nearest_distance = None

    for keyframe in fcurve.keyframe_points:
        key_frame = keyframe.co.x

        # Ignore a key already located at the insertion frame.
        if abs(key_frame - frame) < 1e-5:
            continue

        distance = abs(key_frame - frame)

        if nearest_distance is None or distance < nearest_distance:
            nearest_key = keyframe
            nearest_distance = distance

    if nearest_key is not None:
        return nearest_key.interpolation

    return "BEZIER"


def get_action_fcurves(animation_data):
    """
    Returns F-Curves from an object's assigned Action.

    Supports:
        - Blender 5.x layered/slotted Actions.
        - Older legacy Actions where action.fcurves exists.

    Args:
        animation_data (bpy.types.AnimData):
            Animation data belonging to an object.

    Returns:
        list[bpy.types.FCurve]:
            F-Curves associated with the object's active Action slot.
    """
    if animation_data is None:
        return []

    action = animation_data.action

    if action is None:
        return []

    # ---------------------------------------------------------
    # Legacy Blender Action support
    # ---------------------------------------------------------
    legacy_fcurves = getattr(action, "fcurves", None)

    if legacy_fcurves is not None:
        return list(legacy_fcurves)

    # ---------------------------------------------------------
    # Blender 4.4+ layered/slotted Action support
    # ---------------------------------------------------------
    action_slot = getattr(
        animation_data,
        "action_slot",
        None,
    )

    if action_slot is None:
        return []

    fcurves = []

    for layer in action.layers:
        for strip in layer.strips:

            # Only keyframe strips provide channelbag().
            channelbag_method = getattr(
                strip,
                "channelbag",
                None,
            )

            if not callable(channelbag_method):
                continue

            channelbag = strip.channelbag(
                action_slot,
                ensure=False,
            )

            if channelbag is None:
                continue

            fcurves.extend(channelbag.fcurves)

    return fcurves
