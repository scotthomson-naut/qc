# Standard python imports
from math import isclose

# Blender imports
import bpy

# Company imports

# Constants
TOLERANCE=1e-5

# Meta data
LABEL = "Scale Applied"
DESCRIPTION = (
    "Checks if Object's Scale is Applied"
)

# -------------------------------------------------------------------------
# Templates
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
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

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
        if obj.type in exclude_types:
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


# -------------------------
# Fix
# -------------------------

def fix_objects_scale(result_data=None):
    """
    Applies scale using Blender's built-in:

        Object > Apply > Scale

    Location and rotation are preserved.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": {
                "Cube": {
                    "previous_scale": (2.0, 1.0, 0.5),
                    "scale": (1.0, 1.0, 1.0),
                }
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

    # transform_apply requires Object Mode.
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

            if not object_has_unapplied_scale(
                obj
            ):
                continue

            # Linked library objects cannot be modified.
            if obj.library is not None:
                issues.append(
                    "Skipped linked object: {}".format(
                        obj.name
                    )
                )
                continue

            previous_scale = tuple(
                obj.scale
            )

            # Blender applies the scale to the mesh datablock.
            # Make the mesh single-user so other objects sharing
            # the same data are not unintentionally changed.
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            # -----------------------------------------------------
            # Save visibility/selectability
            # -----------------------------------------------------

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
                    obj.hide_set(False)
                except RuntimeError:
                    pass

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

                # -------------------------------------------------
                # Exact Blender Apply Scale operation
                # -------------------------------------------------

                operator_result = (
                    bpy.ops.object.transform_apply(
                        location=False,
                        rotation=False,
                        scale=True,
                        properties=False,
                    )
                )

                if "FINISHED" not in operator_result:
                    issues.append(
                        "Could not apply scale to {}.".format(
                            obj.name
                        )
                    )
                    continue

                fixed_objects[obj.name] = {
                    "previous_scale":
                        previous_scale,

                    "scale":
                        tuple(obj.scale),

                    "scale_applied":
                        True,
                }

            except Exception as error:
                issues.append(
                    "Could not apply scale to {}: {}".format(
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

        # Restore original mode when possible.
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


# -------------------------
# Support Functions (Fix)
# -------------------------

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
