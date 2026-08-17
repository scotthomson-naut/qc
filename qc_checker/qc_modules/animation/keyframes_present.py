# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Keyframes Present"
DESCRIPTION = (
    "Checks for objects that have animation data and an assigned Action, "
    "but the Action contains no keyframes."
)
WHY = (
    "Helps clean up orphan data blocks, "
    "prevent file bloat, and avoid unexpected evaluation overhead or "
    "confusion during rigging and non-linear animation mixing."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds objects with an assigned Action containing zero keyframes.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_empty_actions()
    )

    issues = []

    for object_name, data in sorted(
        failed_objects.items()
    ):
        issues.append(
            (
                'Failed object: {} - Action "{}" '
                "contains zero keyframes."
            ).format(
                object_name,
                data["action_name"],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Unassigns Actions containing zero keyframes from failed objects.

    The empty Action datablock itself is not deleted because another
    object or datablock may still reference it.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    return unassign_empty_actions(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_empty_actions(
        objects=None,
    ):
    """
    Finds objects whose assigned Action contains no keyframes.

    Supports both legacy Actions and Blender's layered Action system.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_type": "MESH",
                "action_name": "CubeAction",
                "fcurve_count": 3,
                "keyframe_count": 0,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and should not be reported by local QC checks.
        if obj.library is not None:
            continue

        animation_data = getattr(
            obj,
            "animation_data",
            None,
        )

        if animation_data is None:
            continue

        action = get_object_action(
            obj
        )

        if action is None:
            continue

        fcurves = get_action_fcurves(
            action
        )

        keyframe_count = count_action_keyframes(
            action,
            fcurves=fcurves,
        )

        if keyframe_count > 0:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "action_name": action.name,
            "fcurve_count": len(fcurves),
            "keyframe_count": keyframe_count,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def unassign_empty_actions(
        result_data=None,
    ):
    """
    Unassigns empty Actions from failed objects.

    Each object and Action is revalidated before making changes. This
    prevents an Action that gained keyframes after the QC run from being
    removed accidentally.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if not isinstance(
        result_data,
        dict,
    ):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        failed_objects = {}

    fixed_objects = {}
    issues = []

    for object_name, stored_data in failed_objects.items():
        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        if obj.library is not None:
            continue

        animation_data = getattr(
            obj,
            "animation_data",
            None,
        )

        if animation_data is None:
            continue

        action = get_object_action(
            obj
        )

        if action is None:
            continue

        expected_action_name = ""

        if isinstance(
            stored_data,
            dict,
        ):
            expected_action_name = (
                stored_data.get(
                    "action_name",
                    "",
                )
            )

        if (
            expected_action_name
            and action.name != expected_action_name
        ):
            issues.append(
                (
                    'Skipped "{}" because its assigned Action '
                    'changed from "{}" to "{}".'
                ).format(
                    object_name,
                    expected_action_name,
                    action.name,
                )
            )
            continue

        keyframe_count = count_action_keyframes(
            action
        )

        if keyframe_count > 0:
            issues.append(
                (
                    'Skipped "{}" because Action "{}" now '
                    "contains {} keyframe{}."
                ).format(
                    object_name,
                    action.name,
                    keyframe_count,
                    ""
                    if keyframe_count == 1
                    else "s",
                )
            )
            continue

        action_name = action.name

        try:
            animation_data.action = None

            fixed_objects[object_name] = {
                "action_unassigned": action_name,
            }

        except Exception as error:
            issues.append(
                (
                    'Could not unassign Action "{}" '
                    'from object "{}": {}'
                ).format(
                    action_name,
                    object_name,
                    error,
                )
            )

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_object_action(obj):
    """
    Returns the Action currently assigned to an object.

    Args:
        obj (bpy.types.Object):
            Object to inspect.

    Returns:
        bpy.types.Action | None
    """
    animation_data = getattr(
        obj,
        "animation_data",
        None,
    )

    if animation_data is None:
        return None

    return getattr(
        animation_data,
        "action",
        None,
    )


def get_action_fcurves(action):
    """
    Returns every unique FCurve contained in an Action.

    Supports:

        - Legacy Action.fcurves
        - Layered Actions using:
          layers -> strips -> channelbags -> fcurves

    Args:
        action (bpy.types.Action):
            Action to inspect.

    Returns:
        list[bpy.types.FCurve]:
            Unique FCurves found in the Action.
    """
    if action is None:
        return []

    fcurves = []
    seen_pointers = set()

    def add_fcurve(fcurve):
        if fcurve is None:
            return

        try:
            pointer = fcurve.as_pointer()
        except Exception:
            pointer = id(fcurve)

        if pointer in seen_pointers:
            return

        seen_pointers.add(
            pointer
        )

        fcurves.append(
            fcurve
        )

    # ---------------------------------------------------------
    # Legacy Actions
    # ---------------------------------------------------------

    legacy_fcurves = getattr(
        action,
        "fcurves",
        None,
    )

    if legacy_fcurves is not None:
        try:
            for fcurve in legacy_fcurves:
                add_fcurve(
                    fcurve
                )
        except Exception:
            pass

    # ---------------------------------------------------------
    # Layered Actions
    # ---------------------------------------------------------

    layers = getattr(
        action,
        "layers",
        None,
    )

    if layers is not None:
        try:
            for layer in layers:
                strips = getattr(
                    layer,
                    "strips",
                    None,
                )

                if strips is None:
                    continue

                for strip in strips:
                    channelbags = getattr(
                        strip,
                        "channelbags",
                        None,
                    )

                    if channelbags is None:
                        continue

                    for channelbag in channelbags:
                        bag_fcurves = getattr(
                            channelbag,
                            "fcurves",
                            None,
                        )

                        if bag_fcurves is None:
                            continue

                        for fcurve in bag_fcurves:
                            add_fcurve(
                                fcurve
                            )

        except Exception:
            pass

    return fcurves


def count_action_keyframes(
        action,
        fcurves=None,
    ):
    """
    Counts all keyframe points contained in an Action.

    Args:
        action (bpy.types.Action):
            Action to inspect.

        fcurves (list | None):
            Optional previously collected FCurves.

    Returns:
        int:
            Total number of keyframe points.
    """
    if action is None:
        return 0

    if fcurves is None:
        fcurves = get_action_fcurves(
            action
        )

    keyframe_count = 0

    for fcurve in fcurves:
        keyframe_points = getattr(
            fcurve,
            "keyframe_points",
            None,
        )

        if keyframe_points is None:
            continue

        keyframe_count += len(
            keyframe_points
        )

    return keyframe_count
