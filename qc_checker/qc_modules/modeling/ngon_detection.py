# Standard python imports

# Blender imports
import bpy
import bmesh

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_ngons()

    return {
        "issues": [
            "Failed object: {} ({} n-gons)".format(
                name,
                data["ngon_count"]
            )
            for name, data in failed_objects.items()
        ],
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------

def get_objects_with_ngons(objects=None):
    """
    Finds mesh objects containing n-gons.

    An n-gon is any face with more than four vertices.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "ngon_faces": [10, 15, 28],
                "ngon_count": 3,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    results = {}

    for obj in objects:
        if obj.type != 'MESH':
            continue

        bm = bmesh.new()

        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            ngon_faces = [
                face.index
                for face in bm.faces
                if len(face.verts) > 4
            ]

            if ngon_faces:
                results[obj.name] = {
                    "ngon_faces": ngon_faces,
                    "ngon_count": len(ngon_faces),
                }

        finally:
            bm.free()

    return results
