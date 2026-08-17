# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Animated Values"
DESCRIPTION = (
    "Checks for objects with keyed transform channels where none of "
    "the keyed transform values actually change. "
)
WHY = (
    "Unchanged keys often occur when using aggressive auto-keyframing or "
    "bulk keying sets, creating static F-curves that complicate future editing."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "minimum_keyframes": {
        "type": "int",
        "label": "Minimum Keyframes",
        "description": (
            "Minimum number of keys required before a constant "
            "F-Curve is reported."
        ),
        "default": 2,
        "min": 2,
        "max": 1000,
    },

    "value_tolerance": {
        "type": "float",
        "label": "Value Tolerance",
        "description": (
            "Maximum difference allowed between key values for "
            "them to be considered identical."
        ),
        "default": 0.00001,
        "min": 0.0,
        "max": 1.0,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds objects whose keyed transform F-Curves are all constant.

    Args:
        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_objects = (
        get_objects_with_constant_fcurves(
            settings=settings,
        )
    )

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        constant_curves = object_data.get(
            "constant_fcurves",
            [],
        )

        issues.append(
            (
                "Failed object: {} - all {} keyed transform "
                "F-Curve{} contain constant values."
            ).format(
                object_name,
                len(constant_curves),
                ""
                if len(constant_curves) == 1
                else "s",
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "settings": settings,
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Reduces each constant F-Curve to one keyframe.

    The first keyframe is preserved and all later keyframes on that
    F-Curve are removed.

    Args:
        result_data (dict | None):
            Result returned by main().

        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    return reduce_constant_fcurves(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_constant_fcurves(
        objects=None,
        settings=None,
    ):
    """
    Finds objects whose eligible keyed transform F-Curves are all constant.

    An object passes as soon as at least one eligible keyed transform
    F-Curve changes value. Constant location, rotation, or scale channels
    therefore do not fail an object that is genuinely animated elsewhere.

    Only F-Curves belonging to the object's assigned Action are checked.
    Both legacy and layered Blender Actions are supported.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to current scene objects.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "Cube": {
                "object_type": "MESH",
                "action_name": "CubeAction",
                "constant_fcurve_count": 3,
                "constant_fcurves": [
                    {
                        "data_path": "location",
                        "array_index": 0,
                        "keyframe_count": 3,
                        "value": 2.0,
                        "frames": [1.0, 20.0, 40.0],
                    }
                ],
            }
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    minimum_keyframes = max(
        2,
        int(
            settings["minimum_keyframes"]
        ),
    )

    value_tolerance = max(
        0.0,
        float(
            settings["value_tolerance"]
        ),
    )

    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and should not be reported by local QC checks.
        if obj.library is not None:
            continue

        action = get_object_action(
            obj
        )

        if action is None:
            continue

        constant_fcurves = []
        changing_fcurves = []
        eligible_fcurve_count = 0

        for fcurve in get_action_fcurves(
            action
        ):
            if not is_transform_fcurve(
                fcurve
            ):
                continue

            keyframe_points = getattr(
                fcurve,
                "keyframe_points",
                None,
            )

            if keyframe_points is None:
                continue

            if len(keyframe_points) < minimum_keyframes:
                continue

            eligible_fcurve_count += 1

            values = [
                float(key.co.y)
                for key in keyframe_points
            ]

            curve_data = {
                "data_path": fcurve.data_path,
                "array_index": fcurve.array_index,
                "keyframe_count": len(
                    keyframe_points
                ),
                "frames": [
                    float(key.co.x)
                    for key in keyframe_points
                ],
            }

            if values_are_constant(
                values,
                tolerance=value_tolerance,
            ):
                curve_data["value"] = values[0]
                constant_fcurves.append(
                    curve_data
                )
            else:
                curve_data["minimum_value"] = min(values)
                curve_data["maximum_value"] = max(values)
                changing_fcurves.append(
                    curve_data
                )

        # No eligible transform animation means there is nothing to test.
        if not eligible_fcurve_count:
            continue

        # The object passes when any keyed transform channel changes.
        if changing_fcurves:
            continue

        # At this point every eligible keyed transform curve is constant.
        failed_objects[obj.name] = {
            "object_type": obj.type,
            "action_name": action.name,
            "eligible_fcurve_count": eligible_fcurve_count,
            "constant_fcurve_count": len(
                constant_fcurves
            ),
            "constant_fcurves": constant_fcurves,
            "changing_fcurves": changing_fcurves,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def reduce_constant_fcurves(
        result_data=None,
        settings=None,
    ):
    """
    Removes redundant keys from constant F-Curves.

    The earliest keyframe is kept. Every later keyframe on the same
    constant curve is removed.

    The Action and curve are revalidated before modification.

    Args:
        result_data (dict | None):
            Result returned by main().

        settings (dict | None):
            Resolved settings.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    value_tolerance = max(
        0.0,
        float(
            settings["value_tolerance"]
        ),
    )

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

    for object_name, object_data in failed_objects.items():
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

        action = get_object_action(
            obj
        )

        if action is None:
            issues.append(
                (
                    'Skipped "{}" because it no longer has '
                    "an assigned Action."
                ).format(
                    object_name
                )
            )
            continue

        expected_action_name = ""

        if isinstance(
            object_data,
            dict,
        ):
            expected_action_name = (
                object_data.get(
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
                    'Skipped "{}" because its Action changed '
                    'from "{}" to "{}".'
                ).format(
                    object_name,
                    expected_action_name,
                    action.name,
                )
            )
            continue

        stored_curves = object_data.get(
            "constant_fcurves",
            [],
        )

        if not isinstance(
            stored_curves,
            list,
        ):
            continue

        fixed_curve_count = 0
        removed_key_count = 0

        for curve_data in stored_curves:
            if not isinstance(
                curve_data,
                dict,
            ):
                continue

            data_path = curve_data.get(
                "data_path",
                "",
            )

            array_index = int(
                curve_data.get(
                    "array_index",
                    0,
                )
            )

            fcurve = find_matching_fcurve(
                action,
                data_path,
                array_index,
            )

            if fcurve is None:
                issues.append(
                    (
                        'Could not find F-Curve "{}[{}]" '
                        'on object "{}".'
                    ).format(
                        data_path,
                        array_index,
                        object_name,
                    )
                )
                continue

            keyframe_points = (
                fcurve.keyframe_points
            )

            if len(keyframe_points) < 2:
                continue

            values = [
                float(key.co.y)
                for key in keyframe_points
            ]

            # Do not alter a curve that changed after the check ran.
            if not values_are_constant(
                values,
                tolerance=value_tolerance,
            ):
                issues.append(
                    (
                        'Skipped "{}[{}]" on "{}" because its '
                        "key values are no longer constant."
                    ).format(
                        data_path,
                        array_index,
                        object_name,
                    )
                )
                continue

            # Sort by frame so the earliest key is preserved.
            points_to_remove = sorted(
                list(keyframe_points),
                key=lambda key: key.co.x,
            )[1:]

            for keyframe_point in reversed(
                points_to_remove
            ):
                keyframe_points.remove(
                    keyframe_point,
                    fast=True,
                )

            fcurve.update()

            fixed_curve_count += 1
            removed_key_count += len(
                points_to_remove
            )

        if fixed_curve_count:
            fixed_objects[object_name] = {
                "fixed_fcurve_count": fixed_curve_count,
                "removed_keyframe_count": removed_key_count,
            }

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


def get_action_fcurves(action):
    """
    Returns all unique F-Curves from an Action.

    Supports:

        - Legacy action.fcurves
        - Layered Actions using:
          layers -> strips -> channelbags -> fcurves

    Args:
        action (bpy.types.Action):
            Action to inspect.

    Returns:
        list[bpy.types.FCurve]
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

    # Legacy Actions.
    action_fcurves = getattr(
        action,
        "fcurves",
        None,
    )

    if action_fcurves is not None:
        try:
            for fcurve in action_fcurves:
                add_fcurve(
                    fcurve
                )
        except Exception:
            pass

    # Layered Actions.
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



def is_transform_fcurve(fcurve):
    """
    Returns True when an F-Curve controls an object transform channel.

    This intentionally checks direct object transforms only. It excludes
    material values, custom properties, constraints, shape keys, and pose
    bone channels.
    """
    if fcurve is None:
        return False

    transform_data_paths = {
        "location",
        "rotation_euler",
        "rotation_quaternion",
        "rotation_axis_angle",
        "scale",
        "delta_location",
        "delta_rotation_euler",
        "delta_rotation_quaternion",
        "delta_scale",
    }

    return getattr(
        fcurve,
        "data_path",
        "",
    ) in transform_data_paths

def values_are_constant(
        values,
        tolerance=0.00001,
    ):
    """
    Returns True when every value is within tolerance of the first value.

    Args:
        values (iterable[float]):
            Values to compare.

        tolerance (float):
            Maximum allowed difference.

    Returns:
        bool
    """
    if not values:
        return False

    first_value = float(
        values[0]
    )

    return all(
        abs(float(value) - first_value)
        <= tolerance
        for value in values[1:]
    )


def find_matching_fcurve(
        action,
        data_path,
        array_index,
    ):
    """
    Finds an Action F-Curve by data path and array index.

    Args:
        action (bpy.types.Action):
            Action to search.

        data_path (str):
            F-Curve RNA data path.

        array_index (int):
            F-Curve component index.

    Returns:
        bpy.types.FCurve | None
    """
    for fcurve in get_action_fcurves(
        action
    ):
        if (
            fcurve.data_path == data_path
            and fcurve.array_index == array_index
        ):
            return fcurve

    return None
