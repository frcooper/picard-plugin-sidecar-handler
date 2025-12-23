from __future__ import annotations

"""mbsidecarctl: companion CLI for Sidecar Handler.

Scans a directory tree and can:
- Attach lyrics (per-audio .lrc) and folder-level cover images as links or copies
- Remove broken sidecar symlinks

This is a development utility and is not included in the plugin ZIP.
"""

import argparse
import logging
import sys
from pathlib import Path

# Allow running as a script from the repo without installing a package.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from sidecar_handler.sidecar_links import (
    AUDIO_EXTS_DEFAULT,
    COVER_CANDIDATES_DEFAULT,
    attach_sidecars,
    cleanup_broken_sidecar_links,
)


def _read_version(repo_root: Path) -> str:
    manifest = repo_root / "MANIFEST.toml"
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return "unknown"

    # Prefer tomllib when available.
    try:
        import tomllib  # type: ignore[attr-defined]

        data = tomllib.loads(text)
        v = data.get("version")
        return v if isinstance(v, str) and v else "unknown"
    except Exception:  # noqa: BLE001 - best-effort for a dev utility
        pass

    # Fallback: simple parse
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("version") and "=" in line:
            _, rhs = line.split("=", 1)
            rhs = rhs.strip().strip('"').strip("'")
            if rhs:
                return rhs
    return "unknown"


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
    return logging.getLogger("mbsidecarctl")


def _build_parser(version: str) -> argparse.ArgumentParser:
    desc = (
        f"mbsidecarctl {version} - bulk attach/cleanup of sidecar artifacts. "
        "Attaches per-audio .lrc lyrics and folder-level cover images, or removes broken sidecar symlinks."
    )

    p = argparse.ArgumentParser(prog="mbsidecarctl", description=desc)
    p.add_argument("root", type=Path, help="Root folder to scan")
    p.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity")
    p.add_argument(
        "--version",
        action="version",
        version=f"mbsidecarctl {version}",
        help="Print version and exit",
    )

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
    repo_root = Path(__file__).resolve().parents[1]
    version = _read_version(repo_root)

    args = _build_parser(version).parse_args(argv)
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
