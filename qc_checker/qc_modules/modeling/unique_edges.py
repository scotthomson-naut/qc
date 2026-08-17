# Blender imports
import bpy
import bmesh

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Unique Edges"
DESCRIPTION = (
    "Checks for duplicate edges - two or more edges connecting the "
    "exact same pair of vertices."
)
WHY = (
    "They create overlapping geometry that confuses rendering, ruins "
    "subdivision surfaces, breaks UV unwrapping, and causes lighting "
    "errors in game engines. These hidden extra lines waste memory "
    "and make models hard to edit."
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
    failed_objects = get_objects_with_duplicate_edges()

    issues = [
        "Failed object: {} - {} duplicate edges".format(
            object_name,
            data["duplicate_edge_count"],
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
    fix_result = fix_duplicate_edges(result_data)

    return fix_result


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_duplicate_edges(objects=None):
    """
    Finds Mesh objects with two or more edges connecting the exact
    same pair of vertices.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "duplicate_edge_indices": [3, 7],
                "duplicate_edge_count": 2,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

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

        duplicate_indices = find_duplicate_edge_indices(obj.data)

        if duplicate_indices:
            failed_objects[obj.name] = {
                "duplicate_edge_indices": duplicate_indices,
                "duplicate_edge_count": len(duplicate_indices),
            }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_duplicate_edges(result_data):
    """
    Removes redundant duplicate edges, keeping one edge per unique
    vertex pair.

    Note:
        Uses bmesh to perform the actual deletion. Any face relying
        solely on a removed edge is removed along with it - this only
        matters in practice for a duplicated edge that also carries
        its own duplicated face, which is itself a real mistake worth
        cleaning up.

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

        if (
            obj.library is not None
            or obj.data.library is not None
        ):
            issues.append(
                "Skipped linked object: {}".format(object_name)
            )
            continue

        # Recheck before fixing.
        duplicate_indices = find_duplicate_edge_indices(obj.data)

        if not duplicate_indices:
            continue

        # Make the mesh single-user so other objects sharing the
        # same data are not unintentionally changed.
        if obj.data.users > 1:
            obj.data = obj.data.copy()

        mesh = obj.data

        edge_count = len(mesh.edges)
        vertex_indices = [0] * (edge_count * 2)
        mesh.edges.foreach_get("vertices", vertex_indices)

        buckets = {}

        for index in range(edge_count):
            v0 = vertex_indices[index * 2]
            v1 = vertex_indices[index * 2 + 1]

            key = tuple(sorted((v0, v1)))

            buckets.setdefault(key, []).append(index)

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
            bm.edges.ensure_lookup_table()

            edges_to_remove = [
                bm.edges[index]
                for index in indices_to_delete
                if index < len(bm.edges)
            ]

            bmesh.ops.delete(
                bm,
                geom=edges_to_remove,
                context='EDGES',
            )

            bm.to_mesh(mesh)
            mesh.update()

            fixed_objects[object_name] = {
                "removed_edge_count": len(edges_to_remove),
            }

        except Exception as error:
            issues.append(
                "Could not fix duplicate edges on {}: {}".format(
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

def find_duplicate_edge_indices(mesh):
    """
    Finds edge indices that connect the exact same pair of vertices
    as at least one other edge on the same mesh.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

    Returns:
        list[int]:
            Indices of all edges involved in a duplicate, sorted.
    """
    edge_count = len(mesh.edges)

    if edge_count == 0:
        return []

    vertex_indices = [0] * (edge_count * 2)
    mesh.edges.foreach_get("vertices", vertex_indices)

    buckets = {}

    for index in range(edge_count):
        v0 = vertex_indices[index * 2]
        v1 = vertex_indices[index * 2 + 1]

        key = tuple(sorted((v0, v1)))

        buckets.setdefault(key, []).append(index)

    duplicate_indices = []

    for indices in buckets.values():
        if len(indices) > 1:
            duplicate_indices.extend(indices)

    return sorted(duplicate_indices)
