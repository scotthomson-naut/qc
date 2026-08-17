# Blender imports
import bpy
import bmesh


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "No N-Gons"
DESCRIPTION = (
    "Checks if Object's mesh have N-Gons (polygons with 5 or more sides)."

)
WHY = (
    "Helps prevent rendering glitches, deformation failures during animation, "
    "and unpredictable results when exporting models to game engines "
    "or other software."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run check for N-Gons.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_ngons()

    return {
        "issues": [
            "Failed object: {} ({} n-gons)".format(
                name,
                data["ngon_count"],
            )
            for name, data
            in failed_objects.items()
        ],

        "failed_objects":
            failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_ngons(
        objects=None,
    ):
    """
    Finds mesh objects containing N-Gons.

    An N-Gon is any polygon containing more than four vertices.

    Meshes are validated on a temporary copy before being passed
    into BMesh. If validation detects invalid geometry, that object
    is skipped here and should be handled by the separate
    mesh_invalid_geometry QC check.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.

            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "ngon_faces": [
                    10,
                    15,
                    28,
                ],
                "ngon_count": 3,
            },
        }
    """
    if objects is None:
        objects = (
            bpy.context.scene.objects
        )

    results = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue

        # -----------------------------------------------------
        # Mesh objects only
        # -----------------------------------------------------

        if obj is None:
            continue

        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        # -----------------------------------------------------
        # Validate mesh before BMesh
        # -----------------------------------------------------

        validated_mesh = None

        try:
            (
                validated_mesh,
                was_invalid,
            ) = get_validated_mesh_copy(
                obj
            )

            # Could not safely create/validate mesh.
            if validated_mesh is None:
                continue

            # Invalid geometry was detected.
            #
            # Do not run topology checks on repaired geometry,
            # because that may not represent the original mesh.
            #
            # mesh_invalid_geometry should report this object.
            if was_invalid:
                continue

            # -------------------------------------------------
            # Safe BMesh conversion
            # -------------------------------------------------

            bm = bmesh.new()

            try:
                bm.from_mesh(
                    validated_mesh
                )

                bm.faces.ensure_lookup_table()

                ngon_faces = [
                    face.index

                    for face in bm.faces

                    if len(
                        face.verts
                    ) > 4
                ]

                if ngon_faces:

                    results[obj.name] = {
                        "ngon_faces": ngon_faces,
                        "ngon_count": len(ngon_faces),

                        "selection": {
                            "mode": "FACE",
                            "indices": ngon_faces,
                        },
                    }
            finally:
                bm.free()

        except Exception:
            # Never allow one malformed mesh to prevent
            # the rest of the scene from being checked.
            print(
                "Could not safely check N-Gons on object: {}".format(
                    obj.name
                )
            )
            continue

        finally:
            # Always remove temporary mesh datablock.
            if validated_mesh is not None:

                try:
                    bpy.data.meshes.remove(
                        validated_mesh
                    )

                except Exception:
                    pass

    return results


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_validated_mesh_copy(obj):
    """
    Creates and validates a temporary copy of an object's mesh.

    This avoids passing potentially invalid mesh data directly
    into bmesh.from_mesh(), which can cause Blender instability
    or crashes with badly corrupted geometry.

    The original mesh is never modified.

    Args:
        obj (bpy.types.Object):
            Mesh object to validate.

    Returns:
        tuple:
            (
                validated_mesh | None,
                was_invalid (bool),
            )

        validated_mesh:
            Temporary validated mesh copy.

            The caller is responsible for removing it with:

                bpy.data.meshes.remove(mesh)

        was_invalid:
            True when Mesh.validate() detected and corrected
            invalid geometry in the temporary copy.
    """
    if obj is None:
        return None, True

    if obj.type != "MESH":
        return None, True

    source_mesh = obj.data

    if source_mesh is None:
        return None, True

    temp_mesh = None

    try:
        # Work only on a copy so QC never modifies
        # the original artist mesh.
        temp_mesh = source_mesh.copy()

        # Mesh.validate() returns True when invalid data
        # was detected and corrected.
        was_invalid = temp_mesh.validate(
            verbose=False,
            clean_customdata=False,
        )

        temp_mesh.update()

        return (
            temp_mesh,
            was_invalid,
        )

    except Exception:
        if temp_mesh is not None:

            try:
                bpy.data.meshes.remove(
                    temp_mesh
                )

            except Exception:
                pass

        return None, True
