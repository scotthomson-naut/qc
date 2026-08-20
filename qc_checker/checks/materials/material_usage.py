# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Material Usage"
DESCRIPTION = (
    "Checks for unused material datablocks, excluding protected, "
    "linked, asset, and Blender-managed materials."
)
WHY = (
    "Cleans up your file, reduce memory use, and remove clutter."
)


# -------------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------------

# Materials that should remain available even with zero users.
PROTECTED_MATERIAL_NAMES = {
    "Dots Stroke",
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks for unused material datablocks.
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
    Removes only the materials reported by main().
    """
    return fix_orphan_materials(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_orphan_materials():
    """
    Finds removable material datablocks with zero users.

    Protected materials are ignored.

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

        if is_protected_material(
            material
        ):
            continue

        orphan_materials[material.name] = {
            "users": material.users,
            "use_fake_user": material.use_fake_user,
            "is_asset": material.asset_data is not None,
            "is_linked": material.library is not None,
        }

    return orphan_materials


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_orphan_materials(
        result_data=None,
    ):
    """
    Removes only materials included in the check result.

    This avoids deleting newly created or protected materials that
    were not part of the original QC result.

    Returns:
        dict:
        {
            "fixed_materials": list[str],
            "issues": list[str],
        }
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed_materials = result_data.get(
        "failed_materials",
        {},
    )

    if not isinstance(failed_materials, dict):
        failed_materials = {}

    removed_materials = []
    issues = []

    for material_name in failed_materials:

        material = bpy.data.materials.get(
            material_name
        )

        if material is None:
            continue

        if material.users != 0:
            issues.append(
                'Skipped "{}": material now has {} user(s).'.format(
                    material.name,
                    material.users,
                )
            )
            continue

        if is_protected_material(
            material
        ):
            issues.append(
                'Skipped protected material: "{}".'.format(
                    material.name
                )
            )
            continue

        try:
            removed_materials.append(
                material.name
            )

            bpy.data.materials.remove(
                material,
                do_unlink=True,
            )

        except Exception as error:
            issues.append(
                'Could not remove "{}": {}'.format(
                    material_name,
                    error,
                )
            )

    return {
        "fixed_materials": removed_materials,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def is_protected_material(material):
    """
    Returns True when a material should not be considered
    an automatically removable orphan.
    """
    if material.name in PROTECTED_MATERIAL_NAMES:
        return True

    # Explicitly preserved by the artist or pipeline.
    if material.use_fake_user:
        return True

    # Blender can internally retain an extra user.
    if getattr(material, "use_extra_user", False):
        return True

    # Do not modify linked-library materials.
    if material.library is not None:
        return True

    # Preserve materials marked as assets.
    if material.asset_data is not None:
        return True

    # Preserve indirect linked datablocks.
    if getattr(material, "is_library_indirect", False):
        return True

    return False
