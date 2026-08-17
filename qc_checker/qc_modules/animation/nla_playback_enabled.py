# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "NLA Playback Enabled"
DESCRIPTION = (
    "Checks for objects that contain muted NLA tracks "
    "or muted NLA strips."
)
WHY = (
    "They can secretly disable parts of an animation, "
    "corrupt game engine exports, or cause confusion when stacking and "
    "blending motions."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds objects that contain muted NLA tracks or strips.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_muted_nla_items()

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        muted_tracks = object_data.get(
            "muted_tracks",
            [],
        )

        muted_strips = object_data.get(
            "muted_strips",
            [],
        )

        issue_parts = []

        if muted_tracks:
            issue_parts.append(
                "{} muted track{}".format(
                    len(muted_tracks),
                    ""
                    if len(muted_tracks) == 1
                    else "s",
                )
            )

        if muted_strips:
            issue_parts.append(
                "{} muted strip{}".format(
                    len(muted_strips),
                    ""
                    if len(muted_strips) == 1
                    else "s",
                )
            )

        issues.append(
            (
                "Failed object: {} - {}."
            ).format(
                object_name,
                " and ".join(issue_parts),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Unmutes the muted NLA tracks and strips found by the check.

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
    return unmute_nla_items(
        result_data=result_data,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_muted_nla_items(
        objects=None,
    ):
    """
    Finds objects containing muted NLA tracks or strips.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_type": "MESH",
                "muted_track_count": 1,
                "muted_strip_count": 2,
                "muted_tracks": [
                    {
                        "track_name": "Base Animation",
                        "track_index": 0,
                    }
                ],
                "muted_strips": [
                    {
                        "track_name": "Secondary",
                        "track_index": 1,
                        "strip_name": "Walk",
                        "strip_index": 0,
                    }
                ],
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

        nla_tracks = getattr(
            animation_data,
            "nla_tracks",
            None,
        )

        if nla_tracks is None:
            continue

        muted_tracks = []
        muted_strips = []

        for track_index, track in enumerate(
            nla_tracks
        ):
            if bool(
                getattr(
                    track,
                    "mute",
                    False,
                )
            ):
                muted_tracks.append({
                    "track_name": track.name,
                    "track_index": track_index,
                })

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
                if not bool(
                    getattr(
                        strip,
                        "mute",
                        False,
                    )
                ):
                    continue

                muted_strips.append({
                    "track_name": track.name,
                    "track_index": track_index,
                    "strip_name": strip.name,
                    "strip_index": strip_index,
                })

        if not muted_tracks and not muted_strips:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "muted_track_count": len(
                muted_tracks
            ),
            "muted_strip_count": len(
                muted_strips
            ),
            "muted_tracks": muted_tracks,
            "muted_strips": muted_strips,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def unmute_nla_items(
        result_data=None,
    ):
    """
    Unmutes the specific NLA tracks and strips reported by the check.

    The check results are revalidated before changes are made.

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

        animation_data = getattr(
            obj,
            "animation_data",
            None,
        )

        if animation_data is None:
            issues.append(
                (
                    'Skipped "{}" because it no longer has '
                    "animation data."
                ).format(
                    object_name
                )
            )
            continue

        if not isinstance(
            object_data,
            dict,
        ):
            continue

        muted_tracks = object_data.get(
            "muted_tracks",
            [],
        )

        muted_strips = object_data.get(
            "muted_strips",
            [],
        )

        if not isinstance(
            muted_tracks,
            list,
        ):
            muted_tracks = []

        if not isinstance(
            muted_strips,
            list,
        ):
            muted_strips = []

        unmuted_track_names = []
        unmuted_strip_names = []

        # -------------------------------------------------------------
        # Unmute tracks
        # -------------------------------------------------------------

        for track_data in muted_tracks:
            if not isinstance(
                track_data,
                dict,
            ):
                continue

            track_name = track_data.get(
                "track_name",
                "",
            )

            track_index = track_data.get(
                "track_index",
                None,
            )

            track = find_nla_track(
                animation_data,
                track_name=track_name,
                track_index=track_index,
            )

            if track is None:
                issues.append(
                    (
                        'Could not find NLA track "{}" '
                        'on object "{}".'
                    ).format(
                        track_name,
                        object_name,
                    )
                )
                continue

            if not bool(
                getattr(
                    track,
                    "mute",
                    False,
                )
            ):
                continue

            try:
                track.mute = False

                unmuted_track_names.append(
                    track.name
                )

            except Exception as error:
                issues.append(
                    (
                        'Could not unmute NLA track "{}" '
                        'on object "{}": {}'
                    ).format(
                        track.name,
                        object_name,
                        error,
                    )
                )

        # -------------------------------------------------------------
        # Unmute strips
        # -------------------------------------------------------------

        for strip_data in muted_strips:
            if not isinstance(
                strip_data,
                dict,
            ):
                continue

            track_name = strip_data.get(
                "track_name",
                "",
            )

            track_index = strip_data.get(
                "track_index",
                None,
            )

            strip_name = strip_data.get(
                "strip_name",
                "",
            )

            strip_index = strip_data.get(
                "strip_index",
                None,
            )

            track = find_nla_track(
                animation_data,
                track_name=track_name,
                track_index=track_index,
            )

            if track is None:
                issues.append(
                    (
                        'Could not find NLA track "{}" for strip "{}" '
                        'on object "{}".'
                    ).format(
                        track_name,
                        strip_name,
                        object_name,
                    )
                )
                continue

            strip = find_nla_strip(
                track,
                strip_name=strip_name,
                strip_index=strip_index,
            )

            if strip is None:
                issues.append(
                    (
                        'Could not find NLA strip "{}" in track "{}" '
                        'on object "{}".'
                    ).format(
                        strip_name,
                        track.name,
                        object_name,
                    )
                )
                continue

            if not bool(
                getattr(
                    strip,
                    "mute",
                    False,
                )
            ):
                continue

            try:
                strip.mute = False

                unmuted_strip_names.append(
                    "{} / {}".format(
                        track.name,
                        strip.name,
                    )
                )

            except Exception as error:
                issues.append(
                    (
                        'Could not unmute NLA strip "{}" '
                        'in track "{}" on object "{}": {}'
                    ).format(
                        strip.name,
                        track.name,
                        object_name,
                        error,
                    )
                )

        if (
            unmuted_track_names
            or unmuted_strip_names
        ):
            fixed_objects[object_name] = {
                "unmuted_track_count": len(
                    unmuted_track_names
                ),
                "unmuted_strip_count": len(
                    unmuted_strip_names
                ),
                "unmuted_tracks": unmuted_track_names,
                "unmuted_strips": unmuted_strip_names,
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def find_nla_track(
        animation_data,
        track_name="",
        track_index=None,
    ):
    """
    Finds an NLA track using its name, with index as a fallback.

    Args:
        animation_data (bpy.types.AnimData):
            Animation data containing the NLA tracks.

        track_name (str):
            Expected track name.

        track_index (int | None):
            Original track index.

    Returns:
        bpy.types.NlaTrack | None
    """
    if animation_data is None:
        return None

    nla_tracks = getattr(
        animation_data,
        "nla_tracks",
        None,
    )

    if nla_tracks is None:
        return None

    if track_name:
        try:
            track = nla_tracks.get(
                track_name
            )

            if track is not None:
                return track

        except Exception:
            pass

        for track in nla_tracks:
            if track.name == track_name:
                return track

    if track_index is not None:
        try:
            track_index = int(
                track_index
            )

            if (
                0 <= track_index
                < len(nla_tracks)
            ):
                return nla_tracks[
                    track_index
                ]

        except Exception:
            pass

    return None


def find_nla_strip(
        track,
        strip_name="",
        strip_index=None,
    ):
    """
    Finds an NLA strip using its name, with index as a fallback.

    Args:
        track (bpy.types.NlaTrack):
            Track containing the strip.

        strip_name (str):
            Expected strip name.

        strip_index (int | None):
            Original strip index.

    Returns:
        bpy.types.NlaStrip | None
    """
    if track is None:
        return None

    strips = getattr(
        track,
        "strips",
        None,
    )

    if strips is None:
        return None

    if strip_name:
        try:
            strip = strips.get(
                strip_name
            )

            if strip is not None:
                return strip

        except Exception:
            pass

        for strip in strips:
            if strip.name == strip_name:
                return strip

    if strip_index is not None:
        try:
            strip_index = int(
                strip_index
            )

            if (
                0 <= strip_index
                < len(strips)
            ):
                return strips[
                    strip_index
                ]

        except Exception:
            pass

    return None
