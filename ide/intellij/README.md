# oku for IntelliJ IDEA — proof of concept

Opens an oku page as text + the kit's own rendering, side by side, inside
IntelliJ IDEA. The preview is what `oku build` ships, because it is made by
the same code: the editor buffer goes to `oku preview --serve`, one process
the whole IDE shares, and the page it writes is shown in the IDE's embedded
Chromium (JCEF). After the first load an edit does not reload the panel: the
new page goes to the kit's `OkuRenderer.update`, which rebuilds only the
blocks the edit changed, so open details, table filters, drawn diagrams and
the reader's place survive. A change to anything else the page carries (the
site tree, kit.json, the theme) reloads it.

The research, the measurements and the plan are in [`docs/index.md`](docs/index.md)
(Turkish; `oku build` in `docs/` renders it).

Status: **proof of concept.** The JSON `oku preview` speaks is the contract
(`docs/cli.md` in this repo, `PREVIEW_PROTOCOL` in `cli.py`): the process
greets with its protocol number, and a plugin and an oku that disagree say
which one to update instead of failing on a missing field.

## Requirements

- IntelliJ IDEA 2026.2 or newer (any IntelliJ-based IDE of that build should
  work; only IDEA 2026.2.3 was tried).
- oku installed as a tool (`./ctl deploy` in this repo), new enough to have
  `oku preview`. The plugin runs the `oku` on PATH, or in `~/.local/bin`
  when the IDE was started from the Dock and has no shell PATH. To point it
  at a checkout while developing, start the IDE with
  `-Doku.executable=/abs/oku/bin/oku`.
- The process writes its stderr to `<IDE system dir>/oku-preview/preview.log`;
  a failure to start shows its last lines in the panel.
- JDK 21 to run Gradle.

## Build and install

```bash
cd ide/intellij
JAVA_HOME=$(/usr/libexec/java_home -v 21) ./gradlew buildPlugin
# → build/distributions/oku-intellij-0.0.1-poc.zip
# Settings → Plugins → ⚙ → Install Plugin from Disk…
```

The build compiles against the IDE at `ideaPath` in `gradle.properties`
(the one on this machine, so nothing is downloaded); pass
`-PideaPath=/path/to/IDE.app` to use another.

## Which files it takes

A `.md` file is an oku page when a `kit.json` or an `_oku` link sits in one of
its directories up to the repository root, or when the file contains an
` ```oku- ` fence. Those open in the oku editor and the bundled Markdown
editor is hidden for them (`FileEditorPolicy.HIDE_OTHER_EDITORS`, per file);
every other `.md` opens as before.

## Verify in a sandbox IDE

```bash
./gradlew runIde -PopenPaths=/abs/oku/docs,/abs/oku/docs/index.md
# add -PokuExecutable=/abs/oku/bin/oku to preview with this checkout
```

`runIde` opens the sandbox with JCEF remote debugging on port 9222, so the
preview can be measured over CDP the way `src/oku_tests/browser/` measures a
built page. From the repository root:

| Script | What it checks |
|---|---|
| `tools/check_preview.py <html>` | A page `oku preview` wrote, in headless Chromium: what rendered, console errors, scroll restored after a reload. No IDE needed. |
| `tools/probe_ide.py probe [shot.png]` | The preview inside the sandbox IDE: the same counts, plus a screenshot. |
| `tools/edit_sync_ide.py <ide-pid> <page.md> [<page.md> …]` | Appends a marker to each page on disk, activates the IDE (it reads external changes on activation), times until each preview shows it, restores the files. |
| `tools/nav_and_edit_ide.py <docs-dir>` | Clicks a link to a page that is not open yet; the IDE should open it and the panel should stay put. |
| `tools/idea_link_ide.py <file> <line>` | Follows the kit's `idea://open?file=…&line=…` link; the IDE should open the file. |
| `tools/measure_render.py <page.md> …` | What one render costs, phase by phase, once per process and in a `--serve` session; prints the chart `docs/index.md` carries. |

Run each with `uv run python ide/intellij/tools/<script>`. The scripts that
edit pages restore them in a `finally`; check `git status docs/` anyway.
