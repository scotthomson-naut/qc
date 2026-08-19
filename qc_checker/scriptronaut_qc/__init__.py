"""Internal package for Scriptronaut QC Checks."""

import sys

from . import api as _public_api


# Stable cross-addon import alias.
sys.modules[
    "scriptronaut_qc_api"
] = _public_api
