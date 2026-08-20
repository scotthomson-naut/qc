# Python imports
from math import isclose

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Rotation Applied"
DESCRIPTION = (
    "Checks if Object's Rotation is Applied. "
    "Resets an object's rotation values in Object Mode back to zero "
    "(X=0, Y=0, Z=0) while permanently baking its current physical "
    "orientation into the mesh data."
)
WHY = (
    "This aligns the local axes with the global axes, ensuring that "
    "modifiers, physics, UV unwrapping, and animations behave predictably."
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
    failed_objects = get_objects_rotation()

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
    fixed = fix_objects_rotation(result_data)

    return fixed


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_rotation(
        objects=None,
        exclude_types=None
    ):
    """
    Returns a dictionary of objects whose transforms are not at defaults.

    Defaults:
        Rotation = (0,0,0)

    Args:
        objects (list): List of Blender objects.
                        Defaults to bpy.data.objects.
        exclude_types (list): Object type to exclude.

    Returns:
        dict:
        {
            "Cube": {
                "rotation": (0.0, 0.5, 0.0),
                "issues": [
                    "Rotation",
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
        # Rotation
        # -------------------------
        if obj.rotation_mode == 'QUATERNION':
            rotation = tuple(obj.rotation_quaternion)
            rotation_bad = (
                not isclose(rotation[0], 1.0, abs_tol=TOLERANCE)
                or any(
                    not isclose(v, 0.0, abs_tol=TOLERANCE)
                    for v in rotation[1:]
                )
            )

        elif obj.rotation_mode == 'AXIS_ANGLE':
            rotation = tuple(obj.rotation_axis_angle)
            rotation_bad = not isclose(rotation[0], 0.0, abs_tol=TOLERANCE)

        else:
            rotation = tuple(obj.rotation_euler)
            rotation_bad = any(
                not isclose(v, 0.0, abs_tol=TOLERANCE)
                for v in rotation
            )

        if rotation_bad:
            issues.append("Rotation")

        # -------------------------
        if issues:
            results[obj.name] = {
                "rotation": rotation,
                "issues": issues,
            }

    return results


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_rotation(
        result_data=None,
        max_passes=3,
    ):
    """
    Applies rotation to failed mesh objects using Blender's built-in:

        Object > Apply > Rotation

    The fix is hierarchy-aware.

    Applying rotation to a parent can change a child's local rotation while
    Blender preserves the child's world-space appearance. Therefore the fix:

        1. Includes descendants of originally failed objects.
        2. Processes parents before children.
        3. Verifies the whole affected hierarchy after each pass.
        4. Retries only objects that still have non-identity rotation.

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

    # Blender's transform_apply operator requires Object Mode.
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
    # Resolve original failures and their mesh descendants
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

        if obj.library is not None:
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
            add_candidate(
                descendant
            )

    candidate_objects.sort(
        key=get_object_parent_depth
    )

    original_rotations = {
        obj.name:
            get_object_rotation_tuple(
                obj
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
                    and object_has_rotation(
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

                # A parent fixed earlier in the pass may already have
                # resolved this object's local rotation.
                if not object_has_rotation(
                    obj
                ):
                    continue

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
                                'Could not apply rotation to "{}": '
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
                        bpy.ops.object.transform_apply(
                            location=False,
                            rotation=True,
                            scale=False,
                            properties=False,
                        )
                    )

                    if (
                        "FINISHED"
                        not in result
                    ):
                        issues.append(
                            "Could not apply rotation to {}.".format(
                                obj.name
                            )
                        )

                except Exception as error:
                    issues.append(
                        (
                            "Could not apply rotation to {}: {}"
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

            if object_has_rotation(
                obj
            ):
                still_failing.append(
                    obj.name
                )
                continue

            original_rotation = (
                original_rotations.get(
                    obj.name,
                    get_object_rotation_tuple(
                        obj
                    ),
                )
            )

            started_with_rotation = (
                rotation_tuple_has_rotation(
                    obj,
                    original_rotation,
                    tolerance=TOLERANCE,
                )
            )

            # Report original failures, and any descendant that was made
            # non-identity during this fix and required correction.
            if (
                obj.name not in original_failed_names
                and not started_with_rotation
            ):
                continue

            fixed_objects[
                obj.name
            ] = {
                "rotation_applied":
                    True,

                "previous_rotation":
                    original_rotation,

                "rotation":
                    get_object_rotation_tuple(
                        obj
                    ),
            }

        if still_failing:
            issues.append(
                (
                    "Rotation is still unapplied on {} object(s) after "
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


def get_object_rotation_tuple(
        obj,
    ):
    """
    Returns the object's current rotation in its active rotation mode.
    """
    if obj.rotation_mode == "QUATERNION":
        return tuple(
            obj.rotation_quaternion
        )

    if obj.rotation_mode == "AXIS_ANGLE":
        return tuple(
            obj.rotation_axis_angle
        )

    return tuple(
        obj.rotation_euler
    )


def rotation_tuple_has_rotation(
        obj,
        rotation,
        tolerance=TOLERANCE,
    ):
    """
    Tests a stored rotation tuple using obj's current rotation mode.
    """
    if obj.rotation_mode == "QUATERNION":

        return (
            not isclose(
                rotation[0],
                1.0,
                abs_tol=tolerance,
            )
            or any(
                not isclose(
                    value,
                    0.0,
                    abs_tol=tolerance,
                )
                for value in rotation[
                    1:
                ]
            )
        )

    if obj.rotation_mode == "AXIS_ANGLE":

        return not isclose(
            rotation[0],
            0.0,
            abs_tol=tolerance,
        )

    return any(
        not isclose(
            value,
            0.0,
            abs_tol=tolerance,
        )
        for value in rotation
    )


def object_has_rotation(
        obj,
        tolerance=TOLERANCE,
    ):
    """
    Checks whether an object has non-identity rotation.

    Supports:
        - Euler
        - Quaternion
        - Axis Angle
    """
    if obj.rotation_mode == "QUATERNION":

        rotation = obj.rotation_quaternion

        return (
            not isclose(
                rotation.w,
                1.0,
                abs_tol=tolerance,
            )
            or not isclose(
                rotation.x,
                0.0,
                abs_tol=tolerance,
            )
            or not isclose(
                rotation.y,
                0.0,
                abs_tol=tolerance,
            )
            or not isclose(
                rotation.z,
                0.0,
                abs_tol=tolerance,
            )
        )

    if obj.rotation_mode == "AXIS_ANGLE":

        return not isclose(
            obj.rotation_axis_angle[0],
            0.0,
            abs_tol=tolerance,
        )

    return any(
        not isclose(
            value,
            0.0,
            abs_tol=tolerance,
        )
        for value in obj.rotation_euler
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
