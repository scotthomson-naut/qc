# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "UV Area Valid"
DESCRIPTION = (
    "Checks if Object has Zero Area UV Faces. "
)
WHY = (
    "Helps find unmapped faces, overlapping artifacts, or collapsed UV "
    "coordinates that cause texture stretching, baking errors, "
    "or game engine import warnings."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks all UV maps for zero-area UV faces.
    """
    failed_objects = (
        get_objects_with_zero_area_uv_faces()
    )

    issues = []

    for object_name, data in (
        failed_objects.items()
    ):

        for uv_map_name, uv_data in (
            data["failed_uv_maps"].items()
        ):
            issues.append(
                (
                    "Failed object: {} - UV map '{}' "
                    "has {} zero-area UV face(s)"
                ).format(
                    object_name,
                    uv_map_name,
                    uv_data[
                        "zero_area_face_count"
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

    # If in edit mode change to Object mode
    if bpy.context.object and bpy.context.object.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    for obj in objects:

        # Directly linked library objects are read-only and outside
        # the scope of local UV QC.
        if obj.library is not None:
            continue

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

        failed_uv_maps = {}

        for uv_layer in mesh.uv_layers:

            uv_data = uv_layer.data
            zero_area_faces = []

            for polygon in mesh.polygons:

                uvs = [
                    uv_data[
                        loop_index
                    ].uv
                    for loop_index
                    in polygon.loop_indices
                ]

                uv_area = get_uv_polygon_area(
                    uvs
                )

                if uv_area > tolerance:
                    continue

                zero_area_faces.append({
                    "polygon_index":
                        polygon.index,

                    "uv_area":
                        uv_area,
                })

            if not zero_area_faces:
                continue

            failed_uv_maps[
                uv_layer.name
            ] = {
                "zero_area_face_count":
                    len(zero_area_faces),

                "polygon_indices": [
                    face["polygon_index"]
                    for face in zero_area_faces
                ],

                "faces":
                    zero_area_faces,
            }

        if not failed_uv_maps:
            continue

        failed_objects[
            obj.name
        ] = {
            "failed_uv_maps":
                failed_uv_maps,

            "failed_uv_map_count":
                len(failed_uv_maps),

            "zero_area_face_count":
                sum(
                    data["zero_area_face_count"]
                    for data
                    in failed_uv_maps.values()
                ),
        }

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

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
