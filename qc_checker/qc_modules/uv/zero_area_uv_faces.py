# Standard python imports


# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Zero Area UV Faces"
DESCRIPTION = (
    "Checks if Object has Zero Area UV Faces"
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
    failed_objects = get_objects_with_zero_area_uv_faces()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} zero-area UV face(s)".format(
                object_name,
                data["zero_area_face_count"],
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

def get_objects_with_zero_area_uv_faces(
        objects=None,
        tolerance=1e-10,
    ):
    """
    Finds mesh objects containing collapsed / zero-area UV faces.

    A UV face fails when its UV-space polygon area is effectively zero.

    This catches:
        - All UV corners collapsed to one point.
        - UV corners collapsed along a straight line.
        - Other degenerate UV polygons with effectively no area.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            UV area values less than or equal to this value
            are considered zero.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "zero_area_face_count": 3,
                "polygon_indices": [42, 78, 105],
                "faces": [
                    {
                        "polygon_index": 42,
                        "uv_area": 0.0,
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

        if mesh is None:
            continue

        # No faces: handled by separate mesh-face QC.
        if not mesh.polygons:
            continue

        # Missing UV maps: handled by separate UV-map QC.
        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            continue

        uv_data = uv_layer.data

        zero_area_faces = []

        for polygon in mesh.polygons:

            uvs = [
                uv_data[loop_index].uv
                for loop_index in polygon.loop_indices
            ]

            uv_area = get_uv_polygon_area(uvs)

            if uv_area > tolerance:
                continue

            zero_area_faces.append({
                "polygon_index": polygon.index,
                "uv_area": uv_area,
            })

        if not zero_area_faces:
            continue

        failed_objects[obj.name] = {
            "uv_map": uv_layer.name,

            "zero_area_face_count":
                len(zero_area_faces),

            "polygon_indices": [
                face["polygon_index"]
                for face in zero_area_faces
            ],

            "faces":
                zero_area_faces,
        }

    return failed_objects

# -------------------------
# Support functions (Find)
# -------------------------

def get_uv_polygon_area(uvs):
    """
    Calculates the area of a polygon in UV space using
    the shoelace formula.

    Args:
        uvs (iterable[Vector]):
            UV coordinates around the polygon.

    Returns:
        float:
            Absolute polygon area in UV space.
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