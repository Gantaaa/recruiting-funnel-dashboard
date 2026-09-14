"""Recruiting funnel analytics: load, validate, and compute RecOps KPIs.

``metrics.compute_all`` is the single source of truth for every number that
appears in the spreadsheet, the web dashboard, and the weekly leadership deck.
"""

from .dataset import load, load_default
from .metrics import compute_all

__all__ = ["load", "load_default", "compute_all"]
__version__ = "1.0.0"
