"""Scriptronaut QC Checks selection operators."""

import bpy

from bpy.props import (
    IntProperty,
    StringProperty,
)
from bpy.types import Operator

from ..core.selection import (
    select_mesh_components,
    select_object,
)
from ..utils.json_io import (
    result_data_from_json,
)


class SCRIPTRONAUT_OT_QC_SelectObject(
    Operator
):
    """
    Selects a failed object and optionally its failed mesh components.

    When component-selection metadata is available, the operator enters
    Edit Mode and selects the reported vertices, edges, or faces.

    If the scene changed after the QC run, component indices may be stale.
    In that case, only the object is selected.
    """

    bl_idname = (
        "scriptronaut.qc_select_object"
    )

    bl_label = (
        "Select QC Failure"
    )

    bl_description = (
        "Select the failed object or its failed mesh components"
    )

    object_name: StringProperty(
        name="Object Name",
        default="",
    )

    check_index: IntProperty(
        name="Check Index",
        default=-1,
    )

    def execute(
        self,
        context,
    ):
        obj = bpy.data.objects.get(
            self.object_name
        )

        if obj is None:
            self.report(
                {"ERROR"},
                'Object "{}" no longer exists.'.format(
                    self.object_name
                ),
            )

            return {"CANCELLED"}

        selection_data = (
            self.get_component_selection_data(
                context
            )
        )

        # -----------------------------------------------------
        # Component selection
        # -----------------------------------------------------

        if isinstance(
            selection_data,
            dict,
        ):
            settings = (
                context.scene
                .scriptronaut_qc_settings
            )

            '''
            # Component indices belong to the mesh state that existed
            # when the check was run. Do not use them after scene edits.
            if settings.scene_modified_since_qc:
                selected = select_object(
                    context,
                    obj,
                )

                if not selected:
                    self.report(
                        {"ERROR"},
                        (
                            'Could not select object "{}".'
                        ).format(
                            obj.name
                        ),
                    )

                    return {"CANCELLED"}

                self.report(
                    {"WARNING"},
                    (
                        "The scene changed after the last QC run. "
                        "The object was selected, but its mesh "
                        "components were not selected. Run the "
                        "check again to refresh the component data."
                    ),
                )

                return {"FINISHED"}
            '''

            success, message = (
                select_mesh_components(
                    context=context,
                    obj=obj,
                    selection_data=selection_data,
                )
            )

            if success:
                self.report(
                    {"INFO"},
                    message,
                )

                return {"FINISHED"}

            # Component metadata may no longer match the mesh even
            # when the global dirty flag was not triggered.
            selected = select_object(
                context,
                obj,
            )

            if not selected:
                self.report(
                    {"ERROR"},
                    (
                        "{} Could not select object "
                        '"{}".'
                    ).format(
                        message,
                        obj.name,
                    ),
                )

                return {"CANCELLED"}

            self.report(
                {"WARNING"},
                (
                    "{} The object was selected instead."
                ).format(
                    message
                ),
            )

            return {"FINISHED"}

        # -----------------------------------------------------
        # Object-only selection
        # -----------------------------------------------------

        success, message = select_object(
            context,
            obj,
        )

        if not success:
            self.report(
                {"WARNING"},
                message,
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            message,
        )

        return {"FINISHED"}

    def get_component_selection_data(
        self,
        context,
    ):
        """
        Gets the component-selection metadata stored by the selected check.

        Returns:
            dict | None:
                A dictionary such as:

                {
                    "mode": "FACE",
                    "indices": [1, 4, 8],
                }

                or None when the check does not provide component data.
        """
        checks = (
            context.scene
            .scriptronaut_qc_checks
        )

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            return None

        check_item = checks[
            self.check_index
        ]

        result_data = result_data_from_json(
            check_item.result_data
        )

        if not isinstance(
            result_data,
            dict,
        ):
            return None

        failed_objects = result_data.get(
            "failed_objects",
            {},
        )

        if not isinstance(
            failed_objects,
            dict,
        ):
            return None

        object_data = failed_objects.get(
            self.object_name,
            {},
        )

        if not isinstance(
            object_data,
            dict,
        ):
            return None

        selection_data = object_data.get(
            "selection"
        )

        if not isinstance(
            selection_data,
            dict,
        ):
            return None

        return selection_data


class SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject(
    Operator
):
    """
    Selects the currently highlighted failed object in Object mode.
    """

    bl_idname = (
        "scriptronaut.qc_select_current_failed_object"
    )

    bl_label = (
        "Select Failed Object"
    )

    bl_description = (
        "Select the currently highlighted failed object"
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
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            self.report(
                {"WARNING"},
                "No failed object is selected.",
            )

            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            self.report(
                {"ERROR"},
                'Object "{}" no longer exists.'.format(
                    object_name
                ),
            )

            return {"CANCELLED"}

        success, message = select_object(
            context,
            obj,
        )

        if not success:
            self.report(
                {"WARNING"},
                message,
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            message,
        )

        return {"FINISHED"}


CLASSES = (
    SCRIPTRONAUT_OT_QC_SelectObject,
    SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject,
)