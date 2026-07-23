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
    failed_objects = get_objects_with_collapsed_uv_edges()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} collapsed UV edge(s)".format(
                object_name,
                data["collapsed_edge_count"],
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

def get_objects_with_collapsed_uv_edges(
        objects=None,
        tolerance=1e-8,
    ):
    """
    Finds mesh objects containing collapsed UV edges.

    A UV edge is considered collapsed when its two UV endpoints
    are effectively at the same UV coordinate.

    This catches:
        - UV edges collapsed to a single point.
        - Partially collapsed UV faces.
        - Degenerate UV mapping where an edge has zero UV length.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Maximum UV edge length considered collapsed.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "collapsed_edge_count": 3,
                "polygon_indices": [12, 47],
                "collapsed_edges": [
                    {
                        "polygon_index": 12,
                        "edge_index": 35,
                        "vertex_indices": [4, 8],
                        "uv_a": (0.25, 0.5),
                        "uv_b": (0.25, 0.5),
                        "uv_length": 0.0,
                    }
                ],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    tolerance_squared = (
        tolerance * tolerance
    )

    for obj in objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data
        if mesh is None:
            continue

        if not mesh.polygons:
            continue

        # Missing UV maps should be handled
        # by a separate QC check.
        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active
        if uv_layer is None:
            continue

        uv_data = uv_layer.data
        collapsed_edges = []
        polygon_indices = set()

        # ---------------------------------------------------------
        # Inspect every polygon edge in UV space
        # ---------------------------------------------------------

        for polygon in mesh.polygons:
            loop_indices = list(
                polygon.loop_indices
            )

            loop_count = len(loop_indices)
            if loop_count < 2:
                continue

            for index, loop_index_a in enumerate(
                loop_indices
            ):
                loop_index_b = loop_indices[
                    (index + 1) % loop_count
                ]

                loop_a = mesh.loops[
                    loop_index_a
                ]

                loop_b = mesh.loops[
                    loop_index_b
                ]

                uv_a = uv_data[
                    loop_index_a
                ].uv

                uv_b = uv_data[
                    loop_index_b
                ].uv

                delta_u = (
                    uv_b.x - uv_a.x
                )

                delta_v = (
                    uv_b.y - uv_a.y
                )

                uv_length_squared = (
                    delta_u * delta_u
                    + delta_v * delta_v
                )

                if (
                    uv_length_squared
                    > tolerance_squared
                ):
                    continue

                collapsed_edges.append({
                    "polygon_index":
                        polygon.index,

                    "edge_index":
                        loop_a.edge_index,

                    "vertex_indices": [
                        loop_a.vertex_index,
                        loop_b.vertex_index,
                    ],

                    "uv_a": (
                        uv_a.x,
                        uv_a.y,
                    ),

                    "uv_b": (
                        uv_b.x,
                        uv_b.y,
                    ),

                    "uv_length":
                        uv_length_squared ** 0.5,
                })

                polygon_indices.add(
                    polygon.index
                )

        # ---------------------------------------------------------
        # Store failures
        # ---------------------------------------------------------

        if not collapsed_edges:
            continue

        failed_objects[obj.name] = {
            "uv_map":
                uv_layer.name,

            "collapsed_edge_count":
                len(collapsed_edges),

            "polygon_indices":
                sorted(polygon_indices),

            "collapsed_edges":
                collapsed_edges,
        }

    return failed_objects
