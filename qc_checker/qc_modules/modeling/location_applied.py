# Blender imports
import bpy



# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Location Applied"
DESCRIPTION = (
    "Checks if Object's Location is Applied"
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

def fix_objects_with_unapplied_location(result_data=None):
    """
    Moves normal Location values into Delta Location.

    This preserves:
        - Geometry world position
        - Origin/pivot world position
        - Rotation
        - Scale

    This is not equivalent to Object > Apply > Location.
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
                # Exact Blender Apply Transform Delta operation
                # -----------------------------------------

                # Use blender's function
                result = bpy.ops.object.transforms_to_deltas(
                    mode='LOC'
                )

                if "FINISHED" not in result:
                    issues.append(
                        "Could not apply location to {}.".format(
                            obj.name
                        )
                    )

                    continue

                fixed_objects[obj.name] = {
                    "delta_location_applied": True,
                }

            except Exception as error:
                issues.append(
                    "Could not apply location to {}: {}".format(
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
# ------------------------------------------------------------------------

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
