<!-- markdownlint-disable MD041 MD022 MD032 MD004 -->

## Agent instructions (canonical)

Generated files (do not edit; regenerate with `python scripts/sync_agent_docs.py --write`):

- `.github/copilot-instructions.md`
- `GEMINI.md`
- `.gemini/styleguide.md`

<!-- BEGIN AGENT INSTRUCTIONS -->

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

<!-- END AGENT INSTRUCTIONS -->

---

## 0) Target outcome

A Picard **Plugin v3** project that:

* Defines a **sidecar rules table** (type label, embedded?, filemask, enabled) in the plugin options UI.
* On save/move, **moves/copies the matching sidecar artifacts** (files and directory trees) alongside the audio file, with the **same conflict policy** Picard used for the audio file.
* Supports **multiple sidecars per audio file** as long as their **resolved masks are unique** for that audio file (your `{base}-front.jpeg` / `{base}-front.jpg` invalid case becomes a config validation error).
* Includes **tests** (filesystem-based) covering embedded + external cases across a baseline “known types” set.
* Includes **packaging + release scripts** that produce a deterministic ZIP and optionally support publishing via the Picard plugins registry which expects a `MANIFEST.toml` at repo root. ([GitHub][1])

---

## 1) Lock the data model (what you will actually implement)

### 1.1 Sidecar tag format (the multivalue tag you described)

Keep your current two-field *concept*, but make it deterministic and validateable by defining an explicit grammar.

**One multivalue string entry = one sidecar rule instance** for a file, in this normalized form:

* **Field 1 (type):** lowercase extension token OR your own type token (e.g., `lrc`, `cue`, `cover`, `xml`, `nfo`, `booklet`, `checksums`, `extras_tree`).
* **Field 2 (name/match):**

  * External: a filemask template containing `{base}` (required) and optionally a suffix/pattern:
    `"{base}.lrc"`, `"{base}-front.jpg"`, `"{base}.sidecar.tar"`, `"{base}.extras/**"`
  * Embedded: `EMBED:<tagname>` (exactly this prefix).

If you adopt the UI rule-table as *the* primary truth (recommended), the “sidecar tag” becomes:

* an *exportable representation* of the configured rows, and/or
* an internal computed value stored in hidden variables, rather than something users hand-edit.

### 1.2 Row schema (used by UI + persisted settings)

Each row should include:

* `type_label` (string, user-facing)
* `embedded` (bool)
* `embedded_tag` (string, only if embedded)
* `filemask` (string, only if external; must include `{base}`)
* `enabled` (bool)
* `is_tree` (bool derived: `filemask` ends with `/**` or points to a directory glob)
* `move_mode` (enum: `move` or `copy`; default `move` — apply to trees too)

Validation rules:

* If `embedded == true`: require `embedded_tag`, forbid `filemask`.
* If `embedded == false`: require `filemask` and require `{base}` to appear.
* Disallow removing last row in UI (your constraint), but provide **“Restore defaults”** so the last row isn’t a trap.
* Uniqueness rule (your requirement): for a given audio file, after expanding `{base}`, the set of resulting masks must be **unique**. If not, log + skip the duplicates deterministically (or hard error at save time; your call—pick one behavior and test it).

---

## 2) Decide the hook point (Picard integration)

You need the **final destination path** (post-script naming, post-move decision). Implement as a **post-save/post-move processor** (whatever Plugin v3 exposes) so you have:

* `src_audio_path` (where the sidecars currently live)
* `dst_audio_path` (final path Picard wrote/moved to)

If you cannot get a true post-save hook in v3, fallback strategy:

* Hook at “about to move” point and compute destination path the same way Picard does (less ideal), or
* Track the move in two phases (pre + post) using a per-file transient map.

(You will confirm the exact v3 hook names in the current Picard docs / source; Picard’s plugin system is being actively revisited. ([MetaBrainz Chatlogs][2]))

---

## 3) Sidecar discovery and move plan

For each audio file being saved:

### 3.1 Compute core values

* `dst_dir = dirname(dst_audio_path)`
* `dst_base = basename_without_ext(dst_audio_path)`
* `src_dir = dirname(src_audio_path)` (or the file’s original directory if available)

