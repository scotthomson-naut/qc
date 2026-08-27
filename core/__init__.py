"""Scriptronaut QC Checks Blender Extension entry point."""

from .scriptronaut_qc.registration import register, unregister

__all__ = ("register", "unregister")
