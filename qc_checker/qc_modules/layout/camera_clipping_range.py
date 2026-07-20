# Standard python imports
from mathutils import Vector

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    """
    failed_objects = get_cameras_with_unreasonable_clipping()

    issues = []

    for camera_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {}".format(
                camera_name,
                ", ".join(data["issues"]),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    failed_objects = result_data.get("failed_objects", {})

    fixed = fix_cameras_with_unreasonable_clipping(failed_objects)

    return {
        "issues": [],
        "fixed_objects": fixed,
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------

def get_cameras_with_unreasonable_clipping(
        cameras=None,
        objects=None,
        near_margin=0.90,
        far_margin=1.10,
        minimum_near_ratio=1e-5,
        maximum_depth_ratio=1e7,
        exclude_types=None,
    ):
    """
    Finds cameras whose clipping planes are unsuitable for the scene.

    The function checks:

        1. Near clipping plane cuts into visible scene geometry.
        2. Far clipping plane cuts off visible scene geometry.
        3. Near clipping is unnecessarily tiny relative to scene scale.
        4. Far-to-near clipping ratio is excessively large.

    Only geometry located in front of each camera is considered.

    Args:
        cameras (iterable[bpy.types.Object] | None):
            Camera objects to inspect.
            Defaults to all scene camera objects.

        objects (iterable[bpy.types.Object] | None):
            Scene objects used to determine visible depth.
            Defaults to all objects in the current scene.

        near_margin (float):
            Recommended near clip as a fraction of the nearest geometry
            depth. For example, 0.90 leaves a 10% safety margin.

        far_margin (float):
            Recommended far clip as a multiple of the farthest geometry
            depth. For example, 1.10 leaves a 10% safety margin.

        minimum_near_ratio (float):
            Minimum reasonable near clip relative to the scene's
            overall bounding-box diagonal.

        maximum_depth_ratio (float):
            Maximum acceptable clip_end / clip_start ratio.

        exclude_types (set[str] | None):
            Object types excluded from scene-scale calculations.

    Returns:
        dict:
        {
            "Camera": {
                "clip_start": 0.1,
                "clip_end": 1000.0,
                "nearest_depth": 2.5,
                "farthest_depth": 1250.0,
                "scene_diagonal": 400.0,
                "recommended_clip_start": 2.25,
                "recommended_clip_end": 1375.0,
                "issues": [
                    "Far clipping plane cuts into scene geometry"
                ]
            }
        }
    """
    scene = bpy.context.scene

    if cameras is None:
        cameras = [
            obj
            for obj in scene.objects
            if obj.type == "CAMERA"
        ]

    if objects is None:
        objects = scene.objects

    if exclude_types is None:
        exclude_types = {
            "CAMERA",
            "LIGHT",
            "SPEAKER",
        }

    geometry_objects = [
        obj
        for obj in objects
        if (
            obj.type not in exclude_types
            and not obj.hide_render
            and has_valid_bounding_box(obj)
        )
    ]

    scene_bounds = get_world_bounds(geometry_objects)

    if scene_bounds is None:
        return {}

    scene_min, scene_max = scene_bounds
    scene_diagonal = (scene_max - scene_min).length

    # Prevent zero-size scenes from producing invalid ratios.
    scene_diagonal = max(scene_diagonal, 1e-8)

    failed_cameras = {}

    for camera_obj in cameras:
        if camera_obj.type != "CAMERA":
            continue

        camera_data = camera_obj.data
        camera_inverse = camera_obj.matrix_world.inverted_safe()

        visible_depths = []

        for obj in geometry_objects:
            for world_corner in get_object_world_corners(obj):
                camera_corner = camera_inverse @ world_corner

                # Blender cameras look down their local negative Z axis.
                depth = -camera_corner.z

                if depth > 0.0:
                    visible_depths.append(depth)

        if not visible_depths:
            continue

        nearest_depth = min(visible_depths)
        farthest_depth = max(visible_depths)

        clip_start = camera_data.clip_start
        clip_end = camera_data.clip_end

        recommended_clip_start = max(
            nearest_depth * near_margin,
            scene_diagonal * minimum_near_ratio,
            1e-6,
        )

        recommended_clip_end = max(
            farthest_depth * far_margin,
            recommended_clip_start * 10.0,
        )

        issues = []

        # Near plane is farther away than the nearest geometry.
        if clip_start >= nearest_depth:
            issues.append(
                "Near clipping plane cuts into scene geometry"
            )

        # Far plane is closer than the farthest geometry.
        if clip_end <= farthest_depth:
            issues.append(
                "Far clipping plane cuts into scene geometry"
            )

        minimum_reasonable_near = (
            scene_diagonal * minimum_near_ratio
        )

        if clip_start < minimum_reasonable_near:
            issues.append(
                "Near clipping plane is unnecessarily small "
                "for the scene scale"
            )

        depth_ratio = (
            clip_end / clip_start
            if clip_start > 0.0
            else float("inf")
        )

        if depth_ratio > maximum_depth_ratio:
            issues.append(
                "Camera clipping range is excessively large"
            )

        if clip_end <= clip_start:
            issues.append(
                "Far clipping plane must be greater than "
                "the near clipping plane"
            )

        if issues:
            failed_cameras[camera_obj.name] = {
                "clip_start": clip_start,
                "clip_end": clip_end,
                "nearest_depth": nearest_depth,
                "farthest_depth": farthest_depth,
                "scene_diagonal": scene_diagonal,
                "depth_ratio": depth_ratio,
                "recommended_clip_start": recommended_clip_start,
                "recommended_clip_end": recommended_clip_end,
                "issues": issues,
            }

    return failed_cameras


def has_valid_bounding_box(obj):
    """
    Returns whether an object has a usable bounding box.

    Args:
        obj (bpy.types.Object): Object to inspect.

    Returns:
        bool: True when the object has valid bounding-box coordinates.
    """
    if not hasattr(obj, "bound_box"):
        return False

    try:
        return any(
            coordinate != -1.0
            for corner in obj.bound_box
            for coordinate in corner
        )
    except (AttributeError, TypeError):
        return False


def get_object_world_corners(obj):
    """
    Returns an object's bounding-box corners in world space.

    Args:
        obj (bpy.types.Object): Object to inspect.

    Returns:
        list[mathutils.Vector]: Eight world-space bounding-box corners.
    """
    return [
        obj.matrix_world @ Vector(corner)
        for corner in obj.bound_box
    ]


def get_world_bounds(objects):
    """
    Calculates combined world-space bounds for multiple objects.

    Args:
        objects (iterable[bpy.types.Object]):
            Objects contributing to the bounds.

    Returns:
        tuple[Vector, Vector] | None:
            Minimum and maximum world-space coordinates.
    """
    world_corners = []

    for obj in objects:
        world_corners.extend(
            get_object_world_corners(obj)
        )

    if not world_corners:
        return None

    minimum = Vector((
        min(point.x for point in world_corners),
        min(point.y for point in world_corners),
        min(point.z for point in world_corners),
    ))

    maximum = Vector((
        max(point.x for point in world_corners),
        max(point.y for point in world_corners),
        max(point.z for point in world_corners),
    ))

    return minimum, maximum


# -------------------------
# Fix
# -------------------------

def fix_cameras_with_unreasonable_clipping(result_data):
    """
    Applies the recommended near and far clipping values.

    Args:
        result_data (dict):
            Result dictionary returned by main().

    Returns:
        dict: Fix result.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for camera_name, camera_info in failed_objects.items():
        camera_obj = bpy.data.objects.get(camera_name)

        if camera_obj is None:
            issues.append(
                "Camera no longer exists: {}".format(camera_name)
            )
            continue

        if camera_obj.type != "CAMERA":
            issues.append(
                "Object is no longer a camera: {}".format(
                    camera_name
                )
            )
            continue

        clip_start = camera_info.get(
            "recommended_clip_start"
        )
        clip_end = camera_info.get(
            "recommended_clip_end"
        )

        if clip_start is None or clip_end is None:
            issues.append(
                "Missing recommended clipping values: {}".format(
                    camera_name
                )
            )
            continue

        camera_obj.data.clip_start = max(
            float(clip_start),
            1e-6,
        )

        camera_obj.data.clip_end = max(
            float(clip_end),
            camera_obj.data.clip_start * 10.0,
        )

        fixed_objects[camera_name] = {
            "clip_start": camera_obj.data.clip_start,
            "clip_end": camera_obj.data.clip_end,
        }

    bpy.context.view_layer.update()

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }
