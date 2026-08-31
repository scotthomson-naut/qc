"""
Get Scene Settings
"""
import bpy


# -------------------------------------------------------------------------
# Components
# -------------------------------------------------------------------------

def _get_available_scene_mesh_objects(
        context=None,
    ):
    """
    Returns mesh objects that are available in the active Scene/View Layer.

    This intentionally mirrors the Core QC eligibility rules that are
    relevant to scene-size calculations without importing core.object_filter,
    which would create an unnecessary dependency from utils back into core.

    Excludes:
        - Objects outside the active Scene.
        - Directly linked library objects.
        - Objects excluded from the active View Layer.
        - Objects hidden/disabled in the active View Layer.
    """
    if context is None:
        context = bpy.context

    scene = getattr(
        context,
        "scene",
        None,
    )

    view_layer = getattr(
        context,
        "view_layer",
        None,
    )

    if (
        scene is None
        or view_layer is None
    ):
        return []

    mesh_objects = []

    for obj in scene.objects:
        if obj.type != "MESH":
            continue

        if getattr(
            obj,
            "library",
            None,
        ) is not None:
            continue

        try:
            if view_layer.objects.get(
                obj.name
            ) is not obj:
                continue

        except Exception:
            continue

        try:
            if not obj.visible_get(
                view_layer=view_layer
            ):
                continue

        except (
            TypeError,
            RuntimeError,
        ):
            try:
                if not obj.visible_get():
                    continue

            except Exception:
                continue

        mesh_objects.append(
            obj
        )

    return mesh_objects


def get_scene_vertices_count(
        context=None,
    ):
    """
    Returns the total number of mesh vertices available to QC in the
    current Scene/View Layer.

    This uses Blender mesh data directly instead of parsing the human-readable
    ``Scene.statistics()`` string, whose contents can vary by scene, mode,
    Blender version and viewport state.
    """
    total = 0

    for obj in _get_available_scene_mesh_objects(
        context=context,
    ):
        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        total += len(
            mesh.vertices
        )

    return total


def get_scene_edges_count(
        context=None,
    ):
    """
    Returns the total number of mesh edges available to QC in the
    current Scene/View Layer.
    """
    total = 0

    for obj in _get_available_scene_mesh_objects(
        context=context,
    ):
        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        total += len(
            mesh.edges
        )

    return total


def get_scene_faces_count(
        context=None,
    ):
    """
    Returns the total number of mesh polygons available to QC in the
    current Scene/View Layer.
    """
    total = 0

    for obj in _get_available_scene_mesh_objects(
        context=context,
    ):
        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        total += len(
            mesh.polygons
        )

    return total


def get_scene_triangles_count(
        context=None,
    ):
    """
    Returns the total number of mesh triangles available to QC in the
    current Scene/View Layer.

    Blender's ``Scene.statistics()`` string is intended for display and does
    not guarantee that a ``Tris:`` field is always present. Parsing it caused
    availability checks such as Connected Geometry and UV Overlap to raise an
    IndexError in some scenes.

    Triangle counts are therefore calculated directly from each mesh's
    loop-triangle cache.
    """
    total = 0

    for obj in _get_available_scene_mesh_objects(
        context=context,
    ):
        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        try:
            mesh.calc_loop_triangles()

            total += len(
                mesh.loop_triangles
            )

        except (
            AttributeError,
            RuntimeError,
            TypeError,
        ):
            # A malformed/unavailable mesh should not prevent every QC check
            # from running. Fall back to a polygon-based triangle estimate.
            for polygon in getattr(
                mesh,
                "polygons",
                (),
            ):
                vertex_count = len(
                    polygon.vertices
                )

                if vertex_count >= 3:
                    total += (
                        vertex_count
                        - 2
                    )

    return total


# -------------------------------------------------------------------------
# Objects
# -------------------------------------------------------------------------

def get_scene_objects_count():
    """
    Returns int: Total number of objects in the current scene.
    """
    return len(bpy.context.scene.objects)


# -------------------------------------------------------------------------
# Renderer
# -------------------------------------------------------------------------

def get_scene_renderer_id():
    """
    Returns str: the identifier of the current active render engine.
    """
    return bpy.context.scene.render.engine


def get_scene_readable_renderer():
    """
    Returns str: Name of the current active render engine.
    """
    engine_mapping = {
        'BLENDER_EEVEE_NEXT': 'EEVEE',
        'BLENDER_EEVEE': 'EEVEE (Legacy)',
        'CYCLES': 'Cycles',
        'BLENDER_WORKBENCH': 'Workbench'
    }

    current_engine = get_scene_renderer_id()
    return engine_mapping.get(current_engine, current_engine)


# -------------------------------------------------------------------------
# Timeline
# -------------------------------------------------------------------------

def get_scene_timeline_range():
    """
    Returns tuple: (in_frame, out_frame) as integers in the timeline.
    """
    scene = bpy.context.scene
    in_frame = scene.frame_start
    out_frame = scene.frame_end
    return in_frame, out_frame


# -------------------------------------------------------------------------
# Collections
# -------------------------------------------------------------------------

def get_scene_root_collections():
    """
    Returns list: Of root-level collections in current scene.
    """
    scene = bpy.context.scene

    # The true root of the scene is the read-only scene master collection
    master_collection = scene.collection
    
    # Return the immediate top-level child collections visible in the Outliner
    return list(master_collection.children)


def get_scene_root_collection_count():
    """
    Returns int: Number of root-level collections in current scene.
    """
    return len(get_scene_root_collections())


# -------------------------------------------------------------------------
# Cameras
# -------------------------------------------------------------------------

def get_scene_camera_count():
    """
    Returns int: Total number of cameras in the current active scene.
    """
    return sum(1 for obj in bpy.context.scene.objects if obj.type == 'CAMERA')


# -------------------------------------------------------------------------
# Lights
# -------------------------------------------------------------------------

def get_scene_lights():
    """
    Returns list: of all light objects in the current scene.
    """
    # Filter the scene's objects by checking if their type is 'LIGHT'
    lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
    return lights


def get_scene_light_count():
    """
    Returns int: Number of lights in the current scene.
    """
    return len(get_scene_lights())

