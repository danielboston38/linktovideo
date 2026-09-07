# prefab-gate KiCad Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship prefab-gate as a KiCad Plugin and Content Manager package, so a KiCad user can run the gate from a toolbar button without a command line.

**Architecture:** A thin wx `ActionPlugin` calls the existing gate through its own `--json` contract. Two pure-Python helpers do the work worth testing — `staging` assembles a minimal project copy in a temp directory, `runner` invokes the gate in-process and returns a structured result. The wx layer only renders. No gate logic is reimplemented.

**Tech Stack:** Python 3 (stdlib only), `pcbnew` + `wx` (supplied by KiCad, never imported by the tested modules), `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-07-prefab-gate-kicad-plugin-design.md`

## Global Constraints

- **Stdlib only.** KiCad's bundled Python cannot `pip install`. No third-party imports anywhere in shipped code.
- **The plugin changes nothing without explicitly asking.** It never writes to the user's project. Check only; no packaging from the GUI.
- **Never run against the open board.** DRC uses `--refill-zones --save-board` and would rewrite the file under the editor. Always stage a copy.
- **The staged copy is a four-file whitelist:** `<name>.kicad_pcb`, every `*.kicad_sch` in the project directory, `<name>.kicad_pro`, `<name>.kicad_dru`. Never the whole directory.
- **Basenames must be preserved when staging.** `kicad-cli pcb drc` derives the schematic from the board's basename and has no flag to override it.
- **One implementation of the policy.** Blocking-vs-cosmetic decisions live in `gate/`; the plugin consumes them.
- **Tests are stdlib `unittest`, no pytest.** Run with:
  `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'`
- **Tested modules must import without `pcbnew` or `wx` present.**
- PCM manifest values, verbatim: `identifier` `com.github.danielboston38.prefab-gate`, `type` `plugin`, `license` `MIT`, `kicad_version` `8.0`, `status` `testing`.
- PCM `version` must match `^\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?$` — **no pre-release suffixes**.
- `download_sha256` / `download_url` / `download_size` / `install_size` **must be absent** from the `metadata.json` inside the archive.

---

## File Structure

| File | Responsibility |
|---|---|
| `prefab-gate/kicad/plugin/__init__.py` | Register the action with pcbnew; stay importable without it |
| `prefab-gate/kicad/plugin/staging.py` | Decide which files a project needs; copy them. No KiCad imports |
| `prefab-gate/kicad/plugin/runner.py` | Invoke the gate, return `(code, verdict, messages, zones_were_stale)`. No KiCad imports |
| `prefab-gate/kicad/plugin/action.py` | wx dialog. Rendering only |
| `prefab-gate/kicad/plugin/icon24.png` | Toolbar icon, 24×24 |
| `prefab-gate/kicad/icon.png` | PCM listing icon, 64×64 |
| `prefab-gate/kicad/metadata.json` | PCM manifest |
| `prefab-gate/kicad/build_pcm.py` | Build the archive; emit submission metadata |
| `prefab-gate/tests/test_staging.py` | Tests for staging |
| `prefab-gate/tests/test_runner.py` | Tests for runner |
| `prefab-gate/tests/test_build_pcm.py` | Tests for the archive layout |

**Deliberate deviation from the spec, flagged for review.** The spec says `staging.collect()` refuses when no schematic sits beside the board. This plan does **not** implement that. The gate already treats a missing schematic as a blocking `parity_not_run` finding, with a better message than staging could give, and duplicating that check would be a second implementation of the same policy — which the spec elsewhere forbids. Staging refuses only when there is no board file at all, which is a precondition for doing anything rather than a policy call.

---

### Task 1: Staging — decide and copy

