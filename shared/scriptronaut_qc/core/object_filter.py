"""Shared QC object filtering and optional product filter hooks."""

from collections import OrderedDict
from contextvars import ContextVar

import bpy


_OBJECT_FILTERS = OrderedDict()

_CURRENT_QC_CATEGORY = ContextVar(
    "scriptronaut_qc_category",
    default="",
)

_CURRENT_QC_CHECK_ID = ContextVar(
    "scriptronaut_qc_check_id",
    default="",
)


def register_object_filter(
        filter_id,
        callback,
        *,
        priority=100,
    ):
    """
    Registers an optional object eligibility filter.

    The callback receives:
        obj
        context
        category
        check_id

    It must return True to keep the object or False to exclude it.
    """
    filter_id = str(
        filter_id
    ).strip()

    if not filter_id:
        raise ValueError(
            "filter_id cannot be empty."
        )

    if not callable(
        callback
    ):
        raise TypeError(
            "Object filter callback must be callable."
        )

    _OBJECT_FILTERS[
        filter_id
    ] = {
        "callback":
            callback,

        "priority":
            int(
                priority
            ),
    }


def unregister_object_filter(
        filter_id,
    ):
    """
    Removes a registered optional object filter.
    """
    _OBJECT_FILTERS.pop(
        str(
            filter_id
        ),
        None,
    )


def get_registered_object_filters():
    """
    Returns object filters in deterministic priority order.
    """
    return sorted(
        (
            (
                filter_id,
                data["callback"],
            )
            for filter_id, data
            in _OBJECT_FILTERS.items()
        ),
        key=lambda item: (
            _OBJECT_FILTERS[
                item[0]
            ][
                "priority"
            ],
            item[0],
        ),
    )


def push_qc_object_filter_context(
        check_id,
    ):
    """
    Sets the current check/category scope while main() or fix() executes.

    Returns tokens that must be passed to pop_qc_object_filter_context().
    """
    check_id = str(
        check_id
        or ""
    )

    category = (
        check_id.split(
            ".",
            1,
        )[0]
        if "."
        in check_id
        else ""
    )

    return (
        _CURRENT_QC_CATEGORY.set(
            category
        ),
        _CURRENT_QC_CHECK_ID.set(
            check_id
        ),
    )


def pop_qc_object_filter_context(
        tokens,
    ):
    """
    Restores the previous object-filter execution context.
    """
    category_token, check_token = tokens

    _CURRENT_QC_CATEGORY.reset(
        category_token
    )

    _CURRENT_QC_CHECK_ID.reset(
        check_token
    )


def get_current_qc_object_filter_context():
    """
    Returns the current category/check identifiers.
    """
    return {
        "category":
            _CURRENT_QC_CATEGORY.get(),

        "check_id":
            _CURRENT_QC_CHECK_ID.get(),
    }


def _passes_optional_object_filters(
        obj,
        context,
    ):
    """
    Applies optional registered filters after Core eligibility checks.
    """
    category = (
        _CURRENT_QC_CATEGORY.get()
    )

    check_id = (
        _CURRENT_QC_CHECK_ID.get()
    )

    for filter_id, callback in (
        get_registered_object_filters()
    ):
        try:
            if not callback(
                obj=obj,
                context=context,
                category=category,
                check_id=check_id,
            ):
                return False

        except Exception as error:
            # Optional product code should never break Core QC execution.
            print(
                (
                    "Scriptronaut QC object filter '{}' failed: {}"
                ).format(
                    filter_id,
                    error,
                )
            )

    return True


def is_object_available_for_qc(
        obj,
        context=None,
    ):
    """
    Returns True when an object should participate in the current QC run.

    Core requirements:
        - Belongs to the active Scene.
        - Is not a directly linked library object.
        - Exists in the active View Layer.
        - Is currently available/visible in that View Layer.

    Optional products may register additional filters. QC Pro uses this hook
    for scene-specific ignored-collection rules.
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

    try:
        if scene.objects.get(
            obj.name
        ) is not obj:
            return False

    except Exception:
        return False

    if getattr(
        obj,
        "library",
        None,
    ) is not None:
        return False

    try:
        if view_layer.objects.get(
            obj.name
        ) is not obj:
            return False

    except Exception:
        return False

    try:
        if not obj.visible_get(
            view_layer=view_layer
        ):
            return False

    except (TypeError, RuntimeError):
        try:
            if not obj.visible_get():
                return False
        except Exception:
            return False

    if not _passes_optional_object_filters(
        obj,
        context,
    ):
        return False

    return True


def get_qc_objects(
        objects=None,
        context=None,
    ):
    """
    Returns QC-eligible objects from the active Scene/View Layer.
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
    Returns one currently eligible object from the active Scene, or None.
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
