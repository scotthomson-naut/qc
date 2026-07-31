"""Utilities for dynamically loading QC check modules."""

import importlib.util
import os
import sys
from types import ModuleType
from .settings import resolve_settings


def load_module_from_path(
    module_name: str,
    script_path: str,
) -> ModuleType:
    """
    Load a Python module from a file path.

    Shared QC framework helpers are injected into the module namespace
    before its source code is executed.

    Args:
        module_name:
            Temporary unique name assigned to the loaded module.

        script_path:
            Full path to the QC check script.

    Returns:
        The loaded Python module.

    Raises:
        FileNotFoundError:
            When the script does not exist.

        ImportError:
            When Python cannot create or execute the module specification.
    """
    script_path = os.path.abspath(
        script_path
    )

    if not os.path.isfile(script_path):
        raise FileNotFoundError(
            "QC script does not exist: {}".format(
                script_path
            )
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        script_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            "Could not create an import specification for: {}".format(
                script_path
            )
        )

    module = importlib.util.module_from_spec(
        spec
    )

    # Make shared framework helpers available inside QC modules.
    module.resolve_settings = resolve_settings

    # Register before execution so imports performed by the module can
    # resolve the module while it is initializing.
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(
            module
        )

    except Exception:
        # Do not retain a partially initialized module.
        sys.modules.pop(
            module_name,
            None,
        )
        raise

    return module
