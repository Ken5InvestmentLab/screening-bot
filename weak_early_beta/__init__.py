"""Weak+Early five-lane beta system.

This package is intentionally isolated from the production Stable/Sniper/Mega
pipeline.  The frozen selector identifiers remain unchanged; only user-facing
labels live here.
"""

from .config import BETA_IDENTITY, SELECTORS

__all__ = ["BETA_IDENTITY", "SELECTORS"]
