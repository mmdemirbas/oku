# oku for IntelliJ IDEA — proof of concept

Opens an oku page as text + the kit's own rendering, side by side, inside
IntelliJ IDEA. The preview is what `oku build` ships, because it is made by
the same code: the editor buffer goes to the installed oku tool
(`md_to_v2_page` → `compute_manifest` → `build_standalone`) and the result is
shown in the IDE's embedded Chromium (JCEF).

The research, the measurements and the plan are in [`docs/index.md`](docs/index.md)
(Turkish; `oku build` in `docs/` renders it).

Status: **proof of concept.** The bridge in
`src/main/resources/oku-preview/preview.py` calls private helpers of
`oku.cli`; the plan replaces it with an `oku preview` subcommand.

## Requirements

- IntelliJ IDEA 2026.2 or newer (any IntelliJ-based IDE of that build should
  work; only IDEA 2026.2.3 was tried).
- oku installed as a tool (`./ctl deploy` in this repo). The plugin finds its
  Python through the `oku` launcher's shebang, on PATH or in `~/.local/bin`.
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
```

`runIde` opens the sandbox with JCEF remote debugging on port 9222, so the
preview can be measured over CDP the way `src/oku_tests/browser/` measures a
built page. From the repository root:

| Script | What it checks |
|---|---|
| `tools/check_preview.py <html>` | A page `preview.py` wrote, in headless Chromium: what rendered, console errors, scroll restored after a reload. No IDE needed. |
| `tools/probe_ide.py probe [shot.png]` | The preview inside the sandbox IDE: the same counts, plus a screenshot. |
| `tools/edit_sync_ide.py <ide-pid> <page.md> [<page.md> …]` | Appends a marker to each page on disk, activates the IDE (it reads external changes on activation), times until each preview shows it, restores the files. |
| `tools/nav_and_edit_ide.py <docs-dir>` | Clicks a link to a page that is not open yet; the IDE should open it and the panel should stay put. |
| `tools/idea_link_ide.py <file> <line>` | Follows the kit's `idea://open?file=…&line=…` link; the IDE should open the file. |

Run each with `uv run python ide/intellij/tools/<script>`. The scripts that
edit pages restore them in a `finally`; check `git status docs/` anyway.
