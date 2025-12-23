from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from .engine import ConflictPolicy, FileOp, TreeOp, Op
from .logutil import get_logger

_logger = get_logger(__name__)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _rename_candidate(path: Path, n: int) -> Path:
    if path.is_dir() or path.suffix == "":
        return path.with_name(f"{path.name} ({n})")
    return path.with_name(f"{path.stem} ({n}){path.suffix}")


def _resolve_conflict(dst: Path, conflict: ConflictPolicy) -> Path | None:
    if not dst.exists():
        return dst

    if conflict == "skip":
        return None

    if conflict == "overwrite":
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
        return dst

    # rename
    for i in range(1, 10_000):
        cand = _rename_candidate(dst, i)
        if not cand.exists():
            return cand
    raise RuntimeError(f"Could not find a free name for {dst}")


def apply_ops(ops: Iterable[Op]) -> None:
    for op in ops:
        if isinstance(op, FileOp):
            _apply_file(op)
        else:
            _apply_tree(op)


def _apply_file(op: FileOp) -> None:
    dst = _resolve_conflict(op.dst, op.conflict)
    if dst is None:
        _logger.info("Skip sidecar (exists): %s", op.dst)
        return

    _ensure_parent(dst)

    if op.mode == "copy":
        shutil.copy2(op.src, dst)
        _logger.info("Copied sidecar: %s -> %s", op.src, dst)
    else:
        shutil.move(str(op.src), str(dst))
        _logger.info("Moved sidecar: %s -> %s", op.src, dst)


def _apply_tree(op: TreeOp) -> None:
    dst = _resolve_conflict(op.dst_dir, op.conflict)
    if dst is None:
        _logger.info("Skip sidecar tree (exists): %s", op.dst_dir)
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if op.mode == "copy":
        shutil.copytree(op.src_dir, dst)
        _logger.info("Copied sidecar tree: %s -> %s", op.src_dir, dst)
    else:
        shutil.move(str(op.src_dir), str(dst))
        _logger.info("Moved sidecar tree: %s -> %s", op.src_dir, dst)
