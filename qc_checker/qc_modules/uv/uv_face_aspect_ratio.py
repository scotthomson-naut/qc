# Standard python imports
from mathutils import Vector

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Stretched UV polygons"
DESCRIPTION = (
    "Checks Stretched UV polygons"
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
    failed_objects = get_objects_with_stretched_uv_polygons()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} stretched UV polygon(s)".format(
                object_name,
                data[
                    "stretched_polygon_count"
                ],
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

def get_objects_with_stretched_uv_polygons(
        objects=None,
        max_stretch_ratio=2.0,
        tolerance=1e-10,
    ):
    """
    Finds mesh objects containing stretched/distorted UV polygons.

    The check compares corresponding 3D edge lengths and UV edge
    lengths for triangulated polygons.

    Uniform UV scaling does NOT count as stretching.

    Example:
        A polygon uniformly scaled to 50% in UV space:
            -> PASS

        A polygon scaled 50% horizontally and 200% vertically:
            -> FAIL

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all objects in the current scene.

        max_stretch_ratio (float):
            Maximum allowed directional distortion.

            Examples:
                1.2 = strict
                1.5 = moderate
                2.0 = allows up to 2x distortion
                3.0 = lenient

        tolerance (float):
            Minimum valid edge length used to avoid division
            by zero on degenerate geometry or UVs.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "stretched_polygon_count": 3,
                "polygon_indices": [12, 57, 103],
                "stretched_polygons": [
                    {
                        "polygon_index": 12,
                        "stretch_ratio": 3.42,
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

        uv_data = uv_layer.data

        # Build Blender's triangulation of the mesh.
        mesh.calc_loop_triangles()

        polygon_stretch = {}

        # ---------------------------------------------------------
        # Check each triangle
        # ---------------------------------------------------------

        for triangle in mesh.loop_triangles:
            loop_indices = list(
                triangle.loops
            )

            if len(loop_indices) != 3:
                continue

            mesh_points = []
            uv_points = []

            for loop_index in loop_indices:

                loop = mesh.loops[
                    loop_index
                ]

                mesh_points.append(
                    mesh.vertices[
                        loop.vertex_index
                    ].co
                )

                uv_points.append(
                    uv_data[
                        loop_index
                    ].uv
                )

            stretch_ratio = (
                get_uv_triangle_stretch_ratio(
                    mesh_points,
                    uv_points,
                    tolerance=tolerance,
                )
            )

            if stretch_ratio is None:
                # Degenerate geometry / collapsed UVs should
                # be handled by their own QC checks.
                continue

            if stretch_ratio <= max_stretch_ratio:
                continue

            polygon_index = (
                triangle.polygon_index
            )

            # A quad/ngon may produce several triangles.
            # Store only its worst stretch value.
            previous = polygon_stretch.get(
                polygon_index,
                0.0,
            )

            polygon_stretch[
                polygon_index
            ] = max(
                previous,
                stretch_ratio,
            )

        # ---------------------------------------------------------
        # Store failures
        # ---------------------------------------------------------

        if not polygon_stretch:
            continue

        polygon_indices = sorted(
            polygon_stretch.keys()
        )

        stretched_polygons = [
            {
                "polygon_index":
                    polygon_index,

                "stretch_ratio":
                    polygon_stretch[
                        polygon_index
                    ],
            }
            for polygon_index
            in polygon_indices
        ]

        failed_objects[obj.name] = {
            "uv_map":
                uv_layer.name,

            "stretched_polygon_count":
                len(polygon_indices),

            "polygon_indices":
                polygon_indices,

            "max_stretch_ratio":
                max_stretch_ratio,

            "stretched_polygons":
                stretched_polygons,
        }

    return failed_objects


# -------------------------
# Suport Functions (Find)
# -------------------------

def get_uv_triangle_stretch_ratio(
        mesh_points,
        uv_points,
        tolerance=1e-10,
    ):
    """
    Measures UV distortion for a triangle.

    For each corresponding edge:

        UV edge length / 3D edge length

    If all three ratios are approximately equal, the UV triangle
    has uniform scaling and is not stretched.

    The returned stretch ratio is:

        largest scale ratio / smallest scale ratio

    Therefore:
        1.0 = no distortion
        1.5 = 1.5x directional distortion
        2.0 = 2x directional distortion

    Returns:
        float | None:
            Stretch ratio, or None for degenerate triangles.
    """
    scale_ratios = []

    edge_pairs = (
        (0, 1),
        (1, 2),
        (2, 0),
    )

    for index_a, index_b in edge_pairs:
        # 3D edge length.
        mesh_length = (
            mesh_points[index_b]
            - mesh_points[index_a]
        ).length

        # UV edge length.
        uv_length = (
            uv_points[index_b]
            - uv_points[index_a]
        ).length

        # Degenerate mesh edge.
        if mesh_length <= tolerance:
            return None

        # Collapsed UV edge.
        # Let the separate collapsed-edge QC handle it.
        if uv_length <= tolerance:
            return None

        scale_ratios.append(
            uv_length / mesh_length
        )

    if not scale_ratios:
        return None

    min_ratio = min(
        scale_ratios
    )

    max_ratio = max(
        scale_ratios
    )

    if min_ratio <= tolerance:
        return None

    return (
        max_ratio / min_ratio
    )
