# Standard Python imports
import math

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Output Frame Range"
DESCRIPTION = (
    "Checks whether the scene render frame range matches the frame range "
    "used by object Actions and NLA strips."
)
WHY = (
    "Ensures that your final animation renders completely without cutting "
    "off early or wasting time rendering empty static frames."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "start_padding": {
        "type": "int",
        "label": "Start Padding",
        "description": (
            "Number of frames to include before the first animated frame."
        ),
        "default": 0,
        "min": 0,
        "max": 10000,
    },

    "end_padding": {
        "type": "int",
        "label": "End Padding",
        "description": (
            "Number of frames to include after the last animated frame."
        ),
        "default": 0,
        "min": 0,
        "max": 10000,
    },

    "allowed_difference": {
        "type": "int",
        "label": "Allowed Difference",
        "description": (
            "Number of frames the scene range may differ from the "
            "expected animation range without failing."
        ),
        "default": 0,
        "min": 0,
        "max": 10000,
    },

    "include_muted_nla": {
        "type": "bool",
        "label": "Include Muted NLA",
        "description": (
            "Include muted NLA tracks and strips when calculating "
            "the expected animation range."
        ),
        "default": False,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Compares the scene render range against the expected animation range.

    The expected range is calculated from:

        - Keyframes in assigned object Actions
        - NLA strip frame ranges

    Args:
        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_settings": dict,
            "animation_range": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    scene = bpy.context.scene

    animation_data = get_scene_animation_range(
        scene=scene,
        settings=settings,
    )

    issues = []
    failed_settings = {}

    if animation_data is None:
        return {
            "issues": [],
            "failed_settings": {},
            "animation_range": None,
            "settings": settings,
        }

    animation_start = animation_data[
        "animation_start"
    ]

    animation_end = animation_data[
        "animation_end"
    ]

    expected_start = (
        animation_start
        - int(settings["start_padding"])
    )

    expected_end = (
        animation_end
        + int(settings["end_padding"])
    )

    scene_start = int(
        scene.frame_start
    )

    scene_end = int(
        scene.frame_end
    )

    allowed_difference = max(
        0,
        int(settings["allowed_difference"]),
    )

    start_difference = abs(
        scene_start - expected_start
    )

    end_difference = abs(
        scene_end - expected_end
    )

    if start_difference > allowed_difference:
        issues.append(
            (
                "Render start frame is {} but the expected "
                "animation start frame is {}."
            ).format(
                scene_start,
                expected_start,
            )
        )

        failed_settings["frame_start"] = {
            "current": scene_start,
            "expected": expected_start,
            "difference": (
                scene_start - expected_start
            ),
        }

    if end_difference > allowed_difference:
        issues.append(
            (
                "Render end frame is {} but the expected "
                "animation end frame is {}."
            ).format(
                scene_end,
                expected_end,
            )
        )

        failed_settings["frame_end"] = {
            "current": scene_end,
            "expected": expected_end,
            "difference": (
                scene_end - expected_end
            ),
        }

    if scene_start > scene_end:
        issues.append(
            (
                "The render start frame is greater than "
                "the render end frame."
            )
        )

        failed_settings["invalid_scene_range"] = {
            "frame_start": scene_start,
            "frame_end": scene_end,
        }

    return {
        "issues": issues,
        "failed_settings": failed_settings,

        "animation_range": {
            "animation_start": animation_start,
            "animation_end": animation_end,
            "expected_start": expected_start,
            "expected_end": expected_end,
            "scene_start": scene_start,
            "scene_end": scene_end,
            "animated_object_count": len(
                animation_data["animated_objects"]
            ),
            "animated_objects": (
                animation_data["animated_objects"]
            ),
        },

        "settings": settings,
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Sets the scene render range to the expected animation range.

    Args:
        result_data (dict | None):
            Result returned by main().

        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "fixed_settings": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    return set_render_range_to_animation(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_scene_animation_range(
        scene=None,
        settings=None,
    ):
    """
    Calculates the complete animation range used by scene objects.

    Assigned Action keyframes and NLA strip bounds are included.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict | None:
        {
            "animation_start": int,
            "animation_end": int,
            "animated_objects": dict,
        }

        Returns None when no object animation is found.
    """
    if scene is None:
        scene = bpy.context.scene

    if settings is None:
        settings = resolve_settings(SETTINGS)

    include_muted_nla = bool(
        settings["include_muted_nla"]
    )

    all_start_frames = []
    all_end_frames = []

    animated_objects = {}

    for obj in scene.objects:

        if obj.library is not None:
            continue

        object_range = get_object_animation_range(
            obj=obj,
            include_muted_nla=include_muted_nla,
        )

        if object_range is None:
            continue

        object_start = object_range[
            "frame_start"
        ]

        object_end = object_range[
            "frame_end"
        ]

        all_start_frames.append(
            object_start
        )

        all_end_frames.append(
            object_end
        )

        animated_objects[obj.name] = {
            "object_type": obj.type,
            "frame_start": object_start,
            "frame_end": object_end,
            "sources": object_range["sources"],
        }

    if not all_start_frames:
        return None

    return {
        "animation_start": int(
            math.floor(
                min(all_start_frames)
            )
        ),

        "animation_end": int(
            math.ceil(
                max(all_end_frames)
            )
        ),

        "animated_objects": animated_objects,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def set_render_range_to_animation(
        result_data=None,
        settings=None,
    ):
    """
    Changes the scene frame range to match the animation range.

    The current animation range is recalculated before changing the
    scene, so stale QC results are not used.

    Args:
        result_data (dict | None):
            Included for compatibility with the QC framework.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "fixed_settings": dict,
            "issues": list[str],
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    scene = bpy.context.scene

    animation_data = get_scene_animation_range(
        scene=scene,
        settings=settings,
    )

    if animation_data is None:
        return {
            "fixed_settings": {},
            "issues": [
                (
                    "No object Action keyframes or NLA strips "
                    "were found in the scene."
                )
            ],
        }

    expected_start = (
        animation_data["animation_start"]
        - int(settings["start_padding"])
    )

    expected_end = (
        animation_data["animation_end"]
        + int(settings["end_padding"])
    )

    previous_start = int(
        scene.frame_start
    )

    previous_end = int(
        scene.frame_end
    )

    try:
        scene.frame_start = int(
            expected_start
        )

        scene.frame_end = int(
            expected_end
        )

    except Exception as error:
        return {
            "fixed_settings": {},
            "issues": [
                (
                    "Could not update the scene render "
                    "frame range: {}"
                ).format(
                    error
                )
            ],
        }

    return {
        "fixed_settings": {
            "frame_start": {
                "previous": previous_start,
                "current": int(
                    scene.frame_start
                ),
            },

            "frame_end": {
                "previous": previous_end,
                "current": int(
                    scene.frame_end
                ),
            },
        },

        "issues": [],
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_object_animation_range(
        obj,
        include_muted_nla=False,
    ):
    """
    Calculates the animation range used by an object.

    Args:
        obj (bpy.types.Object):
            Object to inspect.

        include_muted_nla (bool):
            Whether muted NLA tracks and strips are included.

    Returns:
        dict | None
    """
    animation_data = getattr(
        obj,
        "animation_data",
        None,
    )

    if animation_data is None:
        return None

    start_frames = []
    end_frames = []
    sources = []

    # ---------------------------------------------------------
    # Assigned Action
    # ---------------------------------------------------------

    action = getattr(
        animation_data,
        "action",
        None,
    )

    if action is not None:
        action_range = get_action_keyframe_range(
            action
        )

        if action_range is not None:
            start_frames.append(
                action_range["frame_start"]
            )

            end_frames.append(
                action_range["frame_end"]
            )

            sources.append({
                "source_type": "ACTION",
                "action_name": action.name,
                "frame_start": (
                    action_range["frame_start"]
                ),
                "frame_end": (
                    action_range["frame_end"]
                ),
                "keyframe_count": (
                    action_range["keyframe_count"]
                ),
            })

    # ---------------------------------------------------------
    # NLA strips
    # ---------------------------------------------------------

    nla_tracks = getattr(
        animation_data,
        "nla_tracks",
        None,
    )

    if nla_tracks is not None:
        for track_index, track in enumerate(
            nla_tracks
        ):
            track_is_muted = bool(
                getattr(
                    track,
                    "mute",
                    False,
                )
            )

            if (
                track_is_muted
                and not include_muted_nla
            ):
                continue

            strips = getattr(
                track,
                "strips",
                None,
            )

            if strips is None:
                continue

            for strip_index, strip in enumerate(
                strips
            ):
                strip_is_muted = bool(
                    getattr(
                        strip,
                        "mute",
                        False,
                    )
                )

                if (
                    strip_is_muted
                    and not include_muted_nla
                ):
                    continue

                strip_start = float(
                    strip.frame_start
                )

                strip_end = float(
                    strip.frame_end
                )

                start_frames.append(
                    strip_start
                )

                end_frames.append(
                    strip_end
                )

                sources.append({
                    "source_type": "NLA_STRIP",
                    "track_name": track.name,
                    "track_index": track_index,
                    "strip_name": strip.name,
                    "strip_index": strip_index,
                    "frame_start": strip_start,
                    "frame_end": strip_end,
                    "track_muted": track_is_muted,
                    "strip_muted": strip_is_muted,
                })

    if not start_frames:
        return None

    return {
        "frame_start": min(
            start_frames
        ),

        "frame_end": max(
            end_frames
        ),

        "sources": sources,
    }


def get_action_keyframe_range(action):
    """
    Returns the range occupied by actual keyframe points in an Action.

    Args:
        action (bpy.types.Action):
            Action to inspect.

    Returns:
        dict | None:
        {
            "frame_start": float,
            "frame_end": float,
            "keyframe_count": int,
        }
    """
    if action is None:
        return None

    frames = []

    for fcurve in get_action_fcurves(
        action
    ):
        keyframe_points = getattr(
            fcurve,
            "keyframe_points",
            None,
        )

        if keyframe_points is None:
            continue

        for keyframe in keyframe_points:
            frames.append(
                float(keyframe.co.x)
            )

    if not frames:
        return None

    return {
        "frame_start": min(frames),
        "frame_end": max(frames),
        "keyframe_count": len(frames),
    }


def get_action_fcurves(action):
    """
    Returns all unique F-Curves from an Action.

    Supports:

        - Legacy action.fcurves
        - Layered Actions:
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
                        channel_fcurves = getattr(
                            channelbag,
                            "fcurves",
                            None,
                        )

                        if channel_fcurves is None:
                            continue

                        for fcurve in channel_fcurves:
                            add_fcurve(
                                fcurve
                            )

        except Exception:
            pass

    return fcurves
