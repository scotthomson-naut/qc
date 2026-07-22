# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks mesh materials for disabled node usage.
    """
    failed_objects = (
        get_meshes_with_material_nodes_disabled()
    )

    issues = []

    for object_name, data in failed_objects.items():

        issues.append(
            "Failed object: {} - Material(s) have "
            "'Use Nodes' disabled: {}".format(
                object_name,
                ", ".join(data["materials"]),
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
    fixed = fix_meshes_with_material_nodes_disabled(result_data)

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

def get_meshes_with_material_nodes_disabled(objects=None):
    """
    Finds mesh objects that use materials with 'Use Nodes' disabled.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Character_Body": {
                "materials": [
                    "Skin_Material",
                    "Eye_Material",
                ],
                "material_count": 2,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        if obj.type != "MESH":
            continue

        failed_materials = []

        for material_slot in obj.material_slots:

            material = material_slot.material

            # Empty material slots are ignored here.
            if material is None:
                continue

            if material.use_nodes:
                continue

            # Avoid duplicate names if the same material
            # appears in multiple slots.
            if material.name not in failed_materials:
                failed_materials.append(
                    material.name
                )

        if not failed_materials:
            continue

        failed_objects[obj.name] = {
            "materials": failed_materials,
            "material_count": len(failed_materials),
        }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_meshes_with_material_nodes_disabled(result_data):
    """
    Enables Use Nodes for all failed materials.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_materials = []
    issues = []

    for object_name, object_data in failed_objects.items():

        material_names = object_data.get(
            "materials",
            [],
        )

        for material_name in material_names:
            material = bpy.data.materials.get(
                material_name
            )

            if material is None:
                issues.append(
                    "Material no longer exists: {}".format(
                        material_name
                    )
                )
                continue

            if not material.use_nodes:
                material.use_nodes = True

            if material_name not in fixed_materials:
                fixed_materials.append(
                    material_name
                )

    return {
        "issues": issues,
        "fixed_materials": fixed_materials,
    }
