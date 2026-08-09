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
    Projects a 3D polygon into a stable local 2D coordinate system.

    The basis is built from:
        X axis = first valid polygon edge
        Y axis = polygon normal cross X axis

    Returns:
        list[Vector]:
            2D projected polygon coordinates.
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

    origin = vertices[0]

    tangent = None

    for point in vertices[1:]:

        edge = (
            point
            - origin
        )

        if edge.length_squared > 1e-20:
            tangent = edge.normalized()
            break

    if tangent is None:
        return []

    normal = polygon.normal.normalized()

    if normal.length_squared <= 1e-20:
        return []

    bitangent = normal.cross(
        tangent
    )

    if bitangent.length_squared <= 1e-20:
        return []

    bitangent.normalize()

    projected = []

    for point in vertices:

        relative = (
            point
            - origin
        )

        projected.append(
            Vector((
                relative.dot(
                    tangent
                ),
                relative.dot(
                    bitangent
                ),
            ))
        )

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
