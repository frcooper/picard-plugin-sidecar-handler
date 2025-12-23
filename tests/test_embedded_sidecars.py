from __future__ import annotations

from pathlib import Path

import pytest

from sidecar_handler.config import SidecarRule
from sidecar_handler.engine import plan_sidecar_ops


def test_embedded_tag_present_no_fs_ops(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    rules = [SidecarRule(type_label="cover", embedded=True, enabled=True, embedded_tag="coverart")]
    ops = plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules, metadata={"coverart": "x"})
    assert ops == []


def test_embedded_tag_missing_raises(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    rules = [SidecarRule(type_label="cover", embedded=True, enabled=True, embedded_tag="coverart")]

    with pytest.raises(Exception):
        plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules, metadata={})
