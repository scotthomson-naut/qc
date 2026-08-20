# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "Material Slot Usage"
DESCRIPTION = (
    "Checks for material slots that are not assigned to any face."
)
WHY = (
    "Helps you keep your project clean, prevents export errors, and saves"
    "computer memory. Unused slots add extra data that you do not need."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "ignore_last_empty_slot": {
        "type": "bool",
        "label": "Ignore Last Empty Slot",
        "description": (
            "Ignore the final material slot when it contains no material "
            "and is not assigned to any face."
        ),
        "default": False,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds mesh objects with unused material slots.

    Args:
        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_objects = get_objects_with_unused_material_slots(
        settings=settings,
    )

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        unused_slots = object_data.get(
            "unused_slots",
            [],
        )

        slot_labels = []

        for slot_data in unused_slots:
            slot_index = slot_data.get(
                "slot_index",
                -1,
            )

            material_name = slot_data.get(
                "material_name",
                None,
            )

            if material_name:
                slot_labels.append(
                    '{} "{}"'.format(
                        slot_index,
                        material_name,
                    )
                )
            else:
                slot_labels.append(
                    "{} (empty)".format(
                        slot_index
                    )
                )

        issues.append(
            (
                'Object "{}" has {} unused material slot{}: {}.'
            ).format(
                object_name,
                len(unused_slots),
                ""
                if len(unused_slots) == 1
                else "s",
                ", ".join(slot_labels),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "settings": settings,
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Removes unused material slots reported by the check.

    Args:
        result_data (dict | None):
            Result returned by main().

        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    return remove_unused_material_slots(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_unused_material_slots(
        objects=None,
        settings=None,
    ):
    """
    Finds material slots that are not referenced by any polygon.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to current scene objects.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "ObjectName": {
                "object_type": "MESH",
                "slot_count": 3,
                "used_slot_indices": [0],
                "unused_slot_count": 2,
                "unused_slots": [
                    {
                        "slot_index": 1,
                        "material_name": "Material.001",
                        "is_empty": False,
                        "is_last_slot": False,
                    },
                    {
                        "slot_index": 2,
                        "material_name": None,
                        "is_empty": True,
                        "is_last_slot": True,
                    },
                ],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    ignore_last_empty_slot = bool(
        settings.get(
            "ignore_last_empty_slot",
            False,
        )
    )

    failed_objects = {}

    for obj in objects:

        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        materials = getattr(
            mesh,
            "materials",
            None,
        )

        polygons = getattr(
            mesh,
            "polygons",
            None,
        )

        if materials is None or polygons is None:
            continue

        slot_count = len(materials)

        if slot_count == 0:
            continue

        used_slot_indices = set()

        for polygon in polygons:
            material_index = int(
                polygon.material_index
            )

            if 0 <= material_index < slot_count:
                used_slot_indices.add(
                    material_index
                )

        unused_slots = []
        last_slot_index = slot_count - 1

        for slot_index in range(
            slot_count
        ):
            if slot_index in used_slot_indices:
                continue

            material = materials[
                slot_index
            ]

            is_empty = material is None
            is_last_slot = (
                slot_index == last_slot_index
            )

            if (
                ignore_last_empty_slot
                and is_last_slot
                and is_empty
            ):
                continue

            unused_slots.append({
                "slot_index": slot_index,
                "material_name": (
                    material.name
                    if material is not None
                    else None
                ),
                "is_empty": is_empty,
                "is_last_slot": is_last_slot,
            })

        if not unused_slots:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "slot_count": slot_count,
            "used_slot_indices": sorted(
                used_slot_indices
            ),
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
        settings=None,
    ):
    """
    Removes unused material slots reported by the check.

    Slots are recalculated before removal and deleted from highest index
    to lowest index so lower material-slot indices remain valid.

    Args:
        result_data (dict | None):
            Result returned by main().

        settings (dict | None):
            Resolved settings.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

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

        if obj.library is not None:
            continue

        if obj.type != "MESH":
            issues.append(
                'Object "{}" is no longer a mesh.'.format(
                    object_name
                )
            )
            continue

        current_unused_indices = (
            get_current_unused_slot_indices(
                obj=obj,
                settings=settings,
            )
        )

        if not current_unused_indices:
            continue

        removed_slots = []

        for slot_index in sorted(
            current_unused_indices,
            reverse=True,
        ):
            material_name = None

            if 0 <= slot_index < len(
                obj.material_slots
            ):
                material = obj.material_slots[
                    slot_index
                ].material

                if material is not None:
                    material_name = material.name

            success, error_message = (
                remove_material_slot_by_index(
                    obj=obj,
                    slot_index=slot_index,
                )
            )

            if not success:
                issues.append(
                    (
                        "Could not remove material slot {} "
                        'from object "{}": {}'
                    ).format(
                        slot_index,
                        object_name,
                        error_message,
                    )
                )
                continue

            removed_slots.append({
                "slot_index": slot_index,
                "material_name": material_name,
            })

        if removed_slots:
            fixed_objects[object_name] = {
                "removed_slot_count": len(
                    removed_slots
                ),
                "removed_slots": sorted(
                    removed_slots,
                    key=lambda item: item[
                        "slot_index"
                    ],
                ),
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_current_unused_slot_indices(
        obj,
        settings=None,
    ):
    """
    Recalculates the object's currently unused material slot indices.

    Args:
        obj (bpy.types.Object):
            Mesh object to inspect.

        settings (dict | None):
            Resolved settings.

    Returns:
        list[int]
    """
    if (
        obj is None
        or obj.type != "MESH"
        or obj.library is not None
    ):
        return []

    results = get_objects_with_unused_material_slots(
        objects=[obj],
        settings=settings,
    )

    object_data = results.get(
        obj.name,
        {},
    )

    unused_slots = object_data.get(
        "unused_slots",
        [],
    )

    return [
        slot_data["slot_index"]
        for slot_data in unused_slots
        if isinstance(slot_data, dict)
        and "slot_index" in slot_data
    ]


def remove_material_slot_by_index(
        obj,
        slot_index,
    ):
    """
    Removes one material slot using the Blender operator.

    Args:
        obj (bpy.types.Object):
            Object containing the material slot.

        slot_index (int):
            Material slot index to remove.

    Returns:
        tuple[bool, str | None]:
            Success state and optional error message.
    """
    if obj is None:
        return False, "Object is unavailable."

    if obj.type != "MESH":
        return False, "Object is not a mesh."

    if obj.library is not None:
        return False, "Linked library object is read-only."

    if (
        slot_index < 0
        or slot_index >= len(obj.material_slots)
    ):
        return False, "Material slot index is out of range."

    view_layer = bpy.context.view_layer

    previous_active_object = (
        view_layer.objects.active
    )

    previously_selected = [
        selected_obj
        for selected_obj in bpy.context.selected_objects
    ]

    previous_mode = (
        obj.mode
        if hasattr(obj, "mode")
        else "OBJECT"
    )

    try:
        if bpy.context.object is not None:
            if bpy.context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(
                    mode="OBJECT"
                )

        bpy.ops.object.select_all(
            action="DESELECT"
        )

        obj.select_set(
            True
        )

        view_layer.objects.active = obj

        obj.active_material_index = int(
            slot_index
        )

        result = bpy.ops.object.material_slot_remove()

        if "FINISHED" not in result:
            return (
                False,
                "Blender did not finish removing the slot.",
            )

        return True, None

    except Exception as error:
        return False, str(error)

    finally:
        try:
            bpy.ops.object.select_all(
                action="DESELECT"
            )

            for selected_obj in previously_selected:
                if selected_obj.name in bpy.data.objects:
                    selected_obj.select_set(
                        True
                    )

            if (
                previous_active_object is not None
                and previous_active_object.name
                in bpy.data.objects
            ):
                view_layer.objects.active = (
                    previous_active_object
                )

            if (
                previous_active_object is not None
                and previous_mode != "OBJECT"
                and view_layer.objects.active
                == previous_active_object
            ):
                bpy.ops.object.mode_set(
                    mode=previous_mode
                )

        except Exception:
            pass
