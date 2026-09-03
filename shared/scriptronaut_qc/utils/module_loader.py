"""Utilities for dynamically loading QC check modules."""

import importlib.util
import hashlib
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from .settings import resolve_settings
from ..core.object_filter import (
    get_qc_object,
    get_qc_objects,
    is_object_available_for_qc,
)


def _safe_module_component(
        value: str,
    ) -> str:
    """Return a value that is safe to use as one Python module component."""
    value = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        str(value),
    ).strip("_")

    if not value:
        value = "check"

    if value[0].isdigit():
        value = "_{}".format(value)

    return value


def _find_extension_root(
        script_path: Path,
    ) -> Path | None:
    """Find the extension directory that owns a dynamically loaded script."""
    for directory in (
        script_path.parent,
        *script_path.parents,
    ):
        if (
            (directory / "__init__.py").is_file()
            and (directory / "blender_manifest.toml").is_file()
        ):
            return directory

    return None


def _loaded_package_name(
        package_init: Path,
    ) -> str:
    """Return the already-loaded package whose file is package_init."""
    try:
        expected_path = package_init.resolve()
    except OSError:
        expected_path = package_init.absolute()

    for loaded_name, loaded_module in tuple(sys.modules.items()):
        loaded_file = getattr(loaded_module, "__file__", None)
        if not loaded_file:
            continue

        try:
            loaded_path = Path(loaded_file).resolve()
        except OSError:
            loaded_path = Path(loaded_file).absolute()

        if loaded_path == expected_path:
            return loaded_name

    return ""


def _manifest_extension_id(
        manifest_path: Path,
    ) -> str:
    """Read the extension ID without adding a TOML-version dependency."""
    try:
        manifest_text = manifest_path.read_text(
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return ""

    match = re.search(
        r'^\s*id\s*=\s*["\']([^"\']+)["\']',
        manifest_text,
        re.MULTILINE,
    )

    return match.group(1).strip() if match else ""


def get_dynamic_module_name(
        requested_name: str,
        script_path: str,
    ) -> str:
    """
    Build a deterministic module name inside the owning extension namespace.

    Blender extensions may not register modules such as ``qc_my_check`` at
    Python's top level. External check packs are separate extensions, so the
    namespace is derived from the extension that owns script_path rather than
    from the Core loader package.
    """
    script = Path(script_path).resolve()
    extension_root = _find_extension_root(script)
    namespace = ""

    if extension_root is not None:
        namespace = _loaded_package_name(
            extension_root / "__init__.py"
        )

        if not namespace:
            extension_id = _manifest_extension_id(
                extension_root / "blender_manifest.toml"
            ) or extension_root.name

            # Installed extensions use bl_ext.<repository>.<extension_id>.
            # This fallback is mainly for early loading; normally the owning
            # extension's __init__.py is already present in sys.modules.
            if __package__.startswith("bl_ext."):
                repository_id = _safe_module_component(
                    extension_root.parent.name
                )
                namespace = "bl_ext.{}.{}".format(
                    repository_id,
                    _safe_module_component(extension_id),
                )

    if not namespace:
        # Legacy add-on/development fallback. It remains below the QC
        # framework package instead of creating a top-level module.
        namespace = __package__.rsplit(
            ".utils",
            1,
        )[0]

    path_digest = hashlib.sha1(
        str(script).encode("utf-8")
    ).hexdigest()[:12]

    return "{}._qc_runtime_{}_{}".format(
        namespace,
        _safe_module_component(requested_name),
        path_digest,
    )


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

    qualified_module_name = get_dynamic_module_name(
        module_name,
        script_path,
    )

    spec = importlib.util.spec_from_file_location(
        qualified_module_name,
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
    module.is_object_available_for_qc = is_object_available_for_qc
    module.get_qc_objects = get_qc_objects
    module.get_qc_object = get_qc_object

    # Register before execution so imports performed by the module can
    # resolve the module while it is initializing.
    sys.modules[qualified_module_name] = module

    try:
        spec.loader.exec_module(
            module
        )

    except Exception:
        # Do not retain a partially initialized module.
        sys.modules.pop(
            qualified_module_name,
            None,
        )
        raise

    return module
