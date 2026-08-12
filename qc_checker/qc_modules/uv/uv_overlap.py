# Standard python imports
import math

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "UV Overlap"
DESCRIPTION = (
    "Checks if Object has UV faces that overlap "
    "with other UV faces."
)
WHY = (
    "Overlapping coordinates cause different parts of a 3D model to share "
    "the same exact space on a 2D texture map. While intentional overlap "
    "works well for symmetrical or repeating elements like bricks or wood "
    "planks, unintended overlap breaks texture painting, distorts detail "
    "baking, and causes artifact."
)


# Alpha "DEFAULT"
MAX_SCENE_TRIANGLES = 4000000

# -------------------------------------------------------------------------
# Congruence tolerance
# -------------------------------------------------------------------------
#
# Fixed, not a user setting - same reasoning as UV_BOUNDS_EPSILON in
# uv_within_bounds.py. This absorbs floating-point noise in edge
# length / area comparisons, it isn't a workflow policy choice.
# THIS IS THE ONLY PLACE THIS VALUE IS DEFINED.
CONGRUENCE_TOLERANCE = 1e-4


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks all UV maps for overlapping UV faces.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_overlapping_uv_faces(
            grid_size=0.05
        )
    )

    issues = []

    for object_name, object_data in (
        failed_objects.items()
    ):
        failed_uv_maps = object_data.get(
            "failed_uv_maps",
            {},
        )

        for uv_map_name, uv_map_data in (
            failed_uv_maps.items()
        ):
            issues.append(
                (
                    "Failed object: {} - UV map '{}' has "
                    "{} UV face(s) in {} overlap(s) "
                    "({} likely intentional/mirrored, "
                    "{} likely mistakes)"
                ).format(
                    object_name,
                    uv_map_name,
                    uv_map_data[
                        "overlapping_face_count"
                    ],
                    uv_map_data[
                        "overlap_count"
                    ],
                    uv_map_data[
                        "likely_intentional_overlap_count"
                    ],
                    uv_map_data[
                        "likely_mistake_overlap_count"
                    ],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_overlapping_uv_faces(
        objects=None,
        tolerance=1e-8,
        grid_size=0.05,
    ):
    """
    Finds mesh objects containing overlapping UV faces across all UV maps.

    Uses a 2D spatial grid / bucket system to reduce triangle
    comparisons on dense meshes.

    Note:
        Each overlapping polygon pair is additionally tested for
        congruence (see polygons_are_congruent()) - whether the two
        full UV faces are the same size/shape, just translated,
        rotated, or mirrored relative to each other. This can't know
        artist intent with certainty, but a congruent pair is a
        strong, low-cost signal for intentional UV reuse (mirrored
        halves, trim sheets), while a non-congruent pair (different
        size/shape, partial overlap, distortion) essentially never
        happens by design. A duplicated-and-forgotten island that's
        an exact copy will still read as congruent and won't be
        distinguished from intentional reuse - that's a known,
        accepted limitation of this approach, not a bug.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Numerical tolerance used for overlap tests.

        grid_size (float):
            UV-space size of each spatial bucket.

    Returns:
        dict:
        {
            "Character_Body": {
                "failed_uv_maps": {
                    "UVMap": {
                        "overlapping_face_count": 4,
                        "polygon_indices": [12, 13, 88, 89],
                        "overlap_count": 2,
                        "likely_intentional_overlap_count": 1,
                        "likely_mistake_overlap_count": 1,
                        "overlaps": [
                            {
                                "polygon_a": 12,
                                "polygon_b": 88,
                                "congruent": True,
                            }
                        ],
                    }
                },

                "failed_uv_map_count": 1,

                "overlapping_face_count": 4,

                "polygon_indices": [
                    12,
                    13,
                    88,
                    89,
                ],

                "selection": {
                    "mode": "FACE",
                    "indices": [
                        12,
                        13,
                        88,
                        89,
                    ],
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    # Keep mesh data synchronized with Edit Mode.
    if (
        bpy.context.object
        and bpy.context.object.mode == "EDIT"
    ):
        bpy.ops.object.mode_set(
            mode="OBJECT"
        )

    for obj in objects:

        if obj.type != "MESH":
            continue

        mesh = obj.data

        if (
            mesh is None
            or not mesh.polygons
        ):
            continue

        if not mesh.uv_layers:
            continue

        # Triangulation only depends on geometry,
        # so calculate it once per mesh.
        mesh.calc_loop_triangles()

        if not mesh.loop_triangles:
            continue

        failed_uv_maps = {}

        all_overlapping_polygons = set()

        total_overlap_count = 0
        total_likely_intentional_count = 0
        total_likely_mistake_count = 0

        # -----------------------------------------------------
        # Check every UV map
        # -----------------------------------------------------

        for uv_layer in mesh.uv_layers:

            uv_data = uv_layer.data

            triangles = []

            # -------------------------------------------------
            # Build UV triangle records
            # -------------------------------------------------

            for triangle_index, loop_triangle in enumerate(
                mesh.loop_triangles
            ):
                uv_points = [
                    (
                        uv_data[
                            loop_index
                        ].uv.x,

                        uv_data[
                            loop_index
                        ].uv.y,
                    )

                    for loop_index
                    in loop_triangle.loops
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

            # -------------------------------------------------
            # Build spatial grid
            # -------------------------------------------------

            grid = build_uv_spatial_grid(
                triangles,
                grid_size=grid_size,
            )

            overlapping_polygons = set()
            overlap_pairs = set()

            tested_triangle_pairs = set()

            # -------------------------------------------------
            # Compare only triangles sharing grid cells
            # -------------------------------------------------

            for triangle_indices in grid.values():

                count = len(
                    triangle_indices
                )

                if count < 2:
                    continue

                for local_a in range(
                    count
                ):
                    triangle_a_index = (
                        triangle_indices[
                            local_a
                        ]
                    )

                    triangle_a = triangles[
                        triangle_a_index
                    ]

                    for local_b in range(
                        local_a + 1,
                        count,
                    ):
                        triangle_b_index = (
                            triangle_indices[
                                local_b
                            ]
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

                        if (
                            pair_key
                            in tested_triangle_pairs
                        ):
                            continue

                        tested_triangle_pairs.add(
                            pair_key
                        )

                        triangle_b = triangles[
                            triangle_b_index
                        ]

                        polygon_a = triangle_a[
                            "polygon_index"
                        ]

                        polygon_b = triangle_b[
                            "polygon_index"
                        ]

                        # Ignore triangles from the same
                        # original polygon.
                        if (
                            polygon_a
                            == polygon_b
                        ):
                            continue

                        # Cheap bounding-box rejection.
                        if not bounds_overlap(
                            triangle_a[
                                "bounds"
                            ],
                            triangle_b[
                                "bounds"
                            ],
                            tolerance=tolerance,
                        ):
                            continue

                        if not triangles_overlap_with_area(
                            triangle_a[
                                "uvs"
                            ],
                            triangle_b[
                                "uvs"
                            ],
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

            # -------------------------------------------------
            # UV map passes
            # -------------------------------------------------

            if not overlapping_polygons:
                continue

            sorted_polygons = sorted(
                overlapping_polygons
            )

            # -------------------------------------------------
            # Congruence check per overlapping pair
            # -------------------------------------------------

            overlap_details = []
            likely_intentional_count = 0
            likely_mistake_count = 0

            for pair in sorted(overlap_pairs):
                polygon_a_index, polygon_b_index = pair

                uv_points_a = get_polygon_uv_points(
                    mesh,
                    uv_data,
                    polygon_a_index,
                )

                uv_points_b = get_polygon_uv_points(
                    mesh,
                    uv_data,
                    polygon_b_index,
                )

                congruent = polygons_are_congruent(
                    uv_points_a,
                    uv_points_b,
                    tolerance=CONGRUENCE_TOLERANCE,
                )

                if congruent:
                    likely_intentional_count += 1
                else:
                    likely_mistake_count += 1

                overlap_details.append({
                    "polygon_a": polygon_a_index,
                    "polygon_b": polygon_b_index,
                    "congruent": congruent,
                })

            failed_uv_maps[
                uv_layer.name
            ] = {
                "overlapping_face_count":
                    len(
                        overlapping_polygons
                    ),

                "polygon_indices":
                    sorted_polygons,

                "overlap_count":
                    len(
                        overlap_pairs
                    ),

                "likely_intentional_overlap_count":
                    likely_intentional_count,

                "likely_mistake_overlap_count":
                    likely_mistake_count,

                "overlaps": overlap_details,
            }

            all_overlapping_polygons.update(
                overlapping_polygons
            )

            total_overlap_count += len(
                overlap_pairs
            )

            total_likely_intentional_count += (
                likely_intentional_count
            )

            total_likely_mistake_count += (
                likely_mistake_count
            )

        # -----------------------------------------------------
        # Object passes all UV maps
        # -----------------------------------------------------

        if not failed_uv_maps:
            continue

        combined_polygon_indices = sorted(
            all_overlapping_polygons
        )

        failed_objects[
            obj.name
        ] = {
            "failed_uv_maps":
                failed_uv_maps,

            "failed_uv_map_count":
                len(
                    failed_uv_maps
                ),

            # Total unique geometry faces affected
            # across any UV map.
            "overlapping_face_count":
                len(
                    all_overlapping_polygons
                ),

            # Total overlap relationships across
            # all UV maps.
            "overlap_count":
                total_overlap_count,

            "likely_intentional_overlap_count":
                total_likely_intentional_count,

            "likely_mistake_overlap_count":
                total_likely_mistake_count,

            "polygon_indices":
                combined_polygon_indices,

            # Works with your existing component
            # selection framework.
            "selection": {
                "mode": "FACE",
                "indices":
                    combined_polygon_indices,
            },
        }

    return failed_objects


# -------------------------------------------------------------------------
# Congruence helpers
# -------------------------------------------------------------------------

def get_polygon_uv_points(mesh, uv_data, polygon_index):
    """
    Returns the full UV loop for a polygon, in loop order.

    Note:
        This intentionally reads the ORIGINAL polygon's full UV
        shape, not just the triangle that happened to trigger the
        overlap detection - an n-gon gets split into multiple
        triangles for the overlap test itself, but congruence should
        compare the real UV faces an artist would actually see.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        uv_data (bpy.types.bpy_prop_collection):
            The active UV layer's .data collection.

        polygon_index (int):
            Index into mesh.polygons.

    Returns:
        list[tuple[float, float]]:
            UV points in loop order.
    """
    polygon = mesh.polygons[polygon_index]

    return [
        (
            uv_data[loop_index].uv.x,
            uv_data[loop_index].uv.y,
        )
        for loop_index in polygon.loop_indices
    ]


def polygon_uv_area(uv_points):
    """
    Returns the unsigned area of a 2D polygon via the shoelace
    formula. Generalizes triangle_signed_area_2d() to any vertex
    count.

    Args:
        uv_points (list[tuple[float, float]]):
            Polygon vertices in loop order.

    Returns:
        float:
            Unsigned area.
    """
    total = 0.0
    count = len(uv_points)

    for index in range(count):
        x1, y1 = uv_points[index]
        x2, y2 = uv_points[(index + 1) % count]

        total += (x1 * y2) - (x2 * y1)

    return abs(total) * 0.5


def polygon_uv_edge_lengths(uv_points):
    """
    Returns the sorted edge lengths of a 2D polygon's loop.

    Note:
        Sorting (rather than keeping loop order) is what makes this
        comparison indifferent to where the loop happens to start,
        and to rotation or mirroring - none of those change a
        shape's SET of edge lengths, only the order they'd appear in
        if read sequentially.

    Args:
        uv_points (list[tuple[float, float]]):
            Polygon vertices in loop order.

    Returns:
        list[float]:
            Edge lengths, sorted ascending.
    """
    count = len(uv_points)
    lengths = []

    for index in range(count):
        x1, y1 = uv_points[index]
        x2, y2 = uv_points[(index + 1) % count]

        lengths.append(
            math.hypot(x2 - x1, y2 - y1)
        )

    return sorted(lengths)


def polygons_are_congruent(
        uv_points_a,
        uv_points_b,
        tolerance=CONGRUENCE_TOLERANCE,
    ):
    """
    Checks whether two UV polygons are congruent - same size and
    shape, allowing for any combination of translation, rotation, or
    mirroring between them.

    Note:
        This is a practical heuristic, not a rigorous proof of
        congruence. Matching area plus the full sorted set of edge
        lengths is invariant to translation/rotation/mirroring and
        catches the overwhelming majority of real cases (mirrored
        halves, trim sheet tiles, duplicated islands), but it's
        theoretically possible for two genuinely different shapes to
        coincidentally share the same area and edge-length set
        without being truly congruent. Good enough for a QC signal
        distinguishing "probably fine" from "probably a mistake" -
        not meant to be mathematically airtight.

    Args:
        uv_points_a (list[tuple[float, float]]):
            First polygon's UV loop.

        uv_points_b (list[tuple[float, float]]):
            Second polygon's UV loop.

        tolerance (float):
            Allowed difference in area and per-edge length.

    Returns:
        bool:
            True if the two polygons are considered congruent.
    """
    if len(uv_points_a) != len(uv_points_b):
        return False

    area_a = polygon_uv_area(uv_points_a)
    area_b = polygon_uv_area(uv_points_b)

    if abs(area_a - area_b) > tolerance:
        return False

    edge_lengths_a = polygon_uv_edge_lengths(uv_points_a)
    edge_lengths_b = polygon_uv_edge_lengths(uv_points_b)

    for length_a, length_b in zip(edge_lengths_a, edge_lengths_b):
        if abs(length_a - length_b) > tolerance:
            return False

    return True


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

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