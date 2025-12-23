from __future__ import annotations

from pathlib import Path

import pytest

from sidecar_handler.config import SidecarRule
from sidecar_handler.engine import plan_sidecar_ops
from sidecar_handler.fsops import apply_ops


def test_moves_external_file_sidecar(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    (src_dir / "old.lrc").write_text("lyrics")

    rules = [SidecarRule(type_label="lyrics", embedded=False, enabled=True, filemask="{base}.lrc")]
    ops = plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules, conflict="rename")
    apply_ops(ops)

    assert not (src_dir / "old.lrc").exists()
    assert (dst_dir / "new.lrc").read_text() == "lyrics"


@pytest.mark.parametrize("conflict,expected_name", [("skip", "new.lrc"), ("overwrite", "new.lrc"), ("rename", "new (1).lrc")])
def test_conflict_policies(tmp_path: Path, conflict: str, expected_name: str) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    (src_dir / "old.lrc").write_text("from-src")
    (dst_dir / "new.lrc").write_text("already")

    rules = [SidecarRule(type_label="lyrics", embedded=False, enabled=True, filemask="{base}.lrc")]
    ops = plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules, conflict=conflict)  # type: ignore[arg-type]
    apply_ops(ops)

    if conflict == "skip":
        assert (dst_dir / "new.lrc").read_text() == "already"
        assert (src_dir / "old.lrc").read_text() == "from-src"
    elif conflict == "overwrite":
        assert (dst_dir / "new.lrc").read_text() == "from-src"
        assert not (src_dir / "old.lrc").exists()
    else:
        assert (dst_dir / expected_name).read_text() == "from-src"
        assert (dst_dir / "new.lrc").read_text() == "already"
        assert not (src_dir / "old.lrc").exists()
