# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "NLA Strips Present"
DESCRIPTION = (
    "Checks for objects that contain NLA tracks with no strips. "
)
WHY = (
    "Leftover animation data-blocks can bloat file sizes, corrupt game engine "
    "exports, and cause evaluation conflicts where invisible tracks override "
    "your active keyframes."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds objects that contain one or more empty NLA tracks.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_empty_nla_tracks()

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        track_names = object_data.get(
            "empty_tracks",
            []
        )

        issues.append(
            (
                'Failed object: {} - {} empty NLA track{} found: {}'
            ).format(
                object_name,
                len(track_names),
                ""
                if len(track_names) == 1
                else "s",
                ", ".join(track_names),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Removes empty NLA tracks from failed objects.

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
    return remove_empty_nla_tracks(
        result_data=result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_empty_nla_tracks(
        objects=None,
    ):
    """
    Finds objects containing NLA tracks with no strips.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_type": "MESH",
                "empty_track_count": 2,
                "empty_tracks": [
                    "NlaTrack",
                    "NlaTrack.001",
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

        empty_tracks = []

        for track in nla_tracks:
            strips = getattr(
                track,
                "strips",
                None,
            )

            if strips is None:
                continue

            if len(strips) == 0:
                empty_tracks.append(
                    track.name
                )

        if not empty_tracks:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "empty_track_count": len(
                empty_tracks
            ),
            "empty_tracks": empty_tracks,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def remove_empty_nla_tracks(
        result_data=None,
    ):
    """
    Removes empty NLA tracks from failed objects.

    Every track is revalidated before removal. A track that gained a strip
    after the QC run is skipped.

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

        nla_tracks = getattr(
            animation_data,
            "nla_tracks",
            None,
        )

        if nla_tracks is None:
            continue

        track_names = []

        if isinstance(
            object_data,
            dict,
        ):
            track_names = object_data.get(
                "empty_tracks",
                [],
            )

        if not isinstance(
            track_names,
            list,
        ):
            continue

        removed_tracks = []

        for track_name in track_names:
            track = find_nla_track(
                animation_data,
                track_name,
            )

            if track is None:
                issues.append(
                    (
                        'NLA track "{}" was not found on object "{}".'
                    ).format(
                        track_name,
                        object_name,
                    )
                )
                continue

            strips = getattr(
                track,
                "strips",
                None,
            )

            if strips is None:
                continue

            if len(strips) > 0:
                issues.append(
                    (
                        'Skipped NLA track "{}" on "{}" because '
                        "it now contains one or more strips."
                    ).format(
                        track_name,
                        object_name,
                    )
                )
                continue

            try:
                nla_tracks.remove(
                    track
                )

                removed_tracks.append(
                    track_name
                )

            except Exception as error:
                issues.append(
                    (
                        'Could not remove NLA track "{}" '
                        'from object "{}": {}'
                    ).format(
                        track_name,
                        object_name,
                        error,
                    )
                )

        if removed_tracks:
            fixed_objects[object_name] = {
                "removed_track_count": len(
                    removed_tracks
                ),
                "removed_tracks": removed_tracks,
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
        track_name,
    ):
    """
    Finds an NLA track by name.

    Args:
        animation_data (bpy.types.AnimData):
            Animation data containing NLA tracks.

        track_name (str):
            Name of the NLA track.

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

    try:
        return nla_tracks.get(
            track_name
        )
    except Exception:
        pass

    for track in nla_tracks:
        if track.name == track_name:
            return track

    return None
