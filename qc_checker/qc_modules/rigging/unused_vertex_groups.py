# Standard python imports

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_invalid_vertex_groups()

    issues = []

    for object_name, data in failed_objects.items():

        for group_name in data["empty_groups"]:
            issues.append(
                "{} - Empty vertex group: {}".format(
                    object_name,
                    group_name,
                )
            )

        for group_name in data["groups_without_bones"]:
            issues.append(
                "{} - No matching bone: {}".format(
                    object_name,
                    group_name,
                )
            )

        for group_name in data[
            "groups_matching_non_deform_bones"
        ]:
            issues.append(
                "{} - Matches non-deforming bone: {}".format(
                    object_name,
                    group_name,
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Args:
        result_data (list[str]): List of object names.
    Returns:
        dict: Issues
    """
    #failed_objects = result_data.get("failed_objects", [])

    # Call Function
    fix_invalid_vertex_groups(result_data)

    return {
        "issues": []
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_invalid_vertex_groups(
        objects=None,
        weight_tolerance=1e-6,
    ):
    """
    Finds suspicious vertex groups on rigged mesh objects.

    Checks:
        1. Empty vertex groups.
        2. Weighted groups with no matching deform bone.
        3. Groups that match non-deforming bones.
        4. Ignores vertex groups referenced by supported modifiers.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all mesh objects in the current scene.

        weight_tolerance (float):
            Minimum meaningful vertex weight.

    Returns:
        dict:
        {
            "CharacterMesh": {
                "empty_groups": [...],
                "groups_without_bones": [...],
                "groups_matching_non_deform_bones": [...],
                "modifier_groups": [...],
                "issues": [...]
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if not obj.vertex_groups:
            continue

        armature_objects = get_associated_armatures(obj)

        if not armature_objects:
            # This is intended as rigging QC.
            continue

        all_bone_names = set()
        deform_bone_names = set()

        for armature_obj in armature_objects:
            for bone in armature_obj.data.bones:
                all_bone_names.add(bone.name)

                if bone.use_deform:
                    deform_bone_names.add(bone.name)

        modifier_groups = get_modifier_vertex_groups(obj)

        empty_groups = []
        groups_without_bones = []
        groups_matching_non_deform_bones = []

        for vertex_group in obj.vertex_groups:
            group_name = vertex_group.name

            has_weights = vertex_group_has_weights(
                obj,
                vertex_group,
                tolerance=weight_tolerance,
            )

            # Do not treat groups used by modifiers as bad rig groups.
            if group_name in modifier_groups:
                continue

            if not has_weights:
                empty_groups.append(group_name)
                continue

            if group_name not in all_bone_names:
                groups_without_bones.append(group_name)
                continue

            if group_name not in deform_bone_names:
                groups_matching_non_deform_bones.append(
                    group_name
                )

        if (
            empty_groups
            or groups_without_bones
            or groups_matching_non_deform_bones
        ):
            issues = []

            for group_name in empty_groups:
                issues.append(
                    "Empty vertex group: {}".format(group_name)
                )

            for group_name in groups_without_bones:
                issues.append(
                    "Weighted vertex group has no matching bone: {}".format(
                        group_name
                    )
                )

            for group_name in groups_matching_non_deform_bones:
                issues.append(
                    "Vertex group matches a non-deforming bone: {}".format(
                        group_name
                    )
                )

            failed_objects[obj.name] = {
                "empty_groups": empty_groups,
                "groups_without_bones": groups_without_bones,
                "groups_matching_non_deform_bones":
                    groups_matching_non_deform_bones,
                "modifier_groups": sorted(modifier_groups),
                "issues": issues,
            }

    return failed_objects


def get_associated_armatures(obj):
    """
    Returns armatures associated with a mesh.

    Detects:
        - Armature modifiers.
        - Armature parent.

    Args:
        obj (bpy.types.Object):
            Mesh object.

    Returns:
        list[bpy.types.Object]:
            Unique associated armature objects.
    """
    armatures = []

    def add_armature(armature_obj):
        if (
            armature_obj is not None
            and armature_obj.type == "ARMATURE"
            and armature_obj not in armatures
        ):
            armatures.append(armature_obj)

    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE":
            add_armature(modifier.object)

    if obj.parent is not None:
        if obj.parent.type == "ARMATURE":
            add_armature(obj.parent)

    return armatures


def get_modifier_vertex_groups(obj):
    """
    Returns vertex-group names referenced directly by modifiers.

    This prevents non-rig groups used for masks or modifier influence
    from being incorrectly flagged.

    Args:
        obj (bpy.types.Object):
            Mesh object.

    Returns:
        set[str]:
            Referenced vertex-group names.
    """
    group_names = set()

    for modifier in obj.modifiers:

        # Many Blender modifiers expose a 'vertex_group' string property.
        if hasattr(modifier, "vertex_group"):
            group_name = getattr(
                modifier,
                "vertex_group",
                "",
            )

            if group_name:
                group_names.add(group_name)

        # Some modifiers may expose additional group fields.
        for property_name in (
            "vertex_group_a",
            "vertex_group_b",
        ):
            if not hasattr(modifier, property_name):
                continue

            group_name = getattr(
                modifier,
                property_name,
                "",
            )

            if group_name:
                group_names.add(group_name)

    return group_names


def vertex_group_has_weights(
        obj,
        vertex_group,
        tolerance=1e-6,
    ):
    """
    Checks whether a vertex group has at least one meaningful weight.

    Args:
        obj (bpy.types.Object):
            Mesh object.

        vertex_group (bpy.types.VertexGroup):
            Vertex group.

        tolerance (float):
            Minimum meaningful weight.

    Returns:
        bool:
            True when at least one vertex has weight above tolerance.
    """
    group_index = vertex_group.index

    for vertex in obj.data.vertices:
        for group_element in vertex.groups:

            if group_element.group != group_index:
                continue

            if group_element.weight > tolerance:
                return True

    return False


# -------------------------
# Fix
# -------------------------

def fix_invalid_vertex_groups(result_data):
    """
    Safely removes only empty vertex groups.

    Weighted groups are never automatically deleted because they may
    contain intentional data that needs artist review.

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

    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        removed_groups = []

        for group_name in object_data.get(
            "empty_groups",
            [],
        ):
            vertex_group = obj.vertex_groups.get(
                group_name
            )

            if vertex_group is None:
                continue

            # Recheck before deleting.
            if vertex_group_has_weights(
                obj,
                vertex_group,
            ):
                issues.append(
                    "Skipped '{}.{}' because it now contains weights.".format(
                        object_name,
                        group_name,
                    )
                )
                continue

            obj.vertex_groups.remove(
                vertex_group
            )

            removed_groups.append(
                group_name
            )

        if removed_groups:
            fixed_objects[object_name] = {
                "removed_vertex_groups":
                    removed_groups,
            }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }
