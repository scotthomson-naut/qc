# Standard python imports
import math

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Unique Vertices"
DESCRIPTION = (
    "Checks for overlapping/duplicate vertices (multiple vertices "
    "sharing nearly the same position within a configurable "
    "tolerance)."
)
WHY = (
    "Extra or stacked points break tools, create ugly shadows, ruin "
    "animations, and cause errors when exporting your model to "
    "game engines or 3D printers."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "distance_tolerance": {
        "type": "float",
        "label": "Distance Tolerance",
        "description": (
            "Vertices within this distance of each other are "
            "considered overlapping/duplicate."
        ),
        "default": 0.0001,
        "min": 0.0000001,
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

    failed_objects = get_objects_with_duplicate_vertices(
        settings=settings,
    )

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
        "settings": settings,
    }

# No fix() for this check.
#
# Overlapping vertices are frequently intentional (hard-edge splits,
# UV seams both deliberately create coincident vertices with
# different indices). Auto-merging could destroy correct, deliberate
# geometry - needs an artist to review each case and decide with
# Blender's own Merge by Distance tool.


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_duplicate_vertices(objects=None, settings=None):
    """
    Finds Mesh objects with two or more vertices sharing nearly the
    same position.

    Note:
        Uses a spatial grid to avoid comparing every vertex against
        every other vertex (which would be slow on dense meshes), but
        matches are confirmed with real Euclidean distance, not
        coordinate rounding. An earlier version of this check used
        rounding, which turned out to have a real flaw: whether a
        genuinely close pair got caught depended on where they
        happened to sit relative to arbitrary rounding boundaries,
        not on how far apart they actually were - a pair could be
        closer together than the tolerance and still get missed if
        they straddled a boundary. This version checks actual
        distance, so a tolerance of 0.01 reliably catches every pair
        within 0.01, regardless of position. This also avoids
        constructing a BMesh from raw mesh data (see the
        ngon_detection.py crash investigation - building a BMesh from
        unvalidated geometry is exactly what caused that).

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
                "duplicate_vertex_indices": [0, 1, 4, 5],
                "duplicate_vertex_count": 4,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    distance_tolerance = float(
        settings.get("distance_tolerance", 0.0001)
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

        duplicate_indices = find_duplicate_vertex_indices(
            obj.data,
            distance_tolerance=distance_tolerance,
        )

        if duplicate_indices:
            failed_objects[obj.name] = {
                "duplicate_vertex_indices": duplicate_indices,
                "duplicate_vertex_count": len(duplicate_indices),

                "selection": {
                    "mode": "VERT",
                    "indices": duplicate_indices,
                },
            }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def find_duplicate_vertex_indices(mesh, distance_tolerance):
    """
    Finds vertex indices that are within distance_tolerance of at
    least one other vertex on the same mesh, using true Euclidean
    distance.

    Note:
        Vertices are bucketed into a spatial grid sized to the
        tolerance, purely to avoid an O(n^2) comparison of every
        vertex against every other vertex on dense meshes. For each
        vertex, only that vertex's own cell and its 26 immediate
        neighbor cells are checked - any actual match has to be
        within one cell-width, so this can never miss a real match
        while still avoiding a full all-pairs scan. Every candidate
        found this way is then confirmed with a real distance check,
        not just cell membership - the grid narrows down candidates,
        it doesn't decide the answer by itself.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        distance_tolerance (float):
            Distance below which two vertices are considered
            overlapping. Must be > 0.

    Returns:
        list[int]:
            Indices of all vertices involved in an overlap, sorted.
    """
    vertex_count = len(mesh.vertices)

    if vertex_count == 0:
        return []

    # Guard against zero, negative, or otherwise invalid tolerances.
    safe_tolerance = max(distance_tolerance, 0.0000001)
    tolerance_squared = safe_tolerance * safe_tolerance

    coords = [0.0] * (vertex_count * 3)
    mesh.vertices.foreach_get("co", coords)

    positions = [
        (
            coords[index * 3],
            coords[index * 3 + 1],
            coords[index * 3 + 2],
        )
        for index in range(vertex_count)
    ]

    def cell_key(position):
        return (
            math.floor(position[0] / safe_tolerance),
            math.floor(position[1] / safe_tolerance),
            math.floor(position[2] / safe_tolerance),
        )

    grid = {}

    for index, position in enumerate(positions):
        grid.setdefault(cell_key(position), []).append(index)

    neighbor_offsets = [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
    ]

    duplicate_indices = set()

    for index, position in enumerate(positions):
        cx, cy, cz = cell_key(position)

        for dx, dy, dz in neighbor_offsets:
            candidates = grid.get((cx + dx, cy + dy, cz + dz))

            if not candidates:
                continue

            for other_index in candidates:
                # Only compare each pair once, and never against
                # itself.
                if other_index <= index:
                    continue

                other_position = positions[other_index]

                delta_x = position[0] - other_position[0]
                delta_y = position[1] - other_position[1]
                delta_z = position[2] - other_position[2]

                distance_squared = (
                    delta_x * delta_x
                    + delta_y * delta_y
                    + delta_z * delta_z
                )

                if distance_squared <= tolerance_squared:
                    duplicate_indices.add(index)
                    duplicate_indices.add(other_index)

    return sorted(duplicate_indices)