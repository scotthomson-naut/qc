"""Public Scriptronaut QC pack API.

External check-pack addons should use only this module, rather than importing
private core/ui implementation modules.
"""

from .core.packs import (
    get_registered_check_pack,
    get_registered_check_packs,
    is_check_pack_registered,
    register_check_pack,
    unregister_check_pack,
)


API_VERSION = (1, 0, 0)


def get_api_version():
    """
    Returns the public pack API version.
    """
    return API_VERSION
