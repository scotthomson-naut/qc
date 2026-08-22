"""Shared object filtering used by QC checks."""

import bpy


def is_object_available_for_qc(
        obj,
        context=None,
    ):
    """
    Returns True when an object should participate in the current QC run.

    An object is considered available when it:

        - Belongs to the active Scene.
        - Is not a directly linked library object.
        - Exists in the active View Layer.
        - Is currently available/visible in that View Layer.

    The visibility test intentionally excludes objects hidden by:

        - Disabled/excluded View Layer collections.
        - Collection "Disable in Viewports".
        - Object viewport visibility.

    This keeps automatic checks/fixes aligned with objects Blender can
    actually operate on in the current UI context.

    Library Overrides are intentionally allowed when Blender presents them
    as local/editable objects.

    Args:
        obj (bpy.types.Object | None):
            Object to inspect.

        context:
            Blender context. Defaults to bpy.context.

    Returns:
        bool
    """
    if obj is None:
        return False

    if context is None:
        context = bpy.context

    scene = getattr(
        context,
        "scene",
        None,
    )

    view_layer = getattr(
        context,
        "view_layer",
        None,
    )

    if (
        scene is None
        or view_layer is None
    ):
        return False

    # ---------------------------------------------------------
    # Active Scene only
    # ---------------------------------------------------------

    try:
        if scene.objects.get(
            obj.name
        ) is not obj:
            return False

    except Exception:
        return False

    # ---------------------------------------------------------
    # Directly linked library objects are read-only
    # ---------------------------------------------------------

    if getattr(
        obj,
        "library",
        None,
    ) is not None:
        return False

    # ---------------------------------------------------------
    # Active View Layer only
    # ---------------------------------------------------------

    try:
        if view_layer.objects.get(
            obj.name
        ) is not obj:
            return False

    except Exception:
        return False

    # ---------------------------------------------------------
    # Viewport availability
    # ---------------------------------------------------------

    try:
        if not obj.visible_get(
            view_layer=view_layer
        ):
            return False

    except (TypeError, RuntimeError):
        # Some Blender versions/context combinations do not accept the
        # view_layer keyword. Fall back to the current view layer.
        try:
            if not obj.visible_get():
                return False
        except Exception:
            return False

    return True


def get_qc_objects(
        objects=None,
        context=None,
    ):
    """
    Returns QC-eligible objects from the active Scene/View Layer.

    If objects is supplied it is still filtered against the active Scene
    and active View Layer. This prevents callers from accidentally passing
    bpy.data.objects or objects belonging to another Scene.

    Returns:
        list[bpy.types.Object]
    """
    if context is None:
        context = bpy.context

    scene = getattr(
        context,
        "scene",
        None,
    )

    if scene is None:
        return []

    if objects is None:
        objects = scene.objects

    return [
        obj
        for obj in objects
        if is_object_available_for_qc(
            obj,
            context=context,
        )
    ]


def get_qc_object(
        object_name,
        context=None,
    ):
    """
    Returns an available object from the active Scene, or None.

    This is intended for Fix stages so stale result data cannot resolve an
    object that is now hidden, excluded, linked, or belongs to another Scene.
    """
    if context is None:
        context = bpy.context

    scene = getattr(
        context,
        "scene",
        None,
    )

    if scene is None:
        return None

    obj = scene.objects.get(
        object_name
    )

    if not is_object_available_for_qc(
        obj,
        context=context,
    ):
        return None

    return obj
