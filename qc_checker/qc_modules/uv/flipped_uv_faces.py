# Standard python imports
from mathutils import Vector

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
    failed_objects = get_objects_with_flipped_uv_faces()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} flipped UV face(s)".format(
                object_name,
                data["flipped_face_count"],
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

def get_objects_with_flipped_uv_faces(
        objects=None,
        tolerance=1e-10,
    ):
    """
    Finds mesh objects containing UV faces whose UV orientation
    is mirrored relative to the corresponding 3D polygon.

    The 3D polygon is projected into a local 2D coordinate system
    built from the polygon itself. This avoids false positives caused
    by projecting different cube faces onto different world planes.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Signed areas with an absolute value below this threshold
            are treated as degenerate and skipped.

    Returns:
        dict:
        {
            "ObjectName": {
                "uv_map": "UVMap",
                "flipped_face_count": 2,
                "polygon_indices": [5, 12],
                "flipped_faces": [...]
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

        flipped_faces = []

        for polygon in mesh.polygons:
            loop_indices = list(
                polygon.loop_indices
            )

            if len(loop_indices) < 3:
                continue

            # -----------------------------------------------------
            # UV winding
            # -----------------------------------------------------

            uvs = [
                uv_data[loop_index].uv.copy()
                for loop_index in loop_indices
            ]

            uv_signed_area = get_signed_2d_area(
                uvs
            )

            # Ignore collapsed UV faces.
            if abs(uv_signed_area) <= tolerance:
                continue

            # -----------------------------------------------------
            # Mesh winding in polygon-local 2D coordinates
            # -----------------------------------------------------

            mesh_points_2d = (
                project_polygon_to_local_2d(
                    mesh,
                    polygon,
                )
            )

            if not mesh_points_2d:
                continue

            mesh_signed_area = get_signed_2d_area(
                mesh_points_2d
            )

            if abs(mesh_signed_area) <= tolerance:
                continue

            # Opposite winding means mirrored UV orientation.
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

        if not flipped_faces:
            continue

        failed_objects[obj.name] = {
            "uv_map":
                uv_layer.name,

            "flipped_face_count":
                len(flipped_faces),

            "polygon_indices": [
                item["polygon_index"]
                for item in flipped_faces
            ],

            "flipped_faces":
                flipped_faces,
        }

    return failed_objects


# -------------------------
# Suport Functions (Find)
# -------------------------

def project_polygon_to_local_2d(
        mesh,
        polygon,
    ):
    """
    Projects a 3D polygon into a stable local 2D coordinate system.

    The basis is built from:
        X axis = first valid polygon edge
        Y axis = polygon normal cross X axis

    This preserves the polygon's own winding consistently,
    regardless of its world-space orientation.

    Returns:
        list[Vector]:
            2D projected polygon coordinates.
    """
    vertices = [
        mesh.vertices[index].co.copy()
        for index in polygon.vertices
    ]

    if len(vertices) < 3:
        return []

    origin = vertices[0]

    # Find a usable first edge.
    tangent = None

    for point in vertices[1:]:
        edge = (
            point - origin
        )

        if edge.length_squared > 1e-20:
            tangent = edge.normalized()
            break

    if tangent is None:
        return []

    normal = polygon.normal.normalized()

    if normal.length_squared <= 1e-20:
        return []

    # Local Y axis.
    bitangent = normal.cross(
        tangent
    )

    if bitangent.length_squared <= 1e-20:
        return []

    bitangent.normalize()

    projected = []

    for point in vertices:
        relative = (
            point - origin
        )

        projected.append(
            Vector((
                relative.dot(tangent),
                relative.dot(bitangent),
            ))
        )

    return projected


def get_signed_2d_area(points):
    """
    Calculates signed 2D polygon area.

    Positive and negative values represent opposite winding directions.

    Args:
        points (iterable):
            Points exposing x and y components.

    Returns:
        float:
            Signed polygon area.
    """
    if len(points) < 3:
        return 0.0

    area = 0.0

    for index, point_a in enumerate(
        points
    ):
        point_b = points[
            (index + 1) % len(points)
        ]

        area += (
            point_a.x * point_b.y
            - point_b.x * point_a.y
        )

    return area * 0.5
