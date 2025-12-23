from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence


LinkType = Literal["auto", "symlink", "hardlink", "copy"]
ConflictPolicy = Literal["skip", "overwrite", "rename"]


AUDIO_EXTS_DEFAULT: tuple[str, ...] = (
    ".flac",
    ".mp3",
    ".m4a",
    ".ogg",
    ".opus",
    ".wav",
    ".aiff",
    ".ape",
    ".wv",
)


COVER_CANDIDATES_DEFAULT: tuple[str, ...] = (
    "cover.jpg",
    "cover.png",
    "folder.jpg",
    "folder.png",
    "front.jpg",
    "front.png",
)


@dataclass(frozen=True)
class AttachStats:
    processed_audio: int = 0
    created_lyrics: int = 0
    created_covers: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass(frozen=True)
class CleanupStats:
    removed_broken_links: int = 0
    skipped: int = 0
    errors: int = 0


def _is_broken_symlink(path: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        _ = path.resolve(strict=True)
        return False
    except FileNotFoundError:
        return True


def _rename_candidate(path: Path, n: int) -> Path:
    if path.suffix:
        return path.with_name(f"{path.stem} ({n}){path.suffix}")
    return path.with_name(f"{path.name} ({n})")


def _resolve_conflict(dst: Path, conflict: ConflictPolicy, logger: logging.Logger) -> Path | None:
    if not dst.exists() and not _is_broken_symlink(dst):
        return dst

    if conflict == "skip":
        logger.debug("Conflict: skip %s", dst)
        return None

    if conflict == "overwrite":
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            try:
                dst.unlink()
            except FileNotFoundError:
                # broken symlink
                dst.unlink(missing_ok=True)  # py3.8+ compat handled by try/except
        return dst

    # rename
    for i in range(1, 10_000):
        cand = _rename_candidate(dst, i)
        if not cand.exists() and not _is_broken_symlink(cand):
            return cand
    raise RuntimeError(f"Unable to find free destination name for {dst}")


def _try_symlink(dst: Path, target: Path) -> None:
    dst.symlink_to(target)


def _try_hardlink(dst: Path, target: Path) -> None:
    os.link(target, dst)


def _copy_file(dst: Path, target: Path) -> None:
    shutil.copy2(target, dst)


def _ensure_parent(dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)


def _create_link_or_copy(
    *,
    dst: Path,
    target: Path,
    link_type: LinkType,
    conflict: ConflictPolicy,
    logger: logging.Logger,
) -> bool:
    target = target.resolve()

    dst2 = _resolve_conflict(dst, conflict, logger)
    if dst2 is None:
        return False

    _ensure_parent(dst2)

    # If destination already exists (rename policy can choose a free name), ensure it is absent now.
    if dst2.exists() or _is_broken_symlink(dst2):
        raise RuntimeError(f"Destination not free after conflict resolution: {dst2}")

    if link_type == "symlink":
        _try_symlink(dst2, target)
        return True

    if link_type == "hardlink":
        _try_hardlink(dst2, target)
        return True

    if link_type == "copy":
        _copy_file(dst2, target)
        return True

    # auto
    try:
        _try_symlink(dst2, target)
        return True
    except OSError as exc:
        logger.debug("Symlink failed (%s); trying hardlink/copy", exc)

    try:
        _try_hardlink(dst2, target)
        return True
    except OSError as exc:
        logger.debug("Hardlink failed (%s); falling back to copy", exc)

    _copy_file(dst2, target)
    return True


def _iter_audio_files(root: Path, audio_exts: Sequence[str]) -> Iterable[Path]:
    exts = {e.lower() for e in audio_exts}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in exts:
            yield path


def _index_lyrics_files(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for p in root.rglob("*.lrc"):
        if not p.is_file():
            continue
        index.setdefault(p.stem.lower(), []).append(p)
    return index


def _find_lyrics_for_audio(
    *,
    audio: Path,
    lyrics_index: dict[str, list[Path]],
) -> Path | None:
    # Prefer local sidecar (already in place).
    candidate = audio.with_suffix(".lrc")
    if candidate.exists():
        return candidate

    # Otherwise, look anywhere under root for a unique stem match.
    matches = lyrics_index.get(audio.stem.lower(), [])
    if len(matches) == 1:
        return matches[0]
    return None


def _find_cover_in_dir(folder: Path, candidates: Sequence[str]) -> Path | None:
    for name in candidates:
        p = folder / name
        if p.exists() and p.is_file():
            return p
    return None


def attach_sidecars(
    *,
    root: Path,
    link_type: LinkType = "auto",
    conflict: ConflictPolicy = "skip",
    audio_exts: Sequence[str] = AUDIO_EXTS_DEFAULT,
    cover_candidates: Sequence[str] = COVER_CANDIDATES_DEFAULT,
    attach_lyrics: bool = True,
    attach_cover: bool = True,
    logger: logging.Logger,
) -> AttachStats:
    processed_audio = 0
    created_lyrics = 0
    created_covers = 0
    skipped = 0
    errors = 0

    cover_done_dirs: set[Path] = set()
    lyrics_index = _index_lyrics_files(root) if attach_lyrics else {}

    for audio in _iter_audio_files(root, audio_exts):
        processed_audio += 1

        if attach_lyrics:
            try:
                # Only create link if we can find a lyrics source.
                src_lrc = _find_lyrics_for_audio(audio=audio, lyrics_index=lyrics_index)
                if src_lrc is None:
                    logger.debug("No lyrics for %s", audio)
                else:
                    dst_lrc = audio.with_suffix(".lrc")
                    if dst_lrc.resolve() == src_lrc.resolve():
                        # Already the same file
                        logger.debug("Lyrics already attached: %s", dst_lrc)
                    else:
                        if _create_link_or_copy(
                            dst=dst_lrc,
                            target=src_lrc,
                            link_type=link_type,
                            conflict=conflict,
                            logger=logger,
                        ):
                            created_lyrics += 1
                            logger.info("Attached lyrics: %s -> %s", dst_lrc, src_lrc)
                        else:
                            skipped += 1
            except (OSError, RuntimeError) as exc:
                errors += 1
                logger.error("Failed attaching lyrics for %s: %s", audio, exc)

        if attach_cover:
            folder = audio.parent
            if folder in cover_done_dirs:
                continue
            cover_done_dirs.add(folder)

            try:
                src_cover = _find_cover_in_dir(folder, cover_candidates)
                if src_cover is None:
                    logger.debug("No cover candidates in %s", folder)
                    continue

                # Attach as folder-level cover.{ext} based on source cover extension.
                dst_cover = folder / f"cover{src_cover.suffix.lower()}"
                if dst_cover.resolve() == src_cover.resolve():
                    logger.debug("Cover already present: %s", dst_cover)
                    continue

                if _create_link_or_copy(
                    dst=dst_cover,
                    target=src_cover,
                    link_type=link_type,
                    conflict=conflict,
                    logger=logger,
                ):
                    created_covers += 1
                    logger.info("Attached cover: %s -> %s", dst_cover, src_cover)
                else:
                    skipped += 1

            except (OSError, RuntimeError) as exc:
                errors += 1
                logger.error("Failed attaching cover in %s: %s", folder, exc)

    return AttachStats(
        processed_audio=processed_audio,
        created_lyrics=created_lyrics,
        created_covers=created_covers,
        skipped=skipped,
        errors=errors,
    )


def cleanup_broken_sidecar_links(
    *,
    root: Path,
    remove_lyrics: bool = True,
    remove_cover: bool = True,
    logger: logging.Logger,
) -> CleanupStats:
    removed = 0
    skipped = 0
    errors = 0

    for path in root.rglob("*"):
        if not path.is_file() and not path.is_symlink():
            continue

        try:
            if not _is_broken_symlink(path):
                continue

            name = path.name.lower()
            is_lyrics = remove_lyrics and name.endswith(".lrc")
            is_cover = remove_cover and (name == "cover.jpg" or name == "cover.png")
            if not (is_lyrics or is_cover):
                skipped += 1
                continue

            path.unlink(missing_ok=True)
            removed += 1
            logger.info("Removed broken sidecar link: %s", path)

        except (OSError, RuntimeError) as exc:
            errors += 1
            logger.error("Failed removing broken link %s: %s", path, exc)

    return CleanupStats(removed_broken_links=removed, skipped=skipped, errors=errors)
