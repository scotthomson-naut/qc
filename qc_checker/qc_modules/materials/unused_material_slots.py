# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "Unused Material Slots"
DESCRIPTION = (
    "Checks for material slots that are not assigned to any face."
)


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Finds mesh objects with unused material slots.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_unused_material_slots()

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        unused_slots = object_data["unused_slots"]

        issues.append(
            (
                'Object "{}" has {} unused material slot{}: {}'
            ).format(
                object_name,
                len(unused_slots),
                "" if len(unused_slots) == 1 else "s",
                ", ".join(
                    str(slot["slot_index"])
                    for slot in unused_slots
                ),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data=None):
    """
    Removes unused material slots.

    Blender automatically updates polygon material indices.

    Returns:
        dict
    """
    return remove_unused_material_slots(
        result_data=result_data,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_unused_material_slots(
        objects=None,
    ):
    """
    Finds material slots that are not referenced by any face.

    Returns:
        dict
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        if obj.type != "MESH":
            continue

        mesh = obj.data

        slot_count = len(mesh.materials)

        if slot_count == 0:
            continue

        used_slots = set()

        for polygon in mesh.polygons:
            used_slots.add(
                polygon.material_index
            )

        unused_slots = []

        for slot_index in range(slot_count):

            if slot_index in used_slots:
                continue

            material = mesh.materials[
                slot_index
            ]

            unused_slots.append({
                "slot_index": slot_index,
                "material_name":
                    material.name
                    if material
                    else None,
            })

        if not unused_slots:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "slot_count": slot_count,
            "unused_slot_count": len(
                unused_slots
            ),
            "unused_slots": unused_slots,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def remove_unused_material_slots(
        result_data=None,
    ):
    """
    Removes unused material slots.

    Slots are removed from highest index to lowest so that
    indices remain valid while deleting.

    Returns:
        dict
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

    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():

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

        unused_slots = object_data.get(
            "unused_slots",
            [],
        )

        if not unused_slots:
            continue

        removed = []

        #
        # Blender's remove_material_slot operator requires
        # the object to be active.
        #
        bpy.context.view_layer.objects.active = obj

        obj.select_set(True)

        for slot in sorted(
            unused_slots,
            key=lambda x: x["slot_index"],
            reverse=True,
        ):

            slot_index = slot["slot_index"]

            if slot_index >= len(
                obj.material_slots
            ):
                continue

            obj.active_material_index = (
                slot_index
            )

            try:

                bpy.ops.object.material_slot_remove()

                removed.append(
                    slot_index
                )

            except Exception as error:

                issues.append(
                    (
                        'Could not remove material slot {} '
                        'from "{}": {}'
                    ).format(
                        slot_index,
                        object_name,
                        error,
                    )
                )

        if removed:

            fixed_objects[object_name] = {
                "removed_slots": sorted(
                    removed
                ),
                "removed_count": len(
                    removed
                ),
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
