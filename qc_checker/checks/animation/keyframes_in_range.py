# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "Keyframes in Range"
DESCRIPTION = (
    "Checks for objects with keyframes before scene start frame "
    "or after the scene end frame."
)
WHY = (
    "Prevents unexpected object snapping, "
    "broken render loops, and export errors."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    """
    failed_objects = get_objects_with_keyframes_outside_timeline()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Keyframes outside timeline: {}".format(
                object_name,
                ", ".join(
                    format_frame(frame)
                    for frame in data["outside_frames"]
                ),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_keyframes_outside_timeline(
        objects=None,
        frame_start=None,
        frame_end=None,
    ):
    """
    Finds objects with keyframes outside the current scene timeline.

    Checks:
        - Object Actions
        - Layered Actions in newer Blender versions

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

        frame_start (float | None):
            First valid frame.
            Defaults to scene.frame_start.

        frame_end (float | None):
            Last valid frame.
            Defaults to scene.frame_end.

    Returns:
        dict:
        {
            "Cube": {
                "frame_start": 1,
                "frame_end": 250,
                "outside_frames": [-10.0, 275.0],
                "before_start": [-10.0],
                "after_end": [275.0],
                "keyframes": [
                    {
                        "frame": -10.0,
                        "data_path": "location",
                        "array_index": 0,
                    },
                    {
                        "frame": 275.0,
                        "data_path": "rotation_euler",
                        "array_index": 2,
                    },
                ],
            },
        }
    """
    scene = bpy.context.scene

    if objects is None:
        objects = scene.objects

    if frame_start is None:
        frame_start = scene.frame_start

    if frame_end is None:
        frame_end = scene.frame_end

    failed_objects = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and should not be reported by local QC checks.
        if obj.library is not None:
            continue

        action = get_object_action(obj)

        if action is None:
            continue

        outside_keyframes = []

        for fcurve in get_action_fcurves(action):
            for keyframe_point in fcurve.keyframe_points:
                frame = float(
                    keyframe_point.co.x
                )

                if (
                    frame_start
                    <= frame
                    <= frame_end
                ):
                    continue

                outside_keyframes.append({
                    "frame": frame,
                    "data_path": fcurve.data_path,
                    "array_index": fcurve.array_index,
                })

        if not outside_keyframes:
            continue

        outside_keyframes.sort(
            key=lambda item: (
                item["frame"],
                item["data_path"],
                item["array_index"],
            )
        )

        before_start = sorted({
            item["frame"]
            for item in outside_keyframes
            if item["frame"] < frame_start
        })

        after_end = sorted({
            item["frame"]
            for item in outside_keyframes
            if item["frame"] > frame_end
        })

        failed_objects[obj.name] = {
            "frame_start": frame_start,
            "frame_end": frame_end,
            "outside_frames": sorted({
                item["frame"]
                for item in outside_keyframes
            }),
            "before_start": before_start,
            "after_end": after_end,
            "keyframes": outside_keyframes,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_object_action(obj):
    """
    Returns the active Action assigned to an object.
    """
    animation_data = obj.animation_data

    if animation_data is None:
        return None

    return animation_data.action


def get_action_fcurves(action):
    """
    Returns FCurves from both legacy and layered Actions.

    Supports older Blender Actions using:
        action.fcurves

    Also attempts to support newer layered Actions.
    """
    found_fcurves = []
    seen_fcurves = set()

    # ---------------------------------------------------------
    # Legacy Actions
    # ---------------------------------------------------------

    action_fcurves = getattr(
        action,
        "fcurves",
        None,
    )

    if action_fcurves is not None:
        for fcurve in action_fcurves:
            pointer = fcurve.as_pointer()

            if pointer in seen_fcurves:
                continue

            seen_fcurves.add(pointer)
            found_fcurves.append(fcurve)

    # ---------------------------------------------------------
    # Layered Actions
    # ---------------------------------------------------------

    layers = getattr(
        action,
        "layers",
        None,
    )

    if layers is not None:
        for layer in layers:
            strips = getattr(
                layer,
                "strips",
                [],
            )

            for strip in strips:
                channelbags = getattr(
                    strip,
                    "channelbags",
                    [],
                )

                for channelbag in channelbags:
                    fcurves = getattr(
                        channelbag,
                        "fcurves",
                        [],
                    )

                    for fcurve in fcurves:
                        pointer = fcurve.as_pointer()

                        if pointer in seen_fcurves:
                            continue

                        seen_fcurves.add(pointer)
                        found_fcurves.append(
                            fcurve
                        )

    return found_fcurves


def format_frame(frame):
    """
    Displays whole frames without a decimal.
    """
    if float(frame).is_integer():
        return str(
            int(frame)
        )

    return "{:.3f}".format(
        frame
    ).rstrip("0").rstrip(".")
