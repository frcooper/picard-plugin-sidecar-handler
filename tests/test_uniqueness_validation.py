from __future__ import annotations

from pathlib import Path

import pytest

from sidecar_handler.config import SidecarRule, ConfigError
from sidecar_handler.engine import plan_sidecar_ops


def test_duplicate_resolved_mask_is_error(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    src_audio = src_dir / "old.flac"
    dst_audio = dst_dir / "new.flac"
    src_audio.write_bytes(b"")
    dst_audio.write_bytes(b"")

    rules = [
        SidecarRule(type_label="a", embedded=False, enabled=True, filemask="{base}-front.jpg"),
        SidecarRule(type_label="b", embedded=False, enabled=True, filemask="{base}-front.jpg"),
    ]

    with pytest.raises(ConfigError):
        plan_sidecar_ops(src_audio_path=src_audio, dst_audio_path=dst_audio, rules=rules)