### 3.2 Expand enabled external rules to concrete matches

For each enabled external row:

1. Expand `{base}` → `dst_base` **for destination naming**, and `{base}` → `src_base` (if you want to match sidecars by original basename).
   Practical default: match sidecars in `src_dir` by **source basename**, then move them to `dst_dir` named by **destination basename**. This keeps sidecars aligned with whatever Picard renamed the audio file to.

2. Interpret `filemask`:

   * If ends with `/**` or matches a directory: treat as **tree**.
   * Else treat as **file** glob.

3. Find matches in `src_dir` only (safety).

   * For `file`: glob for the expanded pattern.
   * For `tree`: resolve the directory name and verify it is inside `src_dir`.

4. If 0 matches: no-op.

5. If >1 match for a single mask: either

   * move all of them if they are distinct file paths, or
   * treat as config error.
     (Given your uniqueness constraint is about masks, not results, moving all matches is usually fine. Just ensure it’s deterministic.)

### 3.3 Embedded rules

No filesystem work. For embedded rows:

* Validate that the relevant tag exists in metadata (if available at this hook).
* Log at debug level that it was “handled (embedded)”.

### 3.4 Conflicts = follow Picard’s conflict policy

You said: *“on conflicts, behavior for the sidecar should be the same as the main file.”*

Implementation approach:

* Determine what Picard did for the audio file (overwrite/rename/skip) if the API exposes it.
* If not exposed, implement your own conflict policy setting that defaults to “mirror Picard behavior best-effort”, and document the limitation.

At minimum, implement:

* `skip` if dst exists
* `overwrite`
* `rename` (e.g., `name (1).ext`)
  …and choose the one that matches Picard’s active option set when you can read it.

---

## 4) “Supersede Move additional files” behavior

You cannot reliably mutate core Picard options without risking state corruption.

Do this instead:

* Add plugin setting: **“Supersede additional files handling”** (default off).
* If enabled:

  * Before moving sidecars, detect whether Picard additional-files patterns are non-empty.
  * Log a **one-time warning** explaining that users should disable “Move additional files” patterns to avoid double-moving.


---

## 5) UI implementation plan (multi-column list + add/edit/remove)

Use a **QTableView + model** (or whatever v3 uses—Qt is still common in Picard plugins, as seen in existing plugins’ options pages). ([GitHub][3])

Minimum UI behavior:

* Columns:

  1. Sidecar Type (string)
  2. Embedded (checkbox)
  3. Embedded Tag (string, only editable when Embedded=true) **OR** Filemask (string, only editable when Embedded=false)
  4. Enabled (checkbox)

* Buttons: Add / Edit / Remove

* Remove disabled when there is only 1 row (your requirement)

* Validation in the dialog:

  * Embedded row requires `embedded_tag`
  * External row requires `filemask` and `{base}`

Persist the table as a single JSON blob in plugin settings (simpler) or as parallel arrays; JSON is easier to evolve.

---

## 6) Test plan (filesystem-based, deterministic)

Use pytest with temp dirs.

### 6.1 Baseline known-types set

Create default rows for:

* `lyrics` → `{base}.lrc`
* `cue` → `{base}.cue`
* `nfo` → `{base}.nfo`
* `xml` → `{base}.xml`
* `log` → `{base}.log`
* `m3u` → `{base}.m3u`
* `booklet` → `{base}.pdf`
* `checksums` → `{base}.sfv` and/or `{base}.md5`
* `cover_embedded` → `EMBED:coverart` (embedded example)

### 6.2 External file sidecars test cases

For each type above (except embedded):

* Arrange:

  * `src_dir` contains `src_base.flac` (empty file is fine)
  * Sidecar file exists (e.g., `src_base.lrc`)
* Act:

  * Run your move logic with `dst_audio_path = dst_dir/dst_base.flac`
* Assert:

  * Sidecar moved to `dst_dir/dst_base.lrc` (or whichever mask dictates)
  * Source sidecar removed (if move mode)
  * Logs contain “moved sidecar …”

Add conflict variants:

* Destination sidecar already exists → assert skip/overwrite/rename consistent with your chosen policy.

### 6.3 External tree sidecars test cases

Create:

* `src_dir/src_base.extras/` with nested files
* filemask `{base}.extras/**`
  Assert:
