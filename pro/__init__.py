"""Scriptronaut QC Checker Pro Blender Extension entry point."""

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
