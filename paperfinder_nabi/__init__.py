"""Utilities for gathering and ranking research papers."""

from .core import (
    fetch_recent_entries_single,
    fetch_recent_entries_multi,
    score_papers,
    run,
)

__all__ = [
    "fetch_recent_entries_single",
    "fetch_recent_entries_multi",
    "score_papers",
    "run",
]

__version__ = "0.1.0"
