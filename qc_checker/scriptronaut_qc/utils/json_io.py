"""Scriptronaut QC Checks internal module."""

import json
import os
from typing import Any

from ..constants import CHECK_PREFERENCES_FILE, CHECK_SETTINGS_FILE


def load_all_check_preferences():
    """
    Loads the complete check-preferences JSON file.

    Returns:
        dict
    """
    if not os.path.isfile(
        CHECK_PREFERENCES_FILE
    ):
        return {}

    try:
        with open(
            CHECK_PREFERENCES_FILE,
            "r",
            encoding="utf-8",
        ) as json_file:
            data = json.load(
                json_file
            )

    except (
        OSError,
        ValueError,
        TypeError,
    ):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def save_all_check_preferences(preferences):
    """
    Saves the complete check-preferences dictionary.
    """
    folder = os.path.dirname(
        CHECK_PREFERENCES_FILE
    )

    if folder:
        os.makedirs(
            folder,
            exist_ok=True,
        )

    temporary_path = (
        CHECK_PREFERENCES_FILE
        + ".tmp"
    )

    with open(
        temporary_path,
        "w",
        encoding="utf-8",
    ) as json_file:
        json.dump(
            preferences,
            json_file,
            indent=4,
            sort_keys=True,
        )

    os.replace(
        temporary_path,
        CHECK_PREFERENCES_FILE,
    )


def load_check_list(folder_path):
    """
    Loads the optional CHECK_SETTINGS_FILE configuration.

    Args:
        folder_path (str): Root QC modules folder.

    Returns:
        dict: Category names mapped to lists of script names.
              Returns an empty dictionary when the file is missing
              or invalid.
    """
    json_path = os.path.join(folder_path, CHECK_SETTINGS_FILE)

    if not os.path.isfile(json_path):
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as stream:
            data = json.load(stream)

        return data if isinstance(data, dict) else {}

    except Exception:
        print("Could not read QC check list:")
        print(traceback.format_exc())
        return {}


def save_check_list(folder_path, check_list):
    """
    Saves the QC category configuration to CHECK_SETTINGS_FILE.

    Args:
        folder_path (str): Root QC modules directory.
        check_list (dict): Category names mapped to script-name lists.

    Returns:
        tuple[bool, str]: Success state and error message.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return False, "QC modules folder does not exist."

    json_path = os.path.join(folder_path, CHECK_SETTINGS_FILE)

    try:
        with open(json_path, "w", encoding="utf-8") as stream:
            json.dump(check_list, stream, indent=4, sort_keys=True)
        return True, ""
    except Exception:
        return False, traceback.format_exc()


def result_data_to_json(result_data):
    """
    Serializes full QC result data into compact JSON.

    Large component-index arrays can otherwise become dramatically larger
    when pretty printed with indentation.
    """
    try:
        return json.dumps(
            result_data,
            separators=(",", ":"),
        )
    except Exception:
        return json.dumps(
            {
                "issues": [
                    "Result data could not be converted to JSON."
                ],
                "raw_result": str(
                    result_data
                ),
            },
            separators=(",", ":"),
        )


def build_result_summary(result_data):
    """
    Builds the lightweight UI representation of a QC result.

    Full component indices stay in result_data. The summary contains only
    failed object names and the component-selection mode needed by the panel.
    """
    summary = {
        "failed_objects": {},
        "failed_object_count": 0,
    }

    if not isinstance(
        result_data,
        dict,
    ):
        return summary

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        return summary

    for object_name, object_data in (
        failed_objects.items()
    ):
        selection_mode = ""

        if isinstance(
            object_data,
            dict,
        ):
            selection = object_data.get(
                "selection"
            )

            if isinstance(
                selection,
                dict,
            ):
                selection_mode = str(
                    selection.get(
                        "mode",
                        "",
                    )
                ).upper()

        summary[
            "failed_objects"
        ][
            str(
                object_name
            )
        ] = {
            "selection_mode":
                selection_mode,
        }

    summary[
        "failed_object_count"
    ] = len(
        summary[
            "failed_objects"
        ]
    )

    return summary


def result_summary_to_json(result_data):
    """
    Serializes the lightweight UI result summary.
    """
    return json.dumps(
        build_result_summary(
            result_data
        ),
        separators=(",", ":"),
    )


def result_summary_from_json(json_text):
    """
    Deserializes the lightweight UI result summary.
    """
    if not json_text:
        return {
            "failed_objects": {},
            "failed_object_count": 0,
        }

    try:
        result = json.loads(
            json_text
        )
    except Exception:
        result = {}

    if not isinstance(
        result,
        dict,
    ):
        result = {}

    failed_objects = result.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        failed_objects = {}

    return {
        "failed_objects":
            failed_objects,

        "failed_object_count":
            len(
                failed_objects
            ),
    }


def result_data_from_json(json_text):
    """
    Deserializes JSON into QC result data.

    Args:
        json_text (str): JSON string.

    Returns:
        dict: Parsed result dictionary.
    """
    if not json_text:
        return {}

    try:
        return json.loads(json_text)
    except Exception:
        return {}
