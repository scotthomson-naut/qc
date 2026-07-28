# Standard python imports

# Blender imports
import bpy

# Company imports

# Constants
# Matches Blender's own "Merge by Distance" operator default value.
DISTANCE_TOLERANCE = 0.0001
ROUND_DECIMALS = 4

# Meta data
SEVERITY = "warning"
LABEL = "No Duplicate Vertices"
DESCRIPTION = (
    "Checks for overlapping/duplicate vertices (multiple vertices "
    "sharing nearly the same position within tolerance). Note: "
    "overlapping vertices are also a normal, intentional result of "
    "hard-edge and UV seam splits - this flags candidates for review "
    "rather than confirmed mistakes."
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_duplicate_vertices()

    issues = [
        "Failed object: {} - {} overlapping vertices".format(
            object_name,
            data["duplicate_vertex_count"],
        )
        for object_name, data in failed_objects.items()
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Overlapping vertices are frequently intentional (hard-edge splits,
# UV seams both deliberately create coincident vertices with
# different indices). Auto-merging could destroy correct, deliberate
# geometry - needs an artist to review each case and decide with
# Blender's own Merge by Distance tool.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_duplicate_vertices(
        objects=None,
        distance_tolerance=DISTANCE_TOLERANCE,
    ):
    """
    Finds Mesh objects with two or more vertices sharing nearly the
    same position.

    Note:
        Uses coordinate rounding to bucket nearby vertices together,
        rather than Blender's own bmesh.ops.find_doubles(). This
        avoids constructing a BMesh from raw mesh data (see the
        ngon_detection.py crash investigation - building a BMesh from
        unvalidated geometry is exactly what caused that). The
        tradeoff: rounding is an approximation, not true distance-
        based clustering, so a small number of near-duplicates that
        straddle a rounding boundary could theoretically be missed.
        Good enough for a QC flag; not meant to replace Merge by
        Distance's own precision.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        distance_tolerance (float):
            Approximate distance below which two vertices are
            considered overlapping. Matches Blender's own Merge by
            Distance default.

    Returns:
        dict:
        {
            "Cube": {
                "duplicate_vertex_indices": [0, 1, 4, 5],
                "duplicate_vertex_count": 4,
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

        duplicate_indices = find_duplicate_vertex_indices(
            obj.data,
            distance_tolerance=distance_tolerance,
        )

        if duplicate_indices:
            failed_objects[obj.name] = {
                "duplicate_vertex_indices": duplicate_indices,
                "duplicate_vertex_count": len(duplicate_indices),
            }

    return failed_objects


def find_duplicate_vertex_indices(mesh, distance_tolerance):
    """
    Finds vertex indices that share nearly the same position as at
    least one other vertex on the same mesh.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        distance_tolerance (float):
            Approximate distance below which two vertices are
            considered overlapping.

    Returns:
        list[int]:
            Indices of all vertices involved in an overlap, sorted.
    """
    vertex_count = len(mesh.vertices)

    if vertex_count == 0:
        return []

    coords = [0.0] * (vertex_count * 3)
    mesh.vertices.foreach_get("co", coords)

    buckets = {}

    for index in range(vertex_count):
        x = coords[index * 3]
        y = coords[index * 3 + 1]
        z = coords[index * 3 + 2]

        key = (
            round(x, ROUND_DECIMALS),
            round(y, ROUND_DECIMALS),
            round(z, ROUND_DECIMALS),
        )

        buckets.setdefault(key, []).append(index)

    duplicate_indices = []

    for indices in buckets.values():
        if len(indices) > 1:
            duplicate_indices.extend(indices)

    return sorted(duplicate_indices)