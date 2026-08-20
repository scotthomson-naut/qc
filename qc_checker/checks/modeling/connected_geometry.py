# Python imports
import time
import copy

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
WHY = (
    "Stray elements cause unexpected render glitches, break physics "
    "simulations, ruin rigging deformations, and make 3D printing "
    "or game export."
)


# Alpha "DEFAULT"
MAX_SCENE_TRIANGLES = 10000000


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

    "profile_slow_objects": {
        "type": "bool",
        "label": "Profile Slow Objects",
        "description": (
            "Print per-object Connected Geometry execution times to the "
            "system console so expensive meshes can be identified."
        ),
        "default": True,
    },

    "slow_object_seconds": {
        "type": "float",
        "label": "Slow Object Threshold",
        "description": (
            "Only objects taking at least this many seconds are listed "
            "in the profiling summary."
        ),
        "default": 1.0,
        "min": 0.0,
        "max": 3600.0,
        "precision": 2,
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
        profile_slow_objects=bool(
            settings.get(
                "profile_slow_objects",
                True,
            )
        ),
        slow_object_seconds=float(
            settings.get(
                "slow_object_seconds",
                1.0,
            )
        ),
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
        profile_slow_objects=True,
        slow_object_seconds=1.0,
    ):
    """
    Finds disconnected geometry components on mesh objects.

    Performance:
        Mesh connectivity is analyzed directly from Mesh vertices, edges,
        and polygons instead of copying every mesh into a BMesh.

        Objects sharing the same Mesh datablock are analyzed once and reuse
        the same result.

    Profiling:
        When enabled, execution time is recorded per unique Mesh datablock.
        Linked objects sharing that mesh do not duplicate the analysis cost.

    Returns:
        dict
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

    failed_objects = {}

    analysis_cache = {}
    timing_cache = {}
    mesh_representative = {}

    profile_start_time = (
        time.perf_counter()
    )

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue


        if obj.type != "MESH":
            continue

        mesh = getattr(
            obj,
            "data",
            None,
        )

        if mesh is None:
            continue

        mesh_representative.setdefault(
            mesh,
            obj.name,
        )

        if obj.mode == "EDIT":
            try:
                obj.update_from_editmode()
            except Exception:
                pass

        if mesh not in analysis_cache:

            object_start_time = (
                time.perf_counter()
            )

            try:
                analysis_cache[
                    mesh
                ] = (
                    analyze_mesh_components_fast(
                        mesh=mesh,
                        settings=settings,
                    )
                )

            finally:
                timing_cache[
                    mesh
                ] = (
                    time.perf_counter()
                    - object_start_time
                )

        cached_result = (
            analysis_cache[
                mesh
            ]
        )

        if cached_result is None:
            continue

        object_result = copy.deepcopy(
            cached_result
        )

        object_result[
            "object_type"
        ] = obj.type

        object_result[
            "mesh_name"
        ] = mesh.name

        failed_objects[
            obj.name
        ] = object_result

    if profile_slow_objects:

        total_elapsed = (
            time.perf_counter()
            - profile_start_time
        )

        print_connected_geometry_profile(
            timing_cache=timing_cache,
            mesh_representative=(
                mesh_representative
            ),
            total_elapsed=total_elapsed,
            slow_object_seconds=(
                slow_object_seconds
            ),
        )

    return failed_objects


def format_profile_time(
        seconds,
    ):
    """
    Formats profiling time as seconds or minutes/seconds.
    """
    seconds = float(
        seconds
    )

    if seconds < 60.0:
        return "{:.2f}s".format(
            seconds
        )

    minutes = int(
        seconds
        // 60.0
    )

    remaining_seconds = (
        seconds
        - (
            minutes
            * 60.0
        )
    )

    return "{}m {:.2f}s".format(
        minutes,
        remaining_seconds,
    )


def print_connected_geometry_profile(
        timing_cache,
        mesh_representative,
        total_elapsed,
        slow_object_seconds=1.0,
    ):
    """
    Prints a sorted performance summary for Connected Geometry.

    Timing is per unique Mesh datablock so linked duplicates do not
    artificially inflate the measured compute cost.
    """
    threshold = max(
        0.0,
        float(
            slow_object_seconds
        ),
    )

    records = []

    for mesh, seconds in (
        timing_cache.items()
    ):

        records.append({
            "object_name":
                mesh_representative.get(
                    mesh,
                    mesh.name,
                ),

            "mesh_name":
                mesh.name,

            "seconds":
                seconds,

            "vertices":
                len(
                    mesh.vertices
                ),

            "edges":
                len(
                    mesh.edges
                ),

            "faces":
                len(
                    mesh.polygons
                ),
        })

    records.sort(
        key=lambda item: (
            item[
                "seconds"
            ]
        ),
        reverse=True,
    )

    slow_records = [
        item
        for item in records
        if (
            item[
                "seconds"
            ]
            >= threshold
        )
    ]

    print("")
    print(
        "Connected Geometry Performance"
    )
    print(
        "-" * 104
    )

    if slow_records:

        print(
            "{:<34} {:>12} {:>14} {:>14} {:>14}".format(
                "Object",
                "Time",
                "Vertices",
                "Edges",
                "Faces",
            )
        )

        print(
            "-" * 104
        )

        for item in slow_records:

            print(
                "{:<34} {:>12} {:>14,} {:>14,} {:>14,}".format(
                    item[
                        "object_name"
                    ][:34],

                    format_profile_time(
                        item[
                            "seconds"
                        ]
                    ),

                    item[
                        "vertices"
                    ],

                    item[
                        "edges"
                    ],

                    item[
                        "faces"
                    ],
                )
            )

    else:
        print(
            (
                "No meshes exceeded the {:.2f} second "
                "slow-object threshold."
            ).format(
                threshold
            )
        )

    print(
        "-" * 104
    )

    print(
        "Unique meshes checked: {}".format(
            len(
                records
            )
        )
    )

    print(
        "Meshes above threshold: {}".format(
            len(
                slow_records
            )
        )
    )

    print(
        "Total Connected Geometry time: {}".format(
            format_profile_time(
                total_elapsed
            )
        )
    )

    if records:

        slowest = records[
            0
        ]

        print(
            "Slowest mesh: {} ({})".format(
                slowest[
                    "object_name"
                ],

                format_profile_time(
                    slowest[
                        "seconds"
                    ]
                ),
            )
        )

    print(
        "-" * 104
    )
    print("")


def analyze_object_components(
        obj,
        settings=None,
    ):
    """
    Compatibility wrapper for analyzing one mesh object.

    The optimized implementation reads Mesh data directly rather than
    constructing a temporary BMesh.
    """
    if (
        obj is None
        or obj.type != "MESH"
        or obj.library is not None
    ):
        return None

    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

    mesh = getattr(
        obj,
        "data",
        None,
    )

    if mesh is None:
        return None

    if obj.mode == "EDIT":
        try:
            obj.update_from_editmode()
        except Exception:
            pass

    result = analyze_mesh_components_fast(
        mesh=mesh,
        settings=settings,
    )

    if result is None:
        return None

    result = copy.deepcopy(
        result
    )

    result[
        "object_type"
    ] = obj.type

    result[
        "mesh_name"
    ] = mesh.name

    return result


def analyze_mesh_components_fast(
        mesh,
        settings=None,
    ):
    """
    Finds connected components directly from a Mesh datablock.

    Connectivity is defined through mesh edges:
        - Every edge unions its two endpoint vertices.
        - Isolated vertices remain one-vertex components.
        - Faces belong to the component containing their vertices.

    This avoids:
        bmesh.new()
        bm.from_mesh(mesh)
        Python sets containing BMVert/BMEdge/BMFace objects
        repeated link_edges/link_faces traversal

    Complexity is approximately O(V + E + F * average_face_size).

    Returns:
        dict | None
            Same serialized result structure used by the previous
            BMesh-based implementation.
    """
    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

    vertex_count = len(
        mesh.vertices
    )

    if vertex_count == 0:
        return None

    # A single vertex is necessarily one connected component.
    if (
        vertex_count == 1
        and len(mesh.edges) == 0
    ):
        return None

    # ---------------------------------------------------------
    # Disjoint-set / Union-Find
    # ---------------------------------------------------------

    parent = list(
        range(
            vertex_count
        )
    )

    rank = [
        0
    ] * vertex_count

    def find(
            vertex_index,
        ):
        root = vertex_index

        while parent[
            root
        ] != root:
            root = parent[
                root
            ]

        while parent[
            vertex_index
        ] != vertex_index:

            next_index = parent[
                vertex_index
            ]

            parent[
                vertex_index
            ] = root

            vertex_index = (
                next_index
            )

        return root

    def union(
            vertex_a,
            vertex_b,
        ):
        root_a = find(
            vertex_a
        )

        root_b = find(
            vertex_b
        )

        if root_a == root_b:
            return

        rank_a = rank[
            root_a
        ]

        rank_b = rank[
            root_b
        ]

        if rank_a < rank_b:
            parent[
                root_a
            ] = root_b

        elif rank_a > rank_b:
            parent[
                root_b
            ] = root_a

        else:
            parent[
                root_b
            ] = root_a

            rank[
                root_a
            ] += 1

    # ---------------------------------------------------------
    # Edges define vertex connectivity
    # ---------------------------------------------------------

    for edge in mesh.edges:

        vertices = edge.vertices

        union(
            vertices[0],
            vertices[1],
        )

    # Compress every root once.
    roots = [
        find(
            vertex_index
        )
        for vertex_index
        in range(
            vertex_count
        )
    ]

    # ---------------------------------------------------------
    # Build compact component records
    # ---------------------------------------------------------

    components_by_root = {}

    for vertex_index, root in enumerate(
        roots
    ):

        component = (
            components_by_root.get(
                root
            )
        )

        if component is None:

            component = {
                "vertex_indices": [],
                "edge_indices": [],
                "face_indices": [],
                "first_vertex_index":
                    vertex_index,
            }

            components_by_root[
                root
            ] = component

        component[
            "vertex_indices"
        ].append(
            vertex_index
        )

    # If there is only one root, the entire mesh is connected.
    if len(
        components_by_root
    ) <= 1:
        return None

    for edge in mesh.edges:

        root = roots[
            edge.vertices[
                0
            ]
        ]

        components_by_root[
            root
        ][
            "edge_indices"
        ].append(
            edge.index
        )

    for polygon in mesh.polygons:

        if not polygon.vertices:
            continue

        root = roots[
            polygon.vertices[
                0
            ]
        ]

        components_by_root[
            root
        ][
            "face_indices"
        ].append(
            polygon.index
        )

    # Match the previous deterministic component ordering:
    # lowest original vertex index first.
    components = sorted(
        components_by_root.values(),
        key=lambda component: (
            component[
                "first_vertex_index"
            ]
        ),
    )

    # ---------------------------------------------------------
    # Determine main component
    # ---------------------------------------------------------

    main_component_index = (
        get_main_serialized_component_index(
            components
        )
    )

    if main_component_index < 0:
        return None

    loose_components = []

    minimum_vertices = int(
        settings.get(
            "minimum_loose_vertices",
            1,
        )
    )

    ignore_vertex_only = bool(
        settings.get(
            "ignore_vertex_only_components",
            False,
        )
    )

    ignore_edge_only = bool(
        settings.get(
            "ignore_edge_only_components",
            False,
        )
    )

    ignore_faces = bool(
        settings.get(
            "ignore_face_components",
            False,
        )
    )

    for component_index, component in enumerate(
        components
    ):

        if (
            component_index
            == main_component_index
        ):
            continue

        vertex_indices = component[
            "vertex_indices"
        ]

        edge_indices = component[
            "edge_indices"
        ]

        face_indices = component[
            "face_indices"
        ]

        component_vertex_count = len(
            vertex_indices
        )

        component_edge_count = len(
            edge_indices
        )

        component_face_count = len(
            face_indices
        )

        if (
            component_vertex_count
            < minimum_vertices
        ):
            continue

        if (
            component_face_count == 0
            and component_edge_count == 0
            and ignore_vertex_only
        ):
            continue

        if (
            component_face_count == 0
            and component_edge_count > 0
            and ignore_edge_only
        ):
            continue

        if (
            component_face_count > 0
            and ignore_faces
        ):
            continue

        loose_components.append(
            serialize_index_component(
                component=component,
                component_index=(
                    component_index
                ),
            )
        )

    if not loose_components:
        return None

    main_component = components[
        main_component_index
    ]

    # Components are disjoint, so concatenation + sort is cheaper than
    # constructing sets of BMesh objects and then serializing them.
    loose_vertex_indices = []

    loose_edge_indices = []

    loose_face_indices = []

    for component in loose_components:

        loose_vertex_indices.extend(
            component[
                "vertex_indices"
            ]
        )

        loose_edge_indices.extend(
            component[
                "edge_indices"
            ]
        )

        loose_face_indices.extend(
            component[
                "face_indices"
            ]
        )

    loose_vertex_indices.sort()
    loose_edge_indices.sort()
    loose_face_indices.sort()

    return {
        "object_type":
            "MESH",

        "mesh_name":
            mesh.name,

        "total_component_count":
            len(
                components
            ),

        "main_component_index":
            main_component_index,

        "main_component":
            serialize_index_component(
                component=main_component,
                component_index=(
                    main_component_index
                ),
            ),

        "loose_component_count":
            len(
                loose_components
            ),

        "loose_vertex_count":
            len(
                loose_vertex_indices
            ),

        "loose_edge_count":
            len(
                loose_edge_indices
            ),

        "loose_face_count":
            len(
                loose_face_indices
            ),

        "loose_vertex_indices":
            loose_vertex_indices,

        "loose_edge_indices":
            loose_edge_indices,

        "loose_face_indices":
            loose_face_indices,

        "loose_components":
            loose_components,

        "selection": {
            "mode":
                "MIXED",

            "vertex_indices":
                loose_vertex_indices,

            "edge_indices":
                loose_edge_indices,

            "face_indices":
                loose_face_indices,
        },
    }


def get_main_serialized_component_index(
        components,
    ):
    """
    Selects the main mesh body from index-based component records.

    Priority matches the previous implementation:
        1. Highest face count
        2. Highest edge count
        3. Highest vertex count
        4. Lowest original vertex index
    """
    if not components:
        return -1

    def component_score(
            index_and_component,
        ):

        index, component = (
            index_and_component
        )

        return (
            len(
                component[
                    "face_indices"
                ]
            ),

            len(
                component[
                    "edge_indices"
                ]
            ),

            len(
                component[
                    "vertex_indices"
                ]
            ),

            -component[
                "first_vertex_index"
            ],
        )

    main_index, _component = max(
        enumerate(
            components
        ),
        key=component_score,
    )

    return main_index


def serialize_index_component(
        component,
        component_index,
    ):
    """
    Serializes a direct-Mesh component record into the same result
    structure used by the original BMesh implementation.
    """
    vertex_indices = component[
        "vertex_indices"
    ]

    edge_indices = component[
        "edge_indices"
    ]

    face_indices = component[
        "face_indices"
    ]

    if face_indices:
        component_type = (
            "FACE_ISLAND"
        )

    elif edge_indices:
        component_type = (
            "LOOSE_EDGES"
        )

    else:
        component_type = (
            "ISOLATED_VERTICES"
        )

    return {
        "component_index":
            component_index,

        "component_type":
            component_type,

        "vertex_count":
            len(
                vertex_indices
            ),

        "edge_count":
            len(
                edge_indices
            ),

        "face_count":
            len(
                face_indices
            ),

        "vertex_indices":
            list(
                vertex_indices
            ),

        "edge_indices":
            list(
                edge_indices
            ),

        "face_indices":
            list(
                face_indices
            ),
    }


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

    if obj.library is not None:
        return {
            "error": "Linked library object is read-only.",
        }

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
