"""Scriptronaut QC Checks internal module."""

import importlib.util
from types import ModuleType

def load_module_from_path(module_name, script_path):
    """
    Loads a Python module from a file path.

    Args:
        module_name (str): Temporary name to assign to the module.
        script_path (str): Full path to the Python script.

    Returns:
        module: The imported Python module.
    """
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