**Files:**
- Create: `prefab-gate/kicad/plugin/staging.py`
- Test: `prefab-gate/tests/test_staging.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `StagingError(Exception)`; `collect(board_path: str) -> list[str]` (absolute paths, board first); `stage(board_path: str, dest: str) -> str` (returns staged board path).

- [ ] **Step 1: Write the failing tests**

```python
"""Staging picks the files DRC needs and nothing else."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kicad"))

from plugin import staging  # noqa: E402


def _project(tmp, *, pro=True, dru=True, sheets=()):
    """A believable KiCad project directory. Returns the board path."""
    board = os.path.join(tmp, "demo.kicad_pcb")
    open(board, "w").write("(kicad_pcb)")
    open(os.path.join(tmp, "demo.kicad_sch"), "w").write("(kicad_sch)")
    for name in sheets:
        open(os.path.join(tmp, name + ".kicad_sch"), "w").write("(kicad_sch)")
    if pro:
        open(os.path.join(tmp, "demo.kicad_pro"), "w").write("{}")
    if dru:
        open(os.path.join(tmp, "demo.kicad_dru"), "w").write("(version 1)")
    return board


class CollectTest(unittest.TestCase):

    def test_board_comes_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = _project(tmp)
            self.assertEqual(staging.collect(board)[0], os.path.abspath(board))

    def test_collects_every_schematic_sheet(self):
        """Hierarchical designs have more than the root sheet, and parity
        needs all of them."""
        with tempfile.TemporaryDirectory() as tmp:
            board = _project(tmp, sheets=("power", "video"))
            names = {os.path.basename(p) for p in staging.collect(board)}
            self.assertEqual(
                {"demo.kicad_sch", "power.kicad_sch", "video.kicad_sch"},
                {n for n in names if n.endswith(".kicad_sch")})

    def test_collects_project_and_rules_files(self):
        """Severities live in .kicad_pro and custom rules in .kicad_dru.
        Without them DRC silently uses defaults and judges a different board."""
        with tempfile.TemporaryDirectory() as tmp:
            board = _project(tmp)
            names = {os.path.basename(p) for p in staging.collect(board)}
            self.assertIn("demo.kicad_pro", names)
            self.assertIn("demo.kicad_dru", names)

    def test_tolerates_missing_optional_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = _project(tmp, pro=False, dru=False)
            names = {os.path.basename(p) for p in staging.collect(board)}
            self.assertEqual({"demo.kicad_pcb", "demo.kicad_sch"}, names)

    def test_excludes_everything_drc_does_not_read(self):
        """3D models and libraries are what make projects large; footprints
        are embedded in the board and symbols in the schematic."""
        with tempfile.TemporaryDirectory() as tmp:
            board = _project(tmp)
            os.mkdir(os.path.join(tmp, "lib.pretty"))
            open(os.path.join(tmp, "lib.pretty", "a.kicad_mod"), "w").write("x")
            open(os.path.join(tmp, "part.step"), "w").write("x" * 1000)
            open(os.path.join(tmp, "board-F_Cu.gbr"), "w").write("x")
            open(os.path.join(tmp, "backup.zip"), "w").write("x")
            names = {os.path.basename(p) for p in staging.collect(board)}
            for unwanted in ("a.kicad_mod", "part.step", "board-F_Cu.gbr",
                             "backup.zip"):
                self.assertNotIn(unwanted, names)

    def test_unsaved_board_refuses(self):
        """pcbnew returns an empty filename for a board never saved."""
        with self.assertRaises(staging.StagingError):
            staging.collect("")

    def test_missing_board_refuses(self):
        with self.assertRaises(staging.StagingError):
            staging.collect("/nonexistent/demo.kicad_pcb")


class StageTest(unittest.TestCase):

    def test_preserves_basenames(self):
        """kicad-cli derives the schematic from the board's basename."""
        with tempfile.TemporaryDirectory() as tmp, \
             tempfile.TemporaryDirectory() as dest:
            staging.stage(_project(tmp), dest)
            self.assertTrue(os.path.isfile(os.path.join(dest, "demo.kicad_pcb")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "demo.kicad_sch")))

    def test_returns_the_staged_board(self):
        with tempfile.TemporaryDirectory() as tmp, \
             tempfile.TemporaryDirectory() as dest:
            staged = staging.stage(_project(tmp), dest)
            self.assertEqual(os.path.join(dest, "demo.kicad_pcb"), staged)
            self.assertTrue(os.path.isfile(staged))

    def test_leaves_the_originals_alone(self):
        """The whole reason staging exists."""
        with tempfile.TemporaryDirectory() as tmp, \
             tempfile.TemporaryDirectory() as dest:
            board = _project(tmp)
            before = {n: open(os.path.join(tmp, n)).read()
                      for n in os.listdir(tmp)}
            staging.stage(board, dest)
            after = {n: open(os.path.join(tmp, n)).read()
                     for n in os.listdir(tmp)}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_staging.py' -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugin'`

- [ ] **Step 3: Write the implementation**

```python
"""Assemble the smallest project copy kicad-cli DRC needs.

DRC runs with --refill-zones --save-board, which rewrites the board in place.
Run from a plugin that would be the file open in the editor, so the gate is
pointed at a copy instead. This module decides what goes into that copy.

It is a whitelist, not a directory copy. 3D models and footprint or symbol
libraries are excluded because footprints are embedded in the .kicad_pcb and
symbols in the .kicad_sch — DRC never reads the libraries, and they are what
makes a KiCad project large. A real project measured 0.41 MB staged against a
79 MB directory.

.kicad_pro and .kicad_dru are not optional extras. DRC severities live in the
first and custom rules in the second; a copy without them falls back to
defaults and returns a verdict about a design the user does not have — a
failure that looks exactly like success.
"""
import glob
import os
import shutil


class StagingError(Exception):
    """There is no board file to stage."""


def collect(board_path):
    """Absolute paths of every file DRC needs. The board is always first.

    A missing schematic is deliberately not an error here. The gate treats it
    as a blocking parity_not_run finding with a better explanation than this
    module could give, and duplicating the check would put the same policy in
    two places.
    """
    if not board_path:
        raise StagingError(
            "This board has not been saved yet, so there is no file to check. "
            "Save it and run the gate again.")
    board = os.path.abspath(board_path)
    if not os.path.isfile(board):
        raise StagingError(f"No board file at {board}.")

    project = os.path.dirname(board)
    stem = os.path.splitext(os.path.basename(board))[0]

    files = [board]
    files.extend(sorted(glob.glob(os.path.join(project, "*.kicad_sch"))))
    for extension in (".kicad_pro", ".kicad_dru"):
        sidecar = os.path.join(project, stem + extension)
        if os.path.isfile(sidecar):
            files.append(sidecar)
    return files


def stage(board_path, dest):
    """Copy the collected files into dest; return the staged board's path.

    Basenames are preserved because kicad-cli derives the schematic from the
    board's basename and has no flag to override it.
    """
    files = collect(board_path)
    for source in files:
        shutil.copy2(source, os.path.join(dest, os.path.basename(source)))
    return os.path.join(dest, os.path.basename(files[0]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_staging.py' -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Run the whole suite to confirm nothing regressed**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'`
Expected: PASS, 192 tests

- [ ] **Step 6: Commit**

```bash
git add prefab-gate/kicad/plugin/staging.py prefab-gate/tests/test_staging.py
git commit -m "feat(kicad-plugin): stage a minimal project copy for DRC

DRC rewrites the board to refill zones, so a plugin must never point it at
the file open in the editor. Staging copies a four-file whitelist to a temp
directory instead: the board, every schematic sheet, and the .kicad_pro and
.kicad_dru that carry severities and custom rules.

The whitelist is the point. 3D models and libraries are excluded because
footprints and symbols are embedded in the board and schematic, and they are
what make projects large — 0.41 MB staged against a 79 MB directory.

Omitting .kicad_pro or .kicad_dru would be the subtle failure: DRC would fall
back to default rules and return a confident verdict about a different design."
```

---

### Task 2: Runner — invoke the gate, detect stale fills

**Files:**
- Create: `prefab-gate/kicad/plugin/runner.py`
- Test: `prefab-gate/tests/test_runner.py`

**Interfaces:**
- Consumes: `staging.stage` (Task 1).
- Produces: `Result` namedtuple with fields `code: int`, `verdict: dict | None`, `messages: str`, `zones_were_stale: bool`; `run_check(board_path, main=None, hasher=None) -> Result`.

Under `--json` the gate writes only the verdict to stdout and every other message to stderr, so parsing stdout as JSON is a supported contract rather than screen-scraping.

Stale zone fills are detected by hashing the staged board before and after, **not** by matching the gate's note. The gate itself refuses to key on message wording, and its note says "should be committed" while naming a temp path — true for the CLI, nonsense in a dialog.

- [ ] **Step 1: Write the failing tests**

```python
"""The runner adapts the gate's CLI contract for the GUI."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kicad"))

from plugin import runner  # noqa: E402

PASSING = {"passed": True, "blocking": [], "cosmetic": []}


def _fake_main(stdout="", stderr="", code=0, writes=None):
    """Stand in for prefab_gate.main, which the runner calls in-process."""
    def main(argv):
        if writes is not None:
            open(argv[1], "w").write(writes)
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        return code
    return main


class RunCheckTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = os.path.join(self.tmp.name, "demo.kicad_pcb")
        open(self.board, "w").write("(kicad_pcb)")
        open(os.path.join(self.tmp.name, "demo.kicad_sch"), "w").write("(x)")
        self.addCleanup(self.tmp.cleanup)

    def test_parses_the_json_verdict_from_stdout(self):
        result = runner.run_check(
            self.board, main=_fake_main(stdout=json.dumps(PASSING)))
        self.assertEqual(PASSING, result.verdict)
        self.assertEqual(0, result.code)

    def test_keeps_stderr_as_messages(self):
        result = runner.run_check(
            self.board,
            main=_fake_main(stdout=json.dumps(PASSING), stderr="kicad-cli missing"))
        self.assertIn("kicad-cli missing", result.messages)

    def test_survives_a_gate_that_printed_no_verdict(self):
        """Exit 3 paths print to stderr and never emit a verdict."""
        result = runner.run_check(
            self.board, main=_fake_main(stderr="boom", code=3))
        self.assertIsNone(result.verdict)
        self.assertEqual(3, result.code)
        self.assertIn("boom", result.messages)

    def test_reports_stale_zone_fills_when_the_board_changed(self):
        result = runner.run_check(
            self.board,
            main=_fake_main(stdout=json.dumps(PASSING), writes="(refilled)"))
        self.assertTrue(result.zones_were_stale)

    def test_no_stale_report_when_the_board_is_untouched(self):
        result = runner.run_check(
            self.board, main=_fake_main(stdout=json.dumps(PASSING)))
        self.assertFalse(result.zones_were_stale)

    def test_runs_against_a_copy_not_the_original(self):
        """The guarantee: the user's board is never the file DRC is given."""
        original = open(self.board).read()
        runner.run_check(
            self.board,
            main=_fake_main(stdout=json.dumps(PASSING), writes="(refilled)"))
        self.assertEqual(original, open(self.board).read())

    def test_checks_a_path_inside_a_temporary_directory(self):
        seen = {}

        def main(argv):
            seen["board"] = argv[1]
            sys.stdout.write(json.dumps(PASSING))
            return 0

        runner.run_check(self.board, main=main)
        self.assertNotEqual(os.path.abspath(self.board),
                            os.path.abspath(seen["board"]))
        self.assertFalse(os.path.exists(seen["board"]),
                         "the staging directory must be cleaned up")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_runner.py' -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugin.runner'`

- [ ] **Step 3: Write the implementation**

```python
"""Run the gate against a staged copy and return something a dialog can render.

The gate is invoked through prefab_gate.main so that the plugin and the command
line share one implementation of the policy. Under --json the gate puts only
the verdict on stdout and every other message on stderr, which makes parsing
stdout a supported contract rather than screen-scraping.
"""
import collections
import hashlib
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

# Relative: PCM installs this package under a directory of its own choosing, so
# the package name is not "plugin" once installed. An absolute import works in
# the repo and breaks in the field.
from . import staging

Result = collections.namedtuple(
    "Result", "code verdict messages zones_were_stale")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _gate_main():
    """Import the gate lazily, so this module imports without it on the path.

    Two layouts have to work. Installed, PCM flattens everything into one
    directory, so prefab_gate.py is a sibling. In the repo it lives at
    ../../scripts. Nearest first, and neither is assumed.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (here,
                      os.path.normpath(os.path.join(here, "..", "..", "scripts"))):
        if os.path.isfile(os.path.join(candidate, "prefab_gate.py")):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            break
    import prefab_gate
    return prefab_gate.main


def run_check(board_path, main=None, hasher=None):
    """Stage the project, check the copy, and report what happened.

    Stale zone fills are detected by hashing the staged board either side of
    the run rather than by reading the gate's note. The gate declines to key on
    message wording and so does this; its note also says the file "should be
    committed" while naming a path inside a temporary directory, which is true
    for the CLI and meaningless in a dialog.
    """
    main = main or _gate_main()
    hasher = hasher or _sha256

    with tempfile.TemporaryDirectory(prefix="prefab-gate-") as staged_dir:
        board = staging.stage(board_path, staged_dir)
        before = hasher(board)

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["check", board, "--json"])

        stale = hasher(board) != before

    raw = out.getvalue().strip()
    verdict = None
    if raw:
        try:
            verdict = json.loads(raw)
        except json.JSONDecodeError:
            verdict = None
    return Result(code=code, verdict=verdict,
                  messages=err.getvalue().strip(), zones_were_stale=stale)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_runner.py' -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Run the whole suite**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'`
Expected: PASS, 199 tests

- [ ] **Step 6: Commit**

```bash
git add prefab-gate/kicad/plugin/runner.py prefab-gate/tests/test_runner.py
git commit -m "feat(kicad-plugin): run the gate on a staged copy

Calls prefab_gate.main so the GUI and the CLI share one implementation of the
policy. Under --json the gate emits only the verdict on stdout and everything
else on stderr, so parsing stdout is a contract rather than screen-scraping.

Stale zone fills are detected by hashing the staged board either side of the
run, not by matching the gate's note. The gate refuses to key on message
wording and neither does this — and that note says the board 'should be
committed' while naming a temp path, which is true for the CLI and nonsense in
a dialog."
```

---

### Task 3: The action plugin

**Files:**
- Create: `prefab-gate/kicad/plugin/action.py`
- Create: `prefab-gate/kicad/plugin/__init__.py`

**Interfaces:**
- Consumes: `runner.run_check` and `runner.Result` (Task 2); `staging.StagingError` (Task 1).
- Produces: `PrefabGateAction(pcbnew.ActionPlugin)`; `summarise(result, board_path) -> str`.

`summarise` is deliberately separated from the wx code so the wording can be read and changed without KiCad. The dialog itself is left untested; it is kept thin enough that manual smoke testing is honest coverage.

- [ ] **Step 1: Write `action.py`**

```python
"""The toolbar button. Rendering only — no policy lives here."""
import datetime
import os

import wx

import pcbnew

from . import runner, staging


def summarise(result, board_path):
    """The dialog text for a finished run.

    Two things are stated whatever the verdict, because a quiet plugin would
    mislead in both cases. Which file was read: unsaved editor changes cannot
    be detected reliably from a plugin, so rather than guess, the path and its
    modification time are shown and the user resolves the ambiguity. And that
    stale zone fills were reported rather than repaired: the CLI fixes them as
    a side effect of saving, this cannot, and a clean pass on a board whose
    on-disk fills are stale is the exact fault the gate exists to catch.
    """
    stamp = "unknown"
    if os.path.isfile(board_path):
        stamp = datetime.datetime.fromtimestamp(
            os.path.getmtime(board_path)).strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"Checked: {board_path}", f"Last saved: {stamp}", ""]

    if result.verdict is None:
        lines.append("The gate could not run.")
        if result.messages:
            lines += ["", result.messages]
        return "\n".join(lines)

    blocking = result.verdict.get("blocking", [])
    cosmetic = result.verdict.get("cosmetic", [])
    lines.append("PASSED — nothing blocking."
                 if result.verdict.get("passed")
                 else f"BLOCKED — {len(blocking)} blocking finding(s).")

    for finding in blocking:
        lines.append(f"  ✗ {finding.get('type')}: {finding.get('description')}")
    if cosmetic:
        lines.append(f"\n{len(cosmetic)} cosmetic finding(s), waived:")
        for finding in cosmetic:
            lines.append(f"  · {finding.get('type')}: {finding.get('description')}")

    if result.zones_were_stale:
        lines += ["",
                  "Your zone fills are stale. This check refilled them on a "
                  "copy and did not touch your board — refill and save before "
                  "exporting a fab package."]

    lines += ["", "This check wrote nothing. Packaging stays on the command "
                  "line, where the board is not being edited."]
    return "\n".join(lines)


class PrefabGateAction(pcbnew.ActionPlugin):

    def defaults(self):
        self.name = "prefab-gate: check this board"
        self.category = "Design verification"
        self.description = ("Run DRC with zone refill and schematic parity "
                            "against a copy, and report what blocks fab.")
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "icon24.png")

    def Run(self):
        board_path = pcbnew.GetBoard().GetFileName()
        try:
            result = runner.run_check(board_path)
        except staging.StagingError as exc:
            wx.MessageBox(str(exc), "prefab-gate", wx.OK | wx.ICON_WARNING)
            return

        icon = wx.ICON_INFORMATION
        if result.verdict is None or not result.verdict.get("passed"):
            icon = wx.ICON_WARNING
        dialog = wx.MessageDialog(None, summarise(result, board_path),
                                  "prefab-gate", wx.OK | icon)
        dialog.ShowModal()
        dialog.Destroy()
```

- [ ] **Step 2: Write `__init__.py`**

```python
"""Register the action with pcbnew when running inside KiCad.

pcbnew is absent outside KiCad, and the staging and runner modules must stay
importable there so they can be tested. Only the registration is skipped, and
only when pcbnew itself is missing — a broken action.py still raises, rather
than disappearing behind a bare except.
"""
try:
    import pcbnew  # noqa: F401
except ImportError:
    pass
else:
    from .action import PrefabGateAction

    PrefabGateAction().register()
```

- [ ] **Step 3: Verify the tested modules still import without KiCad**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'`
Expected: PASS, 199 tests — proving `__init__.py` does not drag in `pcbnew`

- [ ] **Step 4: Commit**

```bash
git add prefab-gate/kicad/plugin/action.py prefab-gate/kicad/plugin/__init__.py
git commit -m "feat(kicad-plugin): add the toolbar action

The dialog states two things whatever the verdict, because staying quiet about
either would mislead. Which file was read, with its mtime: unsaved editor
changes cannot be detected reliably from a plugin, so it shows what it checked
instead of guessing. And that stale zone fills were reported, not repaired —
the CLI fixes them as a side effect of saving, this cannot, and a clean pass on
a board with stale on-disk fills is the fault the gate exists to catch.

Registration is skipped when pcbnew is absent so the tested modules stay
importable outside KiCad, but only for a missing pcbnew — a broken action still
raises rather than vanishing behind a bare except."
```

---

### Task 4: Icons

**Files:**
- Create: `prefab-gate/kicad/icon.png` (64×64)
- Create: `prefab-gate/kicad/plugin/icon24.png` (24×24)

Both are required: 64×64 for the PCM listing, 24×24 for the pcbnew toolbar. Written with stdlib `zlib` + `struct` so no image library is needed.

- [ ] **Step 1: Write the generator and produce both files**

```python
# prefab-gate/kicad/make_icons.py
"""Generate the two PNG icons the PCM and the toolbar require.

Stdlib only — KiCad's bundled Python has no Pillow, and adding a build-time
dependency to draw two flat images would be a poor trade. The mark is a shield
outline with a gate bar across it: verification, and a thing that stays shut.
"""
import os
import struct
import zlib

INK = (0x1F, 0x6F, 0x4B)      # green, "passed"
BAR = (0xF5, 0xF5, 0xF5)


def _shield(x, y, size):
    """True inside a rounded shield centred in a size x size field."""
    u, v = (x + 0.5) / size * 2 - 1, (y + 0.5) / size
    half = 0.86 - 0.34 * v * v
    if v < 0.62:
        return abs(u) <= half
    taper = (1 - v) / 0.38
    return abs(u) <= half * (0.35 + 0.65 * taper)


def _pixels(size):
    bar_top, bar_bottom = int(size * 0.46), int(size * 0.58)
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            if not _shield(x, y, size):
                row += bytes((0, 0, 0, 0))
            elif bar_top <= y < bar_bottom and size * 0.18 < x < size * 0.82:
                row += bytes(BAR) + b"\xff"
            else:
                row += bytes(INK) + b"\xff"
        yield bytes(row)


def _chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def write_png(path, size):
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    body = zlib.compress(b"".join(_pixels(size)), 9)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n"
                     + _chunk(b"IHDR", header)
                     + _chunk(b"IDAT", body)
                     + _chunk(b"IEND", b""))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    write_png(os.path.join(here, "icon.png"), 64)
    write_png(os.path.join(here, "plugin", "icon24.png"), 24)
    print("wrote icon.png (64) and plugin/icon24.png (24)")
```

- [ ] **Step 2: Run it and verify the dimensions**

```bash
cd prefab-gate/kicad && python3 make_icons.py
python3 -c "
import struct
for p, want in (('icon.png', 64), ('plugin/icon24.png', 24)):
    d = open(p, 'rb').read()
    w, h = struct.unpack('>II', d[16:24])
    print(f'  {p}: {w}x{h}', 'OK' if (w, h) == (want, want) else 'WRONG')
"
```
Expected: `icon.png: 64x64 OK` and `plugin/icon24.png: 24x24 OK`

- [ ] **Step 3: Commit**

```bash
git add prefab-gate/kicad/make_icons.py prefab-gate/kicad/icon.png prefab-gate/kicad/plugin/icon24.png
git commit -m "feat(kicad-plugin): add the PCM and toolbar icons

Two are required and they are different sizes: 64x64 for the manager's listing
and 24x24 for the pcbnew toolbar button. Generated from stdlib zlib and struct
rather than committing opaque binaries with no source, and without adding an
image library KiCad's bundled Python cannot install."
```

---

### Task 5: PCM manifest and archive builder

**Files:**
- Create: `prefab-gate/kicad/metadata.json`
- Create: `prefab-gate/kicad/build_pcm.py`
- Test: `prefab-gate/tests/test_build_pcm.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `build(repo_root, out_dir) -> (archive_path, submission_metadata_dict)`.

- [ ] **Step 1: Write `metadata.json`**

`download_*` fields are deliberately absent — the spec forbids them inside the archive; `build_pcm.py` adds them to the submission copy only.

```json
{
    "$schema": "https://go.kicad.org/pcm/schemas/v1",
    "name": "prefab-gate",
    "description": "Refuses to produce a fab package from a board that has not passed verification.",
    "description_full": "prefab-gate runs kicad-cli DRC with zone refill and schematic parity checking, classifies every finding as blocking or cosmetic, and reports whether the board is fit to fabricate.\n\nThe toolbar button checks and reports. It never writes to your project: the check runs against a copy of the board, schematic, project and custom-rules files in a temporary directory, because DRC refills zones and would otherwise rewrite the board open in your editor.\n\nStale zone fills are reported rather than silently repaired, and the dialog always names the file it read, because unsaved editor changes cannot be detected reliably from a plugin.\n\nExporting a verified fab package - gerbers, drill, CPL and BOM, with a manifest pinning them to the board that was checked - is available from the command line version.",
    "identifier": "com.github.danielboston38.prefab-gate",
    "type": "plugin",
    "author": {
        "name": "Mark Dymek",
        "contact": {
            "web": "https://github.com/danielboston38"
        }
    },
    "license": "MIT",
    "resources": {
        "homepage": "https://github.com/danielboston38/prefab-gate"
    },
    "tags": ["drc", "fabrication", "verification", "gerber", "design-review"],
    "versions": [
        {
            "version": "0.1.0",
            "status": "testing",
            "kicad_version": "8.0"
        }
    ]
}
```

- [ ] **Step 2: Write the failing tests**

```python
"""The archive must match KiCad's PCM layout exactly."""
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kicad"))

import build_pcm  # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     ".."))


class BuildTest(unittest.TestCase):

    def setUp(self):
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.out.cleanup)
        self.archive, self.submission = build_pcm.build(REPO, self.out.name)
        self.names = set(zipfile.ZipFile(self.archive).namelist())

    def test_metadata_sits_at_the_archive_root(self):
        self.assertIn("metadata.json", self.names)

    def test_plugin_code_is_under_plugins(self):
        for expected in ("plugins/__init__.py", "plugins/action.py",
                         "plugins/staging.py", "plugins/runner.py"):
            self.assertIn(expected, self.names)

    def test_the_gate_package_travels_with_the_plugin(self):
        """The plugin imports gate/ — shipping without it installs a plugin
        that cannot run."""
        self.assertTrue(any(n.startswith("plugins/gate/") for n in self.names))
        self.assertIn("plugins/prefab_gate.py", self.names)

    def test_both_icons_are_present(self):
        self.assertIn("resources/icon.png", self.names)
        self.assertIn("plugins/icon24.png", self.names)

    def test_archive_metadata_omits_download_fields(self):
        """The spec forbids them inside the package."""
        packed = json.loads(
            zipfile.ZipFile(self.archive).read("metadata.json"))
        for banned in ("download_sha256", "download_url", "download_size",
                       "install_size"):
            self.assertNotIn(banned, packed["versions"][0])

    def test_submission_metadata_carries_the_download_fields(self):
        version = self.submission["versions"][0]
        self.assertEqual(64, len(version["download_sha256"]))
        self.assertGreater(version["download_size"], 0)
        self.assertGreater(version["install_size"], 0)

    def test_version_has_no_prerelease_suffix(self):
        """The v2 schema rejects them; intent belongs in status."""
        version = self.submission["versions"][0]["version"]
        self.assertRegex(version, r"^\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?$")

    def test_identifier_matches_the_schema(self):
        self.assertRegex(self.submission["identifier"],
                         r"^[a-zA-Z][-a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$")

    def test_no_pycache_is_shipped(self):
        self.assertFalse([n for n in self.names if "__pycache__" in n])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_build_pcm.py' -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_pcm'`

- [ ] **Step 4: Write `build_pcm.py`**

```python
"""Build the PCM archive and the metadata that describes it.

KiCad expects metadata.json at the archive root, plugin code under plugins/,
and a 64x64 resources/icon.png. The gate package travels inside plugins/ so the
installed plugin can import it.

The download_* fields are computed here rather than maintained by hand, because
three numbers describing an artifact will drift from it otherwise. They are
written only into the submission copy: the spec forbids them inside the
archive.
"""
import hashlib
import json
import os
import zipfile


def _files(root):
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if name.endswith(".pyc"):
                continue
            yield os.path.join(base, name)


def build(repo_root, out_dir):
    """Write the archive into out_dir; return (path, submission_metadata)."""
    kicad = os.path.join(repo_root, "kicad")
    metadata = json.load(open(os.path.join(kicad, "metadata.json")))
    version = metadata["versions"][0]["version"]
    archive = os.path.join(out_dir, f"prefab-gate-{version}-pcm.zip")

    install_size = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps(metadata, indent=4))

        for path in _files(os.path.join(kicad, "plugin")):
            arc = "plugins/" + os.path.relpath(path, os.path.join(kicad, "plugin"))
            zf.write(path, arc)
            install_size += os.path.getsize(path)

        scripts = os.path.join(repo_root, "scripts")
        for path in _files(scripts):
            arc = "plugins/" + os.path.relpath(path, scripts)
            zf.write(path, arc)
            install_size += os.path.getsize(path)

        icon = os.path.join(kicad, "icon.png")
        zf.write(icon, "resources/icon.png")
        install_size += os.path.getsize(icon)

    submission = json.loads(json.dumps(metadata))
    submission["versions"][0].update({
        "download_sha256": hashlib.sha256(open(archive, "rb").read()).hexdigest(),
        "download_size": os.path.getsize(archive),
        "install_size": install_size,
    })
    return archive, submission


