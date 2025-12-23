from __future__ import annotations

import logging
from pathlib import Path

from sidecar_handler.sidecar_links import attach_sidecars, cleanup_broken_sidecar_links


def _logger() -> logging.Logger:
    logger = logging.getLogger("test-sidecar-links")
    logger.addHandler(logging.NullHandler())
    return logger


def test_attach_lyrics_copy_mode(tmp_path: Path) -> None:
    root = tmp_path
    d = root / "album"
    d.mkdir()

    audio = d / "track.flac"
    audio.write_bytes(b"")

    # Source lyrics live elsewhere under root.
    src_store = root / "lyrics"
    src_store.mkdir()
    (src_store / "track.lrc").write_text("lyrics")

    stats = attach_sidecars(
        root=root,
        link_type="copy",
        conflict="overwrite",
        attach_cover=False,
        logger=_logger(),
    )

    assert stats.created_lyrics == 1
    assert (d / "track.lrc").read_text() == "lyrics"


def test_attach_cover_copy_mode(tmp_path: Path) -> None:
    root = tmp_path
    d = root / "album"
    d.mkdir()

    audio = d / "track.flac"
    audio.write_bytes(b"")

    # Cover exists as folder.jpg; attach should create cover.jpg.
    (d / "folder.jpg").write_bytes(b"jpg")

    stats = attach_sidecars(
        root=root,
        link_type="copy",
        conflict="overwrite",
        attach_lyrics=False,
        logger=_logger(),
    )

    assert stats.created_covers == 1
    assert (d / "cover.jpg").read_bytes() == b"jpg"


def test_cleanup_only_removes_broken_symlinks(tmp_path: Path) -> None:
    root = tmp_path
    d = root / "album"
    d.mkdir()

    # Create a broken symlink if permitted on this OS.
    broken = d / "track.lrc"
    try:
        broken.symlink_to(d / "missing.lrc")
    except OSError:
        return

    stats = cleanup_broken_sidecar_links(root=root, logger=_logger())
    assert stats.removed_broken_links == 1
    assert not broken.exists()
