# Standard python imports

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
    failed_materials = get_orphan_materials()

    issues = [
        "Orphan material: {}".format(material_name)
        for material_name in failed_materials
    ]

    return {
        "issues": issues,
        "failed_materials": failed_materials,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_orphan_materials()

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

def get_orphan_materials():
    """
    Finds material datablocks with zero users.

    Returns:
        dict:
        {
            "Unused_Material": {
                "users": 0,
                "use_fake_user": False,
            }
        }
    """
    orphan_materials = {}

    for material in bpy.data.materials:

        if material.users != 0:
            continue

        orphan_materials[material.name] = {
            "users": material.users,
            "use_fake_user": material.use_fake_user,
        }

    return orphan_materials


# -------------------------
# Fix
# -------------------------

def fix_orphan_materials():
    """
    Removes all material datablocks that have zero users.

    Returns:
        list[str]:
            Names of removed materials.
    """
    removed_materials = []

    # Convert to list because bpy.data.materials changes
    # while materials are removed.
    for material in list(bpy.data.materials):

        if material.users != 0:
            continue

        removed_materials.append(material.name)

        bpy.data.materials.remove(
            material,
            do_unlink=True,
        )

    return removed_materials
