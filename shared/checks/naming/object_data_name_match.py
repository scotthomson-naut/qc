# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Object/Data Name Match"
DESCRIPTION = (
    "Checks that single-user datablock names match their object "
    "names, across every object type (Mesh, Camera, Curve, "
    "Armature, Light, etc). Like BoxRed -> Cube.001 "
    "Shared datablocks are allowed and ignored. "
)
WHY = (
    "An object holds position and rotation data, while its internal datablock "
    "holds the actual geometry or properties. When they mismatch, "
    "identifying assets becomes difficult."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks whether object names match their datablock names, across
    every object type.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_mismatched_data_names()
    )

    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Datablock is named '{}'".format(
                object_name,
                data["datablock_name"],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(
        result_data=None,
    ):
    """
    Fixes the CURRENT Object/Data Name Match failures.

    Other naming checks may rename an object after this check was run.
    Stored result_data is therefore not a safe object identifier for a
    naming fix. Re-evaluating the inexpensive naming check here ensures
    rename operations are built from the current object/datablock names.
    """
    live_failed_objects = (
        get_objects_with_mismatched_data_names()
    )

    live_result_data = {
        "failed_objects":
            live_failed_objects,
    }

    return fix_objects_with_mismatched_data_names(
        live_result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_mismatched_data_names(
        objects=None,
    ):
    """
    Finds single-user objects (of any type) whose object name does
    not match their datablock name.

    Note:
        Unlike the original version of this check, this is no longer
        restricted to obj.type == "MESH" - every object type with a
        datablock (Camera, Curve, Armature, Light, Lattice, Metaball,
        Speaker, GreasePencil, etc.) is checked the same way, since
        every datablock type shares the same .name and .users
        properties (inherited from Blender's base ID type), and the
        comparison logic and severity don't actually differ by
        object type. Empty objects (obj.data is always None) are
        naturally skipped, same as before.

        Shared datablocks are intentionally ignored because one
        datablock cannot match multiple differently named objects.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_name": "Cube",
                "datablock_name": "Mesh.002",
                "datablock_users": 1,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        # Linked library objects and linked datablocks are outside the scope
        # of local automatic naming fixes.
        if obj.library is not None:
            continue

        if obj.data is None:
            continue

        if getattr(
            obj.data,
            "library",
            None,
        ) is not None:
            continue

        # Shared datablocks are valid and cannot necessarily match
        # every object name.
        if obj.data.users > 1:
            continue

        if obj.name == obj.data.name:
            continue

        failed_objects[obj.name] = {
            "object_name": obj.name,
            "datablock_name": obj.data.name,
            "datablock_users": obj.data.users,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_datablock_collection(
        datablock,
    ):
    """
    Returns the bpy.data collection containing datablock.

    Important:
        Do NOT key this from datablock.bl_rna.identifier.

        Blender uses subtype RNA identifiers for several datablocks. For
        example, lights can report identifiers such as SpotLight/AreaLight
        and text data can report TextCurve instead of the base Light/Curve
        identifiers. They still live in bpy.data.lights and bpy.data.curves.

        isinstance() against Blender's base RNA types correctly handles
        those subclasses.
    """
    type_map = (
        (
            bpy.types.Mesh,
            bpy.data.meshes,
            "MESH",
        ),
        (
            bpy.types.Curve,
            bpy.data.curves,
            "CURVE",
        ),
        (
            bpy.types.Camera,
            bpy.data.cameras,
            "CAMERA",
        ),
        (
            bpy.types.Light,
            bpy.data.lights,
            "LIGHT",
        ),
        (
            bpy.types.Armature,
            bpy.data.armatures,
            "ARMATURE",
        ),
        (
            bpy.types.Lattice,
            bpy.data.lattices,
            "LATTICE",
        ),
        (
            bpy.types.MetaBall,
            bpy.data.metaballs,
            "METABALL",
        ),
        (
            bpy.types.Speaker,
            bpy.data.speakers,
            "SPEAKER",
        ),
    )

    # Volume is unavailable in some older Blender builds, so guard it.
    volume_type = getattr(
        bpy.types,
        "Volume",
        None,
    )

    if (
        volume_type is not None
        and isinstance(
            datablock,
            volume_type,
        )
    ):
        return (
            bpy.data.volumes,
            "VOLUME",
        )

    # Grease Pencil changed API/type names between Blender generations.
    grease_pencil_type = getattr(
        bpy.types,
        "GreasePencilv3",
        None,
    )

    if grease_pencil_type is None:
        grease_pencil_type = getattr(
            bpy.types,
            "GreasePencil",
            None,
        )

    grease_pencils = getattr(
        bpy.data,
        "grease_pencils",
        None,
    )

    if (
        grease_pencil_type is not None
        and grease_pencils is not None
        and isinstance(
            datablock,
            grease_pencil_type,
        )
    ):
        return (
            grease_pencils,
            "GREASE_PENCIL",
        )

    for (
        datablock_type,
        collection,
        collection_key,
    ) in type_map:

        if isinstance(
            datablock,
            datablock_type,
        ):
            return (
                collection,
                collection_key,
            )

    return (
        None,
        None,
    )

# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_with_mismatched_data_names(
        result_data=None,
    ):
    """
    Renames single-user datablocks to match their object names.

    The rename is solved as a dependency graph before Blender data is
    modified. This safely handles rename chains and cycles while allowing
    unrelated safe renames to continue when one target has a live blocker.

    Rules:
        - Shared datablocks are never renamed automatically.
        - Rename cycles are supported.
        - Zero-user/orphan datablocks occupying a target name are moved aside.
        - A live external blocker prevents only the dependent rename chain.
        - Safe datablocks are staged under temporary names before final names
          are assigned, preventing Blender from generating .001 suffixes.
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
    rename_items = []

    # ---------------------------------------------------------
    # Gather valid rename operations
    # ---------------------------------------------------------

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

        datablock = obj.data

        if datablock is None:
            continue

        if datablock.users > 1:
            issues.append(
                (
                    'Skipped "{}": datablock "{}" '
                    'is shared by {} users.'
                ).format(
                    obj.name,
                    datablock.name,
                    datablock.users,
                )
            )
            continue

        if datablock.name == obj.name:
            continue

        (
            collection,
            collection_key,
        ) = get_datablock_collection(
            datablock
        )

        if collection is None:
            issues.append(
                (
                    'Could not determine datablock collection '
                    'for object "{}".'
                ).format(
                    obj.name
                )
            )
            continue

        rename_items.append({
            "object": obj,
            "datablock": datablock,
            "collection": collection,
            # Group by the actual bpy.data namespace, not the RNA subtype.
            # SpotLight/AreaLight all share bpy.data.lights; TextCurve and
            # other Curve subtypes all share bpy.data.curves.
            "collection_key": collection_key,
            "old_name": datablock.name,
            "target_name": obj.name,
            "safe": True,
            "blocked_reason": None,
            "dependency": None,
            "orphan_blocker": None,
        })

    if not rename_items:
        return {
            "fixed_objects": {},
            "issues": issues,
        }

    # ---------------------------------------------------------
    # Group by stable datablock type
    # ---------------------------------------------------------

    groups = {}

    for item in rename_items:
        key = item[
            "collection_key"
        ]

        if key not in groups:
            groups[key] = {
                "collection": item[
                    "collection"
                ],
                "items": [],
            }

        groups[key][
            "items"
        ].append(
            item
        )

    # ---------------------------------------------------------
    # Process each datablock type independently
    # ---------------------------------------------------------

    for group in groups.values():
        collection = group[
            "collection"
        ]
        items = group[
            "items"
        ]

        item_by_datablock = {
            item["datablock"]: item
            for item in items
        }
        affected_datablocks = set(
            item_by_datablock.keys()
        )

        # -----------------------------------------------------
        # Preflight target ownership
        # -----------------------------------------------------

        for item in items:
            target_name = item[
                "target_name"
            ]
            datablock = item[
                "datablock"
            ]
            blocker = collection.get(
                target_name
            )

            if blocker is None:
                continue
            if blocker is datablock:
                continue

            if blocker in affected_datablocks:
                item[
                    "dependency"
                ] = item_by_datablock[
                    blocker
                ]
                continue

            if blocker.users == 0:
                item[
                    "orphan_blocker"
                ] = blocker
                continue

            item[
                "safe"
            ] = False
            item[
                "blocked_reason"
            ] = (
                (
                    'Manual naming conflict for "{}": datablock "{}" '
                    'cannot be renamed to "{}" because another live '
                    'datablock already owns that exact name ({} user(s)). '
                    'Running Fix again cannot resolve this safely; rename '
                    'one of the conflicting datablocks/objects manually.'
                ).format(
                    item["object"].name,
                    datablock.name,
                    target_name,
                    blocker.users,
                )
            )

        # -----------------------------------------------------
        # Propagate blocked dependencies
        # -----------------------------------------------------

        changed = True
        while changed:
            changed = False
            for item in items:
                if not item[
                    "safe"
                ]:
                    continue

                dependency = item.get(
                    "dependency"
                )
                if dependency is None:
                    continue
                if dependency[
                    "safe"
                ]:
                    continue

                item[
                    "safe"
                ] = False
                item[
                    "blocked_reason"
                ] = (
                    (
                        'Cannot rename datablock for "{}" to "{}": '
                        'the datablock currently using that name '
                        'cannot be moved safely.'
                    ).format(
                        item["object"].name,
                        item["target_name"],
                    )
                )
                changed = True

        # -----------------------------------------------------
        # Move orphan blockers for safe items only
        # -----------------------------------------------------

        safe_items = [
            item
            for item in items
            if item[
                "safe"
            ]
        ]

        orphan_blockers = []
        seen_orphans = set()

        for item in safe_items:
            blocker = item.get(
                "orphan_blocker"
            )
            if blocker is None:
                continue

            pointer = blocker.as_pointer()
            if pointer in seen_orphans:
                continue

            seen_orphans.add(
                pointer
            )
            orphan_blockers.append(
                blocker
            )

        for index, blocker in enumerate(
            orphan_blockers
        ):
            old_orphan_name = blocker.name
            orphan_temp_name = (
                "__SCRIPTRONAUT_QC_ORPHAN_{}_{}__"
            ).format(
                index,
                blocker.as_pointer(),
            )

            try:
                blocker.name = orphan_temp_name
            except Exception as error:
                for item in items:
                    if item.get(
                        "orphan_blocker"
                    ) is not blocker:
                        continue
                    item[
                        "safe"
                    ] = False
                    item[
                        "blocked_reason"
                    ] = (
                        (
                            'Could not free target datablock name "{}" '
                            'for object "{}": {}'
                        ).format(
                            item["target_name"],
                            item["object"].name,
                            error,
                        )
                    )

                try:
                    blocker.name = old_orphan_name
                except Exception:
                    pass

        # -----------------------------------------------------
        # Propagate any orphan-related failures
        # -----------------------------------------------------

        changed = True
        while changed:
            changed = False
            for item in items:
                if not item[
                    "safe"
                ]:
                    continue

                dependency = item.get(
                    "dependency"
                )
                if (
                    dependency is not None
                    and not dependency[
                        "safe"
                    ]
                ):
                    item[
                        "safe"
                    ] = False
                    item[
                        "blocked_reason"
                    ] = (
                        (
                            'Cannot rename datablock for "{}" to "{}": '
                            'the datablock currently using that name '
                            'cannot be moved safely.'
                        ).format(
                            item["object"].name,
                            item["target_name"],
                        )
                    )
                    changed = True

        # Report blocked items.
        for item in items:
            if item[
                "safe"
            ]:
                continue

            reason = item.get(
                "blocked_reason"
            )
            if (
                reason
                and reason not in issues
            ):
                issues.append(
                    reason
                )

        safe_items = [
            item
            for item in items
            if item[
                "safe"
            ]
        ]

        if not safe_items:
            continue

        # -----------------------------------------------------
        # Pass 1: stage every safe datablock under a temp name
        # -----------------------------------------------------

        staged_items = []
        temporary_failed = False

        for index, item in enumerate(
            safe_items
        ):
            datablock = item[
                "datablock"
            ]
            temporary_name = (
                "__SCRIPTRONAUT_QC_TEMP_{}_{}__"
            ).format(
                index,
                datablock.as_pointer(),
            )

            try:
                datablock.name = temporary_name
                staged_items.append(
                    item
                )
            except Exception as error:
                temporary_failed = True
                issues.append(
                    (
                        'Could not temporarily rename datablock '
                        'for "{}": {}'
                    ).format(
                        item["object"].name,
                        error,
                    )
                )
                break

        if temporary_failed:
            # Stage moved items again before restoring originals, so
            # original cyclic names cannot collide during rollback.
            for index, item in enumerate(
                staged_items
            ):
                try:
                    item[
                        "datablock"
                    ].name = (
                        "__SCRIPTRONAUT_QC_ROLLBACK_{}_{}__"
                    ).format(
                        index,
                        item["datablock"].as_pointer(),
                    )
                except Exception:
                    pass

            for item in staged_items:
                try:
                    item[
                        "datablock"
                    ].name = item[
                        "old_name"
                    ]
                except Exception:
                    pass
            continue

        # -----------------------------------------------------
        # Pass 2: assign final names
        # -----------------------------------------------------

        for item in safe_items:
            obj = item[
                "object"
            ]
            datablock = item[
                "datablock"
            ]
            old_name = item[
                "old_name"
            ]
            target_name = item[
                "target_name"
            ]

            try:
                datablock.name = target_name
            except Exception as error:
                issues.append(
                    (
                        'Could not rename datablock for "{}": {}'
                    ).format(
                        obj.name,
                        error,
                    )
                )
                continue

            if datablock.name != target_name:
                issues.append(
                    (
                        'Could not assign exact datablock name "{}" '
                        'to "{}". Blender assigned "{}" instead.'
                    ).format(
                        target_name,
                        obj.name,
                        datablock.name,
                    )
                )
                continue

            fixed_objects[
                obj.name
            ] = {
                "fixed": True,
                "previous_datablock_name": old_name,
                "datablock_name": datablock.name,
            }

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }

