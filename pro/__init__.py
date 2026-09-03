"""Scriptronaut QC Checker Pro Blender Extension entry point."""

bl_info = {
    "name": "Scriptronaut QC Checker Pro",
    "author": "Scriptronaut",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "3D View > Sidebar > Scriptronaut",
    "description": "Production-focused scene and asset QC checks for Blender.",
    "category": "3D View",
}

from .scriptronaut_qc.registration import (
    register as register_core,
    unregister as unregister_core,
)

from .scriptronaut_qc_pro.registration import (
    register as register_pro,
    unregister as unregister_pro,
)


def register():
    register_core()
    register_pro()


def unregister():
    unregister_pro()
    unregister_core()


__all__ = (
    "register",
    "unregister",
)
