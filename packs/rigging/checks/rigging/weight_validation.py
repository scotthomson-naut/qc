# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Weight Validation"
DESCRIPTION = (
    "Checks skinned meshes for unweighted vertices, invalid bone groups, "
    "excessive influences, and non-normalized deform weights."
)
WHY = "Invalid skin weights can cause deformation and export errors."

SETTINGS = {
    "max_influences": {
        "type": "int",
        "label": "Maximum Influences",
        "default": 4,
        "min": 1,
    },
    "minimum_weight": {
        "type": "float",
        "label": "Minimum Weight",
        "default": 0.0001,
        "min": 0.0,
    },
    "normalization_tolerance": {
        "type": "float",
        "label": "Normalization Tolerance",
        "default": 0.001,
        "min": 0.0,
    },
}

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds objects.
    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "can_auto_fix": bool,
        }
    """
    settings = resolve_settings(SETTINGS, preferences)
    failures = find_weight_issues(settings=settings)
    issues = []

    for object_name, data in sorted(failures.items()):
        if data["unweighted_vertices"]:
            issues.append(
                'Object "{}" has {} unweighted vertices.'.format(
                    object_name,
                    len(data["unweighted_vertices"]),
                )
            )
        if data["too_many_influences"]:
            issues.append(
                'Object "{}" has {} vertices above the influence limit.'.format(
                    object_name,
                    len(data["too_many_influences"]),
                )
            )
        if data["non_normalized_vertices"]:
            issues.append(
                'Object "{}" has {} non-normalized vertices.'.format(
                    object_name,
                    len(data["non_normalized_vertices"]),
                )
            )
        if data["invalid_vertex_groups"]:
            issues.append(
                'Object "{}" has weighted groups without matching deform bones: {}.'.format(
                    object_name,
                    ", ".join(data["invalid_vertex_groups"]),
                )
            )

    return {
        "issues": issues,
        "failed_objects": failures,
        "settings": settings,
        "can_auto_fix": False,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def find_weight_issues(objects=None, settings=None):
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    max_influences = int(settings.get("max_influences", 4))
    minimum_weight = float(settings.get("minimum_weight", 0.0001))
    tolerance = float(settings.get("normalization_tolerance", 0.001))

    failures = {}

    for obj in get_qc_objects(objects):
        if obj.type != "MESH":
            continue

        armature = get_armature_object(obj)
        if armature is None:
            continue

        deform_bones = {
            bone.name
            for bone in armature.data.bones
            if bone.use_deform
        }

        invalid_groups = set()
        unweighted = []
        too_many = []
        non_normalized = []

        for vertex in obj.data.vertices:
            weights = []

            for group_ref in vertex.groups:
                if not (0 <= group_ref.group < len(obj.vertex_groups)):
                    continue

                if group_ref.weight <= minimum_weight:
                    continue

                group_name = obj.vertex_groups[group_ref.group].name

                if group_name not in deform_bones:
                    invalid_groups.add(group_name)
                    continue

                weights.append(float(group_ref.weight))

            if not weights:
                unweighted.append(vertex.index)
                continue

            if len(weights) > max_influences:
                too_many.append(vertex.index)

            if abs(sum(weights) - 1.0) > tolerance:
                non_normalized.append(vertex.index)

        if invalid_groups or unweighted or too_many or non_normalized:
            failures[obj.name] = {
                "armature": armature.name,
                "invalid_vertex_groups": sorted(invalid_groups),
                "unweighted_vertices": unweighted,
                "too_many_influences": too_many,
                "non_normalized_vertices": non_normalized,
            }

    return failures


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
