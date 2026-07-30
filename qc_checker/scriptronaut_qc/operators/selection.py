"""Scriptronaut QC Checks internal module."""

import os
import traceback

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty
from bpy.types import Operator

from .. import constants
from ..core.context import QCContext
from ..core import *
from ..properties import SCRIPTRONAUT_PG_CheckSetting
from ..utils import *

class SCRIPTRONAUT_OT_QC_SelectObject(Operator):
    """
    Selects and activates an object associated with a QC issue.
    """
    bl_idname = "scriptronaut.qc_select_object"
    bl_label = "Select QC Object"
    bl_description = "Select this object in the scene"

    object_name: StringProperty(
        name="Object Name",
        default="",
    )

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)

        if obj is None:
            self.report(
                {"ERROR"},
                'Object "{}" no longer exists.'.format(self.object_name),
            )
            return {"CANCELLED"}

        # Ensure the object is visible and selectable.
        try:
            obj.hide_set(False)
        except RuntimeError:
            pass

        obj.hide_viewport = False
        obj.hide_select = False

        # Deselect everything currently selected.
        for selected_obj in context.selected_objects:
            selected_obj.select_set(False)

        # Select and activate the failed object.
        obj.select_set(True)
        context.view_layer.objects.active = obj

        self.report(
            {"INFO"},
            'Selected object: "{}"'.format(obj.name),
        )

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject(
    Operator
):
    bl_idname = (
        "scriptronaut.qc_select_current_failed_object"
    )

    bl_label = (
        "Select Failed Object"
    )

    def execute(
        self,
        context,
    ):
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        failed_objects = (
            scene.scriptronaut_qc_failed_objects
        )

        if (
            settings.failed_object_index < 0
            or
            settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            return {"CANCELLED"}

        for selected_obj in (
            context.selected_objects
        ):
            selected_obj.select_set(
                False
            )

        try:
            obj.hide_set(False)
        except RuntimeError:
            pass

        obj.hide_viewport = False
        obj.hide_select = False

        obj.select_set(
            True
        )

        context.view_layer.objects.active = (
            obj
        )

        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_SelectObject,
    SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject,
)