if __name__ == "__main__":
    root = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    out = os.path.join(root, "dist")
    os.makedirs(out, exist_ok=True)
    path, meta = build(root, out)
    with open(os.path.join(out, "metadata.submission.json"), "w") as handle:
        json.dump(meta, handle, indent=4)
    print(f"archive: {path}")
    print("submission metadata: "
          f"{os.path.join(out, 'metadata.submission.json')}")
    print("Set download_url to the release asset URL before submitting.")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_build_pcm.py' -v`
Expected: PASS, 9 tests

- [ ] **Step 6: Build the archive and check its size**

```bash
cd prefab-gate/kicad && python3 build_pcm.py && ls -lh ../dist/
```
Expected: an archive well under 1 MB — the whole point of not shipping the hardware repo

- [ ] **Step 7: Run the whole suite**

Run: `cd prefab-gate/scripts && PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'`
Expected: PASS, 208 tests

- [ ] **Step 8: Add `dist/` to the ignore list and commit**

```bash
echo "dist/" >> prefab-gate/.gitignore
git add prefab-gate/kicad/metadata.json prefab-gate/kicad/build_pcm.py \
        prefab-gate/tests/test_build_pcm.py prefab-gate/.gitignore
git commit -m "feat(kicad-plugin): build the PCM archive

Assembles KiCad's expected layout - metadata.json at the root, plugin code and
the gate package under plugins/, a 64x64 resources/icon.png - and computes
download_sha256, download_size and install_size rather than leaving three
numbers to be kept in step with the artifact they describe by hand.

Those fields go only into the submission copy. The spec forbids them inside the
archive, which is an easy rule to break by copying one file to both places, so
a test asserts their absence."
```

