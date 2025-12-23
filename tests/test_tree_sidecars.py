from __future__ import annotations

from pathlib import Path

import pytest

from sidecar_handler.config import SidecarRule
from sidecar_handler.engine import plan_sidecar_ops
from sidecar_handler.fsops import apply_ops


def test_moves_tree_sidecar(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    tree = src_dir / "old.extras"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested" / "a.txt").write_text("a")

    rules = [SidecarRule(type_label="extras", embedded=False, enabled=True, filemask="{base}.extras/**")]
    ops = plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules, conflict="rename")
    apply_ops(ops)

    assert not tree.exists()
    assert (dst_dir / "new.extras" / "nested" / "a.txt").read_text() == "a"


def test_tree_path_escape_refused(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    # Attempts to escape src_dir.
    rules = [SidecarRule(type_label="bad", embedded=False, enabled=True, filemask="../{base}.extras/**")]

    with pytest.raises(Exception):
        plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules)
