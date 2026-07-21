# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue
    """
    failed_objects = get_meshes_without_faces()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Mesh has no faces "
            "({} vertices, {} edges)".format(
                object_name,
                data["vertex_count"],
                data["edge_count"],
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

def get_meshes_without_faces(objects=None):
    """
    Finds mesh objects that contain no faces.

    A mesh fails when it exists but has zero polygons. This includes:
        - Empty mesh objects
        - Meshes containing only vertices
        - Meshes containing only edges

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Mesh_Object": {
                "vertex_count": 4,
                "edge_count": 4,
                "face_count": 0,
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

        face_count = len(mesh.polygons)

        if face_count > 0:
            continue

        failed_objects[obj.name] = {
            "vertex_count": len(mesh.vertices),
            "edge_count": len(mesh.edges),
            "face_count": face_count,
        }

    return failed_objects
