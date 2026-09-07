# prefab-gate as a KiCad plugin

**Date:** 2026-09-07
**Status:** approved, not yet implemented

## Why

prefab-gate is deterministic. It runs `kicad-cli` DRC with zone refill and
schematic parity, classifies each finding, and refuses to export a fab package
from a board that has not passed. No model is in the loop and none is needed —
which means the audience for it is every KiCad user, not only the ones running
Claude Code.

Today it ships one way: as a Claude Code plugin, in a subdirectory of a
hardware project about an NES video board. That is the wrong shelf. Packaging
it for KiCad's Plugin and Content Manager puts it where the people who need it
already look.

## Goals

- Run the existing gate from inside KiCad, with no command line.
- Reuse the gate's logic exactly. No second implementation of the policy.
- Never modify the user's files.
- Keep the CLI and the Claude Code plugin working unchanged.

## Non-goals

- Exporting fab packages from the GUI. See "Check only" below.
- Reimplementing DRC. The gate drives `kicad-cli`; that does not change.
- Supporting KiCad releases whose `kicad-cli` lacks the flags the gate needs.
  The existing capability probe already refuses those, with a better message
  than a version comparison would give.

## Decisions

### Check only

The toolbar button runs a check and shows a verdict. It writes nothing.

Packaging stays a CLI job because the gate's central guarantee — *what was
checked is what gets packaged* — rests on hashing a file on disk and finding it
unchanged before publishing. In the editor, the board on screen and the board
on disk can differ at any moment, and a gate that says PASS about a board the
user is not looking at is worse than no gate at all. The CLI operates on a file
nobody is editing, which is the condition the guarantee assumes.

This also keeps the plugin's surface small enough to trust.

### Its own repository

prefab-gate moves to `danielboston38/prefab-gate`, using

    git subtree split --prefix=prefab-gate

