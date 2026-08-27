"""QC check availability helpers."""

from ..utils.scene import (
    get_scene_triangles_count,
)


def evaluate_check_availability(
        module,
    ):
    """
    Determines whether a QC check is safe to run for the current scene.

    Returns:
        tuple:
            (
                is_available,
                reason,
            )
    """
    max_triangles = getattr(
        module,
        "MAX_SCENE_TRIANGLES",
        None,
    )

    # No scene-size restriction.
    if max_triangles is None:
        return (
            True,
            "",
        )

    try:
        max_triangles = int(
            max_triangles
        )
    except (
        TypeError,
        ValueError,
    ):
        return (
            True,
            "",
        )

    if max_triangles <= 0:
        return (
            True,
            "",
        )

    scene_triangles = (
        get_scene_triangles_count()
    )

    if scene_triangles <= max_triangles:
        return (
            True,
            "",
        )

    reason = (
        "Disabled for this scene during Alpha testing. "
        "Scene contains {:,} triangles; this check is limited "
        "to {:,} triangles."
    ).format(
        scene_triangles,
        max_triangles,
    )

    return (
        False,
        reason,
    )
