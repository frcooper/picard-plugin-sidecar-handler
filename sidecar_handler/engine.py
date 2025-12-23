from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

from .config import ConfigError, SidecarRule, validate_rules_static
from .logutil import get_logger


ConflictPolicy = Literal["skip", "overwrite", "rename"]

_logger = get_logger(__name__)


@dataclass(frozen=True)
class FileOp:
    src: Path
    dst: Path
    mode: Literal["move", "copy"]
    conflict: ConflictPolicy


@dataclass(frozen=True)
class TreeOp:
    src_dir: Path
    dst_dir: Path
    mode: Literal["move", "copy"]
    conflict: ConflictPolicy


Op = FileOp | TreeOp


def _base_no_ext(path: Path) -> str:
    return path.stem


def _expand(mask: str, base: str) -> str:
    return mask.replace("{base}", base)


def _normalize_mask(mask: str) -> str:
    return mask.replace("\\", "/")


def validate_rules_for_audio(rules: Iterable[SidecarRule], dst_base: str) -> None:
    """Per-audio validation: expanded destination masks must be unique."""

    validate_rules_static(rules)

    seen: dict[str, SidecarRule] = {}
    for rule in rules:
        if not rule.enabled or rule.embedded:
            continue
        expanded = _expand(_normalize_mask(rule.filemask), dst_base)
        if expanded in seen:
            raise ConfigError(
                "Duplicate resolved filemask for this audio file: "
                f"{expanded!r} (rules: {seen[expanded].type_label!r} and {rule.type_label!r})"
            )
        seen[expanded] = rule


def plan_sidecar_ops(
    *,
    src_audio_path: os.PathLike[str] | str,
    dst_audio_path: os.PathLike[str] | str,
    rules: Sequence[SidecarRule],
    metadata: Mapping[str, object] | None = None,
    conflict: ConflictPolicy = "rename",
) -> list[Op]:
    src_audio = Path(src_audio_path)
    dst_audio = Path(dst_audio_path)

    src_dir = src_audio.parent
    dst_dir = dst_audio.parent

    src_base = _base_no_ext(src_audio)
    dst_base = _base_no_ext(dst_audio)

    validate_rules_for_audio(rules, dst_base)

    ops: list[Op] = []

    for rule in rules:
        if not rule.enabled:
            continue

        if rule.embedded:
            tag = rule.embedded_tag
            if metadata is not None and tag:
                if tag not in metadata or not metadata.get(tag):
                    raise ConfigError(f"Embedded tag missing or empty: {tag}")
            _logger.debug("Embedded sidecar handled: %s", rule.type_label)
            continue

        mask = _normalize_mask(rule.filemask)

        if rule.is_tree:
            # '{base}.extras/**' -> directory name '{base}.extras'
            dir_template = mask[:-3]
            src_dirname = _expand(dir_template, src_base)
            dst_dirname = _expand(dir_template, dst_base)

            src_tree = (src_dir / src_dirname).resolve()
            src_root = src_dir.resolve()
            try:
                src_tree.relative_to(src_root)
            except ValueError as exc:
                raise ConfigError(f"Tree path escapes source directory: {src_tree}") from exc

            if not src_tree.exists():
                continue

            dst_tree = (dst_dir / dst_dirname)
            ops.append(TreeOp(src_dir=src_tree, dst_dir=dst_tree, mode=rule.move_mode, conflict=conflict))
            continue

        # File glob relative to src_dir.
        src_pattern = str(src_dir / _expand(mask, src_base))
        matches = sorted({Path(p) for p in glob.glob(src_pattern, recursive=True)})
        if not matches:
            continue

        for src_match in matches:
            src_match = src_match.resolve()
            src_root = src_dir.resolve()
            try:
                rel = src_match.relative_to(src_root)
            except ValueError as exc:
                raise ConfigError(f"Matched file escapes source directory: {src_match}") from exc

            # Destination path keeps the same relative directory, but rewrites the basename
            # to propagate renames deterministically.
            dst_name = rel.name.replace(src_base, dst_base)
            dst_path = dst_dir / rel.parent / dst_name

            ops.append(FileOp(src=src_match, dst=dst_path, mode=rule.move_mode, conflict=conflict))

    return ops
