# Python imports
from mathutils import Vector

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "UV Orientation"
DESCRIPTION = (
    "Checks all UV maps for flipped or mirrored UV faces. "
)
WHY = (
    "Incorrect UV orientation can cause mirrored textures, baking issues, "
    "unexpected shading, and export problems."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks all UV maps for flipped UV faces.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_flipped_uv_faces()
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
                    "{} flipped UV face(s)"
                ).format(
                    object_name,
                    uv_map_name,
                    uv_map_data[
                        "flipped_face_count"
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

def get_objects_with_flipped_uv_faces(
        objects=None,
        tolerance=1e-10,
    ):
    """
    Finds mesh objects containing flipped UV faces across all UV maps.

    A UV face fails when its UV winding is opposite to the winding of
    the corresponding 3D polygon.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all scene objects.

        tolerance (float):
            Signed areas with an absolute value below this threshold
            are treated as degenerate and skipped.

    Returns:
        dict:
        {
            "ObjectName": {
                "failed_uv_maps": {
                    "UVMap": {
                        "flipped_face_count": 2,
                        "polygon_indices": [5, 12],
                        "flipped_faces": [...],
                    }
                },
                "failed_uv_map_count": 1,
                "flipped_face_count": 2,
                "selection": {
                    "mode": "FACE",
                    "indices": [5, 12],
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    # If in Edit Mode, switch to Object Mode so mesh data is current.
    if (
        bpy.context.object
        and bpy.context.object.mode == "EDIT"
    ):
        bpy.ops.object.mode_set(
            mode="OBJECT"
        )

    for obj in objects:

        # Directly linked library objects are read-only and outside
        # the scope of local UV QC.
        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = obj.data

        if (
            mesh is None
            or not mesh.polygons
        ):
            continue

        # Missing UV maps should be handled by the UV Map Exists check.
        if not mesh.uv_layers:
            continue

        failed_uv_maps = {}
        all_failed_polygon_indices = set()

        # -----------------------------------------------------
        # Check every UV map
        # -----------------------------------------------------

        for uv_layer in mesh.uv_layers:

            uv_data = uv_layer.data

            flipped_faces = []

            for polygon in mesh.polygons:

                loop_indices = list(
                    polygon.loop_indices
                )

                if len(loop_indices) < 3:
                    continue

                # -------------------------------------------------
                # UV winding
                # -------------------------------------------------

                uvs = [
                    uv_data[
                        loop_index
                    ].uv.copy()

                    for loop_index
                    in loop_indices
                ]

                uv_signed_area = (
                    get_signed_2d_area(
                        uvs
                    )
                )

                # Collapsed UV faces are handled by the UV Area check.
                if (
                    abs(uv_signed_area)
                    <= tolerance
                ):
                    continue

                # -------------------------------------------------
                # Mesh winding
                # -------------------------------------------------

                mesh_points_2d = (
                    project_polygon_to_local_2d(
                        mesh,
                        polygon,
                    )
                )

                if not mesh_points_2d:
                    continue

                mesh_signed_area = (
                    get_signed_2d_area(
                        mesh_points_2d
                    )
                )

                if (
                    abs(mesh_signed_area)
                    <= tolerance
                ):
                    continue

                # -------------------------------------------------
                # Opposite winding = flipped UV orientation
                # -------------------------------------------------

                if (
                    mesh_signed_area
                    * uv_signed_area
                    < 0.0
                ):
                    flipped_faces.append({
                        "polygon_index":
                            polygon.index,

                        "uv_signed_area":
                            uv_signed_area,

                        "mesh_signed_area":
                            mesh_signed_area,
                    })

                    all_failed_polygon_indices.add(
                        polygon.index
                    )

            if not flipped_faces:
                continue

            failed_uv_maps[
                uv_layer.name
            ] = {
                "flipped_face_count":
                    len(flipped_faces),

                "polygon_indices": [
                    item["polygon_index"]
                    for item in flipped_faces
                ],

                "flipped_faces":
                    flipped_faces,
            }

        # -----------------------------------------------------
        # Object passes all UV maps
        # -----------------------------------------------------

        if not failed_uv_maps:
            continue

        # Combined unique failed polygon indices.
        combined_polygon_indices = sorted(
            all_failed_polygon_indices
        )

        failed_objects[
            obj.name
        ] = {
            "failed_uv_maps":
                failed_uv_maps,

            "failed_uv_map_count":
                len(failed_uv_maps),

            # Total failures across UV maps. A polygon appearing in two
            # UV maps counts twice here because both UV maps failed.
            "flipped_face_count":
                sum(
                    uv_map_data[
                        "flipped_face_count"
                    ]
                    for uv_map_data
                    in failed_uv_maps.values()
                ),

            # Unique geometry polygons affected anywhere.
            "polygon_indices":
                combined_polygon_indices,

            # Works with your Select Failed Components framework.
            "selection": {
                "mode": "FACE",
                "indices":
                    combined_polygon_indices,
            },
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def project_polygon_to_local_2d(
        mesh,
        polygon,
    ):
    """
    Projects a 3D polygon onto a FIXED world-axis-aligned 2D plane,
    chosen by dominant axis magnitude.

    Note:
        This replaces an earlier version that built a custom local
        basis (tangent/bitangent) FROM polygon.normal. That was a
        self-referential tautology: polygon.normal is itself derived
        from the polygon's current winding order (it flips when
        winding flips), so using it to build the very frame the
        winding gets re-measured in caused the measurement to always
        cancel out - confirmed by testing where a correctly-wound
        face and a deliberately flipped face both reported the exact
        same Mesh Signed Area, when they should have reported
        opposite signs.

        The fix: compute a Newell-method normal directly from raw
        vertex positions, then choose the projection plane using
        only the ABSOLUTE VALUE of that normal's components.
        Reversing a polygon's winding negates every component of a
        Newell normal equally, so magnitude - and therefore which
        plane gets chosen - never changes between a face and its
        flipped twin. Only the actual vertex order then affects the
        final signed area, which is exactly the one thing that
        should affect it.

    Returns:
        list[Vector]:
            2D projected polygon coordinates in a fixed world plane.
    """
    vertices = [
        mesh.vertices[
            index
        ].co.copy()

        for index
        in polygon.vertices
    ]

    if len(vertices) < 3:
        return []

    # -----------------------------------------------------------
    # Newell's method - computed directly from raw vertex positions
    # in the polygon's current winding order. This DOES flip sign
    # when winding flips (expected and correct - that's the actual
    # signal we want), but we only ever use its magnitude below,
    # never its direction, which keeps plane SELECTION itself
    # winding-independent.
    # -----------------------------------------------------------

    normal_x = 0.0
    normal_y = 0.0
    normal_z = 0.0

    count = len(vertices)

    for index in range(count):
        current = vertices[index]
        next_point = vertices[(index + 1) % count]

        normal_x += (
            (current.y - next_point.y)
            * (current.z + next_point.z)
        )

        normal_y += (
            (current.z - next_point.z)
            * (current.x + next_point.x)
        )

        normal_z += (
            (current.x - next_point.x)
            * (current.y + next_point.y)
        )

    abs_x = abs(normal_x)
    abs_y = abs(normal_y)
    abs_z = abs(normal_z)

    if abs_x <= 1e-20 and abs_y <= 1e-20 and abs_z <= 1e-20:
        # Fully degenerate polygon (zero area from any angle).
        return []

    # -----------------------------------------------------------
    # Choose the FIXED projection plane by magnitude only - never
    # by sign/direction, which is what keeps this winding-safe.
    # -----------------------------------------------------------

    if abs_x >= abs_y and abs_x >= abs_z:
        # X-dominant: project onto the YZ plane.
        projected = [
            Vector((point.y, point.z))
            for point in vertices
        ]

    elif abs_y >= abs_x and abs_y >= abs_z:
        # Y-dominant: project onto the ZX plane.
        projected = [
            Vector((point.z, point.x))
            for point in vertices
        ]

    else:
        # Z-dominant: project onto the XY plane.
        projected = [
            Vector((point.x, point.y))
            for point in vertices
        ]

    return projected


def get_signed_2d_area(
        points,
    ):
    """
    Calculates signed 2D polygon area.

    Positive and negative values represent opposite winding directions.
    """
    if len(points) < 3:
        return 0.0

    area = 0.0

    for index, point_a in enumerate(
        points
    ):
        point_b = points[
            (index + 1)
            % len(points)
        ]

        area += (
            point_a.x
            * point_b.y
            - point_b.x
            * point_a.y
        )

    return area * 0.5
