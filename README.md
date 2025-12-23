# Sidecar Handler (Picard Plugin v3)

Moves/copies configured “sidecar” artifacts (files and directory trees) alongside the audio file when Picard saves/moves it.

## What it does

- Sidecar rules are configured in the plugin options as a table:
  - Type label
  - Embedded?
  - Embedded tag **or** filemask
  - Enabled
- External rules match files/trees next to the **source** audio file and place them next to the **destination** audio file, renaming `{base}` from source basename → destination basename.
- Embedded rules only validate tag presence (no filesystem writes).

## Notes / limitations

- Sidecar conflict handling supports `skip`, `overwrite`, or `rename`.
- Mirroring Picard’s exact conflict decision for the audio file depends on Picard’s plugin API exposure at runtime; if it is not available, the plugin uses its own conflict policy.

## Development

- This repo uses Picard’s shared venv: `../picard/.venv`.
- Run tests: `python -m pytest`
- Build deterministic zip: `python scripts/build.py`

## Companion script (dev utility)

This repo also includes a small helper CLI for bulk attaching sidecars (lyrics + folder-level cover) and cleaning up broken sidecar symlinks.

- Help (includes version + description): `python scripts/mbsidecarctl.py -h`
- Attach (best-effort link, fallback to copy): `python scripts/mbsidecarctl.py <root> attach -v`
- Attach (force copy, overwrite existing destinations): `python scripts/mbsidecarctl.py <root> attach --link-type copy --conflict overwrite -v`
- Cleanup broken links: `python scripts/mbsidecarctl.py <root> cleanup -v`

Note: this script is a development utility and is not included in the built plugin ZIP.

## Developer notes

- `AGENTS.md` is the canonical source for agent instructions.
- Generated files: `.github/copilot-instructions.md`, `GEMINI.md`, `.gemini/styleguide.md`.
- Regenerate: `python scripts/sync_agent_docs.py --write`.
