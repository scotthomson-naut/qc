# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Duplicate Constraints"
DESCRIPTION = (
    "Checks objects and pose bones for constraints with equivalent "
    "target configurations."
)
WHY = (
    "Duplicate constraints can stack influence and make rigs unstable "
    "or difficult to debug."
)


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
    failures = find_duplicate_constraints()
    issues = []

    for owner_name, data in sorted(failures.items()):
        for group in data["duplicate_groups"]:
            issues.append(
                '{} has duplicate {} constraints: {}.'.format(
                    owner_name,
                    group["constraint_type"],
                    ", ".join(group["constraint_names"]),
                )
            )

    return {
        "issues": issues,
        "failed_objects": failures,
    }


def fix(result_data=None):
    """
    Fixes.

    Args:
        result_data (dict | None):
            Result returned by main().

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    return fix_duplicate_constraints(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def find_duplicate_constraints(objects=None):
    if objects is None:
        objects = bpy.context.scene.objects

    failures = {}

    for obj in get_qc_objects(objects):
        record_duplicates(
            failures,
            obj,
            obj.name,
            "OBJECT",
            obj.name,
        )

        if obj.type == "ARMATURE":
            for pose_bone in obj.pose.bones:
                record_duplicates(
                    failures,
                    pose_bone,
                    "{} / {}".format(obj.name, pose_bone.name),
                    "POSE_BONE",
                    obj.name,
                    pose_bone.name,
                )

    return failures


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_duplicate_constraints(result_data=None):
    if not isinstance(result_data, dict):
        result_data = {}

    failures = result_data.get("failed_objects", {})
    fixed_objects = {}
    issues = []

    if not isinstance(failures, dict):
        failures = {}

    for owner_name, data in failures.items():
        owner = resolve_owner(data)
        if owner is None:
            continue

        removed = []

        for group in data.get("duplicate_groups", []):
            for constraint_name in group.get("constraint_names", [])[1:]:
                constraint = owner.constraints.get(constraint_name)
                if constraint is None:
                    continue
                try:
                    owner.constraints.remove(constraint)
                    removed.append(constraint_name)
                except Exception as error:
                    issues.append(
                        'Could not remove "{}" from {}: {}'.format(
                            constraint_name,
                            owner_name,
                            error,
                        )
                    )

        if removed:
            fixed_objects[owner_name] = {
                "removed_constraints": removed,
            }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def record_duplicates(
        failures,
        owner,
        owner_name,
        owner_type,
        object_name,
        bone_name="",
    ):
    if len(owner.constraints) <= 1:
        return

    groups = {}

    for constraint in owner.constraints:
        signature = constraint_signature(constraint)
        groups.setdefault(signature, []).append(constraint.name)

    duplicate_groups = []

    for signature, names in groups.items():
        if len(names) <= 1:
            continue

        duplicate_groups.append({
            "constraint_type": signature[0],
            "constraint_names": names,
        })

    if duplicate_groups:
        failures[owner_name] = {
            "owner_type": owner_type,
            "object_name": object_name,
            "bone_name": bone_name,
            "duplicate_groups": duplicate_groups,
        }


def constraint_signature(constraint):
    target = getattr(constraint, "target", None)
    pole_target = getattr(constraint, "pole_target", None)

    return (
        constraint.type,
        getattr(target, "name", ""),
        getattr(constraint, "subtarget", ""),
        getattr(pole_target, "name", ""),
        getattr(constraint, "pole_subtarget", ""),
        round(float(getattr(constraint, "influence", 1.0)), 6),
        int(getattr(constraint, "chain_count", 0)),
    )


def resolve_owner(data):
    obj = get_qc_object(data.get("object_name", ""))
    if obj is None:
        return None

    if data.get("owner_type") == "POSE_BONE":
        if obj.type != "ARMATURE":
            return None
        return obj.pose.bones.get(data.get("bone_name", ""))

    return obj
