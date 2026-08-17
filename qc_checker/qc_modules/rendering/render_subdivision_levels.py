# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Render Subdivision Levels"
DESCRIPTION = (
    "Checks for Subdivision Surface modifiers whose render subdivision "
    "level is significantly higher than the configured maximum or the "
    "modifier's viewport subdivision level."
)
WHY = (
    "Prevents sudden system memory exhaustion, long render freezes, "
    "and application crashes. Each extra subdivision level multiplies "
    "face counts exponentially, meaning a high render level can silently "
    "turn a light scene into a gigabyte-heavy monster during final export."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "maximum_render_levels": {
        "type": "int",
        "label": "Maximum Render Levels",
        "description": (
            "Fail when a Subdivision Surface modifier's render level "
            "is above this value."
        ),
        "default": 3,
        "min": 0,
        "max": 12,
    },

    "maximum_levels_above_viewport": {
        "type": "int",
        "label": "Maximum Levels Above Viewport",
        "description": (
            "Maximum allowed difference between the render level and "
            "viewport level."
        ),
        "default": 1,
        "min": 0,
        "max": 12,
    },

    "ignore_disabled_render_modifiers": {
        "type": "bool",
        "label": "Ignore Disabled Render Modifiers",
        "description": (
            "Ignore Subdivision Surface modifiers that are disabled "
            "for rendering."
        ),
        "default": True,
    },

    "include_simple_subdivision": {
        "type": "bool",
        "label": "Include Simple Subdivision",
        "description": (
            "Also check Subdivision Surface modifiers using the "
            "Simple subdivision method."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds objects with excessive render subdivision levels.

    Args:
        preferences (dict | None):
            User-configured check settings.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_objects = get_objects_with_excessive_render_subdivision(
        settings=settings,
    )

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        modifiers = object_data.get(
            "modifiers",
            [],
        )

        for modifier_data in modifiers:
            reasons = modifier_data.get(
                "reasons",
                [],
            )

            issues.append(
                (
                    'Object "{}" has excessive render subdivision '
                    'on modifier "{}": viewport level {}, render '
                    "level {}. {}"
                ).format(
                    object_name,
                    modifier_data["modifier_name"],
                    modifier_data["viewport_levels"],
                    modifier_data["render_levels"],
                    " ".join(reasons),
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
    Reduces excessive render subdivision levels.

    The safe target is the lower of:

        maximum_render_levels

    and:

        viewport_levels + maximum_levels_above_viewport

    The modifier is revalidated before it is changed.

    Args:
        result_data (dict | None):
            Result returned by main().

        preferences (dict | None):
            User-configured check settings.

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

    return reduce_excessive_render_subdivision(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_excessive_render_subdivision(
        objects=None,
        settings=None,
    ):
    """
    Finds Subdivision Surface modifiers with excessive render levels.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to objects in the current scene.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "ObjectName": {
                "object_type": "MESH",
                "modifier_count": 1,
                "modifiers": [
                    {
                        "modifier_name": "Subdivision",
                        "modifier_type": "SUBSURF",
                        "subdivision_type": "CATMULL_CLARK",
                        "viewport_levels": 2,
                        "render_levels": 6,
                        "level_difference": 4,
                        "recommended_render_levels": 3,
                        "show_render": True,
                        "reasons": [
                            ...
                        ],
                    }
                ],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    maximum_render_levels = max(
        0,
        int(settings["maximum_render_levels"]),
    )

    maximum_levels_above_viewport = max(
        0,
        int(settings["maximum_levels_above_viewport"]),
    )

    ignore_disabled = bool(
        settings["ignore_disabled_render_modifiers"]
    )

    include_simple = bool(
        settings["include_simple_subdivision"]
    )

    failed_objects = {}

    for obj in objects:

        if obj.library is not None:
            continue

        modifiers = getattr(
            obj,
            "modifiers",
            None,
        )

        if modifiers is None:
            continue

        failed_modifiers = []

        for modifier in modifiers:
            if modifier.type != "SUBSURF":
                continue

            show_render = bool(
                getattr(
                    modifier,
                    "show_render",
                    True,
                )
            )

            if ignore_disabled and not show_render:
                continue

            subdivision_type = getattr(
                modifier,
                "subdivision_type",
                "CATMULL_CLARK",
            )

            if (
                subdivision_type == "SIMPLE"
                and not include_simple
            ):
                continue

            viewport_levels = int(
                getattr(
                    modifier,
                    "levels",
                    0,
                )
            )

            render_levels = int(
                getattr(
                    modifier,
                    "render_levels",
                    viewport_levels,
                )
            )

            level_difference = (
                render_levels
                - viewport_levels
            )

            above_absolute_limit = (
                render_levels
                > maximum_render_levels
            )

            above_viewport_limit = (
                level_difference
                > maximum_levels_above_viewport
            )

            if (
                not above_absolute_limit
                and not above_viewport_limit
            ):
                continue

            recommended_render_levels = get_recommended_render_levels(
                viewport_levels=viewport_levels,
                maximum_render_levels=maximum_render_levels,
                maximum_levels_above_viewport=(
                    maximum_levels_above_viewport
                ),
            )

            reasons = []

            if above_absolute_limit:
                reasons.append(
                    (
                        "Render level exceeds the configured "
                        "maximum of {}."
                    ).format(
                        maximum_render_levels
                    )
                )

            if above_viewport_limit:
                reasons.append(
                    (
                        "Render level is {} level{} above the "
                        "viewport level; the configured maximum "
                        "difference is {}."
                    ).format(
                        level_difference,
                        ""
                        if level_difference == 1
                        else "s",
                        maximum_levels_above_viewport,
                    )
                )

            failed_modifiers.append({
                "modifier_name": modifier.name,
                "modifier_type": modifier.type,
                "subdivision_type": subdivision_type,
                "viewport_levels": viewport_levels,
                "render_levels": render_levels,
                "level_difference": level_difference,
                "recommended_render_levels": (
                    recommended_render_levels
                ),
                "show_render": show_render,
                "reasons": reasons,
            })

        if not failed_modifiers:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "modifier_count": len(
                failed_modifiers
            ),
            "modifiers": failed_modifiers,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def reduce_excessive_render_subdivision(
        result_data=None,
        settings=None,
    ):
    """
    Reduces excessive render subdivision levels reported by the check.

    Current modifier values are revalidated rather than relying entirely
    on potentially stale QC results.

    Args:
        result_data (dict | None):
            Result returned by main().

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

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

    maximum_render_levels = max(
        0,
        int(settings["maximum_render_levels"]),
    )

    maximum_levels_above_viewport = max(
        0,
        int(settings["maximum_levels_above_viewport"]),
    )

    ignore_disabled = bool(
        settings["ignore_disabled_render_modifiers"]
    )

    include_simple = bool(
        settings["include_simple_subdivision"]
    )

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

        if not isinstance(
            object_data,
            dict,
        ):
            continue

        modifier_results = object_data.get(
            "modifiers",
            [],
        )

        if not isinstance(
            modifier_results,
            list,
        ):
            continue

        fixed_modifiers = []

        for modifier_data in modifier_results:
            if not isinstance(
                modifier_data,
                dict,
            ):
                continue

            modifier_name = modifier_data.get(
                "modifier_name",
                "",
            )

            modifier = find_modifier(
                obj=obj,
                modifier_name=modifier_name,
            )

            if modifier is None:
                issues.append(
                    (
                        'Modifier "{}" was not found on '
                        'object "{}".'
                    ).format(
                        modifier_name,
                        object_name,
                    )
                )
                continue

            if modifier.type != "SUBSURF":
                issues.append(
                    (
                        'Modifier "{}" on "{}" is no longer '
                        "a Subdivision Surface modifier."
                    ).format(
                        modifier.name,
                        object_name,
                    )
                )
                continue

            show_render = bool(
                getattr(
                    modifier,
                    "show_render",
                    True,
                )
            )

            if ignore_disabled and not show_render:
                continue

            subdivision_type = getattr(
                modifier,
                "subdivision_type",
                "CATMULL_CLARK",
            )

            if (
                subdivision_type == "SIMPLE"
                and not include_simple
            ):
                continue

            viewport_levels = int(
                getattr(
                    modifier,
                    "levels",
                    0,
                )
            )

            current_render_levels = int(
                getattr(
                    modifier,
                    "render_levels",
                    viewport_levels,
                )
            )

            level_difference = (
                current_render_levels
                - viewport_levels
            )

            is_excessive = (
                current_render_levels
                > maximum_render_levels
                or level_difference
                > maximum_levels_above_viewport
            )

            if not is_excessive:
                continue

            recommended_render_levels = get_recommended_render_levels(
                viewport_levels=viewport_levels,
                maximum_render_levels=maximum_render_levels,
                maximum_levels_above_viewport=(
                    maximum_levels_above_viewport
                ),
            )

            if (
                recommended_render_levels
                >= current_render_levels
            ):
                continue

            try:
                modifier.render_levels = int(
                    recommended_render_levels
                )

            except Exception as error:
                issues.append(
                    (
                        'Could not change render subdivision on '
                        'modifier "{}" for object "{}": {}'
                    ).format(
                        modifier.name,
                        object_name,
                        error,
                    )
                )
                continue

            fixed_modifiers.append({
                "modifier_name": modifier.name,
                "previous_render_levels": (
                    current_render_levels
                ),
                "current_render_levels": int(
                    modifier.render_levels
                ),
                "viewport_levels": viewport_levels,
            })

        if fixed_modifiers:
            fixed_objects[object_name] = {
                "modifier_count": len(
                    fixed_modifiers
                ),
                "modifiers": fixed_modifiers,
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }



# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_recommended_render_levels(
        viewport_levels,
        maximum_render_levels,
        maximum_levels_above_viewport,
    ):
    """
    Calculates the highest render level allowed by both limits.

    The result is never lower than the viewport subdivision level because
    lowering render quality below viewport quality may be unexpected.

    Returns:
        int
    """
    viewport_levels = max(
        0,
        int(viewport_levels),
    )

    maximum_render_levels = max(
        0,
        int(maximum_render_levels),
    )

    maximum_levels_above_viewport = max(
        0,
        int(maximum_levels_above_viewport),
    )

    relative_limit = (
        viewport_levels
        + maximum_levels_above_viewport
    )

    recommended = min(
        maximum_render_levels,
        relative_limit,
    )

    return max(
        viewport_levels,
        recommended,
    )


def find_modifier(
        obj,
        modifier_name,
    ):
    """
    Finds a modifier by name.

    Returns:
        bpy.types.Modifier | None
    """
    if obj is None:
        return None

    modifiers = getattr(
        obj,
        "modifiers",
        None,
    )

    if modifiers is None:
        return None

    try:
        modifier = modifiers.get(
            modifier_name
        )

        if modifier is not None:
            return modifier

    except Exception:
        pass

    for modifier in modifiers:
        if modifier.name == modifier_name:
            return modifier

    return None