---

### Task 6: Manual verification in KiCad

This is the only coverage the wx layer gets, so it is a task rather than a footnote.

- [ ] **Step 1: Install the archive**

KiCad → Plugin and Content Manager → *Install from File* → `prefab-gate/dist/prefab-gate-0.1.0-pcm.zip`

- [ ] **Step 2: Confirm the gate package survived the install**

Check that `plugins/gate/` is present in the installed plugin directory and was not flattened.

This is expected to pass and is no longer a design risk: the official repository's InteractiveHtmlBom ships `plugins/` with five subdirectories, including nested packages (`plugins/ecad/kicad_extra/__init__.py`) and assets three levels deep. The documentation's "no subdirectories" means "do not wrap your plugin in an extra folder". Verify anyway — it costs one `ls`.

- [ ] **Step 3: Run it against the NES board**

Open `nes_power_video.kicad_pcb`, click the toolbar button. Expected: PASSED, 0 blocking, 6 cosmetic silkscreen findings on J2/J3, and the dialog naming the board path and its last-saved time.

- [ ] **Step 4: Confirm it wrote nothing**

```bash
cd ~/nes_power_video && git status --short
```
Expected: no modification to `nes_power_video.kicad_pcb`. **This is the plugin's central promise; if the board is dirty, stop.**

