# Blender imports
import bpy
import bmesh

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Unique Faces"
DESCRIPTION = (
    "Checks for duplicate faces - two or more faces sharing the same "
    "vertices."
)
WHY = (
    "Create 'z-fighting' visual flicker, break lighting calculations, "
    "mess up physics and weight painting, and cause issues when "
    "3D printing or exporting assets."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "ignore_flipped_winding": {
        "type": "bool",
        "label": "Ignore Reversed Winding Duplicates",
        "description": (
            "If enabled, faces that share the same vertices but with "
            "reversed winding order (opposite normal direction) are "
            "not flagged."
        ),
        "default": False,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Run for issue.

    Note:
        resolve_settings() is called here but not imported anywhere
        in this file - not confirmed how it reaches this module, best
        understanding is the QC framework injects it into each check
        module's namespace at runtime, same as how "preferences"
        arrives as an argument. Flag with your team if this errors as
        undefined.

    Args:
        preferences (dict | None):
            User-configured settings for this check, resolved against
            SETTINGS. Passed in by the QC framework.

    Returns:
        dict: {issues (list(str)), failed_objects(dict), settings (dict)}
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    failed_objects = get_objects_with_duplicate_faces(
        settings=settings,
    )

    issues = [
        "Failed object: {} - {} duplicate faces".format(
            object_name,
            data["duplicate_face_count"],
        )
        for object_name, data in failed_objects.items()
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "settings": settings,
    }


def fix(result_data=None, preferences=None):
    """
    Fix for issue.

    Args:
        result_data (dict | None): Result returned by main().
        preferences (dict | None): User-configured settings.
    Returns:
        dict: Fix result.
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    # Call Function
    fix_result = fix_duplicate_faces(
        result_data,
        settings=settings,
    )

    return fix_result


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_duplicate_faces(objects=None, settings=None):
    """
    Finds Mesh objects with two or more faces sharing the exact same
    vertices.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        settings (dict | None):
            Resolved check settings. Defaults to SETTINGS' own
            defaults when not provided (e.g. called directly outside
            of main()).

    Returns:
        dict:
        {
            "Cube": {
                "duplicate_face_indices": [2, 5],
                "duplicate_face_count": 2,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    ignore_flipped_winding = bool(
        settings.get("ignore_flipped_winding", False)
    )

    failed_objects = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        duplicate_indices = find_duplicate_face_indices(
            obj.data,
            ignore_flipped_winding=ignore_flipped_winding,
        )

        if duplicate_indices:
            failed_objects[obj.name] = {
                "duplicate_face_indices": duplicate_indices,
                "duplicate_face_count": len(duplicate_indices),
            }

    return failed_objects


def canonical_face_key(vertex_indices, ignore_winding=False):
    """
    Builds a key identifying a face's vertex loop for duplicate
    detection.

    Rotating which vertex a face's loop happens to start at never
    changes the face - [0, 1, 2, 3] and [1, 2, 3, 0] are the same
    face, same winding, and are always treated as identical here.

    Whether reversed winding ([3, 2, 1, 0]) is ALSO treated as
    identical depends on ignore_winding:

        - ignore_winding=False (default): reversed winding gets a
          different key, so a face and its flipped-normal twin are
          NOT considered duplicates of each other.

        - ignore_winding=True: direction is normalized away too, so
          a face and its flipped-normal twin ARE considered
          duplicates of each other.

    Args:
        vertex_indices (tuple[int]):
            A face's vertex indices, in loop order.

        ignore_winding (bool):
            When True, treats reversed-winding faces as duplicates
            too. When False, only exact same-winding faces match.

    Returns:
        frozenset[int] | tuple[int]:
            frozenset when ignoring winding (direction-independent),
            otherwise a rotated tuple (direction-dependent).
    """
    if ignore_winding:
        return frozenset(vertex_indices)

    min_position = vertex_indices.index(min(vertex_indices))

    return vertex_indices[min_position:] + vertex_indices[:min_position]


def find_duplicate_face_indices(mesh, ignore_flipped_winding=False):
    """
    Finds face indices that are duplicates of at least one other face
    on the same mesh.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        ignore_flipped_winding (bool):
            When True, only exact same-winding duplicates are
            flagged - reversed-winding pairs (potential double-sided
            geometry) are ignored. When False (default), both
            same-winding and reversed-winding duplicates are flagged.

    Returns:
        list[int]:
            Indices of all faces involved in a duplicate, sorted.
    """
    # Inverted on purpose: "ignore flipped winding" (don't flag
    # reversed pairs) requires a winding-SENSITIVE key, so flipped
    # faces get DIFFERENT keys and are never bucketed together.
    # canonical_face_key's own "ignore_winding" means the opposite -
    # True there discards direction (frozenset), MERGING flipped
    # pairs into the same bucket, which is what causes them to be
    # flagged. So the two booleans are intentionally inverted here.
    merge_reversed_winding = not ignore_flipped_winding

    buckets = {}

    for polygon in mesh.polygons:
        key = canonical_face_key(
            tuple(polygon.vertices),
            ignore_winding=merge_reversed_winding,
        )

        buckets.setdefault(key, []).append(polygon.index)

    duplicate_indices = []

    for indices in buckets.values():
        if len(indices) > 1:
            duplicate_indices.extend(indices)

    return sorted(duplicate_indices)


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_duplicate_faces(result_data, settings=None):
    """
    Removes redundant duplicate faces, keeping one face per unique
    combination as determined by the resolved settings.

    Note:
        Uses bmesh to perform the actual deletion, with context
        'FACES' - this removes only the redundant face itself, not
        the underlying vertices/edges, which may still be in use by
        neighboring surviving geometry.

    Args:
        result_data (dict):
            Result returned by main().

        settings (dict | None):
            Resolved check settings. Must match whatever settings
            main() used to detect the duplicates being fixed here, or
            the fix could target different faces than what was
            actually reported as failing.

    Returns:
        dict:
            Fix result.
    """
    if not isinstance(result_data, dict):
        result_data = {}

    if settings is None:
        settings = resolve_settings(SETTINGS)

    ignore_flipped_winding = bool(
        settings.get("ignore_flipped_winding", False)
    )

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(object_name)
            )
            continue

        if obj.data is None or not isinstance(obj.data, bpy.types.Mesh):
            issues.append(
                "Skipped '{}', datablock changed since check ran.".format(
                    object_name
                )
            )
            continue

        if (
            obj.library is not None
            or obj.data.library is not None
        ):
            issues.append(
                "Skipped linked object: {}".format(object_name)
            )
            continue

        # Recheck before fixing, using the same settings the original
        # check used.
        duplicate_indices = find_duplicate_face_indices(
            obj.data,
            ignore_flipped_winding=ignore_flipped_winding,
        )

        if not duplicate_indices:
            continue

        # Make the mesh single-user so other objects sharing the
        # same data are not unintentionally changed.
        if obj.data.users > 1:
            obj.data = obj.data.copy()

        mesh = obj.data

        # Same inversion as find_duplicate_face_indices - see that
        # function's comment for why.
        merge_reversed_winding = not ignore_flipped_winding

        buckets = {}

        for polygon in mesh.polygons:
            key = canonical_face_key(
                tuple(polygon.vertices),
                ignore_winding=merge_reversed_winding,
            )
            buckets.setdefault(key, []).append(polygon.index)

        indices_to_delete = []

        for indices in buckets.values():
            if len(indices) > 1:
                # Keep the first occurrence, remove the rest.
                indices_to_delete.extend(indices[1:])

        if not indices_to_delete:
            continue

        bm = bmesh.new()

        try:
            bm.from_mesh(mesh)
            bm.faces.ensure_lookup_table()

            faces_to_remove = [
                bm.faces[index]
                for index in indices_to_delete
                if index < len(bm.faces)
            ]

            bmesh.ops.delete(
                bm,
                geom=faces_to_remove,
                context='FACES',
            )

            bm.to_mesh(mesh)
            mesh.update()

            fixed_objects[object_name] = {
                "removed_face_count": len(faces_to_remove),
            }

        except Exception as error:
            issues.append(
                "Could not fix duplicate faces on {}: {}".format(
                    object_name,
                    error,
                )
            )

        finally:
            bm.free()

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }