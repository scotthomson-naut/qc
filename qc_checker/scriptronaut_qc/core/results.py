"""Scriptronaut QC Checks internal module."""

from typing import Any

def normalize_check_result(result):
    """
    Converts a QC check result into a standard dictionary format.

    Supported return types:
        None
        str
        list
        tuple
        dict

    Returns:
        dict: Dictionary containing at least an "issues" key.
    """
    if result is None:
        return {"issues": []}

    if isinstance(result, str):
        return {"issues": [result]}

    if isinstance(result, (list, tuple)):
        return {"issues": list(result)}

    if isinstance(result, dict):
        if "issues" not in result:
            result["issues"] = []
        return result

    return {"issues": [str(result)]}

def get_issues_from_result(result_data):
    """
    Extracts the issues list from normalized result data.

    Args:
        result_data (dict): Normalized QC result.

    Returns:
        list[str]: List of issue strings.
    """
    issues = result_data.get("issues", [])

    if issues is None:
        return []

    if isinstance(issues, str):
        return [issues]

    if isinstance(issues, (list, tuple)):
        return list(issues)

    return [str(issues)]

def get_filtered_result_for_object(
        result_data,
        object_name,
    ):
    """
    Returns a copy of QC result data containing only
    one failed object.

    This lets existing fix(result_data) implementations
    fix a single object without modification.
    """
    filtered_result = dict(
        result_data
    )

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        return filtered_result

    if object_name not in failed_objects:
        filtered_result[
            "failed_objects"
        ] = {}

        return filtered_result

    filtered_result[
        "failed_objects"
    ] = {
        object_name:
            failed_objects[
                object_name
            ]
    }

    return filtered_result
