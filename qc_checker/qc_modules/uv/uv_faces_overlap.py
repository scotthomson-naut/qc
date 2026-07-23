# Standard python imports
import math

# Blender imports
import bpy

# Company imports


# Meta data
LABEL = "Overlapping UV Faces"
DESCRIPTION = (
    "Checks mesh objects for UV faces that overlap "
    "with other UV faces."
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
    description = "Checks for Uv faces that Overlap."
    failed_objects =  get_objects_with_overlapping_uv_faces(grid_size=0.05)
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} UV face(s) "
            "in {} overlap(s)".format(
                object_name,
                data[
                    "overlapping_face_count"
                ],
                data[
                    "overlap_count"
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

def get_objects_with_overlapping_uv_faces(
        objects=None,
        tolerance=1e-8,
        grid_size=0.05,
    ):
    """
    Finds mesh objects containing overlapping UV faces.

    Uses a 2D spatial grid / bucket system to reduce triangle
    comparisons on dense meshes.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Numerical tolerance used for overlap tests.

        grid_size (float):
            UV-space size of each spatial bucket.

            Examples:
                0.10 = fewer, larger buckets
                0.05 = good general default
                0.02 = more, smaller buckets

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "overlapping_face_count": 4,
                "polygon_indices": [12, 13, 88, 89],
                "overlap_count": 2,
                "overlaps": [
                    {
                        "polygon_a": 12,
                        "polygon_b": 88,
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

        uv_data = uv_layer.data

        mesh.calc_loop_triangles()

        triangles = []

        # ---------------------------------------------------------
        # Build UV triangle records
        # ---------------------------------------------------------

        for triangle_index, loop_triangle in enumerate(mesh.loop_triangles):
            uv_points = [
                (
                    uv_data[loop_index].uv.x,
                    uv_data[loop_index].uv.y,
                )
                for loop_index in loop_triangle.loops
            ]

            # Ignore collapsed UV triangles.
            if abs(
                triangle_signed_area_2d(
                    uv_points
                )
            ) <= tolerance:
                continue

            bounds = get_triangle_bounds(
                uv_points
            )

            triangles.append({
                "triangle_index":
                    triangle_index,

                "polygon_index":
                    loop_triangle.polygon_index,

                "uvs":
                    uv_points,

                "bounds":
                    bounds,
            })

        if not triangles:
            continue

        # ---------------------------------------------------------
        # Build spatial grid
        # ---------------------------------------------------------

        grid = build_uv_spatial_grid(
            triangles,
            grid_size=grid_size,
        )

        overlapping_polygons = set()
        overlap_pairs = set()

        # Prevent testing the same triangle pair multiple times
        # when they occupy several grid cells.
        tested_triangle_pairs = set()

        # ---------------------------------------------------------
        # Compare only triangles sharing grid cells
        # ---------------------------------------------------------

        for triangle_indices in grid.values():
            count = len(triangle_indices)

            if count < 2:
                continue

            for local_a in range(count):
                triangle_a_index = (
                    triangle_indices[local_a]
                )

                triangle_a = triangles[
                    triangle_a_index
                ]

                for local_b in range(local_a + 1, count):
                    triangle_b_index = (
                        triangle_indices[local_b]
                    )

                    pair_key = (
                        min(
                            triangle_a_index,
                            triangle_b_index,
                        ),
                        max(
                            triangle_a_index,
                            triangle_b_index,
                        ),
                    )

                    if pair_key in tested_triangle_pairs:
                        continue

                    tested_triangle_pairs.add(
                        pair_key
                    )

                    triangle_b = triangles[
                        triangle_b_index
                    ]

                    polygon_a = (
                        triangle_a[
                            "polygon_index"
                        ]
                    )

                    polygon_b = (
                        triangle_b[
                            "polygon_index"
                        ]
                    )

                    # Ignore triangles from same original polygon.
                    if polygon_a == polygon_b:
                        continue

                    # Final cheap bounding-box rejection.
                    if not bounds_overlap(
                        triangle_a["bounds"],
                        triangle_b["bounds"],
                        tolerance=tolerance,
                    ):
                        continue

                    if not triangles_overlap_with_area(
                        triangle_a["uvs"],
                        triangle_b["uvs"],
                        tolerance=tolerance,
                    ):
                        continue

                    overlapping_polygons.add(
                        polygon_a
                    )

                    overlapping_polygons.add(
                        polygon_b
                    )

                    polygon_pair = tuple(
                        sorted((
                            polygon_a,
                            polygon_b,
                        ))
                    )

                    overlap_pairs.add(
                        polygon_pair
                    )

        # ---------------------------------------------------------
        # Store result
        # ---------------------------------------------------------

        if not overlapping_polygons:
            continue

        failed_objects[obj.name] = {
            "uv_map":
                uv_layer.name,

            "overlapping_face_count":
                len(
                    overlapping_polygons
                ),

            "polygon_indices":
                sorted(
                    overlapping_polygons
                ),

            "overlap_count":
                len(
                    overlap_pairs
                ),

            "overlaps": [
                {
                    "polygon_a":
                        pair[0],

                    "polygon_b":
                        pair[1],
                }
                for pair in sorted(
                    overlap_pairs
                )
            ],
        }

    return failed_objects


# -------------------------
# Support Functions (Find)
# -------------------------

def build_uv_spatial_grid(
        triangles,
        grid_size=0.05,
    ):
    """
    Places UV triangles into 2D spatial buckets.

    A triangle is inserted into every grid cell touched by
    its bounding box.

    Args:
        triangles (list[dict]):
            Triangle records containing a "bounds" dictionary.

        grid_size (float):
            UV width/height of each grid cell.

    Returns:
        dict:
        {
            (grid_x, grid_y): [
                triangle_index,
                ...
            ]
        }
    """
    if grid_size <= 0.0:
        raise ValueError(
            "grid_size must be greater than zero."
        )

    grid = {}

    for triangle_index, triangle in enumerate(triangles):
        bounds = triangle[
            "bounds"
        ]

        min_cell_x = math.floor(
            bounds["min_u"]
            / grid_size
        )

        max_cell_x = math.floor(
            bounds["max_u"]
            / grid_size
        )

        min_cell_y = math.floor(
            bounds["min_v"]
            / grid_size
        )

        max_cell_y = math.floor(
            bounds["max_v"]
            / grid_size
        )

        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                cell_key = (
                    cell_x,
                    cell_y,
                )

                grid.setdefault(
                    cell_key,
                    [],
                ).append(
                    triangle_index
                )

    return grid


def triangle_signed_area_2d(points):
    """
    Returns the signed area of a 2D triangle.
    """
    a, b, c = points

    return 0.5 * (
        (b[0] - a[0])
        * (c[1] - a[1])
        -
        (b[1] - a[1])
        * (c[0] - a[0])
    )


def get_triangle_bounds(points):
    """
    Returns a 2D bounding box for a triangle.
    """
    u_values = [
        point[0]
        for point in points
    ]

    v_values = [
        point[1]
        for point in points
    ]

    return {
        "min_u": min(u_values),
        "max_u": max(u_values),
        "min_v": min(v_values),
        "max_v": max(v_values),
    }


def bounds_overlap(
        bounds_a,
        bounds_b,
        tolerance=1e-8,
    ):
    """
    Checks whether two bounding boxes can overlap
    with positive area.
    """
    if (bounds_a["max_u"] <= bounds_b["min_u"] + tolerance):
        return False

    if (bounds_b["max_u"] <= bounds_a["min_u"] + tolerance):
        return False

    if (bounds_a["max_v"] <= bounds_b["min_v"] + tolerance):
        return False

    if (bounds_b["max_v"] <= bounds_a["min_v"] + tolerance):
        return False

    return True


def triangles_overlap_with_area(
        triangle_a,
        triangle_b,
        tolerance=1e-8,
    ):
    """
    Returns True when two UV triangles overlap with
    positive area.

    Edge-only and vertex-only contact do not count.
    """

    # A vertex strictly inside the other triangle.
    for point in triangle_a:
        if point_strictly_inside_triangle(
            point,
            triangle_b,
            tolerance=tolerance,
        ):
            return True

    for point in triangle_b:
        if point_strictly_inside_triangle(
            point,
            triangle_a,
            tolerance=tolerance,
        ):
            return True

    edges_a = (
        (triangle_a[0], triangle_a[1]),
        (triangle_a[1], triangle_a[2]),
        (triangle_a[2], triangle_a[0]),
    )

    edges_b = (
        (triangle_b[0], triangle_b[1]),
        (triangle_b[1], triangle_b[2]),
        (triangle_b[2], triangle_b[0]),
    )

    # Proper edge crossings.
    for edge_a in edges_a:
        for edge_b in edges_b:
            if segments_properly_intersect(
                edge_a[0],
                edge_a[1],
                edge_b[0],
                edge_b[1],
                tolerance=tolerance,
            ):
                return True

    # Completely coincident UV triangles.
    if triangles_are_coincident(
        triangle_a,
        triangle_b,
        tolerance=tolerance,
    ):
        return True

    return False


def point_strictly_inside_triangle(
        point,
        triangle,
        tolerance=1e-8,
    ):
    """
    Returns True only when point is strictly inside triangle.
    """
    a, b, c = triangle

    d1 = signed_edge(point, a, b)

    d2 = signed_edge(point, b, c)

    d3 = signed_edge(point, c, a)

    all_positive = (
        d1 > tolerance
        and d2 > tolerance
        and d3 > tolerance
    )

    all_negative = (
        d1 < -tolerance
        and d2 < -tolerance
        and d3 < -tolerance
    )

    return (
        all_positive
        or all_negative
    )


def signed_edge(point, a, b):
    return (
        (point[0] - b[0])
        * (a[1] - b[1])
        -
        (a[0] - b[0])
        * (point[1] - b[1])
    )


def orientation(a, b, c):
    return (
        (b[0] - a[0])
        * (c[1] - a[1])
        -
        (b[1] - a[1])
        * (c[0] - a[0])
    )


def segments_properly_intersect(
        a1,
        a2,
        b1,
        b2,
        tolerance=1e-8,
    ):
    """
    Checks for a proper edge crossing.

    Shared endpoints and simple boundary touching
    are intentionally ignored.
    """
    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)

    return (
        (
            o1 > tolerance
            and o2 < -tolerance
        )
        or
        (
            o1 < -tolerance
            and o2 > tolerance
        )
    ) and (
        (
            o3 > tolerance
            and o4 < -tolerance
        )
        or
        (
            o3 < -tolerance
            and o4 > tolerance
        )
    )


def triangles_are_coincident(
        triangle_a,
        triangle_b,
        tolerance=1e-8,
    ):
    """
    Detects duplicate/coincident UV triangles regardless
    of vertex ordering.
    """
    used = set()

    for point_a in triangle_a:
        matched = False
        for index_b, point_b in enumerate(
            triangle_b
        ):
            if index_b in used:
                continue

            if (
                abs(
                    point_a[0]
                    - point_b[0]
                ) <= tolerance
                and
                abs(
                    point_a[1]
                    - point_b[1]
                ) <= tolerance
            ):
                used.add(
                    index_b
                )

                matched = True
                break

        if not matched:
            return False

    return True
