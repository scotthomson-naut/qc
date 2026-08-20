# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Action Present"
DESCRIPTION = (
    "Checks for objects that contain empty animation data. "
    "Objects using an Action, NLA strips, or drivers are considered valid."
)
WHY = (
    "Unused animation channels or empty action slots can linger in data blocks, "
    "wasting processing cycles evaluating transforms that do nothing."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds objects that contain animation data but have no usable
    Action, NLA strips, or drivers.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_empty_animation_data()

    issues = []

    for object_name in sorted(
        failed_objects
    ):
        issues.append(
            (
                "Failed object: {} - Animation data exists, "
                "but no Action, NLA strips, or drivers are assigned."
            ).format(
                object_name
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Removes empty animation data from failed objects.

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
    return remove_empty_animation_data(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_empty_animation_data(
        objects=None,
    ):
    """
    Finds objects whose animation_data exists but contains no Action,
    NLA strips, or drivers.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_type": "MESH",
                "has_action": False,
                "has_nla_strips": False,
                "has_drivers": False,
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

        has_action = (
            get_object_action(obj)
            is not None
        )

        has_nla_strips = (
            animation_data_has_nla_strips(
                animation_data
            )
        )

        has_drivers = (
            animation_data_has_drivers(
                animation_data
            )
        )

        if (
            has_action
            or has_nla_strips
            or has_drivers
        ):
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "has_action": has_action,
            "has_nla_strips": has_nla_strips,
            "has_drivers": has_drivers,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def remove_empty_animation_data(
        result_data=None,
    ):
    """
    Clears empty animation data from failed objects.

    The object is checked again before clearing its animation data so
    valid animation added after the QC run is not accidentally removed.

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

    for object_name in failed_objects:
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

        # Revalidate before removing anything.
        if get_object_action(obj) is not None:
            issues.append(
                (
                    'Skipped "{}" because an Action is now assigned.'
                ).format(
                    object_name
                )
            )
            continue

        if animation_data_has_nla_strips(
            animation_data
        ):
            issues.append(
                (
                    'Skipped "{}" because it now contains NLA strips.'
                ).format(
                    object_name
                )
            )
            continue

        if animation_data_has_drivers(
            animation_data
        ):
            issues.append(
                (
                    'Skipped "{}" because it now contains drivers.'
                ).format(
                    object_name
                )
            )
            continue

        try:
            obj.animation_data_clear()

            fixed_objects[object_name] = {
                "animation_data_cleared": True,
            }

        except Exception as error:
            issues.append(
                (
                    'Could not clear animation data from "{}": {}'
                ).format(
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
    Returns the Action assigned to an object.

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


def animation_data_has_nla_strips(
        animation_data,
    ):
    """
    Returns True when animation data contains at least one NLA strip.

    Empty or muted NLA tracks still count only when they contain strips.
    """
    nla_tracks = getattr(
        animation_data,
        "nla_tracks",
        None,
    )

    if not nla_tracks:
        return False

    for track in nla_tracks:
        strips = getattr(
            track,
            "strips",
            None,
        )

        if strips and len(strips) > 0:
            return True

    return False


def animation_data_has_drivers(
        animation_data,
    ):
    """
    Returns True when animation data contains at least one driver.
    """
    drivers = getattr(
        animation_data,
        "drivers",
        None,
    )

    return bool(
        drivers
        and len(drivers) > 0
    )
