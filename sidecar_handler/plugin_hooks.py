from __future__ import annotations

import weakref
from pathlib import Path
from typing import Any

from .config import ConfigError, coerce_rules, default_rules, rules_to_json
from .engine import plan_sidecar_ops
from .fsops import apply_ops


RULES_KEY = "rules_json"
SUPERSEDE_KEY = "supersede_additional_files"
WARNED_KEY = "warned_about_additional_files"


def ensure_plugin_defaults(api) -> None:  # type: ignore[no-untyped-def]
    """Register plugin options so defaults and stored values resolve correctly.

    Picard's ConfigSection is not a dict; options must be registered for
    __getitem__ to return either stored values or defaults.
    """

    api.plugin_config.register_option(RULES_KEY, rules_to_json(default_rules()))
    api.plugin_config.register_option(SUPERSEDE_KEY, False)
    api.plugin_config.register_option(WARNED_KEY, False)


_old_paths: "weakref.WeakKeyDictionary[Any, str]" = weakref.WeakKeyDictionary()


def on_file_pre_save(api, file):  # type: ignore[no-untyped-def]
    """Capture the pre-rename/move path.

    Picard post-save only provides the file object, whose `.filename` is already updated.
    We therefore capture the original filename here to use as the sidecar source.
    """

    try:
        p = getattr(file, "filename", None)
        if p:
            _old_paths[file] = str(p)
    except (TypeError, AttributeError):
        api.logger.debug("Sidecar Handler: failed capturing pre-save filename", exc_info=True)


def on_file_post_save(api, file):  # type: ignore[no-untyped-def]
    """Move/copy sidecars after Picard completes save+rename/move."""

    try:
        dst_path = getattr(file, "filename", None)
        src_path = _old_paths.pop(file, None) or dst_path
        if not src_path or not dst_path:
            return

        ensure_plugin_defaults(api)

        # One-time warning if users have Picard's own additional-files moving enabled.
        if api.plugin_config[SUPERSEDE_KEY] and not api.plugin_config[WARNED_KEY]:
            move_additional = False
            pattern = ""
            try:
                move_additional = bool(api.global_config.setting["move_additional_files"])
                pattern = str(api.global_config.setting["move_additional_files_pattern"])
            except (AttributeError, TypeError):
                pass
            if move_additional and str(pattern).strip():
                api.logger.warning(
                    "Sidecar Handler: Picard 'Move additional files' is enabled; "
                    "disable it to avoid double-moving sidecars."
                )
                api.plugin_config[WARNED_KEY] = True

        rules = coerce_rules(api.plugin_config[RULES_KEY])

        # Best-effort conflict policy: Picard does not expose the per-file decision.
        conflict = "rename"

        meta_map = None
        try:
            meta = getattr(file, "metadata", None)
            if meta is not None:
                meta_map = dict(meta)
        except (TypeError, ValueError):
            meta_map = None

        ops = plan_sidecar_ops(
            src_audio_path=Path(src_path),
            dst_audio_path=Path(dst_path),
            rules=rules,
            metadata=meta_map,
            conflict=conflict,
        )
        apply_ops(ops)

    except ConfigError as exc:
        api.logger.error("Sidecar Handler: configuration error: %s", exc)
    except (OSError, RuntimeError, AttributeError, TypeError, ValueError):
        api.logger.error("Sidecar Handler: processing failed", exc_info=True)
