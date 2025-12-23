from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sidecar_handler.sidecar_links import (
    AUDIO_EXTS_DEFAULT,
    COVER_CANDIDATES_DEFAULT,
    attach_sidecars,
    cleanup_broken_sidecar_links,
)


def _configure_logging(verbosity: int) -> logging.Logger:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("sidecar-links")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sidecar-links")
    p.add_argument("root", type=Path, help="Root folder to scan")
    p.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity")

    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("attach", help="Attach lyrics and/or cover as sidecar links")
    a.add_argument(
        "--link-type",
        choices=["auto", "symlink", "hardlink", "copy"],
        default="auto",
        help="How to create sidecars (auto tries symlink then hardlink then copy)",
    )
    a.add_argument(
        "--conflict",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help="What to do if the destination sidecar already exists",
    )
    a.add_argument(
        "--no-lyrics",
        action="store_true",
        help="Do not attach .lrc per-audio sidecars",
    )
    a.add_argument(
        "--no-cover",
        action="store_true",
        help="Do not attach folder-level cover.jpg/png sidecar",
    )
    a.add_argument(
        "--audio-ext",
        action="append",
        default=list(AUDIO_EXTS_DEFAULT),
        help="Audio extension to include (repeatable). Default covers common formats.",
    )
    a.add_argument(
        "--cover-candidate",
        action="append",
        default=list(COVER_CANDIDATES_DEFAULT),
        help="Cover filenames to look for within each directory (repeatable)",
    )

    c = sub.add_parser("cleanup", help="Remove broken sidecar symlinks")
    c.add_argument(
        "--no-lyrics",
        action="store_true",
        help="Do not remove broken .lrc links",
    )
    c.add_argument(
        "--no-cover",
        action="store_true",
        help="Do not remove broken cover.jpg/png links",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logger = _configure_logging(args.verbose)

    root: Path = args.root
    if not root.exists():
        logger.error("Root does not exist: %s", root)
        return 2

    if args.cmd == "attach":
        stats = attach_sidecars(
            root=root,
            link_type=args.link_type,
            conflict=args.conflict,
            audio_exts=args.audio_ext,
            cover_candidates=args.cover_candidate,
            attach_lyrics=not args.no_lyrics,
            attach_cover=not args.no_cover,
            logger=logger,
        )
        logger.info(
            "Done: processed_audio=%d created_lyrics=%d created_covers=%d skipped=%d errors=%d",
            stats.processed_audio,
            stats.created_lyrics,
            stats.created_covers,
            stats.skipped,
            stats.errors,
        )
        return 1 if stats.errors else 0

    stats = cleanup_broken_sidecar_links(
        root=root,
        remove_lyrics=not args.no_lyrics,
        remove_cover=not args.no_cover,
        logger=logger,
    )
    logger.info(
        "Done: removed_broken_links=%d skipped=%d errors=%d",
        stats.removed_broken_links,
        stats.skipped,
        stats.errors,
    )
    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
