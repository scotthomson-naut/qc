# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "Material Slot Usage"
DESCRIPTION = (
    "Checks for material slots that are not assigned to any face. "
    "Unused empty slots can be fixed automatically; populated unused slots "
    "are reported for manual review."
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

    Empty unused slots are safe to remove automatically.

    Populated unused slots are intentionally reported but not automatically
    removed because polygon material indices alone cannot prove that the
    material slot is unused by the wider production setup.

    Args:
        preferences (dict | None):
            User-configured check preferences.

    Returns:
        dict
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_objects = (
        get_objects_with_unused_material_slots(
            settings=settings,
        )
    )

    issues = []
    auto_fixable_slot_count = 0

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        unused_slots = object_data.get(
            "unused_slots",
            [],
        )

        empty_slots = [
            slot_data
            for slot_data in unused_slots
            if slot_data.get(
                "is_empty",
                False,
            )
        ]

        populated_slots = [
            slot_data
            for slot_data in unused_slots
            if not slot_data.get(
                "is_empty",
                False,
            )
        ]

        auto_fixable_slot_count += len(
            empty_slots
        )

        if empty_slots:
            issues.append(
                (
                    'Object "{}" has {} unused empty material slot{}: {}. '
                    "Automatic Fix can remove {}."
                ).format(
                    object_name,
                    len(
                        empty_slots
                    ),
                    ""
                    if len(
                        empty_slots
                    ) == 1
                    else "s",
                    ", ".join(
                        str(
                            slot_data.get(
                                "slot_index",
                                -1,
                            )
                        )
                        for slot_data in empty_slots
                    ),
                    "it"
                    if len(
                        empty_slots
                    ) == 1
                    else "them",
                )
            )

        if populated_slots:
            issues.append(
                (
                    'Object "{}" has {} populated material slot{} not '
                    "assigned to any face: {}. Manual review is required; "
                    "QC will not remove populated material slots automatically."
                ).format(
                    object_name,
                    len(
                        populated_slots
                    ),
                    ""
                    if len(
                        populated_slots
                    ) == 1
                    else "s",
                    ", ".join(
                        '{} "{}"'.format(
                            slot_data.get(
                                "slot_index",
                                -1,
                            ),
                            slot_data.get(
                                "material_name",
                                "Unknown",
                            ),
                        )
                        for slot_data in populated_slots
                    ),
                )
            )

    return {
        "issues":
            issues,

        "failed_objects":
            failed_objects,

        "settings":
            settings,

        "can_auto_fix":
            bool(
                auto_fixable_slot_count
            ),
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Removes only unused EMPTY material slots reported by the check.

    Populated unused material slots are never removed automatically.

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

    for obj in get_qc_objects(objects):

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

        # ---------------------------------------------------------
        # Preserve one material slot
        # ---------------------------------------------------------
        #
        # Material Assigned owns the requirement that a mesh has a
        # valid material slot. If this object has no polygons, every
        # slot is technically unused. Removing all of them here would
        # make Material Assigned fail again after it had already been
        # fixed.
        #
        # Therefore Material Slot Usage only reports/removes redundant
        # unused slots and never reduces a mesh below one slot.
        # ---------------------------------------------------------

        preserve_slot_index = (
            0
            if not used_slot_indices
            else None
        )

        for slot_index in range(
            slot_count
        ):
            if slot_index in used_slot_indices:
                continue

            if (
                preserve_slot_index is not None
                and slot_index == preserve_slot_index
            ):
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
    Removes only unused EMPTY material slots.

    Populated slots are deliberately preserved even when no polygon currently
    references them. Such slots may be intentional or used indirectly by
    production tools, modifiers, Geometry Nodes, exporters or scripts.

    Slots are recalculated immediately before removal and deleted from highest
    index to lowest index so lower material-slot indices remain valid.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

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
        obj = get_qc_object(
            object_name
        )

        if obj is None:
            issues.append(
                'Object "{}" is no longer available.'.format(
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

        current_unused_slots = (
            get_current_unused_slots(
                obj=obj,
                settings=settings,
            )
        )

        empty_unused_indices = [
            slot_data[
                "slot_index"
            ]
            for slot_data in current_unused_slots
            if (
                isinstance(
                    slot_data,
                    dict,
                )
                and slot_data.get(
                    "is_empty",
                    False,
                )
                and "slot_index"
                in slot_data
            )
        ]

        if not empty_unused_indices:
            continue

        removed_slots = []

        for slot_index in sorted(
            empty_unused_indices,
            reverse=True,
        ):
            # Material Assigned owns the requirement that a mesh retains
            # at least one valid material slot.
            if len(
                obj.material_slots
            ) <= 1:
                break

            success, error_message = (
                remove_material_slot_by_index(
                    obj=obj,
                    slot_index=slot_index,
                )
            )

            if not success:
                issues.append(
                    (
                        "Could not remove empty material slot {} "
                        'from object "{}": {}'
                    ).format(
                        slot_index,
                        object_name,
                        error_message,
                    )
                )
                continue

            removed_slots.append({
                "slot_index":
                    slot_index,

                "material_name":
                    None,

                "is_empty":
                    True,
            })

        if removed_slots:
            fixed_objects[
                object_name
            ] = {
                "removed_slot_count":
                    len(
                        removed_slots
                    ),

                "removed_slots":
                    sorted(
                        removed_slots,
                        key=lambda item: item[
                            "slot_index"
                        ],
                    ),
            }

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_current_unused_slots(
        obj,
        settings=None,
    ):
    """
    Recalculates the object's current unused material-slot data.
    """
    if (
        obj is None
        or obj.type != "MESH"
        or obj.library is not None
    ):
        return []

    results = (
        get_objects_with_unused_material_slots(
            objects=[
                obj
            ],
            settings=settings,
        )
    )

    object_data = results.get(
        obj.name,
        {},
    )

    unused_slots = object_data.get(
        "unused_slots",
        [],
    )

    if not isinstance(
        unused_slots,
        list,
    ):
        return []

    return unused_slots


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
