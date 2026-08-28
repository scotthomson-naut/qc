# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Driver Validation"
DESCRIPTION = (
        "Checks object, object-data, and shape-key drivers for invalid "
        "expressions, missing targets, and invalid target data paths."
    )
WHY = "Broken drivers can silently stop rig controls and corrective behavior."


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
            "can_auto_fix": bool,
        }
    """
    failures = find_driver_issues()
    issues = []

    for owner_name, data in sorted(failures.items()):
        for driver_data in data.get("drivers", []):
            issues.append(
                '{} driver "{}[{}]": {}.'.format(
                    owner_name,
                    driver_data.get("data_path", ""),
                    driver_data.get("array_index", 0),
                    "; ".join(
                        driver_data.get("problems", [])
                    ),
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

def find_driver_issues(objects=None):
    if objects is None:
        objects = bpy.context.scene.objects

    failures = {}

    for obj in get_qc_objects(objects):
        inspect_driver_owner(
            obj,
            obj.name,
            failures,
        )

        data = getattr(obj, "data", None)

        if data is not None:
            inspect_driver_owner(
                data,
                "{} / data".format(obj.name),
                failures,
            )

            shape_keys = getattr(
                data,
                "shape_keys",
                None,
            )

            if shape_keys is not None:
                inspect_driver_owner(
                    shape_keys,
                    "{} / shape_keys".format(
                        obj.name
                    ),
                    failures,
                )

    return failures


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def inspect_driver_owner(
        owner,
        owner_name,
        failures,
    ):
    animation_data = getattr(
        owner,
        "animation_data",
        None,
    )

    if animation_data is None:
        return

    drivers = getattr(
        animation_data,
        "drivers",
        None,
    )

    if not drivers:
        return

    failed_drivers = []

    for fcurve in drivers:
        problems = validate_driver_fcurve(
            fcurve
        )

        if problems:
            failed_drivers.append({
                "data_path": fcurve.data_path,
                "array_index": fcurve.array_index,
                "problems": problems,
            })

    if failed_drivers:
        failures[owner_name] = {
            "drivers": failed_drivers,
        }


def validate_driver_fcurve(fcurve):
    problems = []
    driver = fcurve.driver

    if not fcurve.data_path:
        problems.append("Data path is empty.")

    if not getattr(driver, "is_valid", True):
        problems.append("Driver is marked invalid.")

    if (
        driver.type == "SCRIPTED"
        and not driver.expression.strip()
    ):
        problems.append(
            "Scripted driver expression is empty."
        )

    for variable in driver.variables:
        if not variable.targets:
            problems.append(
                'Variable "{}" has no targets.'.format(
                    variable.name
                )
            )
            continue

        for target_index, target in enumerate(
            variable.targets
        ):
            if target.id is None:
                problems.append(
                    'Variable "{}" target {} has no ID.'.format(
                        variable.name,
                        target_index,
                    )
                )
                continue

            data_path = getattr(
                target,
                "data_path",
                "",
            )

            if (
                variable.type in {
                    "SINGLE_PROP",
                    "CONTEXT_PROP",
                }
                and not data_path
            ):
                problems.append(
                    'Variable "{}" target {} has no data path.'.format(
                        variable.name,
                        target_index,
                    )
                )

            if data_path:
                try:
                    target.id.path_resolve(
                        data_path
                    )
                except Exception:
                    problems.append(
                        'Variable "{}" target {} has invalid data path "{}".'.format(
                            variable.name,
                            target_index,
                            data_path,
                        )
                    )

            bone_target = getattr(
                target,
                "bone_target",
                "",
            )

            if (
                bone_target
                and getattr(
                    target.id,
                    "type",
                    None,
                ) == "ARMATURE"
                and target.id.pose.bones.get(
                    bone_target
                ) is None
            ):
                problems.append(
                    'Variable "{}" target bone "{}" does not exist.'.format(
                        variable.name,
                        bone_target,
                    )
                )

    return problems
