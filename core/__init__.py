"""Scriptronaut QC Checker Core Blender add-on entry point."""

bl_info = {
    "name": "Scriptronaut QC Checker Core",
    "author": "Scriptronaut",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "3D View > Sidebar > Scriptronaut",
    "description": "Production-focused scene and asset QC checks for Blender.",
    "category": "3D View",
}


def _get_registration_functions():
    """
    Resolve the shared Core registration functions.

    The development product is assembled as:

        qc_checker/
            __init__.py
            scriptronaut_qc/
            checks/

    Keep the import lazy so Blender can inspect bl_info without importing the
    complete QC framework first.

    Prefer the modular registration module used by the current framework.
    Fall back to package-level register/unregister exports for compatibility
    with older Core builds.
    """
    try:
        from .scriptronaut_qc.registration import (
            register as framework_register,
            unregister as framework_unregister,
        )

    except ImportError:
        from .scriptronaut_qc import (
            register as framework_register,
            unregister as framework_unregister,
        )

    return (
        framework_register,
        framework_unregister,
    )


def register():
    """
    Register Scriptronaut QC Checker Core.
    """
    framework_register, _ = (
        _get_registration_functions()
    )

    framework_register()


def unregister():
    """
    Unregister Scriptronaut QC Checker Core.
    """
    _, framework_unregister = (
        _get_registration_functions()
    )

    framework_unregister()


if __name__ == "__main__":
    register()
