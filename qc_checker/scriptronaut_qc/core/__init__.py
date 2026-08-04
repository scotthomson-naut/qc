"""QC framework core services."""

from .context import QCContext
from .preferences import *
from .discovery import *
from .results import *
from .execution import *
from .categories import *
from .callbacks import *
from .runtime import *
from .icons import *

from .selection import (
    select_mesh_components,
    select_object,
)

from .results import result_can_auto_fix