* Entire subtree moved (or copied) to `dst_dir/dst_base.extras/…`
* Safety test: if resolved directory escapes `src_dir`, operation refused.

### 6.4 Embedded test cases

No real embedding.

* Feed metadata dict with `coverart` present and row `EMBED:coverart`
* Assert:

  * No filesystem changes
  * Validation passes
  * Log indicates embedded handled

### 6.5 Uniqueness rule test

Configure two rows whose expanded masks collide for the same audio file:

* `{base}-front.jpg`
* `{base}-front.jpg` (or two rows that normalize to same)
  Assert:
* Save-time validation fails OR one rule is skipped deterministically (whichever behavior you chose).

---

## 7) Repo layout + packaging

### 7.1 Layout

Follow the standard multi-file plugin layout: plugin directory under the ZIP with `__init__.py` and module files. (This is the layout used by many plugins; single-file plugins can be flat, but yours won’t be.) ([MetaBrainz Community Discourse][4])

Example (conceptual):

* `sidecar_handler/`

  * `__init__.py` (register hooks, load settings, register options page)
  * `options.py` (UI + config schema)
  * `engine.py` (matching + move plan)
  * `fsops.py` (move/copy/rename utilities)
  * `logutil.py`
* `MANIFEST.toml` (required if you want registry submission) ([GitHub][1])
* `tests/`
* `scripts/`

  * `build.py` (deterministic zip)
  * `release.ps1` + `release.sh` (tag + build + checksum)

### 7.2 Packaging ZIP rules

Build script should:

* Produce `dist/sidecar-handler_<version>.zip`
* Ensure the zip contains the top-level plugin folder (not the repo root contents).
* Produce a `dist/SHA256SUMS` file.

---

## 8) Release + registry submission workflow

### 8.1 Versioning

* Single source of truth: `MANIFEST.toml` version field (and optionally `__init__.py` reads it).
* Tag releases `vX.Y.Z`.

### 8.2 CI

* Run unit tests
* Build zip artifact
* Attach artifact to GitHub release (if you use GitHub), or publish wherever you host.

### 8.3 Picard plugins registry

If you want the plugin to be installable via Picard’s managed plugin list, plan to submit it to the official registry:

* The registry expects a `MANIFEST.toml` at repo root and supports mapping branches/refs to Picard API ranges. ([GitHub][1])

---

## 9) Implementation checklist (do these in order)

1. **Scaffold repo** + minimal plugin that loads in Picard (no functionality yet).
2. Implement **settings schema** + default rows + options page UI.
3. Implement **engine**: expand masks → discover matches → plan operations.
4. Implement **fsops** with conflict behaviors + tree safety constraints.
5. Wire **post-save hook** to call engine for each saved file.
6. Add **logging** with levels + one-time warnings.
7. Write **tests** (start with one external file type, then expand).
8. Add **build script** (deterministic zip).
9. Add **release scripts** (tag, build, hash).
10. Add CI (tests + build artifact).

---

## 10) Two details you still must choose (or you will rework later)

* **Match source basename vs destination basename:**
  Recommended: match in `src_dir` using **source base**, write into `dst_dir` using **destination base** (so renames propagate).

* **Duplicate mask handling:**
  Recommended: **fail fast at config validation** (edit dialog + pre-save check) because it’s deterministic and matches your “invalid” examples.


[1]: https://github.com/metabrainz/picard-plugins-registry "GitHub - metabrainz/picard-plugins-registry: Official Picard Plugins Registry"
[2]: https://chatlogs.metabrainz.org/libera/musicbrainz-picard-development/msg/5532020/?utm_source=chatgpt.com "IRC Logs for #musicbrainz-picard-development"
[3]: https://raw.githubusercontent.com/metabrainz/picard-plugins/3b1f94b004b6aeb93e6c3692dfe470b1f951c759/plugins/happidev_lyrics/happidev_lyrics.py?utm_source=chatgpt.com "https://raw.githubusercontent.com/metabrainz/picar..."
[4]: https://community.metabrainz.org/t/how-to-run-plugins-on-picard-as-a-developer/674175?utm_source=chatgpt.com "How to run plugins on Picard as a developer"
