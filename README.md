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
