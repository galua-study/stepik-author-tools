"""Compatibility imports for the read-only client and snapshot reader."""

from .api.client import NoRedirect as NoRedirect
from .api.client import StepikClient as StepikClient
from .serialization.schemas import normalize_snapshot as normalize_snapshot
from .serialization.schemas import read_snapshot as read_snapshot
