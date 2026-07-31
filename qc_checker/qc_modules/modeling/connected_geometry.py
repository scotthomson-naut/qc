# Blender imports
import bpy
import bmesh


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Connected Geometry"
DESCRIPTION = (
    "Checks mesh objects for vertices, edges, or faces that are not "
    "connected to the object's main mesh body."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "minimum_loose_vertices": {
        "type": "int",
        "label": "Minimum Loose Vertices",
        "description": (
            "Only report disconnected components containing at least this "
            "number of vertices."
        ),
        "default": 1,
        "min": 1,
    },

    "ignore_vertex_only_components": {
        "type": "bool",
        "label": "Ignore Isolated Vertices",
        "description": (
            "Ignore disconnected components containing vertices but no "
            "edges or faces."
        ),
        "default": False,
    },

    "ignore_edge_only_components": {
        "type": "bool",
        "label": "Ignore Loose Edges",
        "description": (
            "Ignore disconnected components containing edges but no faces."
        ),
        "default": False,
    },

    "ignore_face_components": {
        "type": "bool",
        "label": "Ignore Disconnected Faces",
        "description": (
            "Ignore disconnected components containing one or more faces."
        ),
        "default": False,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds mesh objects containing geometry components that are disconnected
    from the main mesh body.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_objects = get_objects_with_loose_geometry(
        settings=settings,
    )

    issues = []

    for object_name, object_data in sorted(
        failed_objects.items()
    ):
        component_count = object_data.get(
            "loose_component_count",
            0,
        )

        loose_vertex_count = object_data.get(
            "loose_vertex_count",
            0,
        )

        loose_edge_count = object_data.get(
            "loose_edge_count",
            0,
        )

        loose_face_count = object_data.get(
            "loose_face_count",
            0,
        )

        issues.append(
            (
                'Object "{}" has {} disconnected geometry component{} '
                "outside the main mesh body: {} vertices, {} edges and "
                "{} faces."
            ).format(
                object_name,
                component_count,
                "" if component_count == 1 else "s",
                loose_vertex_count,
                loose_edge_count,
                loose_face_count,
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "settings": settings,
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Removes disconnected geometry components while preserving the current
    main mesh body.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    return remove_loose_geometry_components(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_loose_geometry(
        objects=None,
        settings=None,
    ):
    """
    Finds disconnected geometry components on mesh objects.

    The main component is selected using this priority:

        1. Highest face count
        2. Highest edge count
        3. Highest vertex count
        4. Lowest original vertex index

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to objects in the current scene.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        object_result = analyze_object_components(
            obj=obj,
            settings=settings,
        )

        if object_result is None:
            continue

        failed_objects[obj.name] = object_result

    return failed_objects


def analyze_object_components(
        obj,
        settings=None,
    ):
    """
    Analyzes the connected geometry components of one mesh object.

    Returns:
        dict | None
    """
    if obj is None or obj.type != "MESH":
        return None

    if settings is None:
        settings = resolve_settings(SETTINGS)

    mesh = getattr(obj, "data", None)

    if mesh is None:
        return None

    # Synchronize Edit Mode changes back to the mesh datablock.
    if obj.mode == "EDIT":
        try:
            obj.update_from_editmode()
        except Exception:
            pass

    bm = bmesh.new()

    try:
        bm.from_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if not bm.verts:
            return None

        components = find_connected_components(bm)

        if len(components) <= 1:
            return None

        main_component_index = get_main_component_index(
            components
        )

        loose_components = []

        for component_index, component in enumerate(
            components
        ):
            if component_index == main_component_index:
                continue

            if should_ignore_component(
                component=component,
                settings=settings,
            ):
                continue

            loose_components.append(
                serialize_component(
                    component=component,
                    component_index=component_index,
                )
            )

        if not loose_components:
            return None

        main_component = components[
            main_component_index
        ]

        loose_vertex_indices = sorted({
            vertex_index
            for component in loose_components
            for vertex_index in component[
                "vertex_indices"
            ]
        })

        loose_edge_indices = sorted({
            edge_index
            for component in loose_components
            for edge_index in component[
                "edge_indices"
            ]
        })

        loose_face_indices = sorted({
            face_index
            for component in loose_components
            for face_index in component[
                "face_indices"
            ]
        })

        return {
            "object_type": obj.type,
            "mesh_name": mesh.name,
            "total_component_count": len(
                components
            ),
            "main_component_index": main_component_index,
            "main_component": serialize_component(
                component=main_component,
                component_index=main_component_index,
            ),
            "loose_component_count": len(
                loose_components
            ),
            "loose_vertex_count": len(
                loose_vertex_indices
            ),
            "loose_edge_count": len(
                loose_edge_indices
            ),
            "loose_face_count": len(
                loose_face_indices
            ),
            "loose_vertex_indices": loose_vertex_indices,
            "loose_edge_indices": loose_edge_indices,
            "loose_face_indices": loose_face_indices,
            "loose_components": loose_components,
        }

    finally:
        bm.free()


# -------------------------------------------------------------------------
# Component detection
# -------------------------------------------------------------------------

def find_connected_components(bm):
    """
    Finds geometry components connected through shared vertices and edges.

    A component can contain:

    - One isolated vertex
    - A collection of loose edges
    - One or more connected faces

    Returns:
        list[dict]
    """
    unvisited = set(bm.verts)
    components = []

    while unvisited:
        start_vertex = min(
            unvisited,
            key=lambda vertex: vertex.index,
        )

        stack = [start_vertex]
        component_vertices = set()
        component_edges = set()
        component_faces = set()

        while stack:
            vertex = stack.pop()

            if vertex not in unvisited:
                continue

            unvisited.remove(vertex)
            component_vertices.add(vertex)

            for edge in vertex.link_edges:
                component_edges.add(edge)

                for connected_vertex in edge.verts:
                    if connected_vertex in unvisited:
                        stack.append(connected_vertex)

            for face in vertex.link_faces:
                component_faces.add(face)

                for face_vertex in face.verts:
                    if face_vertex in unvisited:
                        stack.append(face_vertex)

        components.append({
            "vertices": component_vertices,
            "edges": component_edges,
            "faces": component_faces,
        })

    return components


def get_main_component_index(components):
    """
    Selects the main mesh body.

    Components with faces are preferred over edge-only components.
    Edge-only components are preferred over isolated vertices.

    Returns:
        int
    """
    if not components:
        return -1

    def component_score(index_and_component):
        index, component = index_and_component

        vertices = component["vertices"]
        edges = component["edges"]
        faces = component["faces"]

        first_vertex_index = min(
            (
                vertex.index
                for vertex in vertices
            ),
            default=0,
        )

        return (
            len(faces),
            len(edges),
            len(vertices),
            -first_vertex_index,
        )

    main_index, _component = max(
        enumerate(components),
        key=component_score,
    )

    return main_index


def should_ignore_component(
        component,
        settings,
    ):
    """
    Determines whether a disconnected component should be ignored.

    Returns:
        bool
    """
    vertex_count = len(
        component["vertices"]
    )

    edge_count = len(
        component["edges"]
    )

    face_count = len(
        component["faces"]
    )

    minimum_vertices = int(
        settings.get(
            "minimum_loose_vertices",
            1,
        )
    )

    if vertex_count < minimum_vertices:
        return True

    if (
        face_count == 0
        and edge_count == 0
        and settings.get(
            "ignore_vertex_only_components",
            False,
        )
    ):
        return True

    if (
        face_count == 0
        and edge_count > 0
        and settings.get(
            "ignore_edge_only_components",
            False,
        )
    ):
        return True

    if (
        face_count > 0
        and settings.get(
            "ignore_face_components",
            False,
        )
    ):
        return True

    return False


def serialize_component(
        component,
        component_index,
    ):
    """
    Converts a component into serializable QC result data.

    Returns:
        dict
    """
    vertices = component["vertices"]
    edges = component["edges"]
    faces = component["faces"]

    if faces:
        component_type = "FACE_ISLAND"
    elif edges:
        component_type = "LOOSE_EDGES"
    else:
        component_type = "ISOLATED_VERTICES"

    return {
        "component_index": component_index,
        "component_type": component_type,
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "face_count": len(faces),
        "vertex_indices": sorted(
            vertex.index
            for vertex in vertices
        ),
        "edge_indices": sorted(
            edge.index
            for edge in edges
        ),
        "face_indices": sorted(
            face.index
            for face in faces
        ),
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def remove_loose_geometry_components(
        result_data=None,
        settings=None,
    ):
    """
    Removes every currently detected secondary geometry component.

    The mesh is reanalyzed immediately before modification. This prevents
    the fix from relying entirely on stale component indices.

    Args:
        result_data (dict | None):
            Result returned by main().

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    if not isinstance(result_data, dict):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(failed_objects, dict):
        failed_objects = {}

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        if obj.type != "MESH":
            issues.append(
                'Object "{}" is no longer a mesh.'.format(
                    object_name
                )
            )
            continue

        fix_result = remove_object_loose_components(
            obj=obj,
            settings=settings,
        )

        if fix_result.get("error"):
            issues.append(
                'Could not fix object "{}": {}.'.format(
                    object_name,
                    fix_result["error"],
                )
            )
            continue

        if fix_result.get("removed_vertex_count", 0) == 0:
            continue

        fixed_objects[object_name] = fix_result

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


def remove_object_loose_components(
        obj,
        settings=None,
    ):
    """
    Removes disconnected components from one object.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    mesh = obj.data

    if obj.mode == "EDIT":
        try:
            obj.update_from_editmode()
        except Exception:
            pass

    bm = bmesh.new()

    try:
        bm.from_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        components = find_connected_components(bm)

        if len(components) <= 1:
            return {
                "removed_component_count": 0,
                "removed_vertex_count": 0,
                "removed_edge_count": 0,
                "removed_face_count": 0,
            }

        main_component_index = get_main_component_index(
            components
        )

        components_to_remove = []

        for component_index, component in enumerate(
            components
        ):
            if component_index == main_component_index:
                continue

            if should_ignore_component(
                component=component,
                settings=settings,
            ):
                continue

            components_to_remove.append(component)

        if not components_to_remove:
            return {
                "removed_component_count": 0,
                "removed_vertex_count": 0,
                "removed_edge_count": 0,
                "removed_face_count": 0,
            }

        vertices_to_remove = set()
        edges_to_remove = set()
        faces_to_remove = set()

        for component in components_to_remove:
            vertices_to_remove.update(
                component["vertices"]
            )
            edges_to_remove.update(
                component["edges"]
            )
            faces_to_remove.update(
                component["faces"]
            )

        removed_vertex_count = len(
            vertices_to_remove
        )

        removed_edge_count = len(
            edges_to_remove
        )

        removed_face_count = len(
            faces_to_remove
        )

        bmesh.ops.delete(
            bm,
            geom=list(vertices_to_remove),
            context="VERTS",
        )

        bm.to_mesh(mesh)
        mesh.update()

        return {
            "mesh_name": mesh.name,
            "removed_component_count": len(
                components_to_remove
            ),
            "removed_vertex_count": removed_vertex_count,
            "removed_edge_count": removed_edge_count,
            "removed_face_count": removed_face_count,
        }

    except Exception as error:
        return {
            "error": str(error),
        }

    finally:
        bm.free()
