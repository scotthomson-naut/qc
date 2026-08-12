"""
Get Scene Settings
"""
import bpy


# -------------------------------------------------------------------------
# Components
# -------------------------------------------------------------------------

def get_scene_vertices_count():
    """
    Returns int: The Total number of Vertices in the current Scene.
    """
    # Put in Object mode
    bpy.ops.object.mode_set(mode='OBJECT')

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
    bpy.ops.object.mode_set(mode='OBJECT')

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
    bpy.ops.object.mode_set(mode='OBJECT')

    # Pulls the exact statistics string used in Blender's viewport/status bar
    stats = bpy.context.scene.statistics(bpy.context.view_layer)

    # Example string formatting: "Verts:1,200 | Edges:2,400 | Faces:1,200 | Tris:2,400"
    faces = int(stats.split("Faces:")[1].split(" |")[0].replace(",", ""))

    return faces


def get_scene_triangles_count():
    """
    Returns int: The Total number of Triangles in the current scene.
    """
    # Put in Object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # Pulls the exact statistics string used in Blender's viewport/status bar
    stats = bpy.context.scene.statistics(bpy.context.view_layer)

    # Example string formatting: "Verts:1,200 | Edges:2,400 | Faces:1,200 | Tris:2,400"
    triangles = int(stats.split("Tris:")[1].split(" |")[0].replace(",", ""))

    return triangles


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

