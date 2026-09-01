# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Final Names"
DESCRIPTION = (
    "Checks single-user datablock names for temporary, test, or debug "
    "prefixes such as tmp_, temp_, debug_, or test_. The Object name is "
    "treated as the authoritative production name."
)
WHY = (
    "Keeps internal datablock names production-ready and aligned with their "
    "owning Object name without renaming the Object itself."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

CASE_SENSITIVE = False

DEFAULT_PREFIXES = (
    "tmp",
    "temp",
    "debug",
    "test",
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks DATABLOCK names for temporary/debug prefixes.

    Object names are intentionally not validated or modified by this check.
    The Object name is treated as the final production name.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_invalid_prefixes()
    )

    issues = []

    for object_name, data in failed_objects.items():

        datablock_name_data = data.get(
            "datablock_name"
        )

        if datablock_name_data:
            issues.append(
                (
                    "Failed object: {} - Datablock name {!r} uses "
                    "invalid prefix {!r}; Fix will rename the datablock "
                    "to match the Object name."
                ).format(
                    object_name,
                    datablock_name_data[
                        "name"
                    ],
                    datablock_name_data[
                        "prefix"
                    ],
                )
            )

    return {
        "issues":
            issues,

        "failed_objects":
            failed_objects,
    }


def fix(
        result_data=None,
    ):
    """
    Renames invalid single-user datablocks to match their Object names.
    """
    return fix_invalid_prefixes(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_invalid_prefixes(
        objects=None,
        prefixes=None,
    ):
    """
    Finds objects whose DATABLOCK name starts with a temporary/debug/test
    prefix.

    The Object name itself is NOT checked. It is the authoritative final name.

    Examples that fail:

        Object: body_GEO_NEW
        Mesh:   temp

        Object: Chair
        Mesh:   tmp_ChairMesh

    Examples that pass:

        Object: temp_Chair
        Mesh:   ChairMesh

    because this check does not judge the Object name.

    Shared datablocks are ignored because one datablock may belong to several
    differently named objects and cannot safely be renamed to match all of
    them.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to current scene objects.

        prefixes (iterable[str] | None):
            Prefixes to check.

    Returns:
        dict
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    failed_objects = {}

    for obj in get_qc_objects(
        objects
    ):

        if obj.library is not None:
            continue

        datablock = getattr(
            obj,
            "data",
            None,
        )

        if datablock is None:
            continue

        if getattr(
            datablock,
            "library",
            None,
        ) is not None:
            continue

        # Shared datablocks are intentionally ignored. One datablock cannot
        # safely be renamed to several different Object names.
        if getattr(
            datablock,
            "users",
            1,
        ) > 1:
            continue

        datablock_name_result = (
            get_invalid_prefix_data(
                datablock.name,
                prefixes=prefixes,
            )
        )

        if datablock_name_result is None:
            continue

        failed_objects[
            obj.name
        ] = {
            "object_name":
                obj.name,

            "datablock_name":
                datablock_name_result,

            "target_datablock_name":
                obj.name,

            "datablock_users":
                datablock.users,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_invalid_prefix_data(
        name,
        prefixes=None,
    ):
    """
    Checks one name for an invalid temporary/debug/test prefix.

    Returns:
        dict | None
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    prefixes = sorted(
        prefixes,
        key=len,
        reverse=True,
    )

    compare_name = (
        name
        if CASE_SENSITIVE
        else name.lower()
    )

    for prefix in prefixes:

        compare_prefix = (
            prefix
            if CASE_SENSITIVE
            else prefix.lower()
        )

        if compare_name.startswith(
            compare_prefix
        ):
            return {
                "name":
                    name,

                "prefix":
                    prefix,
            }

    return None


def get_datablock_collection(
        datablock,
    ):
    """
    Returns the bpy.data collection that owns datablock.

    Uses Blender base RNA types so subtype datablocks such as SpotLight,
    AreaLight and TextCurve resolve correctly.
    """
    type_map = (
        (
            bpy.types.Mesh,
            bpy.data.meshes,
        ),
        (
            bpy.types.Curve,
            bpy.data.curves,
        ),
        (
            bpy.types.Camera,
            bpy.data.cameras,
        ),
        (
            bpy.types.Light,
            bpy.data.lights,
        ),
        (
            bpy.types.Armature,
            bpy.data.armatures,
        ),
        (
            bpy.types.Lattice,
            bpy.data.lattices,
        ),
        (
            bpy.types.MetaBall,
            bpy.data.metaballs,
        ),
        (
            bpy.types.Speaker,
            bpy.data.speakers,
        ),
    )

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
        return bpy.data.volumes

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
        return grease_pencils

    for (
        datablock_type,
        collection,
    ) in type_map:

        if isinstance(
            datablock,
            datablock_type,
        ):
            return collection

    return None


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_invalid_prefixes(
        result_data=None,
        prefixes=None,
        strip_separators=True,
    ):
    """
    Renames invalid single-user datablocks to match their Object names.

    Important:
        The old implementation removed the invalid prefix from the datablock
        name. This version instead uses the Object name as the final target.

        Example:

            Object:    body_GEO_NEW
            Datablock: temp

        becomes:

            Object:    body_GEO_NEW
            Datablock: body_GEO_NEW

    Object names are never changed by this check.

    Shared datablocks are skipped.

    If another live datablock already owns the exact Object name, the rename
    is skipped rather than allowing Blender to silently create .001/.002.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    # Re-evaluate current state so another naming fix cannot leave stale names.
    live_failed_objects = (
        get_objects_with_invalid_prefixes(
            prefixes=prefixes,
        )
    )

    if not isinstance(
        result_data,
        dict,
    ):
        result_data = {}

    original_failed_objects = (
        result_data.get(
            "failed_objects",
            {},
        )
    )

    if not isinstance(
        original_failed_objects,
        dict,
    ):
        original_failed_objects = {}

    # Only fix objects that were part of the original Fix request, but use
    # their CURRENT scene state.
    target_names = [
        object_name
        for object_name in original_failed_objects
        if object_name in live_failed_objects
    ]

    fixed_objects = {}
    issues = []

    for object_name in target_names:

        obj = get_qc_object(
            object_name
        )

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        if obj.library is not None:
            continue

        datablock = getattr(
            obj,
            "data",
            None,
        )

        if datablock is None:
            issues.append(
                (
                    "Could not rename datablock for {!r}: "
                    "object has no datablock."
                ).format(
                    obj.name
                )
            )
            continue

        if getattr(
            datablock,
            "library",
            None,
        ) is not None:
            continue

        if datablock.users > 1:
            issues.append(
                (
                    "Skipped datablock {!r} on object {!r}: "
                    "datablock is shared by {} users."
                ).format(
                    datablock.name,
                    obj.name,
                    datablock.users,
                )
            )
            continue

        # Verify the datablock is STILL a Final Names failure.
        invalid_data = get_invalid_prefix_data(
            datablock.name,
            prefixes=prefixes,
        )

        if invalid_data is None:
            continue

        old_datablock_name = (
            datablock.name
        )

        target_name = (
            obj.name
        )

        collection = (
            get_datablock_collection(
                datablock
            )
        )

        if collection is None:
            issues.append(
                (
                    "Could not determine datablock collection for "
                    "object {!r}."
                ).format(
                    obj.name
                )
            )
            continue

        blocker = collection.get(
            target_name
        )

        if (
            blocker is not None
            and blocker is not datablock
        ):
            issues.append(
                (
                    "Could not rename datablock {!r} on object {!r} "
                    "to {!r}: another live datablock already owns "
                    "that exact name."
                ).format(
                    old_datablock_name,
                    obj.name,
                    target_name,
                )
            )
            continue

        try:
            datablock.name = (
                target_name
            )

        except Exception as error:
            issues.append(
                (
                    "Could not rename datablock {!r} on object {!r}: {}"
                ).format(
                    old_datablock_name,
                    obj.name,
                    error,
                )
            )
            continue

        if datablock.name != target_name:
            issues.append(
                (
                    "Could not assign exact datablock name {!r} to "
                    "object {!r}. Blender assigned {!r} instead."
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
            "datablock_name": {
                "old_name":
                    old_datablock_name,

                "new_name":
                    datablock.name,

                "matched_invalid_prefix":
                    invalid_data[
                        "prefix"
                    ],
            }
        }

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }
