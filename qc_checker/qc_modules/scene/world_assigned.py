# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "World Datablock Exists"
DESCRIPTION = (
    "Checks if a World datablock exists"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    result = check_world_exists_and_assigned()
    issues = []

    if not result["is_valid"]:
        issues.extend(result["issues"])

    return {
        "issues": issues,
        "world_data": result,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    fixed = fix_world_exists_and_assigned(result_data)

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

def check_world_exists_and_assigned(scene=None):
    """
    Checks that a World datablock exists and is assigned to the scene.

    Checks:
        1. At least one World datablock exists in the Blender file.
        2. The current scene has a World assigned.
        3. The assigned World is a valid World datablock.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect.
            Defaults to the current scene.

    Returns:
        dict:
        {
            "is_valid": bool,
            "world_count": int,
            "assigned_world": str | None,
            "issues": list[str],
        }
    """
    if scene is None:
        scene = bpy.context.scene

    issues = []

    world_count = len(bpy.data.worlds)

    assigned_world = (
        scene.world.name
        if scene.world is not None
        else None
    )

    # ---------------------------------------------------------
    # Check World datablock exists
    # ---------------------------------------------------------

    if world_count == 0:

        issues.append(
            "No World datablock exists."
        )

    # ---------------------------------------------------------
    # Check World is assigned
    # ---------------------------------------------------------

    if scene.world is None:

        issues.append(
            "No World is assigned to scene '{}'.".format(
                scene.name
            )
        )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    return {
        "is_valid": not issues,
        "world_count": world_count,
        "assigned_world": assigned_world,
        "issues": issues,
    }


# -------------------------
# Fix
# -------------------------

def fix_world_exists_and_assigned(result_data):
    """
    Fixes missing or unassigned World datablocks.

    If no World datablock exists, a new World named "World" is created.

    If World datablocks exist but none is assigned to the current scene,
    the first available World is assigned.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict: Fix result.
    """
    scene = bpy.context.scene
    fixed = []

    # ---------------------------------------------------------
    # Already valid
    # ---------------------------------------------------------

    if scene.world is not None:

        return {
            "issues": [],
            "fixed": [],
            "world": scene.world.name,
        }

    # ---------------------------------------------------------
    # Find or create World
    # ---------------------------------------------------------

    if len(bpy.data.worlds) > 0:

        # Prefer a World actually named "World".
        world = bpy.data.worlds.get("World")

        if world is None:
            world = bpy.data.worlds[0]

    else:

        world = bpy.data.worlds.new(
            name="World"
        )

        world.use_nodes = True

        fixed.append(
            "Created World datablock: {}".format(
                world.name
            )
        )

    # ---------------------------------------------------------
    # Assign World
    # ---------------------------------------------------------

    scene.world = world

    fixed.append(
        "Assigned World '{}' to scene '{}'".format(
            world.name,
            scene.name,
        )
    )

    return {
        "issues": [],
        "fixed": fixed,
        "world": world.name,
    }
