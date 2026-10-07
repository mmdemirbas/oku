# oku for IntelliJ IDEA

Opens an oku page as text + the kit's own rendering, side by side, inside
IntelliJ IDEA. The preview is what `oku build` ships, because it is made by
the same code: the editor buffer goes to `oku preview --serve`, one process
the whole IDE shares, and the page it writes is shown in the IDE's embedded
Chromium (JCEF). After the first load an edit does not reload the panel: the
new page goes to the kit's `OkuRenderer.update`, which rebuilds only the
blocks the edit changed, so open details, table filters, drawn diagrams and
the reader's place survive. A change to anything else the page carries (the
site tree, kit.json, the theme) reloads it.

A file chip in the preview opens its file in the IDE, on the line a
`#f/path:120` reference names, and so does a link to a local `.md`: the
plugin sets the kit's `window.__okuHost` on every load, and the kit asks
it before opening its own viewer. That works on every OS, where the kit's
`idea://` link is offered on macOS only. A link to a heading on another
page (`other.md#setup`) opens that page at the heading: the kit hands over
the id, and oku says which line carries it, so the plugin keeps no copy of
oku's heading-id rule.

While a page is typed, the editor shows what `oku check` would report for it,
on the lines it is about: errors and warnings, from the unsaved text,
checked inside its tree so a link to an anchor another page lacks is caught
too. A second `oku preview --serve` process does the checking, so a preview
never waits behind it.

An `oku-*` fence is JSON in the editor, and its keys complete from the schema
oku names for that fence (generated from the kit's page schema, so the editor
and `oku check` cannot disagree about a shape). Typing ```` ```oku ```` offers
the fence tags. A key the kit does not know is reported by the check on the
fence's line: the Markdown plugin hides problems inside code fences unless
*Show problems in code blocks* is on in its settings.

A `#f/` link is a file reference: Cmd+click opens the file, and the path
completes segment by segment, resolved the way oku resolves it (beside the
page first, then from the project root; a `:line` suffix only when the whole
string is not a file). The Markdown plugin reads every `#…` link as a heading
id and reports `#f/`, `#g/` and `#x/` links as anchors it cannot find; on an
oku page that report is suppressed, and a real missing heading still gets it.

The preview follows the editor: the source line at the top of the editor
is put at the top of the page. A double-click on the page goes the other
way — the caret moves to that line and the editor is scrolled to where the
page is, so neither pane jumps.

The research, the measurements and the plan are in [`docs/index.md`](docs/index.md)
(Turkish; `oku build` in `docs/` renders it).

Installed by `./ctl deploy ide` (below), not through the Marketplace. The JSON
`oku preview` speaks is the contract (`docs/cli.md` in this repo,
`PREVIEW_PROTOCOL` in `cli.py`): the process greets with its protocol
number, and a plugin and an oku that disagree say which one to update
instead of failing on a missing field.

## Requirements

- An IntelliJ-based IDE of build 262 (2026.2) or newer that ships JCEF.
  IntelliJ IDEA 2026.2.3 and Rider 2026.2.3.1 load it; Android Studio
  2026.2.1 has no JCEF and cannot.
- oku installed as a tool (`./ctl deploy` in this repo), new enough to speak
  the plugin's preview protocol. The plugin runs the oku set in
  *Settings → Tools → oku*, else the `oku` on PATH, else `~/.local/bin/oku`
  (an IDE started from the Dock has no shell PATH). A path set there that
  does not run is reported as that, not passed over for another oku. To
  point a development IDE at a checkout, start it with
  `-Doku.executable=/abs/oku/.venv/bin/oku`, which wins over the settings
  (not `bin/oku`: run directly, its shebang finds a python3 without
  jsonschema, and oku then refuses to check).
- Two processes run: one renders previews, one checks pages, so a preview
  never waits behind a check of the whole tree. They write their stderr to
  `<IDE system dir>/oku-preview/preview.log` and `check.log`; a failure to
  start shows the last lines in the panel.

## Install

From the repository root:

```bash
./ctl deploy ide          # lists the IDEs it finds and asks which
./ctl deploy ide all      # every IDE that can load the plugin
./ctl deploy ide IU rider # by product code, part of the name, or data directory
./ctl deploy ide /opt/odd/idea   # an installation the search does not look in
./ctl status              # which plugin build each IDE has
```

It first makes sure the global oku is this checkout's, because the plugin
needs an oku that speaks its preview protocol. Then it builds the zip and
puts it in each chosen IDE's plugins directory. An older copy is replaced,
found by plugin id rather than by directory name. The same build is not
written twice. The new copy is compared with the build before it says ✓.
An IDE that cannot load the plugin is named with the reason and skipped.
A running IDE loads the new copy when it restarts.

