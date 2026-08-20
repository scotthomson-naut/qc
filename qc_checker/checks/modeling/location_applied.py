# Blender imports
import bpy



# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Location Applied"
DESCRIPTION = (
    "Checks if Object's Location is Applied. "
    "Resets an object's location delta's data to zero (X: 0, Y: 0, Z: 0)."
)
WHY = (
    "This prevents unexpected jumps or offsets when using physics, "
    "simulations, modifiers, or constraints."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

TOLERANCE=1e-6


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_unapplied_location()

    issues = []

    for object_name, data in failed_objects.items():
        location = data["location"]
        issues.append(
            "Failed object: {} - Location is not applied: "
            "({:.4f}, {:.4f}, {:.4f})".format(
                object_name,
                location[0],
                location[1],
                location[2],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_objects_with_unapplied_location(result_data)

    return fixed


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

    for obj in objects:
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

def fix_objects_with_unapplied_location(
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


# -------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------

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
