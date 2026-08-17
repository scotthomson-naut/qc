# Blender imports
import bpy
import bmesh

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Correct Normals Direction"
DESCRIPTION = (
    "Checks mesh objects for faces whose normals are flipped "
    "relative to Blender's recalculated face orientation."
)
WHY = (
    "Face normals determine which direction a polygon faces. "
    "Inward-facing or inconsistent normals break lighting calculations, "
    "cause black patches or weird shading artifacts, hide faces in game "
    "engines via backface culling, and disrupt modifiers, "
    "texture maps, and physics."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

NORMAL_DOT_TOLERANCE = -0.5


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks for mesh objects containing flipped face normals.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_flipped_normals()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} flipped face{}".format(
                object_name,
                data["flipped_face_count"],
                ""
                if data["flipped_face_count"] == 1
                else "s",
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Recalculates normals for the failed objects.
    """
    return fix_objects_with_flipped_normals(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_flipped_normals(
        objects=None,
        exclude_non_manifold=True,
    ):
    """
    Finds mesh objects containing flipped face normals.

    The check creates two temporary BMeshes:

        original_bmesh
            Preserves the current face-normal directions.

        corrected_bmesh
            Has its face normals recalculated using Blender's
            recalculate-face-normals operation.

    A face is considered flipped when its original normal points
    substantially opposite its recalculated normal.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to objects in the current scene.

        exclude_non_manifold (bool):
            When True, objects containing non-manifold edges are skipped.
            Recalculating outside orientation is not always reliable for
            open or non-manifold geometry.

    Returns:
        dict:
        {
            "Cube": {
                "flipped_face_count": 2,
                "flipped_faces_indices": [1, 4],
                "polygon_count": 6,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = obj.data

        if mesh is None:
            continue

        if len(mesh.polygons) == 0:
            continue

        flipped_faces = get_flipped_face_indices(
            mesh,
            exclude_non_manifold=exclude_non_manifold,
        )

        if not flipped_faces:
            continue

        failed_objects[obj.name] = {
            "flipped_face_count": len(
                flipped_faces
            ),
            "flipped_faces_indices": flipped_faces,
            "polygon_count": len(
                mesh.polygons
            ),
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_with_flipped_normals(
        result_data=None,
    ):
    """
    Recalculates outside normals on every failed mesh object.

    Shared mesh datablocks are copied before modification so fixing
    one object does not unexpectedly modify another object.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if not isinstance(
        result_data,
        dict,
    ):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        failed_objects = {}

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:
        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        if obj.library is not None:
            issues.append(
                'Skipped linked object: "{}".'.format(
                    object_name
                )
            )
            continue

        try:
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            bm = bmesh.new()

            try:
                bm.from_mesh(
                    obj.data
                )

                bm.faces.ensure_lookup_table()

                bmesh.ops.recalc_face_normals(
                    bm,
                    faces=list(
                        bm.faces
                    ),
                )

                bm.to_mesh(
                    obj.data
                )

            finally:
                bm.free()

            obj.data.update()

            fixed_objects[obj.name] = {
                "normals_recalculated": True,
            }

        except Exception as error:
            issues.append(
                "Could not recalculate normals for {}: {}".format(
                    object_name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_flipped_face_indices(
        mesh,
        exclude_non_manifold=True,
    ):
    """
    Returns polygon indices whose normals are opposite Blender's
    recalculated face orientation.

    The original mesh is never changed.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock to inspect.

        exclude_non_manifold (bool):
            Skip the mesh when it contains boundary, wire, or
            non-manifold edges.

    Returns:
        list[int]:
            Flipped polygon indices.
    """
    original_bmesh = bmesh.new()
    corrected_bmesh = None

    try:
        original_bmesh.from_mesh(
            mesh
        )

        original_bmesh.faces.ensure_lookup_table()
        original_bmesh.edges.ensure_lookup_table()

        original_bmesh.normal_update()

        if (
            exclude_non_manifold
            and has_non_manifold_edges(
                original_bmesh
            )
        ):
            return []

        # Copy the BMesh so recalculation does not change
        # the original normal directions being compared.
        corrected_bmesh = (
            original_bmesh.copy()
        )

        corrected_bmesh.faces.ensure_lookup_table()
        corrected_bmesh.normal_update()

        bmesh.ops.recalc_face_normals(
            corrected_bmesh,
            faces=list(
                corrected_bmesh.faces
            ),
        )

        corrected_bmesh.normal_update()

        flipped_faces = []

        face_count = min(
            len(original_bmesh.faces),
            len(corrected_bmesh.faces),
        )

        for face_index in range(
            face_count
        ):
            original_face = (
                original_bmesh.faces[
                    face_index
                ]
            )

            corrected_face = (
                corrected_bmesh.faces[
                    face_index
                ]
            )

            normal_dot = (
                original_face.normal.dot(
                    corrected_face.normal
                )
            )

            if normal_dot < NORMAL_DOT_TOLERANCE:
                flipped_faces.append(
                    original_face.index
                )

        return sorted(
            flipped_faces
        )

    finally:
        if corrected_bmesh is not None:
            corrected_bmesh.free()

        original_bmesh.free()


def has_non_manifold_edges(bm):
    """
    Returns True when a BMesh contains boundary, wire,
    or non-manifold edges.

    A closed manifold edge should have exactly two linked faces.
    """
    return any(
        len(edge.link_faces) != 2
        for edge in bm.edges
    )

