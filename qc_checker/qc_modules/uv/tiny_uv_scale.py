# Standard python imports
from mathutils import Vector

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Microscopic UV shells"
DESCRIPTION = (
    "Checks if Object has Microscopic UV shells"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    
    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_tiny_uv_shells(
        min_width=0.01,
        min_height=0.01
    )
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} tiny UV shell(s)".format(
                object_name,
                data["tiny_shell_count"],
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

def get_objects_with_tiny_uv_shells(
        objects=None,
        min_width=0.01,
        min_height=0.01,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing UV shells that are extremely small
    in width or height.

    A shell fails when:
        shell_width < min_width
        or
        shell_height < min_height

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all objects in the current scene.

        min_width (float):
            Minimum allowed UV shell width.

        min_height (float):
            Minimum allowed UV shell height.

        tolerance (float):
            Tolerance used when determining UV connectivity.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "tiny_shell_count": 2,
                "tiny_shells": [
                    {
                        "width": 0.004,
                        "height": 0.012,
                        "polygon_indices": [42, 43],
                    }
                ],
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

        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            continue

        uv_islands = get_uv_islands(
            mesh,
            uv_layer,
            tolerance=tolerance,
        )

        tiny_shells = []

        for polygon_indices in uv_islands:
            bounds = get_uv_shell_bounds(
                mesh,
                uv_layer,
                polygon_indices,
            )

            if bounds is None:
                continue

            width = bounds["width"]
            height = bounds["height"]

            if (
                width >= min_width
                and height >= min_height
            ):
                continue

            tiny_shells.append({
                "width": width,
                "height": height,
                "min_u": bounds["min_u"],
                "max_u": bounds["max_u"],
                "min_v": bounds["min_v"],
                "max_v": bounds["max_v"],
                "polygon_indices": sorted(
                    polygon_indices
                ),
            })

        if tiny_shells:

            failed_objects[obj.name] = {
                "uv_map": uv_layer.name,
                "tiny_shell_count": len(
                    tiny_shells
                ),
                "min_width": min_width,
                "min_height": min_height,
                "tiny_shells": tiny_shells,
            }

    return failed_objects

# -------------------------
# Support Functions (Find)
# -------------------------

def get_uv_shell_bounds(
        mesh,
        uv_layer,
        polygon_indices,
    ):
    """
    Calculates the UV bounding box of a UV shell.

    Returns:
        dict | None:
        {
            "min_u": float,
            "max_u": float,
            "min_v": float,
            "max_v": float,
            "width": float,
            "height": float,
        }
    """
    uv_data = uv_layer.data

    u_values = []
    v_values = []

    for polygon_index in polygon_indices:
        polygon = mesh.polygons[
            polygon_index
        ]
        for loop_index in polygon.loop_indices:
            uv = uv_data[
                loop_index
            ].uv

            u_values.append(
                uv.x
            )

            v_values.append(
                uv.y
            )

    if not u_values:
        return None

    min_u = min(u_values)
    max_u = max(u_values)

    min_v = min(v_values)
    max_v = max(v_values)

    return {
        "min_u": min_u,
        "max_u": max_u,
        "min_v": min_v,
        "max_v": max_v,
        "width": max_u - min_u,
        "height": max_v - min_v,
    }


def get_uv_islands(
        mesh,
        uv_layer,
        tolerance=1e-6,
    ):
    """
    Groups polygons into UV-connected shells/islands.
    """
    uv_data = uv_layer.data

    edge_faces = {}

    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            edge_index = (
                mesh.loops[
                    loop_index
                ].edge_index
            )

            edge_faces.setdefault(
                edge_index,
                [],
            ).append(
                polygon.index
            )

    adjacency = {
        polygon.index: set()
        for polygon in mesh.polygons
    }

    for edge_index, face_indices in edge_faces.items():
        if len(face_indices) != 2:
            continue

        face_a = face_indices[0]
        face_b = face_indices[1]

        edge = mesh.edges[
            edge_index
        ]

        vertex_a = edge.vertices[0]
        vertex_b = edge.vertices[1]

        uvs_a = get_face_edge_uvs(
            mesh,
            uv_data,
            face_a,
            vertex_a,
            vertex_b,
        )

        uvs_b = get_face_edge_uvs(
            mesh,
            uv_data,
            face_b,
            vertex_a,
            vertex_b,
        )

        if (
            uvs_a is None
            or uvs_b is None
        ):
            continue

        if uv_edges_match(
            uvs_a,
            uvs_b,
            tolerance=tolerance,
        ):
            adjacency[face_a].add(
                face_b
            )

            adjacency[face_b].add(
                face_a
            )

    islands = []
    visited = set()

    for polygon in mesh.polygons:
        polygon_index = (
            polygon.index
        )

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

            stack.extend(
                neighbor
                for neighbor
                in adjacency[current]
                if neighbor not in visited
            )

        islands.append(
            island
        )

    return islands


def get_face_edge_uvs(
        mesh,
        uv_data,
        polygon_index,
        vertex_a,
        vertex_b,
    ):
    polygon = mesh.polygons[
        polygon_index
    ]

    result = {}

    for loop_index in polygon.loop_indices:
        vertex_index = (
            mesh.loops[
                loop_index
            ].vertex_index
        )

        if vertex_index not in {
            vertex_a,
            vertex_b,
        }:
            continue

        uv = uv_data[
            loop_index
        ].uv

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
    for vertex_index in edge_a:
        if vertex_index not in edge_b:
            return False

        uv_a = edge_a[
            vertex_index
        ]

        uv_b = edge_b[
            vertex_index
        ]

        if (
            abs(
                uv_a[0] - uv_b[0]
            ) > tolerance
            or
            abs(
                uv_a[1] - uv_b[1]
            ) > tolerance
        ):
            return False

    return True