so the existing commits keep their authorship and messages instead of arriving
as a single squashed import. The tool has a different audience, a different
licence (MIT, against the board's CERN-OHL-S-2.0) and a different release
cadence from the hardware it grew up beside.

It also makes the PCM download honest: a package manager installing a 40 KB
tool should not clone a hardware project's PDFs, board images and gerber
history to do it.

**Consequence, accepted:** the board repository's README currently invokes
`python3 prefab-gate/scripts/prefab_gate.py`. After the split that path is
gone. The board repo treats prefab-gate as an external tool — installed via PCM
or cloned separately — and its documentation references `prefab_gate` on PATH.
This is the truthful description of the relationship, and it is worth a
one-time doc edit to stop pretending otherwise. A submodule was considered and
rejected: it would preserve the paths at the cost of a permanent papercut.

### Run on a copy, never on the open board

DRC runs with `--refill-zones --save-board`, which rewrites the board file in
place. From a plugin, that file is the one open in the editor, and rewriting it
underneath pcbnew would leave the editor's in-memory copy silently disagreeing
with disk.

So the plugin copies the project to a temporary directory and runs there.

**The copy must include the whole project, not just the board.** Custom DRC
rules live in `<project>.kicad_dru` and severity settings in `<project>.kicad_pro`.
A copy of only the board and schematic would silently fall back to default
rules and produce a verdict that does not describe the user's design at all —
a failure mode that looks exactly like success. Files to copy:

| File | Why |
|---|---|
| `<name>.kicad_pcb` | the board |
| every `*.kicad_sch` | schematic parity; hierarchical designs have several |
| `<name>.kicad_pro` | DRC severities, which decide blocking vs cosmetic |
| `<name>.kicad_dru` | custom rules, when present |

`kicad-cli pcb drc` derives the schematic from the board's basename, so the
copy must keep the original filenames.

## Architecture

The plugin is a thin wx wrapper importing the same `gate` package the CLI
imports. The policy — what blocks, what is cosmetic, what counts as parity
having run — has exactly one implementation, already covered by 182 tests. If
the wrapper grows past roughly 150 lines, logic has leaked into it that belongs
in the library.

`subtree split` preserves paths, so `scripts/` stays where it is rather than
being flattened — no churn, and the README's commands keep working.

```
prefab-gate/
├── scripts/
│   ├── gate/                  # library, pure stdlib, unchanged
│   └── prefab_gate.py         # CLI, unchanged
├── tests/                     # unchanged, plus the new staging tests
├── .claude-plugin/            # Claude Code plugin, unchanged
└── kicad/
    ├── plugin/
    │   ├── __init__.py        # registers the ActionPlugin
    │   ├── action.py          # wx dialog, verdict rendering
    │   ├── staging.py         # assemble the temp project copy
    │   └── icon24.png         # toolbar icon, 24x24
    ├── icon.png               # PCM listing icon, 64x64
    ├── metadata.json          # PCM manifest (no download_* fields)
    └── build_pcm.py           # builds the zip, emits sha256 and sizes
```

`staging.py` is separated from `action.py` deliberately: deciding which files a
project needs is the part with real consequences, and as a pure function over a
directory listing it is testable with no KiCad and no GUI present. The wx code
around it stays dumb enough not to need tests.

### Flow

1. `pcbnew.GetBoard().GetFileName()` gives the project path.
2. `staging.collect()` returns the file list; refuses if the board has never
   been saved, or if no schematic sits beside it under the board's basename.
3. Copy into a `TemporaryDirectory`.
4. Call the existing check entry point on the copy.
5. Render the verdict; delete the temp directory.

## What the dialog must say

Two things are not optional, because both are cases where a quiet plugin would
mislead.

**Which file it read.** Detecting unsaved editor changes from a plugin is
unreliable, so the plugin does not guess. It states the path and mtime of the
board it checked and lets the user resolve the ambiguity. A heuristic that is
right most of the time is the wrong tool for a guarantee.

**That stale zone fills were reported, not repaired.** The CLI refills and
saves, so it fixes staleness as a side effect. A read-only plugin cannot. When
the board hash changes during the refill on the copy, the verdict says so
explicitly — *your zone fills are stale; refill and save before exporting* —
because a clean PASS on a board whose on-disk fills are stale is precisely the
fault this gate exists to catch.

The verdict otherwise mirrors the CLI: pass or blocked, blocking findings
first, cosmetic ones listed but marked waived, and the count of check
categories disabled in project settings.

## Packaging

Per KiCad's [addon developer documentation](https://dev-docs.kicad.org/en/addons/index.html),
the package is a **ZIP** (ISO 21320-1 compatible) laid out as:

```
metadata.json          at the archive root
plugins/               plugin code, plus the 24x24 toolbar icon
resources/icon.png     64x64, the PCM listing icon
```

Two icons are needed, not one: 64×64 at `resources/icon.png` for the manager's
listing, and a separate 24×24 inside `plugins/` for the pcbnew toolbar button.

`build_pcm.py` assembles the archive from `kicad/plugin/` plus the `gate`
package, and computes `download_sha256`, `download_size` and `install_size`.
Generating them is the point: three numbers describing an artifact, maintained
by hand, drift from it.

**The `download_*` fields must be absent from the `metadata.json` inside the
archive.** They belong only to the copy submitted to the metadata repository.
Shipping them in the package is a spec violation, and an easy one to make by
copying one file to both places.

### Manifest values

Validated against the [v2 schema](https://gitlab.com/kicad/code/kicad/-/raw/master/kicad/pcm/schemas/pcm.v2.schema.json),
which is authoritative where it and the prose documentation disagree — and they
do: the docs say `description` is capped at 150 characters, the schema says 500.

Required at top level: `name`, `description`, `description_full`, `identifier`,
`type`, `author`, `license`, `resources`, `versions`. **`resources` is required**,
which the prose reads as optional; it is an object of link name to URL, so
`{"homepage": "https://github.com/danielboston38/prefab-gate"}` satisfies it.

| Field | Value | Schema constraint |
|---|---|---|
| `identifier` | `com.github.danielboston38.prefab-gate` | `^[a-zA-Z][-a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$` — dots allowed, ≤100 chars |
| `type` | `plugin` | `^[a-z][-a-z0-9]{0,48}[a-z0-9]$` |
| `license` | `MIT` | GPL-compatible, as required for Python plugins |
| `kicad_version` | `8.0` | `^\d{1,2}(\.\d{1,2}(\.\d{1,2})?)?$` |
| `status` | `testing` first, `stable` once it has seen use | one of stable/testing/development/deprecated |
| `tags` | reuse the Claude Code plugin's keywords | `^[a-z][-a-z0-9]{0,49}$`, unique, ≥1 item |

Each `versions[]` entry requires `version`, `status` and `kicad_version`.

**Release versions cannot carry a pre-release suffix.** `version` must match
`^\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?$`, so `0.1.0` is fine and `0.1.0-beta` is
rejected. Pre-release intent is expressed through `status: testing`, not the
version string — worth knowing before tagging.

`kicad_version` is 8.0 because `kicad-cli pcb drc` — with `--schematic-parity`
and JSON output — [arrived in KiCad 8.0](https://www.kicad.org/blog/2024/02/Version-8.0.0-Released/).
The gate's runtime capability probe is still the real check and gives a better
message than a version comparison; the manifest number just stops PCM offering
the plugin to KiCad 7 users who could never run it.

The identifier should match the repository name for a single-package repo —
which the split gives us for free.

**Licence check passes:** KiCad requires Python plugins to be under a
GPL-compatible open-source licence. prefab-gate is MIT, which qualifies.

### Submission

A merge request to `https://gitlab.com/kicad/addons/metadata`, adding
`packages/com.github.danielboston38.prefab-gate/` containing `metadata.json`
and the icon. **Not** `addons/repository`, which the docs explicitly say not to
submit to. Until the MR lands, the same zip installs via PCM's *install from
file*, so the plugin is usable before it is listed.

KiCad also requires the source to be hosted somewhere with issue tracking — a
further reason the split is necessary rather than merely tidy — and reserves
the right to remove packages with unresolved bugs after 90 days. That is a real
maintenance commitment, not a publish-and-forget.

KiCad-Diff was examined as a reference. Its plugin code is a reasonable shape
to follow; its packaging is not — it ships a tarball of a `plugin/` folder and
points the manifest at a GitHub archive URL, which is why installing it costs
21 MB.

## Testing

The existing suite is untouched and keeps its meaning: it covers the logic the
plugin calls.

New tests cover `staging.collect()` — that it gathers every `.kicad_sch` rather
than only the root sheet, includes `.kicad_pro` and `.kicad_dru` when present,
tolerates `.kicad_dru` being absent, preserves basenames, and refuses an
unsaved board. These run against a fixture directory with no KiCad installed.

The wx layer gets no unit tests; it is kept thin enough that manual smoke
testing in KiCad is honest coverage. `test_kicad_contract.py` continues to be
the thing that catches KiCad changing underneath us.

## Open items

- **Whether `plugins/` may contain subdirectories.** The documentation says
  plugin code goes "directly here, no subdirectories", but the `gate` package
  is a directory and most published plugins ship package trees. The likely
  reading is "do not nest your plugin inside an extra folder" rather than a ban
  on Python packages. Resolve it by building the zip and installing it through
  PCM before relying on either reading; if packages really are disallowed,
  `gate` gets vendored as flat modules with a prefix.
- **Icons.** Two are needed and neither exists: 64×64 `resources/icon.png` and
  a 24×24 toolbar icon.
- **Ownership of the `com.github.danielboston38` namespace.** The identifier
  embeds the GitHub account. Worth confirming that is the account the repo will
  live under before it is baked into a published identifier, since changing it
  later means a new package rather than an update.

Closed during design: the `kicad_version` floor is 8.0; the package schema is
the v2 schema linked above, checked rather than inferred.

## Success

A KiCad user installs prefab-gate from the PCM, opens a board, clicks one
button, and gets the same verdict the CLI would give — without their files
being touched, and without having to know what `kicad-cli` is.
