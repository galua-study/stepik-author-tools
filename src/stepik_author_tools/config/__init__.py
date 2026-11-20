"""Packaged defaults and explicit per-project TOML overrides."""

from .settings import Settings, load_settings

__all__ = ["Settings", "load_settings"]
