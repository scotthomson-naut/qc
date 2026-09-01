# Python imports
from math import isclose

# Blender imports
import bpy
from mathutils import Matrix


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
    failed_objects = get_objects_scale()

    return {
        "issues": [
            "Failed object: {}".format(
                name
            )
            for name in failed_objects
        ],

        "failed_objects":
            failed_objects,

        "can_auto_fix":
            bool(
                failed_objects
            ),
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


def get_solidify_scale_factor(
        obj,
        tolerance=TOLERANCE,
    ):
    """
    Returns a practical Solidify thickness compensation factor.

    Uniform scale:
        Uses the exact absolute scale value.

    Non-uniform scale:
        Uses the geometric mean of the absolute XYZ scale values:

            (|sx| * |sy| * |sz|) ** (1 / 3)

        A Solidify modifier has only one scalar Thickness value, so there is
        no mathematically exact single value that preserves world thickness
        for every face normal under non-uniform scale. The geometric mean is
        a stable compromise that preserves the overall apparent thickness
        much better than leaving Thickness unchanged.

    Returns:
        tuple[float, bool]
            (factor, is_exact_uniform)
    """
    values = (
        abs(
            float(
                obj.scale.x
            )
        ),
        abs(
            float(
                obj.scale.y
            )
        ),
        abs(
            float(
                obj.scale.z
            )
        ),
    )

    is_uniform = (
        isclose(
            values[0],
            values[1],
            abs_tol=tolerance,
        )
        and isclose(
            values[1],
            values[2],
            abs_tol=tolerance,
        )
    )

    if is_uniform:
        return (
            (
                values[0]
                + values[1]
                + values[2]
            ) / 3.0,
            True,
        )

    # Defensive protection against a zero-scale axis.
    product = (
        values[0]
        * values[1]
        * values[2]
    )

    if product <= 0.0:
        return (
            1.0,
            False,
        )

    return (
        product ** (
            1.0 / 3.0
        ),
        False,
    )


def get_solidify_modifiers(
        obj,
    ):
    """
    Return Solidify modifiers on obj.
    """
    return [
        modifier
        for modifier in obj.modifiers
        if modifier.type == "SOLIDIFY"
    ]


def get_scale_fix_block_reason(
        obj,
    ):
    """
    Scale Applied no longer blocks Mesh objects simply because they have a
    Solidify modifier.

    Uniform Solidify scale compensation is exact. Non-uniform compensation
    uses a geometric-mean approximation so the object can still be fixed
    without the dramatic thickness blow-up caused by leaving Thickness
    unchanged.
    """
    return ""


def capture_scale_sensitive_modifier_state(
        obj,
    ):
    """
    Capture modifier values that must be compensated when object scale is
    baked into the mesh.
    """
    (
        scale_factor,
        exact_uniform,
    ) = get_solidify_scale_factor(
        obj
    )

    return {
        "solidify": [
            {
                "modifier_name":
                    modifier.name,

                "thickness":
                    float(
                        modifier.thickness
                    ),

                "scale_factor":
                    scale_factor,

                "exact_uniform":
                    exact_uniform,
            }
            for modifier in get_solidify_modifiers(
                obj
            )
        ],
    }


def restore_scale_sensitive_modifier_state(
        obj,
        modifier_state,
    ):
    """
    Compensate scale-sensitive modifier values after scale is baked.

    For uniform scale:
        new_thickness = old_thickness * old_scale

    Example:
        object scale      = 0.021
        Solidify thickness = -0.71

        compensated thickness:
            -0.71 * 0.021 = -0.01491
    """
    issues = []

    if not isinstance(
        modifier_state,
        dict,
    ):
        return issues

    for state in modifier_state.get(
        "solidify",
        [],
    ):
        modifier_name = state.get(
            "modifier_name",
            "",
        )

        modifier = obj.modifiers.get(
            modifier_name
        )

        if (
            modifier is None
            or modifier.type != "SOLIDIFY"
        ):
            issues.append(
                (
                    'Solidify modifier "{}" no longer exists on "{}".'
                ).format(
                    modifier_name,
                    obj.name,
                )
            )
            continue

        scale_factor = float(
            state.get(
                "scale_factor",
                1.0,
            )
        )

        previous_thickness = float(
            state.get(
                "thickness",
                modifier.thickness,
            )
        )

        modifier.thickness = (
            previous_thickness
            * scale_factor
        )

    return issues

def fix_objects_scale(
        result_data=None,
    ):
    """
    Applies scale to failed Mesh objects without changing the visible size or
    world-space transform of their children.

    Instead of bpy.ops.object.transform_apply(), this bakes obj.scale directly
    into the mesh data, resets obj.scale to 1, and compensates direct children
    through matrix_parent_inverse while preserving their matrix_basis.
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

    original_active = view_layer.objects.active
    original_selected = list(context.selected_objects)
    original_mode = context.mode

    if context.object is not None and context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError as error:
            return {
                "fixed_objects": {},
                "issues": [
                    "Could not enter Object Mode: {}".format(error)
                ],
            }

    candidates = []
    seen = set()

    for object_name in failed_objects:
        try:
            obj = get_qc_object(object_name)
        except NameError:
            obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(object_name)
            )
            continue

        try:
            if not is_object_available_for_qc(obj):
                continue
        except NameError:
            pass

        if obj.type != "MESH" or obj.data is None:
            continue

        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(obj.name)
            )
            continue

        if getattr(obj.data, "library", None) is not None:
            issues.append(
                "Skipped object with linked mesh data: {}".format(obj.name)
            )
            continue

        pointer = obj.as_pointer()
        if pointer in seen:
            continue

        seen.add(pointer)
        candidates.append(obj)

    candidates.sort(key=get_object_parent_depth)

    try:
        for obj in candidates:
            if obj.name not in bpy.data.objects:
                continue

            if not object_has_unapplied_scale(obj):
                continue

            mesh = obj.data
            previous_scale = tuple(obj.scale)

            modifier_state = (
                capture_scale_sensitive_modifier_state(
                    obj
                )
            )

            # Preserve only direct children. If their world transforms are
            # preserved, deeper descendants remain preserved automatically.
            child_states = []
            for child in list(obj.children):
                if child.name not in bpy.data.objects:
                    continue

                child_states.append({
                    "child": child,
                    "world": child.matrix_world.copy(),
                    "basis": child.matrix_basis.copy(),
                    "parent_type": child.parent_type,
                })

            if mesh.users > 1:
                mesh = mesh.copy()
                obj.data = mesh

            scale_matrix = Matrix.Diagonal((
                float(obj.scale.x),
                float(obj.scale.y),
                float(obj.scale.z),
                1.0,
            ))

            try:
                mesh.transform(scale_matrix, shape_keys=True)
            except TypeError:
                mesh.transform(scale_matrix)
            except Exception as error:
                issues.append(
                    'Could not bake scale into mesh for "{}": {}'.format(
                        obj.name,
                        error,
                    )
                )
                continue

            obj.scale = (1.0, 1.0, 1.0)

            try:
                mesh.update()
            except Exception:
                pass

            modifier_issues = (
                restore_scale_sensitive_modifier_state(
                    obj,
                    modifier_state,
                )
            )

            issues.extend(
                modifier_issues
            )

            view_layer.update()

            for state in child_states:
                child = state["child"]
                if child.name not in bpy.data.objects:
                    continue

                old_world = state["world"]
                old_basis = state["basis"]

                if child.parent is obj and state["parent_type"] == "OBJECT":
                    try:
                        new_parent_inverse = (
                            obj.matrix_world.inverted_safe()
                            @ old_world
                            @ old_basis.inverted_safe()
                        )
                        child.matrix_parent_inverse = new_parent_inverse
                        child.matrix_basis = old_basis
                    except Exception as error:
                        issues.append(
                            'Could not preserve child "{}" after fixing parent '
                            '"{}": {}'.format(child.name, obj.name, error)
                        )
                        try:
                            child.matrix_world = old_world
                        except Exception:
                            pass
                else:
                    try:
                        child.matrix_world = old_world
                    except Exception as error:
                        issues.append(
                            'Could not restore child "{}" after fixing parent '
                            '"{}": {}'.format(child.name, obj.name, error)
                        )

            view_layer.update()

            if object_has_unapplied_scale(obj):
                issues.append(
                    'Scale is still unapplied on "{}".'.format(obj.name)
                )
                continue

            fixed_objects[obj.name] = {
                "previous_scale":
                    previous_scale,

                "scale":
                    tuple(
                        obj.scale
                    ),

                "scale_applied":
                    True,

                "child_world_transforms_preserved":
                    True,

                "child_local_transforms_preserved":
                    True,

                "solidify_modifiers_compensated":
                    [
                        state[
                            "modifier_name"
                        ]
                        for state in modifier_state.get(
                            "solidify",
                            []
                        )
                    ],

                "solidify_compensation":
                    [
                        {
                            "modifier":
                                state[
                                    "modifier_name"
                                ],

                            "scale_factor":
                                state.get(
                                    "scale_factor",
                                    1.0,
                                ),

                            "exact":
                                bool(
                                    state.get(
                                        "exact_uniform",
                                        False,
                                    )
                                ),
                        }
                        for state in modifier_state.get(
                            "solidify",
                            []
                        )
                    ],
            }

    finally:
        for selected_obj in list(context.selected_objects):
            try:
                selected_obj.select_set(False)
            except RuntimeError:
                pass

        for selected_obj in original_selected:
            if selected_obj.name not in bpy.data.objects:
                continue
            if view_layer.objects.get(selected_obj.name) is None:
                continue
            try:
                selected_obj.select_set(True)
            except RuntimeError:
                pass

        if (
            original_active is not None
            and original_active.name in bpy.data.objects
            and view_layer.objects.get(original_active.name) is not None
        ):
            view_layer.objects.active = original_active

        if original_mode != "OBJECT" and view_layer.objects.active is not None:
            mode_name = get_mode_set_name(original_mode)
            if mode_name:
                try:
                    bpy.ops.object.mode_set(mode=mode_name)
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
