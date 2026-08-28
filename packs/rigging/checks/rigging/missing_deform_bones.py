# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Missing Deform Bones"
DESCRIPTION = (
    "Checks skinned meshes for weighted vertex groups whose bone "
    "names do not exist on the driving armature."
)
WHY = "Missing deform bones can break skinning, export, and deformation."


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Finds objects.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = find_missing_deform_bones()
    issues = []
    for object_name, data in sorted(failed_objects.items()):
        issues.append(
            'Object "{}" references missing bone(s): {}.'.format(
                object_name,
                ", ".join(data["missing_bones"]),
            )
        )
    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "can_auto_fix": False,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def find_missing_deform_bones(objects=None):
    if objects is None:
        objects = bpy.context.scene.objects

    failed = {}

    for obj in get_qc_objects(objects):
        if obj.type != "MESH":
            continue

        armature = get_armature_object(obj)
        if armature is None:
            continue

        bone_names = {bone.name for bone in armature.data.bones}
        weighted_group_names = set()

        for vertex in obj.data.vertices:
            for group_ref in vertex.groups:
                if group_ref.weight <= 0.0:
                    continue

                if 0 <= group_ref.group < len(obj.vertex_groups):
                    weighted_group_names.add(
                        obj.vertex_groups[group_ref.group].name
                    )

        missing = sorted(
            name
            for name in weighted_group_names
            if name not in bone_names
        )

        if missing:
            failed[obj.name] = {
                "armature": armature.name,
                "missing_bone_count": len(missing),
                "missing_bones": missing,
            }

    return failed


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_armature_object(obj):
    try:
        armature = obj.find_armature()
        if armature is not None:
            return armature
    except Exception:
        pass

    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object is not None:
            return modifier.object

    return None