- [ ] **Step 5: Check the unsaved-board path**

File → New Board, click the button without saving. Expected: the "This board has not been saved yet" message, not a traceback.

- [ ] **Step 6: Record the result**

```bash
git commit --allow-empty -m "test(kicad-plugin): verified against KiCad 10.0.6

Installed from file, ran against nes_power_video.kicad_pcb: PASSED, 0
blocking, 6 cosmetic. Board unmodified afterwards, which is the plugin's
central promise. Unsaved-board path reports rather than raising.

Confirms plugins/ tolerates the gate package as a subdirectory, which the
documentation's 'no subdirectories' wording left ambiguous."
```

---

### Task 7: Split into its own repository — **STOP, needs the user**

Everything above is local and reversible. This task creates a public repository and is not.

- [ ] **Step 1: Ask before doing anything**

Confirm with the user: the repository name (`prefab-gate`), and **public or private**. Do not create it on assumption.

- [ ] **Step 2: Split the history**

```bash
cd ~/nes_power_video
git subtree split --prefix=prefab-gate -b prefab-gate-export
git log --oneline prefab-gate-export | wc -l   # sanity: many commits, not one
```

- [ ] **Step 3: Create and push**

```bash
gh repo create prefab-gate --<public|private> \
  --description "Refuses to produce a KiCad fab package from a board that has not passed verification."
git push git@github.com:danielboston38/prefab-gate.git prefab-gate-export:main
```

