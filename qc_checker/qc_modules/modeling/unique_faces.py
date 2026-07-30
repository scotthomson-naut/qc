# Blender imports
import bpy
import bmesh

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Unique Faces"
DESCRIPTION = (
    "Checks for exact duplicate faces - two or more faces sharing "
    "the same vertices in the same winding order. Deliberately "
    "ignores faces that share the same vertices but with reversed "
    "winding (opposite normal direction), since that pattern is a "
    "legitimate, intentional technique for double-sided geometry "
    "(e.g. foliage cards)."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_duplicate_faces()

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
    }


def fix(result_data):
    """
    Fix for issue.

    Args:
        result_data (dict): Result returned by main().
    Returns:
        dict: Fix result.
    """
    # Call Function
    fix_result = fix_duplicate_faces(result_data)

    return fix_result


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_duplicate_faces(objects=None):
    """
    Finds Mesh objects with two or more faces sharing the exact same
    vertices in the exact same winding order.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

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

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        duplicate_indices = find_duplicate_face_indices(obj.data)

        if duplicate_indices:
            failed_objects[obj.name] = {
                "duplicate_face_indices": duplicate_indices,
                "duplicate_face_count": len(duplicate_indices),
            }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_duplicate_faces(result_data):
    """
    Removes redundant exact-duplicate faces, keeping one face per
    unique (vertices, winding) combination.

    Note:
        Uses bmesh to perform the actual deletion, with context
        'FACES' - this removes only the redundant face itself, not
        the underlying vertices/edges, which may still be in use by
        neighboring surviving geometry.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
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

        if obj.data.library is not None:
            issues.append(
                "Skipped linked object: {}".format(object_name)
            )
            continue

        # Recheck before fixing.
        duplicate_indices = find_duplicate_face_indices(obj.data)

        if not duplicate_indices:
            continue

        # Make the mesh single-user so other objects sharing the
        # same data are not unintentionally changed.
        if obj.data.users > 1:
            obj.data = obj.data.copy()

        mesh = obj.data

        buckets = {}

        for polygon in mesh.polygons:
            key = canonical_face_key(tuple(polygon.vertices))
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


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def canonical_face_key(vertex_indices):
    """
    Builds a rotation-independent, winding-dependent key for a face's
    vertex loop.

    Rotating which vertex a face's loop happens to start at doesn't
    change the face - [0, 1, 2, 3] and [1, 2, 3, 0] are the same
    face, same winding. Reversing the order does change it - that's
    the opposite winding direction, and is deliberately NOT
    normalized away here, so flipped-winding "duplicates" get a
    different key and are never matched as duplicates.

    Args:
        vertex_indices (tuple[int]):
            A face's vertex indices, in loop order.

    Returns:
        tuple[int]:
            Rotated so the lowest vertex index comes first, direction
            unchanged.
    """
    min_position = vertex_indices.index(min(vertex_indices))

    return vertex_indices[min_position:] + vertex_indices[:min_position]


def find_duplicate_face_indices(mesh):
    """
    Finds face indices that are exact duplicates (same vertices, same
    winding order) of at least one other face on the same mesh.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

    Returns:
        list[int]:
            Indices of all faces involved in an exact duplicate,
            sorted.
    """
    buckets = {}

    for polygon in mesh.polygons:
        key = canonical_face_key(tuple(polygon.vertices))

        buckets.setdefault(key, []).append(polygon.index)

    duplicate_indices = []

    for indices in buckets.values():
        if len(indices) > 1:
            duplicate_indices.extend(indices)

    return sorted(duplicate_indices)
