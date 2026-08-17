# Standard library imports
import time

# Blender imports
import bpy
import bmesh


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "UV Overlap"
DESCRIPTION = (
    "Checks all UV maps for overlapping UV faces using Blender's native "
    "UV overlap operator."
)
WHY = (
    "Overlapping coordinates cause different parts of a 3D model to share "
    "the same exact space on a 2D texture map. While intentional overlap "
    "works well for symmetrical or repeating elements, unintended overlap "
    "can break texture painting, baking, and other texture workflows."
)


# Alpha safeguard.
MAX_SCENE_TRIANGLES = 10000000


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "uv_maps_to_check": {
        "type": "enum",
        "label": "UV Maps to Check",
        "description": (
            "Choose whether the overlap check scans only each mesh's active "
            "UV map or every UV map. Active UV Map is faster and recommended "
            "for routine QC; All UV Maps performs a more exhaustive check."
        ),
        "default": "ACTIVE",
        "items": [
            (
                "ACTIVE",
                "Active UV Map",
                "Check only the active UV map on each mesh.",
            ),
            (
                "ALL",
                "All UV Maps",
                "Check every UV map on each mesh.",
            ),
        ],
    },

    "profile_slow_objects": {
        "type": "bool",
        "label": "Profile Slow Objects",
        "description": (
            "Print per-object UV overlap execution times to the system "
            "console so expensive meshes can be identified during testing."
        ),
        "default": True,
    },

    "slow_object_seconds": {
        "type": "float",
        "label": "Slow Object Threshold",
        "description": (
            "Only objects taking at least this many seconds are listed "
            "in the slow-object console summary."
        ),
        "default": 1.0,
        "min": 0.0,
        "max": 3600.0,
        "precision": 2,
    },

    "batch_native_overlap": {
        "type": "bool",
        "label": "Batch Native Overlap",
        "description": (
            "Process multiple mesh objects in one Edit Mode session. "
            "Objects are temporarily offset in UV space so overlaps are "
            "tested within each object without creating cross-object "
            "false positives."
        ),
        "default": True,
    },

    "batch_size": {
        "type": "int",
        "label": "Batch Size",
        "description": (
            "Maximum number of mesh objects processed in one native "
            "UV-overlap batch. Smaller values use more mode switches; "
            "larger values use fewer mode switches."
        ),
        "default": 64,
        "min": 2,
        "max": 256,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks UV maps using Blender's native UV overlap detector.

    This intentionally favors speed over the previous Python implementation.

    Unlike the detailed Python solver, Blender's select_overlap operator
    returns the affected UV faces rather than every polygon-pair
    relationship. Therefore this version reports:

        - Which objects fail.
        - Which UV maps fail.
        - Which polygon indices fail.
        - How many unique faces overlap.

    It does not classify likely intentional versus mistaken overlap pairs.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    uv_maps_to_check = str(
        settings.get(
            "uv_maps_to_check",
            "ACTIVE",
        )
    ).upper()

    failed_objects = (
        get_objects_with_overlapping_uv_faces(
            uv_maps_to_check=uv_maps_to_check,
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
            batch_native_overlap=bool(
                settings.get(
                    "batch_native_overlap",
                    True,
                )
            ),
            batch_size=int(
                settings.get(
                    "batch_size",
                    64,
                )
            ),
        )
    )

    issues = []

    for object_name, object_data in (
        failed_objects.items()
    ):
        validation_error = object_data.get(
            "validation_error"
        )

        if validation_error:
            issues.append(
                (
                    "Could not validate UV overlap for object '{}': {}"
                ).format(
                    object_name,
                    validation_error,
                )
            )

            continue

        failed_uv_maps = object_data.get(
            "failed_uv_maps",
            {},
        )

        for uv_map_name, uv_map_data in (
            failed_uv_maps.items()
        ):
            issues.append(
                (
                    "Failed object: {} - UV map '{}' has "
                    "{} face(s) with overlapping UVs."
                ).format(
                    object_name,
                    uv_map_name,
                    uv_map_data[
                        "overlapping_face_count"
                    ],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "settings": settings,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_overlapping_uv_faces(
        objects=None,
        uv_maps_to_check="ACTIVE",
        profile_slow_objects=True,
        slow_object_seconds=1.0,
        batch_native_overlap=True,
        batch_size=64,
    ):
    """
    Finds overlapping UV faces using Blender's native
    bpy.ops.uv.select_overlap() implementation.

    Fast path:
        ACTIVE UV map + Batch Native Overlap enabled.

        Meshes are grouped by a View Layer that can display them and then
        processed in multi-object Edit Mode batches. Before Blender's native
        overlap operator runs, each object's UVs are translated into a
        separate temporary U-space region. Translation preserves overlap
        relationships inside an object while preventing UVs from different
        objects from being reported as overlapping each other.

        The temporary UV translations are always reversed in a finally block.

    Fallback:
        ALL UV maps, or batching disabled, uses the proven per-object native
        implementation.

    Notes:
        - Linked objects sharing the same Mesh datablock are evaluated once.
          Their result is copied to all linked scene objects using that mesh.
        - Batching is currently used for ACTIVE mode only. ALL mode remains
          per-object because each mesh can have a different number and set of
          UV layers.

    Returns:
        dict
    """
    context = bpy.context
    scene = context.scene

    if objects is None:
        objects = list(
            scene.objects
        )

    objects = [
        obj
        for obj in objects
        if (
            obj.library is None
            and obj.type == "MESH"
            and obj.data is not None
            and obj.data.polygons
            and obj.data.uv_layers
        )
    ]

    if not objects:
        return {}

    state = capture_context_state(
        context
    )

    failed_objects = {}
    object_timings = []

    profile_start_time = (
        time.perf_counter()
    )

    try:
        scene.tool_settings.use_uv_select_sync = False

        try:
            scene.tool_settings.uv_select_mode = "FACE"
        except Exception:
            pass

        if (
            context.object is not None
            and context.object.mode != "OBJECT"
        ):
            try:
                bpy.ops.object.mode_set(
                    mode="OBJECT"
                )
            except RuntimeError:
                pass

        use_batching = (
            batch_native_overlap
            and str(
                uv_maps_to_check
            ).upper()
            == "ACTIVE"
        )

        if use_batching:

            batch_results, batch_timings = (
                get_active_uv_overlap_batched(
                    context,
                    objects,
                    batch_size=max(
                        2,
                        int(
                            batch_size
                        ),
                    ),
                )
            )

            failed_objects.update(
                batch_results
            )

            object_timings.extend(
                batch_timings
            )

        else:

            # -----------------------------------------------------
            # Proven per-object fallback
            # -----------------------------------------------------

            for obj in objects:

                object_start_time = (
                    time.perf_counter()
                )

                object_result = None

                try:
                    object_result = (
                        check_object_uv_maps_native(
                            context,
                            obj,
                            uv_maps_to_check=(
                                uv_maps_to_check
                            ),
                        )
                    )

                finally:
                    object_elapsed = (
                        time.perf_counter()
                        - object_start_time
                    )

                    object_timings.append({
                        "name":
                            obj.name,

                        "seconds":
                            object_elapsed,

                        "polygon_count":
                            len(
                                obj.data.polygons
                            ),

                        "triangle_count":
                            get_object_triangle_count(
                                obj
                            ),

                        "uv_map_count":
                            len(
                                obj.data.uv_layers
                            ),
                    })

                if not object_result:
                    continue

                if object_result.get(
                    "skipped",
                    False,
                ):
                    print(
                        "UV Overlap skipped '{}': {}".format(
                            obj.name,
                            object_result.get(
                                "reason",
                                "Unknown reason",
                            ),
                        )
                    )

                    continue

                failed_objects[
                    obj.name
                ] = object_result

    finally:
        restore_context_state(
            context,
            state,
        )

        if profile_slow_objects:

            total_elapsed = (
                time.perf_counter()
                - profile_start_time
            )

            print_uv_overlap_profile(
                object_timings,
                total_elapsed=total_elapsed,
                slow_object_seconds=(
                    slow_object_seconds
                ),
            )

    return failed_objects


def get_active_uv_overlap_batched(
        context,
        objects,
        batch_size=64,
    ):
    """
    Processes ACTIVE UV maps in multi-object Edit Mode batches.

    Linked objects that share one Mesh datablock are represented by a single
    object during overlap detection. The result is then copied to the linked
    objects.

    Returns:
        tuple:
            (
                failed_objects,
                object_timings,
            )
    """
    scene = context.scene

    # ---------------------------------------------------------
    # Group scene objects by Mesh datablock.
    # ---------------------------------------------------------

    mesh_groups = {}

    for obj in objects:

        mesh_groups.setdefault(
            obj.data,
            [],
        ).append(
            obj
        )

    representatives = [
        group[
            0
        ]
        for group in mesh_groups.values()
    ]

    # ---------------------------------------------------------
    # Assign each representative to a View Layer.
    #
    # Prefer the current View Layer when possible.
    # ---------------------------------------------------------

    view_layer_groups = {}

    for obj in representatives:

        view_layer = None

        if object_in_view_layer(
            obj,
            context.view_layer,
        ):
            view_layer = (
                context.view_layer
            )

        else:
            view_layer = (
                find_view_layer_for_object(
                    scene,
                    obj,
                )
            )

        if view_layer is None:
            print(
                (
                    "UV Overlap skipped '{}': object is not "
                    "available in any View Layer."
                ).format(
                    obj.name
                )
            )

            continue

        view_layer_groups.setdefault(
            view_layer.name,
            [],
        ).append(
            obj
        )

    failed_by_mesh = {}
    timing_by_mesh = {}

    # ---------------------------------------------------------
    # Process each View Layer and batch.
    # ---------------------------------------------------------

    for (
        view_layer_name,
        group_objects,
    ) in view_layer_groups.items():

        if context.window is None:
            break

        target_view_layer = (
            scene.view_layers.get(
                view_layer_name
            )
        )

        if target_view_layer is None:
            continue

        context.window.view_layer = (
            target_view_layer
        )

        context.view_layer.update()

        for batch_start in range(
            0,
            len(
                group_objects
            ),
            batch_size,
        ):

            batch = group_objects[
                batch_start:
                batch_start
                + batch_size
            ]

            (
                batch_failed,
                batch_times,
                fallback_objects,
            ) = run_active_uv_overlap_batch(
                context,
                batch,
            )

            failed_by_mesh.update(
                batch_failed
            )

            timing_by_mesh.update(
                batch_times
            )

            # -------------------------------------------------
            # Single-object fallback
            # -------------------------------------------------

            for fallback_obj in (
                fallback_objects
            ):
                fallback_start = (
                    time.perf_counter()
                )

                fallback_result = None

                try:
                    fallback_result = (
                        check_object_uv_maps_native(
                            context,
                            fallback_obj,
                            uv_maps_to_check="ACTIVE",
                        )
                    )

                except Exception as error:
                    fallback_result = {
                        "validation_error":
                            str(
                                error
                            ),
                    }

                finally:
                    timing_by_mesh[
                        fallback_obj.data
                    ] = (
                        time.perf_counter()
                        - fallback_start
                    )

                # The single-object path returning None means the
                # object was successfully validated and passed.
                if not fallback_result:
                    continue

                # If the fallback itself cannot access the object,
                # surface that as a validation failure instead of
                # silently skipping it.
                if fallback_result.get(
                    "skipped",
                    False,
                ):
                    failed_by_mesh[
                        fallback_obj.data
                    ] = {
                        "validation_error":
                            fallback_result.get(
                                "reason",
                                (
                                    "Object could not be checked "
                                    "with the native UV operator."
                                ),
                            ),
                    }

                    continue

                validation_error = (
                    fallback_result.get(
                        "validation_error"
                    )
                )

                if validation_error:
                    failed_by_mesh[
                        fallback_obj.data
                    ] = {
                        "validation_error":
                            validation_error,
                    }

                    continue

                # Convert the normal single-object result into the
                # compact per-Mesh structure used by batched results.
                failed_uv_maps = (
                    fallback_result.get(
                        "failed_uv_maps",
                        {},
                    )
                )

                if not failed_uv_maps:
                    continue

                uv_map_name = next(
                    iter(
                        failed_uv_maps
                    )
                )

                uv_map_data = (
                    failed_uv_maps[
                        uv_map_name
                    ]
                )

                failed_by_mesh[
                    fallback_obj.data
                ] = {
                    "uv_map_name":
                        uv_map_name,

                    "polygon_indices":
                        list(
                            uv_map_data.get(
                                "polygon_indices",
                                [],
                            )
                        ),

                    "fallback":
                        True,
                }

    # ---------------------------------------------------------
    # Expand Mesh-datablock result back to every linked object.
    # ---------------------------------------------------------

    failed_objects = {}
    object_timings = []

    for mesh, linked_objects in (
        mesh_groups.items()
    ):

        mesh_result = (
            failed_by_mesh.get(
                mesh
            )
        )

        mesh_seconds = (
            timing_by_mesh.get(
                mesh,
                0.0,
            )
        )

        # Attribute shared-mesh execution time to the representative only.
        # Linked instances receive zero additional native-compute time.
        for linked_index, obj in enumerate(
            linked_objects
        ):

            object_timings.append({
                "name":
                    obj.name,

                "seconds":
                    (
                        mesh_seconds
                        if linked_index == 0
                        else 0.0
                    ),

                "polygon_count":
                    len(
                        mesh.polygons
                    ),

                "triangle_count":
                    get_object_triangle_count(
                        obj
                    ),

                "uv_map_count":
                    len(
                        mesh.uv_layers
                    ),
            })

            if not mesh_result:
                continue

            validation_error = (
                mesh_result.get(
                    "validation_error"
                )
            )

            if validation_error:
                failed_objects[
                    obj.name
                ] = {
                    "detection_engine":
                        "BLENDER_NATIVE_FALLBACK_ERROR",

                    "uv_maps_to_check":
                        "ACTIVE",

                    "validation_error":
                        validation_error,

                    "failed_uv_maps":
                        {},
                }

                continue

            # Result contains only primitive Python containers, so creating
            # fresh nested structures prevents one object's Details data from
            # accidentally being mutated through another linked instance.
            uv_map_name = mesh_result[
                "uv_map_name"
            ]

            polygon_indices = list(
                mesh_result[
                    "polygon_indices"
                ]
            )

            detection_engine = (
                "BLENDER_NATIVE_SINGLE_FALLBACK"
                if mesh_result.get(
                    "fallback",
                    False,
                )
                else "BLENDER_NATIVE_BATCHED"
            )

            failed_objects[
                obj.name
            ] = {
                "detection_engine":
                    detection_engine,

                "uv_maps_to_check":
                    "ACTIVE",

                "failed_uv_maps": {
                    uv_map_name: {
                        "detection_engine":
                            detection_engine,

                        "uv_maps_to_check":
                            "ACTIVE",

                        "overlapping_face_count":
                            len(
                                polygon_indices
                            ),

                        "polygon_indices":
                            list(
                                polygon_indices
                            ),
                    }
                },

                "failed_uv_map_count":
                    1,

                "overlapping_face_count":
                    len(
                        polygon_indices
                    ),

                "polygon_indices":
                    list(
                        polygon_indices
                    ),

                "selection": {
                    "mode":
                        "FACE",

                    "indices":
                        list(
                            polygon_indices
                        ),
                },
            }

    return (
        failed_objects,
        object_timings,
    )


def run_active_uv_overlap_batch(
        context,
        objects,
    ):
    """
    Runs one native overlap operation for a group of mesh objects.

    Each object's active UV map is temporarily translated to its own
    non-overlapping U range. Internal overlap within each object is unchanged.

    Returns:
        tuple:
            (
                failed_by_mesh,
                timing_by_mesh,
                fallback_objects,
            )

        fallback_objects contains objects Blender did not include in the
        multi-object Edit Mode session. The caller must run those objects
        through the proven single-object native path.
    """
    objects = [
        obj
        for obj in objects
        if (
            obj is not None
            and obj.library is None
        )
    ]

    if not objects:
        return (
            {},
            {},
            [],
        )

    component_states = {}
    uv_offsets = {}
    uv_layers = {}
    object_start_times = {}

    failed_by_mesh = {}
    timing_by_mesh = {}
    fallback_objects = []

    entered_edit_mode = False
    edit_meshes = set()

    try:
        # ---------------------------------------------------------
        # Select batch objects in Object Mode.
        # ---------------------------------------------------------

        if (
            context.object is not None
            and context.object.mode != "OBJECT"
        ):
            bpy.ops.object.mode_set(
                mode="OBJECT"
            )

        for selected_obj in list(
            context.selected_objects
        ):
            try:
                selected_obj.select_set(
                    False
                )
            except RuntimeError:
                pass

        selectable_objects = []

        for obj in objects:

            if not object_in_view_layer(
                obj,
                context.view_layer,
            ):
                continue

            component_states[
                obj.data
            ] = (
                capture_mesh_component_selection(
                    obj.data
                )
            )

            obj.hide_select = False

            try:
                obj.hide_set(
                    False
                )
            except RuntimeError:
                pass

            obj.select_set(
                True
            )

            selectable_objects.append(
                obj
            )

        if not selectable_objects:
            return (
                {},
                {},
                list(
                    objects
                ),
            )

        context.view_layer.objects.active = (
            selectable_objects[
                0
            ]
        )

        for obj in selectable_objects:
            object_start_times[
                obj.data
            ] = time.perf_counter()

        bpy.ops.object.mode_set(
            mode="EDIT"
        )

        entered_edit_mode = True

        # ---------------------------------------------------------
        # Determine which meshes actually entered multi-object
        # Edit Mode.
        #
        # Blender may leave some selected objects out of the edit
        # session depending on visibility, editability, linked data,
        # or context. bmesh.from_edit_mesh() must only be called on
        # meshes that are truly in Edit Mode.
        # ---------------------------------------------------------

        edit_objects = list(
            getattr(
                context,
                "objects_in_mode_unique_data",
                [],
            )
        )

        edit_objects = [
            obj
            for obj in edit_objects
            if (
                obj.type == "MESH"
                and obj.data is not None
            )
        ]

        if not edit_objects:
            return (
                {},
                {},
                list(
                    selectable_objects
                ),
            )

        edit_meshes = {
            obj.data
            for obj in edit_objects
        }

        # Anything Blender leaves out of multi-object Edit Mode is
        # explicitly sent through the proven single-object fallback.
        for obj in selectable_objects:

            if obj.data in edit_meshes:
                continue

            fallback_objects.append(
                obj
            )

            print(
                (
                    "UV Overlap batch fallback '{}': mesh did not "
                    "enter multi-object Edit Mode; checking individually."
                ).format(
                    obj.name
                )
            )

        selectable_objects = [
            obj
            for obj in selectable_objects
            if obj.data in edit_meshes
        ]

        # ---------------------------------------------------------
        # Gather active UV layers and calculate a safe packing stride.
        # ---------------------------------------------------------

        bounds_by_mesh = {}
        maximum_width = 0.0

        for obj in selectable_objects:

            mesh = obj.data

            uv_layer = (
                mesh.uv_layers.active
            )

            if uv_layer is None:
                continue

            bm = bmesh.from_edit_mesh(
                mesh
            )

            bm.faces.ensure_lookup_table()

            bm_uv_layer = (
                bm.loops.layers.uv.get(
                    uv_layer.name
                )
            )

            if bm_uv_layer is None:
                continue

            uv_layers[
                mesh
            ] = (
                bm_uv_layer
            )

            # All source faces must be available to the UV editor.
            for face in bm.faces:
                face.select = True

            clear_bmesh_uv_selection(
                bm,
                bm_uv_layer,
            )

            min_u = None
            max_u = None

            for face in bm.faces:
                for loop in face.loops:

                    uv = loop[
                        bm_uv_layer
                    ].uv

                    u = uv.x

                    if (
                        min_u is None
                        or u < min_u
                    ):
                        min_u = u

                    if (
                        max_u is None
                        or u > max_u
                    ):
                        max_u = u

            if min_u is None:
                continue

            width = max(
                0.0,
                max_u
                - min_u,
            )

            bounds_by_mesh[
                mesh
            ] = (
                min_u,
                max_u,
            )

            maximum_width = max(
                maximum_width,
                width,
            )

        # Keep a generous gap between every object's temporary UV range.
        stride = max(
            maximum_width
            + 10.0,
            20.0,
        )

        # ---------------------------------------------------------
        # Temporarily translate each object's UV map.
        # ---------------------------------------------------------

        for object_index, obj in enumerate(
            selectable_objects
        ):

            mesh = obj.data

            bm_uv_layer = (
                uv_layers.get(
                    mesh
                )
            )

            bounds = (
                bounds_by_mesh.get(
                    mesh
                )
            )

            if (
                bm_uv_layer is None
                or bounds is None
            ):
                continue

            min_u = bounds[
                0
            ]

            target_min_u = (
                object_index
                * stride
            )

            offset = (
                target_min_u
                - min_u
            )

            uv_offsets[
                mesh
            ] = offset

            if offset == 0.0:
                continue

            bm = bmesh.from_edit_mesh(
                mesh
            )

            for face in bm.faces:
                for loop in face.loops:
                    loop[
                        bm_uv_layer
                    ].uv.x += offset

            bmesh.update_edit_mesh(
                mesh,
                loop_triangles=False,
                destructive=False,
            )

        # ---------------------------------------------------------
        # One native overlap call for the whole batch.
        # ---------------------------------------------------------

        success, error_message = (
            run_native_select_overlap(
                context
            )
        )

        if not success:
            raise RuntimeError(
                (
                    "Could not run Blender native batched UV overlap: {}"
                ).format(
                    error_message
                )
            )

        # ---------------------------------------------------------
        # Read result per Mesh datablock.
        # ---------------------------------------------------------

        for obj in selectable_objects:

            mesh = obj.data

            bm_uv_layer = (
                uv_layers.get(
                    mesh
                )
            )

            if bm_uv_layer is None:
                continue

            bm = bmesh.from_edit_mesh(
                mesh
            )

            bm.faces.ensure_lookup_table()

            polygon_indices = (
                get_selected_uv_polygon_indices(
                    bm,
                    bm_uv_layer,
                )
            )

            if polygon_indices:

                uv_layer = (
                    mesh.uv_layers.active
                )

                if uv_layer is not None:

                    failed_by_mesh[
                        mesh
                    ] = {
                        "uv_map_name":
                            uv_layer.name,

                        "polygon_indices":
                            polygon_indices,
                    }

            start_time = (
                object_start_times.get(
                    mesh
                )
            )

            if start_time is not None:

                timing_by_mesh[
                    mesh
                ] = (
                    time.perf_counter()
                    - start_time
                )

    finally:
        # ---------------------------------------------------------
        # Undo temporary UV translations before leaving Edit Mode.
        # ---------------------------------------------------------

        if entered_edit_mode:

            for obj in objects:

                mesh = obj.data

                offset = (
                    uv_offsets.get(
                        mesh
                    )
                )

                bm_uv_layer = (
                    uv_layers.get(
                        mesh
                    )
                )

                if (
                    mesh not in edit_meshes
                    or offset is None
                    or bm_uv_layer is None
                    or offset == 0.0
                ):
                    continue

                try:
                    bm = bmesh.from_edit_mesh(
                        mesh
                    )

                    for face in bm.faces:
                        for loop in face.loops:
                            loop[
                                bm_uv_layer
                            ].uv.x -= offset

                    bmesh.update_edit_mesh(
                        mesh,
                        loop_triangles=False,
                        destructive=False,
                    )

                except Exception:
                    # Continue restoration for all other meshes.
                    pass

            if (
                context.object is not None
                and context.object.mode != "OBJECT"
            ):
                try:
                    bpy.ops.object.mode_set(
                        mode="OBJECT"
                    )
                except RuntimeError:
                    pass

        # ---------------------------------------------------------
        # Restore component selection for each modified Mesh.
        # ---------------------------------------------------------

        for mesh, component_state in (
            component_states.items()
        ):

            try:
                restore_mesh_component_selection(
                    mesh,
                    component_state,
                )
            except Exception:
                pass

    return (
        failed_by_mesh,
        timing_by_mesh,
        fallback_objects,
    )


# -------------------------------------------------------------------------
# Performance profiling helpers
# -------------------------------------------------------------------------

def get_object_triangle_count(
        obj,
    ):
    """
    Returns the object's current loop-triangle count.

    Used only for profiling output.
    """
    mesh = getattr(
        obj,
        "data",
        None,
    )

    if mesh is None:
        return 0

    try:
        mesh.calc_loop_triangles()

        return len(
            mesh.loop_triangles
        )

    except Exception:
        return 0


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


def print_uv_overlap_profile(
        object_timings,
        total_elapsed,
        slow_object_seconds=1.0,
    ):
    """
    Prints a sorted performance summary for slow UV-overlap objects.
    """
    threshold = max(
        0.0,
        float(
            slow_object_seconds
        ),
    )

    sorted_timings = sorted(
        object_timings,
        key=lambda item: (
            item[
                "seconds"
            ]
        ),
        reverse=True,
    )

    slow_timings = [
        item
        for item in sorted_timings
        if (
            item[
                "seconds"
            ]
            >= threshold
        )
    ]

    print("")
    print(
        "UV Overlap Performance"
    )
    print(
        "-" * 96
    )

    if slow_timings:

        print(
            "{:<40} {:>12} {:>12} {:>12} {:>8}".format(
                "Object",
                "Time",
                "Polygons",
                "Triangles",
                "UV Maps",
            )
        )

        print(
            "-" * 96
        )

        for item in slow_timings:

            print(
                "{:<40} {:>12} {:>12,} {:>12,} {:>8}".format(
                    item[
                        "name"
                    ][:40],

                    format_profile_time(
                        item[
                            "seconds"
                        ]
                    ),

                    item[
                        "polygon_count"
                    ],

                    item[
                        "triangle_count"
                    ],

                    item[
                        "uv_map_count"
                    ],
                )
            )

    else:
        print(
            (
                "No objects exceeded the {:.2f} second "
                "slow-object threshold."
            ).format(
                threshold
            )
        )

    print(
        "-" * 96
    )

    print(
        "Objects checked: {}".format(
            len(
                object_timings
            )
        )
    )

    print(
        "Objects above threshold: {}".format(
            len(
                slow_timings
            )
        )
    )

    print(
        "Total UV overlap time: {}".format(
            format_profile_time(
                total_elapsed
            )
        )
    )

    if sorted_timings:

        slowest = (
            sorted_timings[
                0
            ]
        )

        print(
            "Slowest object: {} ({})".format(
                slowest[
                    "name"
                ],

                format_profile_time(
                    slowest[
                        "seconds"
                    ]
                ),
            )
        )

    print(
        "-" * 96
    )
    print("")


# -------------------------------------------------------------------------
# Native overlap execution
# -------------------------------------------------------------------------

def check_object_uv_maps_native(
        context,
        obj,
        uv_maps_to_check="ACTIVE",
    ):
    """
    Checks every UV map on one mesh object using Blender's native
    select-overlap operator.

    UV Select Sync stays OFF. The overlap result is read from Blender's
    version-appropriate BMesh UV-selection API.

    Returns:
        dict | None
    """
    mesh = obj.data

    original_uv_index = (
        mesh.uv_layers.active_index
    )

    failed_uv_maps = {}
    all_overlapping_polygons = set()

    component_state = None

    try:
        # ---------------------------------------------------------
        # Ensure object is available in the active View Layer
        # ---------------------------------------------------------

        success, message = (
            ensure_object_view_layer(
                context,
                obj,
            )
        )

        if not success:
            return {
                "skipped": True,
                "reason": message,
            }

        # ---------------------------------------------------------
        # Activate object
        # ---------------------------------------------------------

        make_only_object_active(
            context,
            obj,
        )

        # Save selection only for THIS mesh, rather than for every mesh
        # in the whole scene.
        component_state = capture_mesh_component_selection(
            mesh
        )

        bpy.ops.object.mode_set(
            mode="EDIT"
        )

        bm = bmesh.from_edit_mesh(
            mesh
        )

        bm.faces.ensure_lookup_table()

        # Native UV overlap only operates on UVs that are available to the
        # UV editor. Select all source faces while keeping UV selection
        # independent because UV Select Sync is disabled.
        for face in bm.faces:
            face.select = True

        bmesh.update_edit_mesh(
            mesh,
            loop_triangles=False,
            destructive=False,
        )

        uv_indices = get_uv_indices_to_check(
            mesh,
            uv_maps_to_check=(
                uv_maps_to_check
            ),
        )

        for uv_index in uv_indices:

            uv_layer = mesh.uv_layers[
                uv_index
            ]

            mesh.uv_layers.active_index = (
                uv_index
            )

            # -----------------------------------------------------
            # Clear UV selection only
            #
            # Blender 5.0+ moved UV selection state directly onto
            # BMLoop / BMFace:
            #
            #     loop.uv_select_vert
            #     loop.uv_select_edge
            #     face.uv_select
            #
            # Blender 4.x uses the older BMLoopUV wrapper:
            #
            #     loop[bm_uv_layer].select
            #     loop[bm_uv_layer].select_edge
            #
            # Keep both paths so the add-on can continue supporting
            # Blender 4.3+.
            # -----------------------------------------------------

            bm = bmesh.from_edit_mesh(
                mesh
            )

            bm.faces.ensure_lookup_table()

            bm_uv_layer = (
                bm.loops.layers.uv.get(
                    uv_layer.name
                )
            )

            if bm_uv_layer is None:
                continue

            clear_bmesh_uv_selection(
                bm,
                bm_uv_layer,
            )

            bmesh.update_edit_mesh(
                mesh,
                loop_triangles=False,
                destructive=False,
            )

            # -----------------------------------------------------
            # Native overlap selection
            # -----------------------------------------------------

            success, error_message = (
                run_native_select_overlap(
                    context
                )
            )

            if not success:
                raise RuntimeError(
                    (
                        "Could not run Blender native UV overlap "
                        "selection on '{}' / '{}': {}"
                    ).format(
                        obj.name,
                        uv_layer.name,
                        error_message,
                    )
                )

            # -----------------------------------------------------
            # Read native UV overlap selection from BMesh
            # -----------------------------------------------------

            bm = bmesh.from_edit_mesh(
                mesh
            )

            bm.faces.ensure_lookup_table()

            bm_uv_layer = (
                bm.loops.layers.uv.get(
                    uv_layer.name
                )
            )

            if bm_uv_layer is None:
                continue

            polygon_indices = (
                get_selected_uv_polygon_indices(
                    bm,
                    bm_uv_layer,
                )
            )

            if not polygon_indices:
                continue

            failed_uv_maps[
                uv_layer.name
            ] = {
                "detection_engine":
                    "BLENDER_NATIVE_UV_LOOPS",

                "uv_maps_to_check":
                    uv_maps_to_check,

                "overlapping_face_count":
                    len(
                        polygon_indices
                    ),

                "polygon_indices":
                    polygon_indices,
            }

            all_overlapping_polygons.update(
                polygon_indices
            )

        if not failed_uv_maps:
            return None

        combined_polygon_indices = sorted(
            all_overlapping_polygons
        )

        return {
            "detection_engine":
                "BLENDER_NATIVE_UV_LOOPS",

            "uv_maps_to_check":
                uv_maps_to_check,

            "failed_uv_maps":
                failed_uv_maps,

            "failed_uv_map_count":
                len(
                    failed_uv_maps
                ),

            "overlapping_face_count":
                len(
                    combined_polygon_indices
                ),

            "polygon_indices":
                combined_polygon_indices,

            "selection": {
                "mode": "FACE",
                "indices":
                    combined_polygon_indices,
            },
        }

    finally:
        if (
            context.object is not None
            and context.object.mode != "OBJECT"
        ):
            try:
                bpy.ops.object.mode_set(
                    mode="OBJECT"
                )
            except RuntimeError:
                pass

        # Restore this mesh's original component selection.
        if component_state is not None:
            restore_mesh_component_selection(
                mesh,
                component_state,
            )

        if (
            mesh.uv_layers
            and original_uv_index
            < len(mesh.uv_layers)
        ):
            mesh.uv_layers.active_index = (
                original_uv_index
            )


def get_uv_indices_to_check(
        mesh,
        uv_maps_to_check="ACTIVE",
    ):
    """
    Returns the UV-layer indices that should be checked for one mesh.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

        uv_maps_to_check (str):
            "ACTIVE" checks only mesh.uv_layers.active.
            "ALL" checks every UV layer.

    Returns:
        list[int]
    """
    if not mesh.uv_layers:
        return []

    mode = str(
        uv_maps_to_check
    ).upper()

    if mode == "ALL":
        return list(
            range(
                len(
                    mesh.uv_layers
                )
            )
        )

    active_index = (
        mesh.uv_layers.active_index
    )

    if (
        active_index < 0
        or active_index
        >= len(mesh.uv_layers)
    ):
        return []

    return [
        active_index
    ]


def clear_bmesh_uv_selection(
        bm,
        bm_uv_layer,
    ):
    """
    Clears UV selection in the Edit Mode BMesh.

    Blender 5.0+:
        UV selection moved from BMLoopUV onto BMLoop/BMFace.

    Blender 4.x:
        UV selection is stored on the legacy BMLoopUV wrapper.

    Args:
        bm (bmesh.types.BMesh):
            Edit-mode BMesh.

        bm_uv_layer:
            Active BMesh UV layer.
    """
    blender_5_or_newer = (
        bpy.app.version >= (
            5,
            0,
            0,
        )
    )

    if blender_5_or_newer:

        for face in bm.faces:

            # Face-level UV selection.
            try:
                face.uv_select = False
            except AttributeError:
                pass

            for loop in face.loops:

                # Blender 5.0+ UV vertex selection.
                try:
                    loop.uv_select_vert = False
                except AttributeError:
                    pass

                # Blender 5.0+ UV edge selection.
                try:
                    loop.uv_select_edge = False
                except AttributeError:
                    pass

        # Tell BMesh the UV selection state is valid.
        try:
            bm.uv_select_sync_valid = True
        except AttributeError:
            pass

        return

    # ---------------------------------------------------------
    # Blender 4.x compatibility
    # ---------------------------------------------------------

    for face in bm.faces:

        for loop in face.loops:

            uv_loop = loop[
                bm_uv_layer
            ]

            try:
                uv_loop.select = False
            except AttributeError:
                pass

            try:
                uv_loop.select_edge = False
            except AttributeError:
                pass


def get_selected_uv_polygon_indices(
        bm,
        bm_uv_layer,
    ):
    """
    Returns source polygon indices selected by Blender's native
    UV overlap operator.

    Supports both Blender 4.x and Blender 5.0+ UV-selection APIs.

    Returns:
        list[int]
    """
    blender_5_or_newer = (
        bpy.app.version >= (
            5,
            0,
            0,
        )
    )

    polygon_indices = []

    if blender_5_or_newer:

        for face in bm.faces:

            selected = False

            # In UV FACE mode Blender 5.x exposes face-level UV
            # selection directly.
            try:
                selected = bool(
                    face.uv_select
                )
            except AttributeError:
                selected = False

            # Defensive fallback: some selection-mode/context
            # combinations may expose only selected UV corners.
            if not selected:

                for loop in face.loops:

                    try:
                        if loop.uv_select_vert:
                            selected = True
                            break
                    except AttributeError:
                        pass

            if selected:
                polygon_indices.append(
                    face.index
                )

        polygon_indices.sort()

        return polygon_indices

    # ---------------------------------------------------------
    # Blender 4.x compatibility
    # ---------------------------------------------------------

    for face in bm.faces:

        selected = False

        for loop in face.loops:

            uv_loop = loop[
                bm_uv_layer
            ]

            try:
                if uv_loop.select:
                    selected = True
                    break
            except AttributeError:
                pass

        if selected:
            polygon_indices.append(
                face.index
            )

    polygon_indices.sort()

    return polygon_indices


def run_native_select_overlap(
        context,
    ):
    """
    Runs bpy.ops.uv.select_overlap() with a suitable UI context.

    The operator normally belongs to the UV/Image Editor. If an Image
    Editor already exists it is used. Otherwise the current area is
    temporarily changed to IMAGE_EDITOR and restored immediately.

    Returns:
        tuple[bool, str]
    """
    # ---------------------------------------------------------
    # First try directly.
    #
    # Some Blender versions/context combinations allow the operator
    # to run without an Image Editor override.
    # ---------------------------------------------------------

    try:
        if bpy.ops.uv.select_overlap.poll():
            result = bpy.ops.uv.select_overlap(
                extend=False
            )

            if "FINISHED" in result:
                return (
                    True,
                    "",
                )
    except RuntimeError:
        pass

    # ---------------------------------------------------------
    # Existing Image Editor
    # ---------------------------------------------------------

    screen = context.screen

    if screen is not None:

        for area in screen.areas:

            if area.type != "IMAGE_EDITOR":
                continue

            region = get_window_region(
                area
            )

            if region is None:
                continue

            try:
                with context.temp_override(
                    area=area,
                    region=region,
                ):
                    if not bpy.ops.uv.select_overlap.poll():
                        continue

                    result = (
                        bpy.ops.uv.select_overlap(
                            extend=False
                        )
                    )

                if "FINISHED" in result:
                    return (
                        True,
                        "",
                    )

            except RuntimeError:
                continue

    # ---------------------------------------------------------
    # Temporarily use current area as Image Editor.
    # ---------------------------------------------------------

    area = context.area

    if area is None:
        return (
            False,
            "No UI area is available for the UV operator.",
        )

    original_area_type = (
        area.type
    )

    try:
        area.type = "IMAGE_EDITOR"

        region = get_window_region(
            area
        )

        if region is None:
            return (
                False,
                "Image Editor has no WINDOW region.",
            )

        with context.temp_override(
            area=area,
            region=region,
        ):
            if not bpy.ops.uv.select_overlap.poll():
                return (
                    False,
                    "bpy.ops.uv.select_overlap.poll() returned False.",
                )

            result = bpy.ops.uv.select_overlap(
                extend=False
            )

        if "FINISHED" not in result:
            return (
                False,
                "Native operator returned {}.".format(
                    result
                ),
            )

        return (
            True,
            "",
        )

    except Exception as error:
        return (
            False,
            str(
                error
            ),
        )

    finally:
        try:
            area.type = (
                original_area_type
            )
        except Exception:
            pass


def get_window_region(
        area,
    ):
    """
    Returns the WINDOW region from a Blender area.
    """
    for region in area.regions:
        if region.type == "WINDOW":
            return region

    return None



# -------------------------------------------------------------------------
# View Layer helpers
# -------------------------------------------------------------------------

def object_in_view_layer(
        obj,
        view_layer,
    ):
    """
    Returns True when obj is available in view_layer.
    """
    if (
        obj is None
        or view_layer is None
    ):
        return False

    return (
        view_layer.objects.get(
            obj.name
        )
        is not None
    )


def find_view_layer_for_object(
        scene,
        obj,
    ):
    """
    Finds the first View Layer in the scene that contains obj.

    Returns:
        bpy.types.ViewLayer | None
    """
    if (
        scene is None
        or obj is None
    ):
        return None

    for view_layer in scene.view_layers:

        if object_in_view_layer(
            obj,
            view_layer,
        ):
            return view_layer

    return None


def ensure_object_view_layer(
        context,
        obj,
    ):
    """
    Ensures obj is available in the active View Layer.

    If necessary, switches to another existing View Layer in the
    current scene that already contains the object.

    Returns:
        tuple:
            (
                success,
                message,
            )
    """
    if object_in_view_layer(
        obj,
        context.view_layer,
    ):
        return (
            True,
            "",
        )

    target_view_layer = (
        find_view_layer_for_object(
            context.scene,
            obj,
        )
    )

    if target_view_layer is None:
        return (
            False,
            (
                "Object '{}' is not available in any "
                "View Layer in scene '{}'."
            ).format(
                obj.name,
                context.scene.name,
            ),
        )

    if context.window is None:
        return (
            False,
            (
                "Cannot switch View Layers because "
                "the current context has no window."
            ),
        )

    try:
        context.window.view_layer = (
            target_view_layer
        )

        context.view_layer.update()

    except Exception as error:
        return (
            False,
            (
                "Could not switch to View Layer '{}': {}"
            ).format(
                target_view_layer.name,
                error,
            ),
        )

    return (
        True,
        "",
    )


# -------------------------------------------------------------------------
# Context preservation
# -------------------------------------------------------------------------

def capture_context_state(
        context,
    ):
    """
    Captures only global context state changed by this check.

    Mesh component selection is intentionally NOT captured globally.
    Each inspected mesh saves/restores only its own component selection.
    """
    scene = context.scene

    active_object = (
        context.view_layer.objects.active
    )

    return {
        "view_layer_name":
            context.view_layer.name,

        "active_object_name":
            (
                active_object.name
                if active_object
                else None
            ),

        "selected_object_names": [
            obj.name
            for obj in context.selected_objects
        ],

        "active_mode":
            (
                active_object.mode
                if active_object
                else "OBJECT"
            ),

        "use_uv_select_sync":
            scene.tool_settings.use_uv_select_sync,

        "uv_select_mode":
            getattr(
                scene.tool_settings,
                "uv_select_mode",
                None,
            ),
    }


def restore_context_state(
        context,
        state,
    ):
    """
    Restores global context state after native overlap detection.
    """
    scene = context.scene

    if (
        context.object is not None
        and context.object.mode != "OBJECT"
    ):
        try:
            bpy.ops.object.mode_set(
                mode="OBJECT"
            )
        except RuntimeError:
            pass

    # ---------------------------------------------------------
    # Restore original View Layer
    # ---------------------------------------------------------

    view_layer_name = state.get(
        "view_layer_name"
    )

    if (
        view_layer_name
        and context.window is not None
    ):
        original_view_layer = (
            scene.view_layers.get(
                view_layer_name
            )
        )

        if original_view_layer is not None:
            try:
                context.window.view_layer = (
                    original_view_layer
                )

                context.view_layer.update()

            except Exception:
                pass

    # ---------------------------------------------------------
    # Restore object selection
    # ---------------------------------------------------------

    for selected_obj in list(
        context.selected_objects
    ):
        try:
            selected_obj.select_set(
                False
            )
        except RuntimeError:
            pass

    for object_name in state[
        "selected_object_names"
    ]:
        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            continue

        if (
            context.view_layer.objects.get(
                object_name
            )
            is None
        ):
            continue

        try:
            obj.select_set(
                True
            )
        except RuntimeError:
            pass

    active_object = None

    active_object_name = state[
        "active_object_name"
    ]

    if active_object_name:
        active_object = (
            bpy.data.objects.get(
                active_object_name
            )
        )

        if (
            active_object is not None
            and context.view_layer.objects.get(
                active_object_name
            )
            is not None
        ):
            context.view_layer.objects.active = (
                active_object
            )

    # ---------------------------------------------------------
    # Restore UV tool settings
    # ---------------------------------------------------------

    scene.tool_settings.use_uv_select_sync = (
        state[
            "use_uv_select_sync"
        ]
    )

    original_uv_select_mode = (
        state.get(
            "uv_select_mode"
        )
    )

    if original_uv_select_mode is not None:
        try:
            scene.tool_settings.uv_select_mode = (
                original_uv_select_mode
            )
        except Exception:
            pass

    # ---------------------------------------------------------
    # Restore original Edit Mode
    # ---------------------------------------------------------

    if (
        active_object is not None
        and state[
            "active_mode"
        ] == "EDIT"
    ):
        try:
            bpy.ops.object.mode_set(
                mode="EDIT"
            )
        except RuntimeError:
            pass


def capture_mesh_component_selection(
        mesh,
    ):
    """
    Captures vertex/edge/face selection for one mesh only.
    """
    return {
        "vertices": [
            vertex.index
            for vertex in mesh.vertices
            if vertex.select
        ],

        "edges": [
            edge.index
            for edge in mesh.edges
            if edge.select
        ],

        "faces": [
            polygon.index
            for polygon in mesh.polygons
            if polygon.select
        ],
    }


def restore_mesh_component_selection(
        mesh,
        state,
    ):
    """
    Restores vertex/edge/face selection for one mesh.
    """
    vertex_indices = set(
        state[
            "vertices"
        ]
    )

    edge_indices = set(
        state[
            "edges"
        ]
    )

    face_indices = set(
        state[
            "faces"
        ]
    )

    for vertex in mesh.vertices:
        vertex.select = (
            vertex.index
            in vertex_indices
        )

    for edge in mesh.edges:
        edge.select = (
            edge.index
            in edge_indices
        )

    for polygon in mesh.polygons:
        polygon.select = (
            polygon.index
            in face_indices
        )


def make_only_object_active(
        context,
        obj,
    ):
    """
    Makes one object the only selected active object.
    """
    if (
        context.object is not None
        and context.object.mode != "OBJECT"
    ):
        bpy.ops.object.mode_set(
            mode="OBJECT"
        )

    for selected_obj in list(
        context.selected_objects
    ):
        try:
            selected_obj.select_set(
                False
            )
        except RuntimeError:
            pass

    if (
        context.view_layer.objects.get(
            obj.name
        )
        is None
    ):
        raise RuntimeError(
            (
                "Object '{}' is not available in the "
                "current View Layer."
            ).format(
                obj.name
            )
        )

    obj.hide_select = False

    try:
        obj.hide_set(
            False
        )
    except RuntimeError:
        pass

    obj.select_set(
        True
    )

    context.view_layer.objects.active = (
        obj
    )
