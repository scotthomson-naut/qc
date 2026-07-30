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

class SCRIPTRONAUT_OT_QC_SelectAll(Operator):
    """
    Selects all QC checks.
    """
    bl_idname = "scriptronaut.qc_select_all"
    bl_label = "Select All Checks"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_checks:
            item.selected = True

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_SelectNone(Operator):
    """
    Deselects all QC checks.
    """
    bl_idname = "scriptronaut.qc_select_none"
    bl_label = "Select None"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_checks:
            item.selected = False

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_SelectCritical(Operator):
    """
    Select only Critical QC checks.
    """
    bl_idname = "scriptronaut.qc_select_critical"
    bl_label = "Select Critical Checks"
    bl_description = "Select only Critical QC checks"

    def execute(self, context):

        checks = context.scene.scriptronaut_qc_checks

        for item in checks:
            item.selected = (
                item.severity == "critical"
            )

        return {"FINISHED"}

class SCRIPTRONAUT_OT_QC_RunSelected(Operator):
    """
    Executes all selected QC scripts and stores the results.
    """
    bl_idname = "scriptronaut.qc_run_selected"
    bl_label = "Run Selected Checks"

    def execute(self, context):
        
        scene = context.scene
        checks = scene.scriptronaut_qc_checks
        ran_any = False

        constants.QC_IS_RUNNING = True

        try:
            for item in checks:
                if not item.selected:
                    continue

                ran_any = True
                item.status = "RUNNING"
                item.issues = "Running..."
                item.result_data = "{}"
                script_path = item.script_path

                if not os.path.isfile(script_path):
                    result_data = {
                        "issues": ["Script does not exist:\n{}".format(script_path)],
                        "script_path": script_path,
                    }
                    item.status = "FAIL"
                    item.issues = "\n".join(result_data["issues"])
                    item.result_data = result_data_to_json(result_data)
                    continue

                try:
                    module = load_module_from_path(
                        "qc_{}".format(item.name),
                        script_path,
                    )

                    main_function = getattr(module, "main", None)
                    if not callable(main_function):
                        result_data = {
                            "issues": ["Missing main() function."],
                            "script_path": script_path,
                        }
                        item.status = "FAIL"
                        item.issues = "\n".join(result_data["issues"])
                        item.result_data = result_data_to_json(result_data)
                        continue

                    raw_result = call_check_main(
                        module,
                        get_check_id_for_item(item),
                    )
                    result_data = normalize_check_result(raw_result)
                    result_data["check_name"] = item.name
                    result_data["script_path"] = script_path
                    issues = get_issues_from_result(result_data)

                    item.result_data = result_data_to_json(result_data)
                    item.has_fix = callable(getattr(module, "fix", None))
                    item.has_settings = module_has_settings(module)

                    if issues:
                        item.status = "FAIL"
                        item.issues = "\n".join(str(issue) for issue in issues)
                    else:
                        item.status = "PASS"
                        item.issues = "No issues found."

                except Exception:
                    result_data = {
                        "issues": [traceback.format_exc()],
                        "check_name": item.name,
                        "script_path": script_path,
                    }
                    item.status = "FAIL"
                    item.issues = "\n".join(result_data["issues"])
                    item.result_data = result_data_to_json(result_data)

        finally:
            constants.QC_IS_RUNNING = False

        if not ran_any:
            self.report({"WARNING"}, "No checks selected.")
            return {"CANCELLED"}

        set_qc_run_timestamp(context)
        refresh_issues_display(context)
        rebuild_failed_objects(context)
        return {"FINISHED"}

CLASSES = (
    SCRIPTRONAUT_OT_QC_SelectAll,
    SCRIPTRONAUT_OT_QC_SelectNone,
    SCRIPTRONAUT_OT_QC_SelectCritical,
    SCRIPTRONAUT_OT_QC_RunSelected,
)
