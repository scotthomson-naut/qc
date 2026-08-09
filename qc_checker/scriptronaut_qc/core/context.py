"""Scriptronaut QC Checks internal module."""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class QCContext:
    """Convenient access to the collections used by QC operators and UI."""
    context: Any

    @property
    def scene(self):
        return self.context.scene

    @property
    def settings(self):
        return self.scene.scriptronaut_qc_settings

    @property
    def checks(self):
        return self.scene.scriptronaut_qc_checks

    @property
    def failed_objects(self):
        return self.scene.scriptronaut_qc_failed_objects

    @property
    def object_checks(self):
        return self.scene.scriptronaut_qc_object_checks

    @property
    def editor_items(self):
        return self.scene.scriptronaut_qc_editor_items


