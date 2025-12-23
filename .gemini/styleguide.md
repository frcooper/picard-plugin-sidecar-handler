# Copilot instructions (picard-plugin-sidecar-handler)

## Repo status / source of truth
- Treat `AGENTS.md` as the authoritative implementation plan and do not introduce UX/features beyond it.

## What you’re building (Picard Plugin v3)
- A MusicBrainz Picard **Plugin v3** that, on save/move, moves/copies “sidecar” artifacts (files and directory trees) next to the audio file.
- Sidecar rules are user-configured via an options UI table with columns: `type_label`, `embedded?`, `filemask/embedded_tag`, `enabled`.

## Core data model + validation (must be deterministic)
- Each row maps to:
  - `type_label` (string)
  - `embedded` (bool)
  - `embedded_tag` (string; required iff `embedded=true`)
  - `filemask` (string; required iff `embedded=false`; must contain `{base}`)
  - `enabled` (bool)
  - `move_mode` (`move`|`copy`; default `move`)
  - `is_tree` derived from `filemask` ending with `/**`
- Validation rules:
  - Embedded rows: require `embedded_tag`, forbid `filemask`.
  - External rows: require `filemask` and require `{base}`.
  - UI must not allow deleting the last row; provide “Restore defaults”.
  - **Uniqueness constraint:** for a given audio file, after expanding `{base}`, resolved masks must be unique; duplicates are a hard config error (fail fast).

## Sidecar resolution semantics
- Compute: `src_dir/src_base` from original audio path, `dst_dir/dst_base` from final Picard destination path.
- Default matching behavior:
  - Match sidecars in `src_dir` using **source basename**; write to `dst_dir` using **destination basename** (so renames propagate).
- External rules:
  - If `filemask` ends with `/**`, treat it as a **tree** move/copy; enforce safety: resolved paths must stay inside `src_dir`.
  - Otherwise treat as file glob relative to `src_dir`.
- Embedded rules:
  - No filesystem writes; validate tag presence if metadata is available at the chosen hook.

## Conflict behavior
- Sidecar conflicts must follow the same policy Picard used for the audio file.
- If Picard doesn’t expose the decision, implement explicit sidecar conflict handling (`skip` / `overwrite` / `rename`) and document the limitation.

## Intended code layout
- plugin entry/registration (`__init__.py`)
- options UI + persisted settings (`options.py`)
- matching/planning logic (`engine.py`)
- filesystem operations + conflict handling (`fsops.py`)
- tests under `tests/`
- deterministic packaging scripts under `scripts/`

## Pinned local workflow
- Run tests: `python -m pytest`
- Build deterministic zip: `python scripts/build.py` (writes to `dist/`)
