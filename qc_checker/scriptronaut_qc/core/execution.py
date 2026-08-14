"""Scriptronaut QC Checks internal module."""

import inspect
import os
import time
import traceback
from typing import Any

from ..utils.json_io import result_summary_to_json
from .preferences import get_check_id_for_item, get_check_preferences, module_has_settings
from .results import normalize_check_result, get_issues_from_result
from ..utils.json_io import result_data_to_json
from ..utils.module_loader import load_module_from_path
from ..utils.time_utils import format_elapsed_time


def call_check_main(
        module,
        check_id,
    ):
    """
    Runs a check's main(), injects preferences when supported,
    and prints its execution time.

    Returns:
        Any:
            Raw result returned by the check.
    """
    main_function = getattr(
        module,
        "main",
        None,
    )

    if not callable(main_function):
        raise AttributeError(
            "QC module has no callable main() function."
        )

    parameters = inspect.signature(
        main_function
    ).parameters

    preferences = get_check_preferences(
        check_id,
        module,
    )

    start_time = time.perf_counter()

    try:
        if "preferences" in parameters:
            result = main_function(
                preferences=preferences
            )
        else:
            result = main_function()

    finally:
        elapsed = (
            time.perf_counter()
            - start_time
        )

        check_name = getattr(
            module,
            "LABEL",
            check_id,
        )

        print(
            "{:<40} {:>15}".format(
                str(check_name),
                format_elapsed_time(elapsed),
            )
        )

    return result


def call_check_fix(
        module,
        check_id,
        result_data=None,
        require_result_data=False,
    ):
    """
    Runs a check's fix() while supporting both current and legacy checks.

    Preferences are passed only when fix() explicitly declares a
    ``preferences`` argument. Result data is supplied by keyword when the
    function declares ``result_data`` and otherwise positionally when the
    function has a compatible positional argument.
    """
    fix_function = getattr(module, "fix", None)

    if not callable(fix_function):
        raise AttributeError("QC module has no callable fix() function.")

    signature = inspect.signature(fix_function)
    parameters = signature.parameters
    preferences = get_check_preferences(check_id, module)

    args = []
    kwargs = {}

    if "result_data" in parameters:
        kwargs["result_data"] = result_data
    else:
        positional_parameters = [
            parameter
            for parameter in parameters.values()
            if parameter.kind in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
            and parameter.name != "preferences"
        ]

        if positional_parameters:
            args.append(result_data)
        elif require_result_data:
            raise TypeError(
                "This fix() does not accept result_data and cannot safely "
                "operate on only one object."
            )

    if "preferences" in parameters:
        kwargs["preferences"] = preferences

    return fix_function(*args, **kwargs)


def rerun_qc_check_item(item):
    """
    Re-runs one QC check item and updates its stored result.
    """
    script_path = item.script_path

    if not os.path.isfile(
        script_path
    ):
        return False

    try:
        module = load_module_from_path(
            "qc_rerun_{}".format(
                item.name
            ),
            script_path,
        )

        main_function = getattr(
            module,
            "main",
            None,
        )

        if not callable(
            main_function
        ):
            return False

        check_id = get_check_id_for_item(
            item
        )

        raw_result = call_check_main(
            module,
            check_id,
        )

        result_data = (
            normalize_check_result(
                raw_result
            )
        )

        result_data[
            "check_name"
        ] = item.name

        result_data[
            "script_path"
        ] = script_path

        issues = (
            get_issues_from_result(
                result_data
            )
        )

        item.result_data = (
            result_data_to_json(
                result_data
            )
        )

        item.result_summary = (
            result_summary_to_json(
                result_data
            )
        )

        item.has_fix = callable(
            getattr(
                module,
                "fix",
                None,
            )
        )

        item.has_settings = module_has_settings(
            module
        )

        if issues:
            item.status = "FAIL"
            item.issues = "\n".join(
                str(issue)
                for issue in issues
            )

        else:
            item.status = "PASS"
            item.issues = (
                "No issues found."
            )

        return True

    except Exception:
        print(
            traceback.format_exc()
        )
        return False