Two choices here hold on any machine:

- **The plugins directory is the IDE's own rule**, read out of its
  `PathManager`: `idea.plugins.path` from the first `idea.properties` that
  sets it, else `idea.config.path`/plugins, else the platform default. On
  Linux the default has no `/plugins` and follows `XDG_DATA_HOME`.
  Android Studio's vendor directory is `Google`. The rules are tested
  for macOS, Linux and Windows layouts in
  `src/oku_tests/test_ide_install.py`, but only macOS was run for real.
- **The build runs on the IDE's own runtime** (its JBR), so a machine
  needs no JDK. That is why `build.gradle.kts` sets a Java 21 bytecode
  target and no toolchain: a toolchain asks for a JDK 21, and the 2026.2
  JBR is Java 25.

`install.py` does the work, and its docstring lists what it accepts.

## Build by hand

```bash
cd ide/intellij
JAVA_HOME="/path/to/IDE.app/Contents/jbr/Contents/Home" ./gradlew buildPlugin   # any JDK 21 or newer
# → build/distributions/oku-intellij-<version>.zip
```

The build compiles against the IDE at `ideaPath` in `gradle.properties`
(the one on this machine, so nothing is downloaded); pass
`-PideaPath=/path/to/IDE.app` to use another. `./ctl deploy ide` passes
the IDE it builds against.

```bash
./gradlew test    # platform tests; run `uv sync` in the oku repository first
```

The tests drive this checkout's `.venv/bin/oku`, so they exercise the oku
the repository holds rather than whichever one is installed. They start a
real `oku preview --serve` against files written to a temporary directory.

```bash
./gradlew verifyPlugin   # the IntelliJ Plugin Verifier, against the IDE at ideaPath
```

## Which files it takes

A `.md` file is an oku page when a `kit.json` or an `_oku` link sits in one of
its directories up to the repository root, or when the file contains an
` ```oku- ` fence. Those open in the oku editor and the bundled Markdown
editor is hidden for them (`FileEditorPolicy.HIDE_OTHER_EDITORS`, per file);
every other `.md` opens as before. The split layout the reader picks
(editor, preview, both) is kept per file between sessions.

*Settings → Tools → oku* has a switch that turns all of it off: no file is
an oku page then, and nothing of oku runs. A file already open changes when
it is opened again.

When no oku can draw a page — none installed, the one set in the settings
does not run, or the IDE has no JCEF — an oku page opens in the Markdown
editor instead, and the first one that does says why in a notification,
once per IDE session. A check that cannot run for any other reason (an oku
too old for the plugin, a process that does not answer) says so at the top
of the file: an empty margin is how a clean page looks.

## Verify in a sandbox IDE

```bash
./gradlew runIde -PopenPaths=/abs/oku/docs,/abs/oku/docs/index.md
# add -PokuExecutable=/abs/oku/.venv/bin/oku to preview with this checkout (uv sync first)
# add -Pbackground to keep the sandbox from ever taking focus (macOS)
```

`runIde` opens the sandbox with JCEF remote debugging on port 9222, so the
preview can be measured over CDP the way `src/oku_tests/browser/` measures a
built page. From the repository root:

| Script | What it checks |
|---|---|
| `tools/check_preview.py <html>` | A page `oku preview` wrote, in headless Chromium: what rendered, console errors, scroll restored after a reload. No IDE needed. |
| `tools/probe_ide.py probe [shot.png]` | The preview inside the sandbox IDE: the same counts, plus a screenshot. |
| `tools/edit_sync_ide.py <ide-pid> <page.md> [<page.md> …]` | Appends a marker to each page on disk, activates the IDE (it reads external changes on activation), times until each preview shows it, restores the files. |
| `tools/quiet_edit_ide.py <page.md>` | The same edit without moving focus: waits for the IDE's own background refresh (seconds, not the plugin's time) and reports whether the edit arrived without a reload. Pairs with `-Pbackground`. |
| `tools/nav_and_edit_ide.py <docs-dir>` | Clicks a link to a page that is not open yet; the IDE should open it and the panel should stay put. |
| `tools/idea_link_ide.py <file> <line>` | Follows the kit's `idea://open?file=…&line=…` link; the IDE should open the file. |
| `tools/measure_render.py <page.md> …` | What one render costs, phase by phase, once per process and in a `--serve` session; prints the chart `docs/index.md` carries. |

Run each with `uv run python ide/intellij/tools/<script>`. The scripts that
edit pages restore them in a `finally`; check `git status docs/` anyway.
