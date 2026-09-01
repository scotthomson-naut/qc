"""
Get Scene Settings
"""
import bpy


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def ensure_object_mode():
    """
    Switches to Object Mode if something is actively in another mode.

    Note:
        bpy.ops.object.mode_set() requires an active object to even
        run - Blender can't be in Edit Mode (or any non-Object mode)
        with no active object, so if there's no active object at all,
        the scene is already guaranteed to be in the state this
        function exists to guarantee. Calling mode_set() anyway in
        that situation throws "Context missing active object" -
        this guard skips the call entirely in exactly the case where
        it isn't needed anyway, avoiding the crash rather than just
        working around it.
    """
    if bpy.context.active_object is not None:
        bpy.ops.object.mode_set(mode='OBJECT')


# -------------------------------------------------------------------------
# Components
# -------------------------------------------------------------------------

def get_scene_vertices_count():
    """
    Returns int: The Total number of Vertices in the current Scene.
    """
    # Put in Object mode
    ensure_object_mode()

    # Pulls the exact statistics string used in Blender's viewport/status bar
    stats = bpy.context.scene.statistics(bpy.context.view_layer)

    # Example string formatting: "Verts:1,200 | Edges:2,400 | Faces:1,200 | Tris:2,400"
    vertices = int(stats.split("Verts:")[1].split(" |")[0].replace(",", ""))

    return vertices


def get_scene_edges_count():
    """
    Returns int: The Total number of Edges in the current scene.
    """
    # Put in Object mode
    ensure_object_mode()

    # Pulls the exact statistics string used in Blender's viewport/status bar
    stats = bpy.context.scene.statistics(bpy.context.view_layer)

    # Example string formatting: "Verts:1,200 | Edges:2,400 | Faces:1,200 | Tris:2,400"
    edges = int(stats.split("Edges:")[1].split(" |")[0].replace(",", ""))

    return edges


def get_scene_faces_count():
    """
    Returns int: The Total number of Faces in the current scene.
    """
    # Put in Object mode
    ensure_object_mode()

    # Pulls the exact statistics string used in Blender's viewport/status bar
    stats = bpy.context.scene.statistics(bpy.context.view_layer)

    # Example string formatting: "Verts:1,200 | Edges:2,400 | Faces:1,200 | Tris:2,400"
    faces = int(stats.split("Faces:")[1].split(" |")[0].replace(",", ""))

    return faces



def get_scene_triangles_count(
        scene=None,
    ):
    """
    Returns the number of mesh triangles in the current scene.

    This intentionally does NOT parse:
        scene.statistics(...)

    Blender's statistics string is UI text and its fields vary with scene
    contents, mode, object types, Blender version, and localization. In scenes
    containing primarily Grease Pencil data, the string may not contain
    "Tris:" at all.

    Only Mesh objects contribute to this QC scene-triangle budget. Grease
    Pencil, Curve, Text, Light, Camera, Empty, etc. are ignored.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect. Defaults to bpy.context.scene.

    Returns:
        int:
            Total triangle count from Mesh datablocks used by eligible scene
            objects.
    """
    if scene is None:
        scene = bpy.context.scene

    total_triangles = 0

    # Mesh datablocks can be shared by many objects. The availability limit is
    # intended to estimate geometry processing cost, so count each unique Mesh
    # datablock once. Connected Geometry itself also analyzes shared meshes once.
    checked_meshes = set()

    for obj in scene.objects:

        if obj is None:
            continue

        if obj.type != "MESH":
            continue

        # Directly linked objects are outside the local editable QC scope.
        if obj.library is not None:
            continue

        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        if getattr(
            mesh,
            "library",
            None,
        ) is not None:
            continue

        mesh_pointer = mesh.as_pointer()

        if mesh_pointer in checked_meshes:
            continue

        checked_meshes.add(
            mesh_pointer
        )

        # Synchronize edits before reading topology where possible.
        if obj.mode == "EDIT":
            try:
                obj.update_from_editmode()
            except Exception:
                pass

        try:
            mesh.calc_loop_triangles()

            total_triangles += len(
                mesh.loop_triangles
            )

        except Exception:
            # An availability helper should never crash the entire QC run.
            # If one malformed mesh cannot be counted, skip that mesh and let
            # the dedicated geometry validation checks report its problem.
            continue

    return total_triangles


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