- [ ] **Step 4: Verify the tests pass from a clean clone**

```bash
cd $(mktemp -d) && git clone git@github.com:danielboston38/prefab-gate.git && cd prefab-gate/scripts
PYTHONPATH=. python3 -m unittest discover -s ../tests -p 'test_*.py'
```
Expected: PASS, 208 tests. A green suite in a fresh clone is what proves the split is complete.

- [ ] **Step 5: Update the board repo**

Remove `prefab-gate/`, point `.claude-plugin/marketplace.json` at the new repo, and rewrite the README's `python3 prefab-gate/scripts/prefab_gate.py` invocations to use `prefab_gate` on PATH. Commit.

---

### Task 8: Submit to the PCM repository — **STOP, needs the user**

> **Confirm with Mark before submitting.** The address is
> `https://gitlab.com/kicad/addons/metadata` — a merge request adding a
> directory under `packages/` named for the package identifier. The restriction
> that caused earlier confusion is narrow: **do not submit to
> `https://gitlab.com/kicad/addons/repository`**, which is the generated
> repository, not the metadata source. An addon submission is public and
> effectively unsendable, so it is still a stop-and-ask, not an assumption.

- [ ] **Step 1: Publish a release**

Tag `0.1.0` in the new repo and attach `prefab-gate-0.1.0-pcm.zip` as a release asset. Take its download URL.

- [ ] **Step 2: Regenerate the submission metadata**

```bash
cd prefab-gate/kicad && python3 build_pcm.py
```
Set `download_url` in `dist/metadata.submission.json` to the release asset URL. The sha256 must match the asset actually uploaded.

- [ ] **Step 3: Open the merge request, after confirming with Mark**

Fork `https://gitlab.com/kicad/addons/metadata`, create
`packages/com.github.danielboston38.prefab-gate/` containing the submission
`metadata.json` and the 64×64 icon, and open the MR.

**Not** `https://gitlab.com/kicad/addons/repository` — that is the generated
repository and is not where packages are submitted. Several packages sharing a
namespace may go in one MR; this is a single package.

- [ ] **Step 4: Note the ongoing commitment**

KiCad may remove packages with unresolved bugs after 90 days. Record that this is now maintained software with an external audience.
