# Python imports
import re

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "Descriptive Names"
DESCRIPTION = (
    "Checks if Object or Datablock names use default Blender names like "
    "Cube, Sphere, Camera, Light, etc."
)
WHY = (
    "Descriptive names help prevent confusion in complex scenes "
    "and production pipelines."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

DEFAULT_OBJECT_NAMES = {
    "Cube",
    "Plane",
    "Sphere",
    "Icosphere",
    "Cylinder",
    "Cone",
    "Torus",
    "Grid",
    "Suzanne",
    "Circle",
    "Empty",
    "Armature",
    "Text",
    "Curve",
    "BezierCurve",
    "BézierCurve",
    "BezierCircle",
    "BézierCircle",
    "NurbsCircle",
    "NurbsCurve",
    "NurbsPath",
    "Surface",
    "SurfCircle",
    "SurfCurve",
    "SurfCylinder",
    "SurfCPatch",
    "SurfSphere",
    "SurfTorus",
    "Metaball",
    "Mball",
    "Text",
    "PointCloud",
    "Volume",
    "GreasePencil",
    "Camera",
    "Light",
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks object names and datablock names for Blender default names.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_default_names()

    issues = []

    for object_name, data in failed_objects.items():

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_data = data.get(
            "object_name"
        )

        if object_name_data:
            issues.append(
                (
                    "Failed object: {} - Object name {!r} "
                    "uses default Blender name {!r}"
                ).format(
                    object_name,
                    object_name_data["name"],
                    object_name_data["base_name"],
                )
            )

        # -----------------------------------------------------
        # Datablock name
        # -----------------------------------------------------

        datablock_name_data = data.get(
            "datablock_name"
        )

        if datablock_name_data:
            issues.append(
                (
                    "Failed object: {} - Datablock name {!r} "
                    "uses default Blender name {!r}"
                ).format(
                    object_name,
                    datablock_name_data["name"],
                    datablock_name_data["base_name"],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_default_names(
        objects=None,
        default_names=None,
        include_numbered_suffixes=True,
    ):
    """
    Finds objects whose object name or datablock name uses a default
    Blender name.

    Examples that fail:
        Object name:
            Cube
            Cube.001
            Plane
            Camera
            Light

        Datablock name:
            Object:      Hero_Chair
            Mesh:        Cube

            Object:      ShotCamera
            Camera data: Camera.001

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        default_names (set[str] | None):
            Names considered invalid/default.
            Defaults to DEFAULT_OBJECT_NAMES.

        include_numbered_suffixes (bool):
            If True, detects numbered versions such as:
                Cube.001
                Plane.002
                Camera.003

    Returns:
        dict:
        {
            "Hero_Chair": {
                "object_name": {
                    "name": "Cube.001",
                    "base_name": "Cube",
                    "suffix": 1,
                },

                "datablock_name": {
                    "name": "Cube",
                    "base_name": "Cube",
                    "suffix": None,
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if default_names is None:
        default_names = DEFAULT_OBJECT_NAMES

    failed_objects = {}

    for obj in objects:

        # Directly linked library objects are read-only and are
        # outside the scope of local naming QC.
        if obj.library is not None:
            continue

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_result = (
            get_default_name_data(
                obj.name,
                default_names=default_names,
                include_numbered_suffixes=(
                    include_numbered_suffixes
                ),
            )
        )

        # -----------------------------------------------------
        # Datablock name
        # -----------------------------------------------------

        datablock_name_result = None

        datablock = getattr(
            obj,
            "data",
            None,
        )

        if (
            datablock is not None
            and hasattr(
                datablock,
                "name",
            )
        ):
            datablock_name_result = (
                get_default_name_data(
                    datablock.name,
                    default_names=default_names,
                    include_numbered_suffixes=(
                        include_numbered_suffixes
                    ),
                )
            )

        # -----------------------------------------------------
        # Passed both
        # -----------------------------------------------------

        if (
            object_name_result is None
            and datablock_name_result is None
        ):
            continue

        result = {}

        if object_name_result is not None:
            result["object_name"] = (
                object_name_result
            )

        if datablock_name_result is not None:
            result["datablock_name"] = (
                datablock_name_result
            )

        failed_objects[
            obj.name
        ] = result

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_default_name_data(
        name,
        default_names=None,
        include_numbered_suffixes=True,
    ):
    """
    Checks whether a single name is a Blender default name.

    Args:
        name (str):
            Name to inspect.

        default_names (set[str] | None):
            Default names to check against.

        include_numbered_suffixes (bool):
            Detect names such as Cube.001.

    Returns:
        dict | None:
            None when the name is acceptable.

            Otherwise:
            {
                "name": "Cube.001",
                "base_name": "Cube",
                "suffix": 1,
            }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    if default_names is None:
        default_names = DEFAULT_OBJECT_NAMES

    base_name = name
    suffix = None

    if include_numbered_suffixes:
        match = re.match(
            r"^(.*)\.(\d{3})$",
            name,
        )

        if match:
            base_name = match.group(1)
            suffix = int(
                match.group(2)
            )

    if base_name not in default_names:
        return None

    return {
        "name": name,
        "base_name": base_name,
        "suffix": suffix,
    }
