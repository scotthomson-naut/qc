# Python imports
from math import isclose

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Location Applied"
DESCRIPTION = (
    "Checks if Object's Location is Applied. "
    "Resets an object's location values in the sidebar to 0.0 on all axes "
    "while keeping its current visual position, by baking the offset "
    "directly into the mesh data."
)
WHY = (
    "This prevents unexpected jumps or offsets when using physics, "
    "simulations, modifiers, or constraints, and ensures a clean, "
    "predictable starting point before rigging. Note that this moves the "
    "object's origin/pivot to the world origin, same as Blender's native "
    "Object > Apply > Location - functional pivots (hinges, wheel "
    "centers, etc.) are expected to be defined afterward at the rigging "
    "stage (bones, empties, constraints), not carried on the raw mesh "
    "object's own origin."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

TOLERANCE = 1e-6


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
# -------------------------------------------------------------------------

def fix_objects_with_unapplied_location(
        result_data=None,
        max_retries=2,
    ):
    """
    Applies location to failed mesh objects using Blender's built-in:

        Object > Apply > Location

    All failed objects AND their mesh descendants are selected together and
    passed to a SINGLE transform_apply() call - the same thing that happens
    when a user selects a whole hierarchy and runs Object > Apply > Location
    manually. Blender's own operator already walks the selected hierarchy
    and pushes any compensating location into children as part of that one
    call, however deep the hierarchy goes.

    This bakes the offset directly into the mesh data and resets Location
    to (0, 0, 0), same as native Object > Apply > Location. This is a real
    bake, not a shuffle into Delta Location - Delta Location was previously
    used here to avoid moving the object's origin, but that created an
    incompatibility with how Rotation Applied (and Blender's own operators
    generally) compute hierarchy compensation, corrupting downstream
    fixes. Studio pipelines that need functional pivots preserved should
    define them at the rigging stage (bones, empties, constraints)
    afterward, not by leaving raw mesh objects unapplied.

    A small retry loop is still included, but only as a safety net for
    per-object selection problems (for example, an object that could not
    be unhidden/selected on the first attempt) - not because the hierarchy
    cascade itself requires multiple passes. Each retry re-selects the
    full candidate set again, in bulk, rather than one object per pass.

    Args:
        result_data (dict | None):
            Result returned by main().

        max_retries (int):
            Maximum number of full batch apply attempts, purely as a
            safety net. The hierarchy cascade itself resolves in a single
            successful batch call regardless of hierarchy depth.

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

    active_scene = bpy.context.scene

    def add_candidate(
            obj,
        ):
        if obj is None:
            return

        if not is_object_available_for_qc(
            obj
        ):
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

        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        if is_linked_object(
            obj
        ):
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

    original_locations = {
        obj.name:
            tuple(
                obj.location
            )
        for obj in candidate_objects
    }

    try:

        # -----------------------------------------------------
        # Apply + verify.
        #
        # The whole candidate set is selected TOGETHER and passed to a
        # single transform_apply() call, mirroring exactly what happens
        # when a user selects a parent/child hierarchy and runs
        # Object > Apply > Location manually. Blender resolves the entire
        # location-compensation cascade internally as part of that one
        # call, regardless of how many hierarchy levels are involved.
        # -----------------------------------------------------

        for attempt in range(
            max(
                1,
                int(
                    max_retries
                ),
            )
        ):

            # Only used to decide whether ANOTHER attempt is needed at
            # all - NOT used to build the selection below. Narrowing the
            # selection down to only currently-bad objects would only
            # ever select whichever single object became bad most
            # recently, discovering the next one a level down only on a
            # LATER attempt - the exact one-level-per-pass bug this
            # pattern exists to eliminate.
            still_needs_fix = [
                obj
                for obj in candidate_objects
                if (
                    obj.name in bpy.data.objects
                    and object_has_unapplied_location(
                        obj
                    )
                )
            ]

            if not still_needs_fix:
                break

            # Select the FULL candidate set together - every originally
            # failed object AND every one of its descendants, regardless
            # of what their location currently shows. This is what lets
            # Blender resolve the entire parent-to-child compensation
            # cascade in this single call, the same way it does when a
            # user selects the whole hierarchy natively and hits Apply
            # Location.
            batch = [
                obj
                for obj in candidate_objects
                if obj.name in bpy.data.objects
            ]

            # Blender applies location to the Mesh datablock. Make shared
            # meshes single-user first so other objects are not modified
            # unintentionally.
            for obj in batch:
                if obj.data.users > 1:
                    obj.data = (
                        obj.data.copy()
                    )

            # Temporarily reveal/unlock everything about to be batched,
            # remembering original states so they can be restored after.
            saved_visibility = {}

            for obj in batch:
                try:
                    original_hide_state = (
                        obj.hide_get()
                    )
                except RuntimeError:
                    original_hide_state = False

                saved_visibility[obj.name] = (
                    obj.hide_viewport,
                    obj.hide_select,
                    original_hide_state,
                )

                obj.hide_viewport = False
                obj.hide_select = False

                try:
                    obj.hide_set(
                        False
                    )
                except RuntimeError:
                    pass

            # Deselect everything currently selectable, then select the
            # whole batch together.
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

            for obj in batch:
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

                try:
                    result = (
                        bpy.ops.object.transform_apply(
                            location=True,
                            rotation=False,
                            scale=False,
                            properties=False,
                        )
                    )

                    if (
                        "FINISHED"
                        not in result
                    ):
                        issues.append(
                            "Could not apply location to selected object(s)."
                        )

                except Exception as error:
                    issues.append(
                        "Could not apply location: {}".format(
                            error
                        )
                    )

            # Restore visibility/selectability for every object in this
            # batch, regardless of outcome.
            for obj in batch:
                if obj.name not in bpy.data.objects:
                    continue

                (
                    hide_viewport,
                    hide_select,
                    hide_state,
                ) = saved_visibility[obj.name]

                obj.hide_viewport = hide_viewport
                obj.hide_select = hide_select

                try:
                    obj.hide_set(
                        hide_state
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
                "location_applied":
                    True,

                "previous_location":
                    original_location,

                "location":
                    tuple(
                        obj.location
                    ),
            }

        if still_failing:
            issues.append(
                (
                    "Location is still unapplied on {} object(s) after "
                    "{} attempt(s): {}"
                ).format(
                    len(
                        still_failing
                    ),
                    max(
                        1,
                        int(
                            max_retries
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