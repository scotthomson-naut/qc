from .core.object_filter import (
    get_current_qc_object_filter_context,
    get_registered_object_filters,
    register_object_filter,
    unregister_object_filter,
)

from .core.features import (
    draw_feature,
    has_feature,
    is_feature_enabled,
    register_feature,
    unregister_feature,
)

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
