"""Sidecar Handler plugin (Picard Plugin v3).

Entry point for Picard is `enable(api)`.
Core logic lives in the `sidecar_handler/` package.
"""

from __future__ import annotations

from picard.plugin3.api import PluginApi

from .sidecar_handler.plugin_hooks import on_file_post_save, on_file_pre_save
from .sidecar_handler.options import SidecarHandlerOptionsPage


def enable(api: PluginApi) -> None:
    api.logger.info("Sidecar Handler: plugin enabled")

    api.register_options_page(SidecarHandlerOptionsPage)

    # Two-phase capture to get both old and new paths:
    # - pre-save runs before rename/move
    # - post-save runs after rename/move
    api.register_file_pre_save_processor(on_file_pre_save)
    api.register_file_post_save_processor(on_file_post_save)


def disable() -> None:
    # Best-effort: Picard does not require explicit unregister.
    pass
