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

TOLERANCE = 1e-6


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
        "default": "PRESERVE_PIVOT",
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
        max_passes=3,
    ):
    """
    Moves normal Location values into Delta Location.

    The fix is hierarchy-aware.

    Moving a parent's normal location into Delta Location can change a
    child's local Location while Blender preserves the child's world-space
    appearance. Therefore the fix:

        1. Includes descendants of originally failed objects.
        2. Processes parents before children.
        3. Verifies the whole affected hierarchy after each pass.
        4. Retries only objects that still have non-zero normal Location.

    This preserves:
        - Geometry world position
        - Origin/pivot world position
        - Rotation
        - Scale

    This is not equivalent to Object > Apply > Location.

    Args:
        result_data (dict | None):
            Result returned by main().

        max_passes (int):
            Maximum number of verification/retry passes.

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

    # ---------------------------------------------------------
    # Save current Blender state
    # ---------------------------------------------------------

    original_active = (
        view_layer.objects.active
    )

    original_selected = list(
        context.selected_objects
    )

    original_mode = (
        context.mode
    )

    if (
        context.object is not None
        and context.mode != "OBJECT"
    ):
        try:
            bpy.ops.object.mode_set(
                mode="OBJECT"
            )

        except RuntimeError as error:
            return {
                "fixed_objects": {},
                "issues": [
                    "Could not enter Object Mode: {}".format(
                        error
                    )
                ],
            }

    # ---------------------------------------------------------
    # Resolve original failures and their mesh descendants.
    # ---------------------------------------------------------

    original_failed_objects = []
    candidate_objects = []
    candidate_names = set()

    def add_candidate(
            obj,
        ):
        if obj is None:
            return

        if obj.type != "MESH":
            return

        if obj.data is None:
            return

        if obj.name in candidate_names:
            return

        if is_linked_object(
            obj
        ):
            return

        candidate_names.add(
            obj.name
        )

        candidate_objects.append(
            obj
        )

    for object_name in failed_objects:

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

        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        if is_linked_object(
            obj
        ):
            # Normally this should not be reached because linked objects
            # are excluded by the Find stage, but keep the guard here in
            # case an older/stale result_data payload is being fixed.
            continue

        original_failed_objects.append(
            obj
        )

        add_candidate(
            obj
        )

        for descendant in get_object_descendants(
            obj
        ):
            add_candidate(
                descendant
            )

    candidate_objects.sort(
        key=get_object_parent_depth
    )

    original_locations = {
        obj.name:
            tuple(
                obj.location
            )
        for obj in candidate_objects
    }

    try:

        # -----------------------------------------------------
        # Apply + verify
        # -----------------------------------------------------

        for _pass_index in range(
            max(
                1,
                int(
                    max_passes
                ),
            )
        ):

            remaining = [
                obj
                for obj in candidate_objects
                if (
                    obj.name in bpy.data.objects
                    and object_has_unapplied_location(
                        obj
                    )
                )
            ]

            if not remaining:
                break

            remaining.sort(
                key=get_object_parent_depth
            )

            for obj in remaining:

                # A parent processed earlier in the pass may already
                # have resolved this object's local location.
                if not object_has_unapplied_location(
                    obj
                ):
                    continue

                original_hide_viewport = (
                    obj.hide_viewport
                )

                original_hide_select = (
                    obj.hide_select
                )

                try:
                    original_hide_state = (
                        obj.hide_get()
                    )
                except RuntimeError:
                    original_hide_state = False

                try:
                    obj.hide_viewport = False
                    obj.hide_select = False

                    try:
                        obj.hide_set(
                            False
                        )
                    except RuntimeError:
                        pass

                    for selected_obj in list(
                        context.selected_objects
                    ):
                        try:
                            selected_obj.select_set(
                                False
                            )
                        except RuntimeError:
                            pass

                    if (
                        view_layer.objects.get(
                            obj.name
                        )
                        is None
                    ):
                        issues.append(
                            (
                                'Could not apply location to "{}": '
                                "object is not in the current View Layer."
                            ).format(
                                obj.name
                            )
                        )
                        continue

                    obj.select_set(
                        True
                    )

                    view_layer.objects.active = (
                        obj
                    )

                    result = (
                        bpy.ops.object.transforms_to_deltas(
                            mode="LOC"
                        )
                    )

                    if (
                        "FINISHED"
                        not in result
                    ):
                        issues.append(
                            "Could not apply location to {}.".format(
                                obj.name
                            )
                        )

                except Exception as error:
                    issues.append(
                        (
                            "Could not apply location to {}: {}"
                        ).format(
                            obj.name,
                            error,
                        )
                    )

                finally:
                    obj.hide_viewport = (
                        original_hide_viewport
                    )

                    obj.hide_select = (
                        original_hide_select
                    )

                    try:
                        obj.hide_set(
                            original_hide_state
                        )
                    except RuntimeError:
                        pass

            view_layer.update()

        # -----------------------------------------------------
        # Final verification
        # -----------------------------------------------------

        still_failing = []

        original_failed_names = {
            obj.name
            for obj in original_failed_objects
        }

        for obj in candidate_objects:

            if obj.name not in bpy.data.objects:
                continue

            if object_has_unapplied_location(
                obj
            ):
                still_failing.append(
                    obj.name
                )
                continue

            original_location = (
                original_locations.get(
                    obj.name,
                    tuple(
                        obj.location
                    ),
                )
            )

            started_with_location = any(
                abs(
                    value
                ) > TOLERANCE
                for value in original_location
            )

            if (
                obj.name not in original_failed_names
                and not started_with_location
            ):
                continue

            fixed_objects[
                obj.name
            ] = {
                "delta_location_applied":
                    True,

                "previous_location":
                    original_location,

                "location":
                    tuple(
                        obj.location
                    ),

                "delta_location":
                    tuple(
                        obj.delta_location
                    ),
            }

        if still_failing:
            issues.append(
                (
                    "Location is still unapplied on {} object(s) after "
                    "{} pass(es): {}"
                ).format(
                    len(
                        still_failing
                    ),
                    max(
                        1,
                        int(
                            max_passes
                        ),
                    ),
                    ", ".join(
                        still_failing
                    ),
                )
            )

    finally:
        # -----------------------------------------------------
        # Restore original selection
        # -----------------------------------------------------

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

            if selected_obj.name not in bpy.data.objects:
                continue

            if (
                view_layer.objects.get(
                    selected_obj.name
                )
                is None
            ):
                continue

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
            ) is not None
        ):
            view_layer.objects.active = (
                original_active
            )

        if (
            original_mode != "OBJECT"
            and view_layer.objects.active is not None
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
