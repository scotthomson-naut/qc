# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Material Assigned"
DESCRIPTION = (
    "Checks for objects that have missing materials, empty material slots, "
    "or faces assigned to invalid or empty material slots."
)
WHY = (
    "Prevents rendering errors, export failures, and game engine crashes. "
    "It cleans up your project data before sharing or rendering."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds mesh objects with missing materials.

    Returns:
        dict
    """
    failed_objects = get_objects_with_missing_materials()

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        reasons = object_data.get(
            "reasons",
            [],
        )

        issues.append(
            'Object "{}": {}'.format(
                object_name,
                "; ".join(reasons),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Creates and assigns a placeholder material where needed.

    Returns:
        dict
    """
    return assign_placeholder_materials(
        result_data=result_data,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_missing_materials(
        objects=None,
    ):
    """
    Finds mesh objects with missing materials.

    Returns:
        dict
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = obj.data
        materials = mesh.materials
        reasons = []
        empty_slots = []
        invalid_faces = []

        # ---------------------------------------------------------
        # No material slots
        # ---------------------------------------------------------

        if len(materials) == 0:
            reasons.append(
                "Object has no material slots."
            )

        else:
            # -----------------------------------------------------
            # Empty slots
            # -----------------------------------------------------

            for slot_index, material in enumerate(
                materials
            ):
                if material is None:
                    empty_slots.append(
                        slot_index
                    )

            if empty_slots:

                reasons.append(
                    "Empty material slot(s): {}".format(
                        ", ".join(
                            str(i)
                            for i in empty_slots
                        )
                    )
                )

            # -----------------------------------------------------
            # Faces
            # -----------------------------------------------------
            slot_count = len(
                materials
            )

            for polygon in mesh.polygons:
                material_index = (
                    polygon.material_index
                )

                invalid = False

                if (
                    material_index < 0
                    or material_index >= slot_count
                ):
                    invalid = True

                elif (
                    materials[
                        material_index
                    ]
                    is None
                ):
                    invalid = True

                if invalid:
                    invalid_faces.append(
                        polygon.index
                    )

            if invalid_faces:
                reasons.append(
                    "{} face(s) use missing materials.".format(
                        len(
                            invalid_faces
                        )
                    )
                )

        if not reasons:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,

            "reason_count": len(
                reasons
            ),
            "reasons": reasons,
            "empty_slots": empty_slots,
            "invalid_faces": invalid_faces,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def assign_placeholder_materials(
        result_data=None,
    ):
    """
    Assigns a placeholder material.

    - Creates a material slot if none exist.
    - Fills empty slots.
    - Reassigns invalid faces.
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

    placeholder = get_placeholder_material()

    fixed_objects = {}

    issues = []

    for object_name, object_data in failed_objects.items():

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            continue

        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = obj.data

        materials = mesh.materials

        changes = []

        # ---------------------------------------------------------
        # No slots
        # ---------------------------------------------------------

        if len(materials) == 0:

            materials.append(
                placeholder
            )

            changes.append(
                "Created material slot."
            )

        # ---------------------------------------------------------
        # Empty slots
        # ---------------------------------------------------------

        for index, material in enumerate(
            materials
        ):

            if material is None:

                materials[index] = (
                    placeholder
                )

                changes.append(
                    "Filled slot {}".format(
                        index
                    )
                )

        # ---------------------------------------------------------
        # Faces
        # ---------------------------------------------------------

        slot_count = len(
            materials
        )

        for polygon in mesh.polygons:

            material_index = (
                polygon.material_index
            )

            invalid = False

            if (
                material_index < 0
                or material_index >= slot_count
            ):
                invalid = True

            elif (
                materials[
                    material_index
                ]
                is None
            ):
                invalid = True

            if invalid:

                polygon.material_index = 0

        if changes:

            fixed_objects[
                object_name
            ] = {
                "changes": changes,
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_placeholder_material():

    material = bpy.data.materials.get(
        "QC_MissingMaterial"
    )

    if material is None:

        material = bpy.data.materials.new(
            "QC_MissingMaterial"
        )

        material.use_nodes = True

    return material
