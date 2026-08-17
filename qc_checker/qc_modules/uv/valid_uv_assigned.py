# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Valid UV Assigned"
DESCRIPTION = (
    "Checks that every polygon has meaningful UV coordinates across all "
)
WHY = (
    "UV maps. Missing or collapsed UVs can cause stretched textures, "
    "painting and baking errors, and invalid texture mapping."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks all UV maps for polygons without valid UV coordinates.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_meshes_with_unmapped_polygons()
    )

    issues = []

    for object_name, object_data in (
        failed_objects.items()
    ):

        reason = object_data.get(
            "reason"
        )

        if reason:
            issues.append(
                "Failed object: {} - {}".format(
                    object_name,
                    reason,
                )
            )

            continue

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
                    "{} of {} polygon(s) without valid UV coordinates"
                ).format(
                    object_name,
                    uv_map_name,
                    uv_map_data[
                        "unmapped_count"
                    ],
                    uv_map_data[
                        "polygon_count"
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

def get_meshes_with_unmapped_polygons(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing polygons without meaningful UV
    coordinates across all UV maps.

    A polygon is considered invalid when:
        - The mesh has no UV map.
        - The polygon has no UV loop data.
        - All UV coordinates for the polygon are effectively identical.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Tolerance used when comparing UV coordinates.

    Returns:
        dict:
        {
            "MeshObject": {
                "failed_uv_maps": {
                    "UVMap": {
                        "polygon_count": 100,
                        "unmapped_count": 2,
                        "unmapped_polygons": [14, 27],
                    }
                },

                "failed_uv_map_count": 1,
                "unmapped_count": 2,
                "polygon_indices": [14, 27],

                "selection": {
                    "mode": "FACE",
                    "indices": [14, 27],
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    # Keep mesh datablocks synchronized with Edit Mode.
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

        if mesh is None:
            continue

        if not mesh.polygons:
            continue

        polygon_count = len(
            mesh.polygons
        )

        # -----------------------------------------------------
        # No UV maps
        # -----------------------------------------------------

        if not mesh.uv_layers:

            polygon_indices = [
                polygon.index
                for polygon in mesh.polygons
            ]

            failed_objects[
                obj.name
            ] = {
                "failed_uv_maps": {},
                "failed_uv_map_count": 0,

                "polygon_count":
                    polygon_count,

                "unmapped_count":
                    polygon_count,

                "polygon_indices":
                    polygon_indices,

                "reason":
                    "Mesh has no UV map",

                "selection": {
                    "mode": "FACE",
                    "indices":
                        polygon_indices,
                },
            }

            continue

        # -----------------------------------------------------
        # Check every UV map
        # -----------------------------------------------------

        failed_uv_maps = {}

        all_failed_polygon_indices = set()

        total_unmapped_count = 0

        for uv_layer in mesh.uv_layers:

            uv_data = uv_layer.data

            unmapped_polygons = []

            for polygon in mesh.polygons:

                polygon_uvs = []

                for loop_index in (
                    polygon.loop_indices
                ):

                    if loop_index >= len(
                        uv_data
                    ):
                        continue

                    uv = uv_data[
                        loop_index
                    ].uv

                    polygon_uvs.append(
                        (
                            uv.x,
                            uv.y,
                        )
                    )

                # ---------------------------------------------
                # No UV data
                # ---------------------------------------------

                if not polygon_uvs:
                    unmapped_polygons.append(
                        polygon.index
                    )

                    all_failed_polygon_indices.add(
                        polygon.index
                    )

                    continue

                # ---------------------------------------------
                # All corners collapsed to same coordinate
                # ---------------------------------------------

                first_u, first_v = (
                    polygon_uvs[0]
                )

                has_uv_spread = False

                for u, v in polygon_uvs[1:]:

                    if (
                        abs(
                            u - first_u
                        ) > tolerance
                        or
                        abs(
                            v - first_v
                        ) > tolerance
                    ):
                        has_uv_spread = True
                        break

                if has_uv_spread:
                    continue

                unmapped_polygons.append(
                    polygon.index
                )

                all_failed_polygon_indices.add(
                    polygon.index
                )

            # -------------------------------------------------
            # Store UV-map failure
            # -------------------------------------------------

            if not unmapped_polygons:
                continue

            failed_uv_maps[
                uv_layer.name
            ] = {
                "polygon_count":
                    polygon_count,

                "unmapped_count":
                    len(
                        unmapped_polygons
                    ),

                "unmapped_polygons":
                    unmapped_polygons,
            }

            total_unmapped_count += (
                len(
                    unmapped_polygons
                )
            )

        # -----------------------------------------------------
        # Object passes every UV map
        # -----------------------------------------------------

        if not failed_uv_maps:
            continue

        combined_polygon_indices = sorted(
            all_failed_polygon_indices
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

            "polygon_count":
                polygon_count,

            # Total failures across UV maps.
            "unmapped_count":
                total_unmapped_count,

            # Unique geometry faces affected in any UV map.
            "polygon_indices":
                combined_polygon_indices,

            # Works with your component-selection framework.
            "selection": {
                "mode": "FACE",
                "indices":
                    combined_polygon_indices,
            },
        }

    return failed_objects
