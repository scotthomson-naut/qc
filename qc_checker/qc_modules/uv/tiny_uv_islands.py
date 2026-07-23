# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    
    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_small_uv_islands(min_island_area=0.001)
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} extremely small "
            "UV island(s) found".format(
                object_name,
                data["small_island_count"],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_small_uv_islands(
        objects=None,
        min_island_area=0.0001,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing extremely small UV islands.

    UV islands are detected by checking whether adjacent polygons
    share matching UV coordinates along their common mesh edge.

    The size of each island is measured as UV area in UV-space.

    For the standard 0-1 tile:
        Full tile area = 1.0

    Example thresholds:
        0.01     = 1% of the UV tile
        0.001    = 0.1%
        0.0001   = 0.01%

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all objects in the current scene.

        min_island_area (float):
            Islands smaller than this UV area are considered
            extremely small.

        tolerance (float):
            Tolerance used when comparing UV coordinates.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "small_island_count": 2,
                "small_islands": [
                    {
                        "area": 0.000023,
                        "polygon_indices": [42, 43],
                    },
                    {
                        "area": 0.000071,
                        "polygon_indices": [180],
                    }
                ]
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data

        if mesh is None or not mesh.polygons:
            continue

        # Missing UV maps are handled by another QC check.
        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            continue

        islands = get_uv_islands(
            mesh,
            uv_layer,
            tolerance=tolerance,
        )

        small_islands = []

        for island_faces in islands:
            area = get_uv_island_area(
                mesh,
                uv_layer,
                island_faces,
            )

            if area >= min_island_area:
                continue

            small_islands.append({
                "area": area,
                "polygon_indices": sorted(
                    island_faces
                ),
            })

        if not small_islands:
            continue

        failed_objects[obj.name] = {
            "uv_map": uv_layer.name,
            "small_island_count": len(
                small_islands
            ),
            "min_island_area": min_island_area,
            "small_islands": small_islands,
        }

    return failed_objects

# -------------------------
# Support functions (Find)
# -------------------------

def get_uv_islands(
        mesh,
        uv_layer,
        tolerance=1e-6,
    ):
    """
    Groups mesh polygons into UV islands.

    Two neighboring polygons belong to the same UV island when their
    UV coordinates match along their shared mesh edge.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        uv_layer (bpy.types.MeshUVLoopLayer):
            UV layer to inspect.

        tolerance (float):
            UV comparison tolerance.

    Returns:
        list[set[int]]:
            Polygon-index sets representing UV islands.
    """
    uv_data = uv_layer.data

    # Map each mesh edge to polygons using it.
    edge_faces = {}

    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            loop = mesh.loops[loop_index]
            edge_faces.setdefault(
                loop.edge_index,
                [],
            ).append(
                polygon.index
            )

    adjacency = {
        polygon.index: set()
        for polygon in mesh.polygons
    }

    # ---------------------------------------------------------
    # Determine UV-connected neighboring faces
    # ---------------------------------------------------------

    for edge_index, face_indices in edge_faces.items():
        if len(face_indices) != 2:
            continue

        face_a_index = face_indices[0]
        face_b_index = face_indices[1]

        edge = mesh.edges[edge_index]

        vertex_a = edge.vertices[0]
        vertex_b = edge.vertices[1]

        face_a_uvs = get_face_edge_uvs(
            mesh,
            uv_data,
            face_a_index,
            vertex_a,
            vertex_b,
        )

        face_b_uvs = get_face_edge_uvs(
            mesh,
            uv_data,
            face_b_index,
            vertex_a,
            vertex_b,
        )

        if (
            face_a_uvs is None
            or face_b_uvs is None
        ):
            continue

        if uv_edges_match(
            face_a_uvs,
            face_b_uvs,
            tolerance=tolerance,
        ):
            adjacency[face_a_index].add(
                face_b_index
            )

            adjacency[face_b_index].add(
                face_a_index
            )

    # ---------------------------------------------------------
    # Flood-fill connected polygons into islands
    # ---------------------------------------------------------

    islands = []
    visited = set()

    for polygon in mesh.polygons:
        polygon_index = polygon.index

        if polygon_index in visited:
            continue

        island = set()
        stack = [polygon_index]

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            island.add(current)

            for neighbor in adjacency[current]:

                if neighbor not in visited:
                    stack.append(neighbor)

        islands.append(island)

    return islands


def get_face_edge_uvs(
        mesh,
        uv_data,
        polygon_index,
        vertex_a,
        vertex_b,
    ):
    """
    Gets UV coordinates for two mesh vertices along an edge
    as represented by a particular polygon.

    Returns:
        dict | None:
        {
            vertex_index: (u, v),
            ...
        }
    """
    polygon = mesh.polygons[
        polygon_index
    ]

    result = {}

    for loop_index in polygon.loop_indices:
        vertex_index = (
            mesh.loops[loop_index].vertex_index
        )

        if vertex_index not in {
            vertex_a,
            vertex_b,
        }:
            continue

        uv = uv_data[loop_index].uv
        result[vertex_index] = (
            uv.x,
            uv.y,
        )

    if (
        vertex_a not in result
        or vertex_b not in result
    ):
        return None

    return result


def uv_edges_match(
        edge_a,
        edge_b,
        tolerance=1e-6,
    ):
    """
    Checks whether two representations of the same mesh edge
    have matching UV coordinates.
    """
    if edge_a.keys() != edge_b.keys():
        return False

    for vertex_index in edge_a:
        uv_a = edge_a[vertex_index]
        uv_b = edge_b[vertex_index]

        if (
            abs(uv_a[0] - uv_b[0]) > tolerance
            or
            abs(uv_a[1] - uv_b[1]) > tolerance
        ):
            return False

    return True


def get_uv_island_area(
        mesh,
        uv_layer,
        polygon_indices,
    ):
    """
    Calculates the total UV-space area of an island.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        uv_layer (bpy.types.MeshUVLoopLayer):
            UV map.

        polygon_indices (iterable[int]):
            Polygons belonging to the island.

    Returns:
        float:
            Total UV area.
    """
    uv_data = uv_layer.data
    total_area = 0.0

    for polygon_index in polygon_indices:
        polygon = mesh.polygons[
            polygon_index
        ]

        uvs = [
            uv_data[loop_index].uv
            for loop_index in polygon.loop_indices
        ]

        total_area += get_uv_polygon_area(
            uvs
        )

    return total_area


def get_uv_polygon_area(uvs):
    """
    Calculates polygon area in UV space using the shoelace formula.

    Args:
        uvs (list[Vector]):
            Polygon UV coordinates.

    Returns:
        float:
            Absolute UV-space area.
    """
    if len(uvs) < 3:
        return 0.0

    area = 0.0

    for index, uv_a in enumerate(uvs):
        uv_b = uvs[
            (index + 1) % len(uvs)
        ]

        area += (
            uv_a.x * uv_b.y
            - uv_b.x * uv_a.y
        )

    return abs(area) * 0.5
