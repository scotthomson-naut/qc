# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "IK Validation"
DESCRIPTION = (
    "Checks armature IK constraints for missing targets, invalid "
    "subtargets, invalid pole targets, and invalid chain lengths."
)
WHY = "Broken IK constraints can stop limbs from solving correctly."


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
    failures = find_ik_issues()
    issues = []

    for owner_name, data in sorted(failures.items()):
        for problem in data.get("problems", []):
            issues.append(
                "{}: {}".format(
                    owner_name,
                    problem,
                )
            )

    return {
        "issues": issues,
        "failed_objects": failures,
        "can_auto_fix": False,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def find_ik_issues(objects=None):
    if objects is None:
        objects = bpy.context.scene.objects

    failures = {}

    for obj in get_qc_objects(objects):
        if obj.type != "ARMATURE":
            continue

        for pose_bone in obj.pose.bones:
            for constraint in pose_bone.constraints:
                if constraint.type != "IK":
                    continue

                problems = validate_ik_constraint(
                    obj,
                    pose_bone,
                    constraint,
                )

                if not problems:
                    continue

                key = "{} / {} / {}".format(
                    obj.name,
                    pose_bone.name,
                    constraint.name,
                )

                failures[key] = {
                    "object_name": obj.name,
                    "bone_name": pose_bone.name,
                    "constraint_name": constraint.name,
                    "problems": problems,
                }

    return failures


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def validate_ik_constraint(
        armature_object,
        pose_bone,
        constraint,
    ):
    problems = []
    target = constraint.target

    if target is None:
        problems.append("IK target is missing.")
    elif target == armature_object:
        if not constraint.subtarget:
            problems.append(
                "IK target uses the same armature but has no target bone."
            )
        elif target.pose.bones.get(constraint.subtarget) is None:
            problems.append(
                'IK target bone "{}" does not exist.'.format(
                    constraint.subtarget
                )
            )
        elif constraint.subtarget == pose_bone.name:
            problems.append(
                "IK target points to the constrained bone itself."
            )

    pole_target = constraint.pole_target

    if pole_target == armature_object:
        if not constraint.pole_subtarget:
            problems.append(
                "Pole target uses the same armature but has no pole bone."
            )
        elif pole_target.pose.bones.get(
            constraint.pole_subtarget
        ) is None:
            problems.append(
                'Pole target bone "{}" does not exist.'.format(
                    constraint.pole_subtarget
                )
            )
        elif constraint.pole_subtarget == pose_bone.name:
            problems.append(
                "Pole target points to the constrained bone itself."
            )

    chain_count = int(constraint.chain_count)

    if chain_count < 0:
        problems.append("IK chain length is negative.")

    if chain_count > 0:
        available = 1
        parent = pose_bone.parent

        while parent is not None:
            available += 1
            parent = parent.parent

        if chain_count > available:
            problems.append(
                "IK chain length {} exceeds available chain length {}.".format(
                    chain_count,
                    available,
                )
            )

    return problems
