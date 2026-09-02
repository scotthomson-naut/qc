# Blender imports
import bpy



# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Location Applied"
DESCRIPTION = (
    "Checks mesh objects whose normal Location is not zero. "
    "The automatic fix strategy is configurable: preserve the current "
    "origin/pivot by moving Location into Delta Location, use Blender's "
    "native Apply Location behavior, or require a manual fix."
)
WHY = (
    "Non-zero object locations can create unexpected offsets in physics, "
    "simulations, modifiers, constraints, rigging, and downstream pipeline "
    "operations. Different productions may also have different requirements "
    "for preserving an object's existing origin/pivot."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

TOLERANCE = 1e-5


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "fix_mode": {
        "type": "enum",
        "label": "Fix Mode",
        "description": (
            "Choose how automatic Fix handles non-zero Location."
        ),
        "default": "APPLY_LOCATION",
        "items": [
            (
                "PRESERVE_PIVOT",
                "Preserve Pivot (Move to Delta)",
                (
                    "Move normal Location into Delta Location. "
                    "Preserves the current world-space origin/pivot."
                ),
            ),
            (
                "APPLY_LOCATION",
                "Native Apply Location",
                (
                    "Use Blender's Object > Apply > Location behavior. "
                    "Location becomes zero by baking translation into mesh data."
                ),
            ),
            (
                "MANUAL",
                "Manual Only",
                "Report the issue but do not offer an automatic fix.",
            ),
        ],
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds mesh objects whose normal Location is not zero.
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    fix_mode = normalize_fix_mode(
        settings.get(
            "fix_mode",
            "PRESERVE_PIVOT",
        )
    )

    failed_objects = (
        get_objects_with_unapplied_location()
    )

    issues = []

    for object_name, data in failed_objects.items():
        location = data["location"]

        issues.append(
            (
                "Failed object: {} - Location is not applied: "
                "({:.4f}, {:.4f}, {:.4f})"
            ).format(
                object_name,
                location[0],
                location[1],
                location[2],
            )
        )

    return {
        "issues":
            issues,

        "failed_objects":
            failed_objects,

        "settings":
            settings,

        "can_auto_fix":
            (
                fix_mode
                != "MANUAL"
            ),
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Fixes Location using the configured Fix Mode.
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    fix_mode = normalize_fix_mode(
        settings.get(
            "fix_mode",
            "PRESERVE_PIVOT",
        )
    )

    if fix_mode == "MANUAL":
        return {
            "fixed_objects": {},
            "issues": [
                (
                    "Location Applied is configured for Manual Only. "
                    "No objects were changed."
                )
            ],
            "fix_mode": fix_mode,
        }

    if fix_mode == "APPLY_LOCATION":
        result = (
            fix_objects_with_native_apply_location(
                result_data=result_data,
            )
        )

    else:
        result = (
            fix_objects_preserve_pivot(
                result_data=result_data,
            )
        )

    if not isinstance(
        result,
        dict,
    ):
        result = {
            "fixed_objects": {},
            "issues": [],
        }

    result["fix_mode"] = fix_mode

    return result


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_unapplied_location(objects=None):
    """
    Finds mesh objects whose location is not zero.

    An object passes when:
        Location = (0, 0, 0)

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.


    Returns:
        dict:
        {
            "Cube": {
                "location": (1.0, 0.0, 2.5),
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in get_qc_objects(objects):
        if obj.type != "MESH":
            continue

        # Linked library objects are read-only from this file and cannot
        # be fixed safely by this QC check.
        if is_linked_object(
            obj
        ):
            continue

        location = tuple(obj.location)

        has_unapplied_location = any(
            abs(value) > TOLERANCE
            for value in location
        )

        if not has_unapplied_location:
            continue

        failed_objects[obj.name] = {
            "location": location,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# ------------------------------------------------------------------------

def fix_objects_preserve_pivot(
        result_data=None,
    ):
    """
    Moves normal Location directly into Delta Location.

    This implementation intentionally does NOT use
    bpy.ops.object.transforms_to_deltas().

    For Location, Blender's normal Location and Delta Location are additive.
    Moving the current normal Location value into Delta Location therefore
    preserves the object's local/world transform while leaving normal
    Location at exactly (0, 0, 0).

    This is more reliable than the operator for QC purposes because:
        - it does not depend on selection/operator context,
        - it does not create parent/child retry cascades,
        - it produces an exact zero in the normal Location channels,
        - it can explicitly detect animation/drivers that would immediately
          restore the Location value after a fix.

    Animated/driven Location channels are not modified automatically because
    their F-Curves/drivers would re-evaluate the non-zero Location again.
    Those objects are reported for manual review instead.

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

    context = bpy.context
    view_layer = context.view_layer

    # Re-evaluate current failures so stale result payloads do not matter.
    live_failed_objects = (
        get_objects_with_unapplied_location()
    )

    target_names = [
        object_name
        for object_name in failed_objects
        if object_name in live_failed_objects
    ]

    for object_name in target_names:

        try:
            obj = get_qc_object(
                object_name
            )
        except NameError:
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

        if (
            obj.type != "MESH"
            or obj.data is None
            or is_linked_object(
                obj
            )
        ):
            continue

        animation_reason = (
            get_location_animation_reason(
                obj
            )
        )

        if animation_reason:
            issues.append(
                (
                    'Could not automatically apply Location on "{}": {}'
                ).format(
                    obj.name,
                    animation_reason,
                )
            )
            continue

        previous_location = tuple(
            obj.location
        )

        previous_delta_location = tuple(
            obj.delta_location
        )

        previous_world_matrix = (
            obj.matrix_world.copy()
        )

        try:
            # Normal Location and Delta Location are additive. Transfer the
            # exact channel values directly rather than relying on an operator.
            obj.delta_location = (
                obj.delta_location.x
                + obj.location.x,

                obj.delta_location.y
                + obj.location.y,

                obj.delta_location.z
                + obj.location.z,
            )

            obj.location = (
                0.0,
                0.0,
                0.0,
            )

            view_layer.update()

        except Exception as error:
            issues.append(
                (
                    'Could not move Location into Delta Location '
                    'for "{}": {}'
                ).format(
                    obj.name,
                    error,
                )
            )
            continue

        # If depsgraph evaluation brought Location back, an animation system
        # or another evaluated source is controlling the channel.
        if object_has_unapplied_location(
            obj
        ):
            try:
                obj.location = (
                    previous_location
                )

                obj.delta_location = (
                    previous_delta_location
                )

                view_layer.update()

            except Exception:
                pass

            issues.append(
                (
                    'Location on "{}" returned to {} after the fix. '
                    "The channel is being evaluated externally "
                    "(animation, driver, or another transform source), "
                    "so QC left it unchanged."
                ).format(
                    obj.name,
                    tuple(
                        obj.location
                    ),
                )
            )
            continue

        # Defensive world-space verification.
        world_difference = (
            get_matrix_max_difference(
                previous_world_matrix,
                obj.matrix_world,
            )
        )

        if world_difference > 1e-5:

            try:
                obj.location = (
                    previous_location
                )

                obj.delta_location = (
                    previous_delta_location
                )

                view_layer.update()

            except Exception:
                pass

            issues.append(
                (
                    'Skipped "{}": moving Location to Delta Location '
                    "changed its world transform by {:.8f}; original "
                    "transform was restored."
                ).format(
                    obj.name,
                    world_difference,
                )
            )
            continue

        fixed_objects[
            obj.name
        ] = {
            "delta_location_applied":
                True,

            "previous_location":
                previous_location,

            "previous_delta_location":
                previous_delta_location,

            "location":
                tuple(
                    obj.location
                ),

            "delta_location":
                tuple(
                    obj.delta_location
                ),

            "world_transform_preserved":
                True,
        }

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }


def fix_objects_with_native_apply_location(
        result_data=None,
    ):
    """
    Uses Blender's native Object > Apply > Location behavior.

    The failed objects and their mesh descendants are processed as one
    selection so hierarchy compensation is handled by Blender. Mesh data is
    made single-user first when necessary to avoid changing unrelated
    instances that share the same Mesh datablock.

    This mode creates a truly applied Location, but it can change the
    relationship between geometry and the object's origin/pivot.
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

    context = bpy.context
    view_layer = context.view_layer

    fixed_objects = {}
    issues = []

    original_active = (
        view_layer.objects.active
    )

    original_selected = list(
        context.selected_objects
    )

    original_mode = (
        context.mode
    )

    candidate_objects = []
    candidate_names = set()

    def add_candidate(
            obj,
        ):
        if obj is None:
            return

        if not is_object_available_for_qc(
            obj
        ):
            return

        if (
            obj.type != "MESH"
            or obj.data is None
            or is_linked_object(
                obj
            )
        ):
            return

        if obj.name in candidate_names:
            return

        candidate_names.add(
            obj.name
        )

        candidate_objects.append(
            obj
        )

    for object_name in failed_objects:
        obj = get_qc_object(
            object_name
        )

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        add_candidate(
            obj
        )

        for descendant in get_object_descendants(
            obj
        ):
            add_candidate(
                descendant
            )

    original_locations = {
        obj.name:
            tuple(
                obj.location
            )
        for obj in candidate_objects
    }

    try:
        if (
            context.object is not None
            and context.mode != "OBJECT"
        ):
            bpy.ops.object.mode_set(
                mode="OBJECT"
            )

        for obj in candidate_objects:
            if obj.data.users > 1:
                obj.data = (
                    obj.data.copy()
                )

        for selected_obj in list(
            context.selected_objects
        ):
            try:
                selected_obj.select_set(
                    False
                )
            except RuntimeError:
                pass

        selected_objects = []

        for obj in candidate_objects:
            if (
                view_layer.objects.get(
                    obj.name
                )
                is None
            ):
                continue

            try:
                obj.select_set(
                    True
                )

                selected_objects.append(
                    obj
                )

            except RuntimeError as error:
                issues.append(
                    'Could not select "{}": {}'.format(
                        obj.name,
                        error,
                    )
                )

        if selected_objects:
            view_layer.objects.active = (
                selected_objects[0]
            )

            result = bpy.ops.object.transform_apply(
                location=True,
                rotation=False,
                scale=False,
                properties=False,
            )

            if "FINISHED" not in result:
                issues.append(
                    "Blender did not finish Apply Location."
                )

        view_layer.update()

        for obj in candidate_objects:
            if obj.name not in bpy.data.objects:
                continue

            if object_has_unapplied_location(
                obj
            ):
                issues.append(
                    (
                        'Location is still not zero on "{}" '
                        "after Native Apply Location."
                    ).format(
                        obj.name
                    )
                )
                continue

            previous_location = (
                original_locations.get(
                    obj.name,
                    (0.0, 0.0, 0.0),
                )
            )

            if not any(
                abs(
                    value
                ) > TOLERANCE
                for value in previous_location
            ):
                continue

            fixed_objects[
                obj.name
            ] = {
                "location_applied":
                    True,

                "previous_location":
                    previous_location,

                "location":
                    tuple(
                        obj.location
                    ),
            }

    except Exception as error:
        issues.append(
            "Could not apply Location: {}".format(
                error
            )
        )

    finally:
        for selected_obj in list(
            context.selected_objects
        ):
            try:
                selected_obj.select_set(
                    False
                )
            except RuntimeError:
                pass

        for selected_obj in original_selected:
            if (
                selected_obj.name in bpy.data.objects
                and view_layer.objects.get(
                    selected_obj.name
                )
                is not None
            ):
                try:
                    selected_obj.select_set(
                        True
                    )
                except RuntimeError:
                    pass

        if (
            original_active is not None
            and original_active.name in bpy.data.objects
            and view_layer.objects.get(
                original_active.name
            )
            is not None
        ):
            view_layer.objects.active = (
                original_active
            )

        if (
            original_mode != "OBJECT"
            and view_layer.objects.active
            is not None
        ):
            mode_name = get_mode_set_name(
                original_mode
            )

            if mode_name:
                try:
                    bpy.ops.object.mode_set(
                        mode=mode_name
                    )
                except RuntimeError:
                    pass

        view_layer.update()

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }


# -------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------

def normalize_fix_mode(
        value,
    ):
    """
    Returns a supported Location fix mode.
    """
    value = str(
        value
        or ""
    ).strip().upper()

    if value not in {
        "PRESERVE_PIVOT",
        "APPLY_LOCATION",
        "MANUAL",
    }:
        return "PRESERVE_PIVOT"

    return value


def is_linked_object(
        obj,
    ):
    """
    Returns True when obj comes directly from an external Blender library.

    Linked objects are read-only in the current file and should not be
    reported by transform checks that offer automatic fixes.

    Library Overrides are intentionally treated as local/editable here:
        obj.library is None
        obj.override_library is not None

    Returns:
        bool
    """
    if obj is None:
        return False

    return (
        obj.library
        is not None
    )


def get_object_descendants(
        obj,
    ):
    """
    Returns all descendants below obj in parent-first hierarchy order.
    """
    descendants = []

    stack = list(
        obj.children
    )

    visited = set()

    while stack:

        child = stack.pop(
            0
        )

        pointer = child.as_pointer()

        if pointer in visited:
            continue

        visited.add(
            pointer
        )

        descendants.append(
            child
        )

        stack.extend(
            child.children
        )

    descendants.sort(
        key=get_object_parent_depth
    )

    return descendants


def get_object_parent_depth(
        obj,
    ):
    """
    Returns the number of parents above obj.
    """
    depth = 0

    parent = getattr(
        obj,
        "parent",
        None,
    )

    visited = set()

    while parent is not None:

        pointer = parent.as_pointer()

        if pointer in visited:
            break

        visited.add(
            pointer
        )

        depth += 1

        parent = parent.parent

    return depth


def object_has_unapplied_location(
        obj,
        tolerance=TOLERANCE,
    ):
    """
    Returns True when normal Location is not (0, 0, 0).
    """
    return any(
        abs(
            value
        ) > tolerance
        for value in obj.location
    )



def get_location_animation_reason(
        obj,
    ):
    """
    Returns a reason string when normal Location is controlled by animation
    or drivers, otherwise an empty string.

    Automatically rewriting animated Location F-Curves would change authored
    animation, so the QC fix deliberately leaves those objects for manual
    review.
    """
    if obj is None:
        return ""

    animation_data = getattr(
        obj,
        "animation_data",
        None,
    )

    if animation_data is None:
        return ""

    # Drivers directly controlling Location.
    for fcurve in getattr(
        animation_data,
        "drivers",
        [],
    ):
        if getattr(
            fcurve,
            "data_path",
            "",
        ) == "location":
            return (
                "normal Location is controlled by a driver."
            )

    # Active Action F-Curves.
    action = getattr(
        animation_data,
        "action",
        None,
    )

    if action is not None:
        for fcurve in getattr(
            action,
            "fcurves",
            [],
        ):
            if getattr(
                fcurve,
                "data_path",
                "",
            ) == "location":
                return (
                    "normal Location is animated by an Action."
                )

    # NLA strips may evaluate Location even when animation_data.action is None.
    for track in getattr(
        animation_data,
        "nla_tracks",
        [],
    ):
        for strip in getattr(
            track,
            "strips",
            [],
        ):
            strip_action = getattr(
                strip,
                "action",
                None,
            )

            if strip_action is None:
                continue

            for fcurve in getattr(
                strip_action,
                "fcurves",
                [],
            ):
                if getattr(
                    fcurve,
                    "data_path",
                    "",
                ) == "location":
                    return (
                        "normal Location is animated through an NLA strip."
                    )

    return ""


def get_matrix_max_difference(
        matrix_a,
        matrix_b,
    ):
    """
    Returns the largest absolute element difference between two 4x4 matrices.
    """
    difference = 0.0

    for row_index in range(
        4
    ):
        for column_index in range(
            4
        ):
            difference = max(
                difference,
                abs(
                    float(
                        matrix_a[
                            row_index
                        ][
                            column_index
                        ]
                    )
                    - float(
                        matrix_b[
                            row_index
                        ][
                            column_index
                        ]
                    )
                ),
            )

    return difference

def get_mode_set_name(context_mode):
    """
    Converts bpy.context.mode values into names accepted by
    bpy.ops.object.mode_set().
    """
    mode_map = {
        "EDIT_MESH": "EDIT",
        "EDIT_CURVE": "EDIT",
        "EDIT_SURFACE": "EDIT",
        "EDIT_TEXT": "EDIT",
        "EDIT_ARMATURE": "EDIT",
        "EDIT_METABALL": "EDIT",
        "EDIT_LATTICE": "EDIT",
        "POSE": "POSE",
        "SCULPT": "SCULPT",
        "PAINT_WEIGHT": "WEIGHT_PAINT",
        "PAINT_VERTEX": "VERTEX_PAINT",
        "PAINT_TEXTURE": "TEXTURE_PAINT",
        "PARTICLE": "PARTICLE_EDIT",
        "OBJECT": "OBJECT",
    }

    return mode_map.get(context_mode)
