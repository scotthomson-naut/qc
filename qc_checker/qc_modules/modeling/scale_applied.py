# Python imports
from math import isclose

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Scale Applied"
DESCRIPTION = (
    "Checks if Object's Scale is Applied. "
    "Resets an object's transformation values in the sidebar to 1.0 "
    "on all axes while keeping its current visual size."
)
WHY = (
    "This prevents distorted textures, broken modifiers, incorrect physics, "
    "and uneven bevels by ensuring Blender calculates 3D math and "
    "effects uniformly."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

TOLERANCE=1e-5


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = []
    failed_objects = get_objects_scale()

    return {
        "issues": [
            "Failed object: {}".format(name)
            for name in failed_objects
        ],
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_objects_scale(result_data)

    return fixed


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_scale(
        objects=None,
        exclude_types=None
    ):
    """
    Returns a dictionary of objects whose transforms are not at defaults.

    Defaults:
        Scale    = (1,1,1)

    Args:
        objects (list): List of Blender objects.
                        Defaults to bpy.data.objects.
        tolerance (float): Floating point comparison tolerance.
        exclude_types (list): Object type to exclude.

    Returns:
        dict:
        {
            "Cube": {
                "scale": (1.0, 2.0, 1.0),
                "issues": [
                    "Scale"
                ]
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.data.objects

    if exclude_types is None:
        # Skip cameras and lights
        exclude_types = {'CAMERA', 'LIGHT'}

    results = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue

        if obj.type in exclude_types:
            continue

        if obj.type != "MESH":
            continue

        issues = []

        # -------------------------
        # Scale
        # -------------------------
        scale_bad = any(
            not isclose(v, 1.0, abs_tol=TOLERANCE)
            for v in obj.scale
        )

        if scale_bad:
            issues.append("Scale")

        # -------------------------
        if issues:
            results[obj.name] = {
                "scale": tuple(obj.scale),
                "issues": issues,
            }

    return results


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_scale(
        result_data=None,
        max_passes=3,
    ):
    """
    Applies scale to failed mesh objects using Blender's built-in:

        Object > Apply > Scale

    The objects are processed parent-first. This is important because
    applying scale to a parent can change a child's local transform while
    Blender preserves the child's world-space appearance.

    A small verification/retry loop is also used. If applying scale to one
    object causes another originally-failed object to become non-unit again,
    only the still-failing objects are processed on the next pass.

    Location and rotation are preserved.

    Args:
        result_data (dict | None):
            Result returned by main().

        max_passes (int):
            Maximum number of parent-first fix/verification passes.

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
    # Resolve original failures AND their mesh descendants.
    #
    # Important:
    # Applying scale to a parent can make a child that was previously
    # (1, 1, 1) acquire compensating local scale so Blender can preserve
    # the child's world-space appearance.
    #
    # Therefore descendants must participate in verification/retry even
    # when they did not fail the original QC run.
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

        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(
                    obj.name
                )
            )
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
            if descendant.library is not None:
                continue

            add_candidate(
                descendant
            )

    # Parent-first ordering is still important, but now newly-affected
    # descendants are also eligible for the internal retry passes.
    candidate_objects.sort(
        key=get_object_parent_depth
    )

    # Preserve scales before this fix modifies anything. This lets the
    # result explain when a previously-unit child became non-unit because
    # of a parent apply and was then corrected automatically.
    previous_scales = {
        obj.name:
            tuple(
                obj.scale
            )
        for obj in candidate_objects
    }

    try:

        # -----------------------------------------------------
        # Apply + verify.
        # -----------------------------------------------------

        for pass_index in range(
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
                    and object_has_unapplied_scale(
                        obj
                    )
                )
            ]

            if not remaining:
                break

            # Re-sort every pass in case hierarchy changed.
            remaining.sort(
                key=get_object_parent_depth
            )

            for obj in remaining:

                # A parent processed earlier in this pass may already
                # have changed this object's scale back to unit.
                if not object_has_unapplied_scale(
                    obj
                ):
                    continue

                # Blender applies scale to the Mesh datablock. Make
                # shared meshes single-user first so other objects are
                # not modified unintentionally.
                if obj.data.users > 1:
                    obj.data = (
                        obj.data.copy()
                    )

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

                    # Deselect everything currently selectable.
                    for selected_obj in list(
                        context.selected_objects
                    ):
                        try:
                            selected_obj.select_set(
                                False
                            )
                        except RuntimeError:
                            pass

                    # The object must belong to the current View Layer
                    # for an operator-based apply.
                    if (
                        view_layer.objects.get(
                            obj.name
                        )
                        is None
                    ):
                        issues.append(
                            (
                                'Could not apply scale to "{}": '
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

                    operator_result = (
                        bpy.ops.object.transform_apply(
                            location=False,
                            rotation=False,
                            scale=True,
                            properties=False,
                        )
                    )

                    if (
                        "FINISHED"
                        not in operator_result
                    ):
                        issues.append(
                            "Could not apply scale to {}.".format(
                                obj.name
                            )
                        )

                except Exception as error:
                    issues.append(
                        (
                            "Could not apply scale to {}: {}"
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

            if object_has_unapplied_scale(
                obj
            ):
                still_failing.append(
                    obj.name
                )

                continue

            # Only report an object as fixed when:
            #   - it originally failed, or
            #   - its scale changed during this operation because a parent
            #     apply affected it and we corrected it automatically.
            original_scale = previous_scales.get(
                obj.name,
                tuple(
                    obj.scale
                ),
            )

            scale_was_unit = all(
                isclose(
                    value,
                    1.0,
                    abs_tol=TOLERANCE,
                )
                for value in original_scale
            )

            if (
                obj.name not in original_failed_names
                and scale_was_unit
            ):
                # The descendant started valid and ended valid. It may have
                # temporarily changed between passes, but there is no need
                # to expose it as an original QC failure.
                continue

            fixed_objects[
                obj.name
            ] = {
                "previous_scale":
                    original_scale,

                "scale":
                    tuple(
                        obj.scale
                    ),

                "scale_applied":
                    True,
            }

        if still_failing:
            issues.append(
                (
                    "Scale is still unapplied on {} object(s) after "
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
# -------------------------------------------------------------------------

def get_object_descendants(
        obj,
    ):
    """
    Returns every descendant below obj in parent-first hierarchy order.

    Applying scale to a parent can alter local transforms anywhere below
    it, so these objects must be included in post-fix verification.
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

    Root objects return 0, their children return 1, etc.

    Applying transforms parent-first avoids a common case where fixing
    a parent after its child changes the child's local scale again.
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

        # Defensive protection against malformed/cyclic parenting.
        if pointer in visited:
            break

        visited.add(
            pointer
        )

        depth += 1

        parent = parent.parent

    return depth


def object_has_unapplied_scale(
        obj,
        tolerance=TOLERANCE,
    ):
    """
    Returns True when the object's scale is not (1, 1, 1).
    """
    return any(
        not isclose(
            value,
            1.0,
            abs_tol=tolerance,
        )
        for value in obj.scale
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

    return mode_map.get(
        context_mode
    )
