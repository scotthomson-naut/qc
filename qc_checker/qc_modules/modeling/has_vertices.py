# Standard python imports

# Blender imports
import bpy

# Company imports


# Meta data
SEVERITY = "critical"
LABEL = "Has Vertices"
DESCRIPTION = (
    "Checks if Object has Vertices"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue
    """
    failed_objects = get_meshes_without_vertices()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Mesh has no Vertices "
            "({} faces, {} edges)".format(
                object_name,
                data["face_count"],
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

def get_meshes_without_vertices(objects=None):
    """
    Finds mesh objects that contain no Vertices.

    A mesh fails when it exists but has zero vertices. This includes:
        - Empty mesh objects
        - Meshes containing only polygons
        - Meshes containing only edges

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Mesh_Object": {
                "vertex_count": 0,
                "edge_count": 4,
                "face_count": 4,
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

        vertex_count = len(mesh.vertices)

        if vertex_count > 0:
            continue

        failed_objects[obj.name] = {
            "vertex_count": vertex_count,
            "edge_count": len(mesh.edges),
            "face_count": len(mesh.polygons),
        }

    return failed_objects
