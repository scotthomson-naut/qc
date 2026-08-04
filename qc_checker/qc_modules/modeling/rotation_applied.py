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
    "Checks if Object's Rotation is Applied."
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

def fix_objects_rotation(result_data=None):
    """
    Applies rotation using Blender's built-in:

        Object > Apply > Rotation

    This uses:
        bpy.ops.object.transform_apply(
            location=False,
            rotation=True,
            scale=False,
        )

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": {
                "Cube": {
                    "rotation_applied": True,
                },
            },
            "issues": list[str],
        }
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(failed_objects, dict):
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
    if context.object is not None and context.mode != "OBJECT":
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

    try:
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

            if not object_has_rotation(
                obj
            ):
                continue

            # ---------------------------------------------
            # Make linked mesh data single-user
            # ---------------------------------------------

            # Blender applies the transform to the mesh datablock.
            # Copy shared data so other objects using the same mesh
            # are not unintentionally modified.
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            # ---------------------------------------------
            # Make object available to the operator
            # ---------------------------------------------

            original_hide_viewport = (
                obj.hide_viewport
            )

            try:
                original_hide_state = (
                    obj.hide_get()
                )
            except RuntimeError:
                original_hide_state = False

            original_hide_select = (
                obj.hide_select
            )

            try:
                obj.hide_viewport = False
                obj.hide_select = False
                obj.hide_set(False)

                # Deselect everything.
                for selected_obj in list(
                    context.selected_objects
                ):
                    selected_obj.select_set(
                        False
                    )

                # Select and activate only this object.
                obj.select_set(
                    True
                )

                view_layer.objects.active = (
                    obj
                )

                # -----------------------------------------
                # Exact Blender Apply Rotation operation
                # -----------------------------------------

                result = bpy.ops.object.transform_apply(
                    location=False,
                    rotation=True,
                    scale=False,
                    properties=False,
                )

                if "FINISHED" not in result:
                    issues.append(
                        "Could not apply rotation to {}.".format(
                            obj.name
                        )
                    )

                    continue

                fixed_objects[obj.name] = {
                    "rotation_applied": True,
                }

            except Exception as error:
                issues.append(
                    "Could not apply rotation to {}: {}".format(
                        obj.name,
                        error,
                    )
                )

            finally:
                # Restore this object's visibility settings.
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

            try:
                selected_obj.select_set(
                    True
                )
            except RuntimeError:
                pass

        if (
            original_active is not None
            and original_active.name in bpy.data.objects
        ):
            view_layer.objects.active = (
                original_active
            )

        # Restore the original mode when possible.
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
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

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
