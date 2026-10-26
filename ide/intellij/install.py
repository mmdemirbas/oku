"""Install the oku plugin into the JetBrains IDEs on this machine.

`./ctl deploy ide` is the way in: it makes sure the global oku is the one
this checkout builds before it runs this, because the plugin speaks a
preview protocol and an older oku answers nothing the plugin can use.

    python ide/intellij/install.py list
    python ide/intellij/install.py install [all | <ide> ...]

An <ide> is a product code (IU, RD), a data directory name
(IntelliJIdea2026.2), part of the IDE's name (rider), or the path of an
installation the search below does not look in. Name none and a terminal
is asked which; anywhere else nothing is installed.

Where an IDE keeps its plugins is the IDE's own rule, read out of
PathManager (util-8.jar, 2026.2) and matching
https://www.jetbrains.com/help/idea/directories-used-by-the-ide-to-store-settings-caches-plugins-and-logs.html:
`idea.plugins.path` from the first idea.properties that sets it, else
`idea.config.path` + /plugins, else the platform default. The default's
vendor directory is the product's company, so Android Studio's is Google.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
BUILD_FILE = PLUGIN_DIR / "build.gradle.kts"
SOURCE_XML = PLUGIN_DIR / "src/main/resources/META-INF/plugin.xml"


@dataclass(frozen=True)
class Ide:
    home: Path  # the .app on macOS, the installation directory elsewhere
    name: str
    version: str
    code: str
    build: str
    data_dir: str
    provides: frozenset[str]  # bundled plugin, module and alias ids
    config: Path
    plugins: Path
    jbr: Path

    @property
    def label(self) -> str:
        return f"{self.name} {self.version}"


@dataclass(frozen=True)
class Build:
    zip: Path
    plugin_id: str
    version: str
    since: str
    until: str | None
    requires: tuple[str, ...]
    top: str  # the directory the zip unpacks to
    digest: str


@dataclass(frozen=True)
class Found:
    path: Path
    version: str
    digest: str


# --- where IDEs are ---------------------------------------------------------


def _install_patterns(system: str, env: dict[str, str], home: Path) -> list[tuple[Path, str]]:
    """Where the installers and the Toolbox App put IDEs, as (base, glob)."""
    if system == "Darwin":
        toolbox = home / "Library/Application Support/JetBrains/Toolbox/apps"
        info = "Contents/Resources/product-info.json"
        return [
            (Path("/Applications"), f"*.app/{info}"),
            (home / "Applications", f"*.app/{info}"),
            (home / "Applications", f"*/*.app/{info}"),
            (toolbox, f"*/*.app/{info}"),
            (toolbox, f"*/ch-*/*/*.app/{info}"),
        ]
    if system == "Windows":
        local = Path(env.get("LOCALAPPDATA", home / "AppData/Local"))
        programs = Path(env.get("ProgramFiles", "C:/Program Files"))
        return [
            (local / "Programs", "*/product-info.json"),
            (programs / "JetBrains", "*/product-info.json"),
            (local / "JetBrains/Toolbox/apps", "*/product-info.json"),
            (local / "JetBrains/Toolbox/apps", "*/ch-*/*/product-info.json"),
        ]
    toolbox = Path(env.get("XDG_DATA_HOME") or home / ".local/share") / "JetBrains/Toolbox/apps"
    return [
        (Path("/opt"), "*/product-info.json"),
        (Path("/opt"), "*/*/product-info.json"),
        (Path("/usr/local"), "*/product-info.json"),
        (Path("/snap"), "*/current/product-info.json"),
        (home / "opt", "*/product-info.json"),
        (home / "Applications", "*/product-info.json"),
        (toolbox, "*/product-info.json"),
        (toolbox, "*/ch-*/*/product-info.json"),
    ]


def _product_info(home: Path) -> Path:
    mac = home / "Contents/Resources/product-info.json"
    return mac if mac.is_file() else home / "product-info.json"


def _home_of(product_info: Path) -> Path:
    if product_info.parent.name == "Resources" and product_info.parent.parent.name == "Contents":
        return product_info.parent.parent.parent
    return product_info.parent


def _properties(path: Path) -> dict[str, str]:
    """A .properties file, as far as these keys need: key=value, # comments."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] in "#!" or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _expand(value: str, home: Path) -> Path:
    value = value.replace("${user.home}", str(home))
    if "${" in value:
        raise ValueError(f"cannot resolve {value!r}: only ${{user.home}} is understood here")
    return Path(value)


def _platform_dir(
    system: str, env: dict[str, str], home: Path, vendor: str, data_dir: str, kind: str
) -> Path:
    """PathManager.platformPath: kind is "config" or "plugins"."""
    if system == "Darwin":
        config = home / "Library/Application Support" / vendor / data_dir
        return config if kind == "config" else config / "plugins"
    if system == "Windows":
        config = Path(env.get("APPDATA") or home / "AppData/Roaming") / vendor / data_dir
        return config if kind == "config" else config / "plugins"
    if kind == "config":
        return Path(env.get("XDG_CONFIG_HOME") or home / ".config") / vendor / data_dir
    # Linux keeps plugins in the data directory itself, with no /plugins.
    return Path(env.get("XDG_DATA_HOME") or home / ".local/share") / vendor / data_dir


def read_ide(home: Path, system: str, env: dict[str, str], user_home: Path) -> Ide:
    info = json.loads(_product_info(home).read_text(encoding="utf-8"))
    vendor = info.get("productVendor") or "JetBrains"
    data_dir = info["dataDirectoryName"]
    config = _platform_dir(system, env, user_home, vendor, data_dir, "config")
    bin_dir = home / "Contents/bin" if (home / "Contents/bin").is_dir() else home / "bin"
    # PathManager.loadProperties: the first file to set a key decides it.
    files = [
        env.get(f"{info.get('envVarBaseName', 'IDEA')}_PROPERTIES"),
        config / "idea.properties",
        user_home / "idea.properties",
        bin_dir / "idea.properties",
    ]
    props: dict[str, str] = {}
    for file in files:
        if file:
            for key, value in _properties(Path(file)).items():
                props.setdefault(key, value)
    if "idea.config.path" in props:
        config = _expand(props["idea.config.path"], user_home)
    if "idea.plugins.path" in props:
        plugins = _expand(props["idea.plugins.path"], user_home)
    elif "idea.config.path" in props:
        plugins = config / "plugins"
    else:
        plugins = _platform_dir(system, env, user_home, vendor, data_dir, "plugins")
    layout = {e["name"] for e in info.get("layout", []) if e.get("kind") in ("plugin", "pluginAlias")}
    jbr = home / "Contents/jbr/Contents/Home" if system == "Darwin" else home / "jbr"
    return Ide(
        home=home,
        name=info["name"],
        version=info.get("version", ""),
        code=info.get("productCode", ""),
        build=info["buildNumber"],
        data_dir=data_dir,
        provides=frozenset(info.get("bundledPlugins", [])) | frozenset(info.get("modules", [])) | layout,
        config=config,
        plugins=plugins,
        jbr=jbr,
    )


def discover(system: str, env: dict[str, str], home: Path, problems: list[str] | None = None) -> list[Ide]:
    """Every IDE found, one per plugins directory, the newest build kept.

    An installation that cannot be read is named in `problems` rather than
    passed over: an IDE missing from the list with no word said is one the
    reader goes looking for.
    """
    found: dict[Path, Ide] = {}
    for base, pattern in _install_patterns(system, env, home):
        if not base.is_dir():
            continue
        for info in sorted(base.glob(pattern)):
            try:
                ide = read_ide(_home_of(info), system, env, home)
            except (OSError, ValueError, KeyError) as e:
                if problems is not None:
                    problems.append(f"{_home_of(info)}: {e}")
                continue
            kept = found.get(ide.plugins)
            if kept is None or _build_key(ide.build) > _build_key(kept.build):
                found[ide.plugins] = ide
    return sorted(found.values(), key=lambda i: (i.name, _build_key(i.build)))


# --- what was built ---------------------------------------------------------


def _build_key(build: str) -> tuple[int, ...]:
    """262.10968.63 → (262, 10968, 63); a product prefix (IU-) is dropped."""
    build = build.split("-", 1)[-1]
    return tuple(int(p) if p.isdigit() else 0 for p in build.split("."))


def _plugin_xml(jar: Path | bytes) -> ET.Element | None:
    with zipfile.ZipFile(io.BytesIO(jar) if isinstance(jar, bytes) else jar) as z:
        if "META-INF/plugin.xml" not in z.namelist():
            return None
        return ET.fromstring(z.read("META-INF/plugin.xml"))


def _tree_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode() + b"\0" + hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


def read_build(zip_path: Path) -> Build:
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        top = names[0].split("/", 1)[0]
        files = {n.split("/", 1)[1]: z.read(n) for n in names}
    for name, data in files.items():
        if name.startswith("lib/") and name.endswith(".jar") and (xml := _plugin_xml(data)) is not None:
            break
    else:
        raise ValueError(f"{zip_path}: no jar under lib/ holds META-INF/plugin.xml")
    version = xml.find("idea-version")
    return Build(
        zip=zip_path,
        plugin_id=xml.findtext("id", ""),
        version=xml.findtext("version", ""),
        since=version.get("since-build", "") if version is not None else "",
        until=version.get("until-build") if version is not None else None,
        requires=tuple(
            d.text.strip() for d in xml.findall("depends") if d.get("optional") != "true" and d.text
        ),
        top=top,
        digest=_tree_digest(files),
    )


def plugin_id() -> str:
    return ET.parse(SOURCE_XML).getroot().findtext("id", "")


def gradle_facts() -> tuple[str, list[str]]:
    """The version build.gradle.kts gives the plugin, and the bundled plugins it compiles against."""
    text = BUILD_FILE.read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', text, re.M)
    if version is None:
        raise ValueError(f"{BUILD_FILE}: no version line")
    return version.group(1), re.findall(r'bundledPlugin\("([^"]+)"\)', text)


def last_build() -> Build | None:
    """The zip the last build left, which is all `list` has to judge by."""
    version, _ = gradle_facts()
    zip_path = PLUGIN_DIR / "build/distributions" / f"oku-intellij-{version}.zip"
    return read_build(zip_path) if zip_path.is_file() else None


def build_plugin(ide: Ide) -> Build:
    """`gradlew buildPlugin` against `ide`, on the runtime that IDE ships, so a
    machine needs no JDK of its own: whoever installs into an IDE has one."""
    version, _ = gradle_facts()
    gradlew = PLUGIN_DIR / ("gradlew.bat" if platform.system() == "Windows" else "gradlew")
    env = dict(os.environ, JAVA_HOME=str(ide.jbr))
    # --no-watch-fs: a daemon watching the file system has called an edited
    # source up to date, and a zip built from that is the old plugin
    # installed as the new one. Reading the sources costs the build little.
    cmd = [str(gradlew), "-q", "--console=plain", "--no-watch-fs", "buildPlugin", f"-PideaPath={ide.home}"]
    subprocess.run(cmd, cwd=PLUGIN_DIR, env=env, check=True)
    return read_build(PLUGIN_DIR / "build/distributions" / f"oku-intellij-{version}.zip")


# --- what an IDE has --------------------------------------------------------


def why_not(ide: Ide, build: Build) -> str | None:
    """Why `ide` cannot load `build`, or None when it can."""
    if build.since and _build_key(ide.build) < _build_key(build.since):
        return f"build {ide.build} is older than {build.since}, the oldest the plugin supports"
    until = _build_key(build.until.removesuffix(".*")) if build.until else None
    if until and _build_key(ide.build)[: len(until)] > until:
        return f"build {ide.build} is newer than {build.until}, the newest the plugin supports"
    missing = [r for r in build.requires if r not in ide.provides]
    if missing:
        return f"has no {', '.join(missing)}"
    return None


def installed(ide: Ide, plugin_id: str) -> list[Found]:
    """Every copy of the plugin in the IDE's plugins directory, found by id, not by name."""
    out: list[Found] = []
    if not ide.plugins.is_dir():
        return out
    for entry in sorted(ide.plugins.iterdir()):
        jars = (
            sorted((entry / "lib").glob("*.jar"))
            if entry.is_dir()
            else [entry]
            if entry.suffix == ".jar"
            else []
        )
        for jar in jars:
            try:
                xml = _plugin_xml(jar)
            except (OSError, zipfile.BadZipFile):
                continue
            if xml is not None and xml.findtext("id") == plugin_id:
                out.append(Found(entry, xml.findtext("version", ""), _entry_digest(entry)))
                break
    return out


def _entry_digest(entry: Path) -> str:
    if entry.is_file():
        return _tree_digest({entry.name: entry.read_bytes()})
    return _tree_digest(
        {p.relative_to(entry).as_posix(): p.read_bytes() for p in entry.rglob("*") if p.is_file()}
    )


def disabled(ide: Ide, plugin_id: str) -> bool:
    listed = ide.config / "disabled_plugins.txt"
    return listed.is_file() and plugin_id in listed.read_text(encoding="utf-8").split()


def running(ide: Ide) -> bool | None:
    """Whether the IDE itself is running; None where `ps` cannot say.

    A process merely started from the IDE's directory is not the IDE: the
    Gradle daemon this very install starts runs on the IDE's JBR. The IDE is
    its launcher (Contents/MacOS, bin/), or a JVM running its main class.
    """
    try:
        ps = subprocess.run(["ps", "-A", "-o", "command="], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    launchers = (str(ide.home / "Contents/MacOS") + os.sep, str(ide.home / "bin") + os.sep)
    return any(
        line.startswith(launchers)
        or (line.startswith(str(ide.home) + os.sep) and "com.intellij.idea.Main" in line)
        for line in ps.splitlines()
    )


def install(ide: Ide, build: Build) -> bool:
    """Put `build` in the IDE's plugins directory. False: it was already there.

    Every copy found by id is moved aside before the new one goes in, so two
    versions never sit side by side. A rename, not a rewrite: an IDE that is
    running keeps reading the files it opened until it restarts.
    """
    copies = installed(ide, build.plugin_id)
    target = ide.plugins / build.top
    if [c.digest for c in copies] == [build.digest] and copies[0].path == target:
        return False
    ide.plugins.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".oku-install-", dir=ide.plugins.parent))
    try:
        with zipfile.ZipFile(build.zip) as z:
            z.extractall(stage / "new")
        aside: list[tuple[Path, Path]] = []
        try:
            for old in {c.path for c in copies} | ({target} if target.exists() else set()):
                moved = stage / f"old-{len(aside)}"
                old.rename(moved)
                aside.append((old, moved))
            (stage / "new" / build.top).rename(target)
        except OSError:
            # Whatever was moved aside goes back: a failed install leaves the
            # plugin the IDE had, never no plugin.
            for old, moved in reversed(aside):
                moved.rename(old)
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return True


# --- the command ------------------------------------------------------------


def state(ide: Ide, build: Build | None, plugin_id: str) -> str:
    if build is not None and (reason := why_not(ide, build)):
        return f"cannot run oku: {reason}"
    copies = installed(ide, plugin_id)
    if not copies:
        return "not installed"
    words = f"oku {copies[0].version}"
    if build is not None:
        same = copies[0].digest == build.digest
        words += ", the same as this checkout's last build" if same else ", not this checkout's last build"
    if len(copies) > 1:
        words += f", and {len(copies) - 1} more copies"
    if disabled(ide, plugin_id):
        words += ", disabled in Settings → Plugins"
    return words


def table(ides: list[Ide], build: Build | None, plugin_id: str, numbered: bool) -> str:
    """One row per IDE, one column per field, so the eye reads down a column."""
    rows = [
        [str(n), ide.label, f"{ide.code}-{ide.build}", state(ide, build, plugin_id)]
        for n, ide in enumerate(ides, 1)
    ]
    if not numbered:
        rows = [r[1:] for r in rows]
    widths = [max(len(r[c]) for r in rows) for c in range(len(rows[0]) - 1)] if rows else []
    return "\n".join("  " + "  ".join([*(r[c].ljust(w) for c, w in enumerate(widths)), r[-1]]) for r in rows)


def select(ides: list[Ide], tokens: list[str], system: str, env: dict[str, str], home: Path) -> list[Ide]:
    chosen: list[Ide] = []
    for token in tokens:
        if token == "all":
            matches = list(ides)
        elif "/" in token or os.sep in token or token.startswith("~"):
            path = Path(token).expanduser().resolve()
            if not _product_info(path).is_file():
                raise SystemExit(f"✗ {path} is not an IDE installation: it holds no product-info.json")
            matches = [read_ide(path, system, env, home)]
        else:
            t = token.casefold()
            matches = [
                i
                for i in ides
                if t in (i.code.casefold(), i.data_dir.casefold())
                or t in i.name.casefold()
                or t in i.data_dir.casefold()
            ]
            if not matches:
                found = ", ".join(f"{i.label} ({i.code}, {i.data_dir})" for i in ides) or "none"
                raise SystemExit(f"✗ no IDE here matches {token!r}. Found: {found}")
        chosen += [m for m in matches if m not in chosen]
    return chosen


def ask(ides: list[Ide], build: Build, prompt=input) -> list[Ide]:
    print("JetBrains IDEs on this machine:")
    print(table(ides, build, build.plugin_id, numbered=True))
    answer = prompt("Install oku into which? Numbers, or a for all of them; nothing cancels: ").strip()
    if answer in ("a", "all"):
        return [i for i in ides if why_not(i, build) is None]
    picked = []
    for word in answer.replace(",", " ").split():
        if not word.isdigit() or not 1 <= int(word) <= len(ides):
            raise SystemExit(f"✗ not one of the numbers above: {word}")
        picked.append(ides[int(word) - 1])
    return picked


def _found(system: str, env: dict[str, str], home: Path) -> list[Ide]:
    problems: list[str] = []
    ides = discover(system, env, home, problems)
    for problem in problems:
        print(f"! skipped {problem}")
    return ides


def cmd_install(tokens: list[str], system: str, env: dict[str, str], home: Path) -> int:
    ides = _found(system, env, home)
    pid = plugin_id()
    if not tokens and not sys.stdin.isatty():
        print(table(ides, last_build(), pid, numbered=False) if ides else "  no JetBrains IDE found")
        print("✗ name the IDEs to install into, or all: ./ctl deploy ide all")
        return 2
    chosen = select(ides, tokens, system, env, home) if tokens else None
    builder = _builder(ides + [c for c in chosen or [] if c not in ides], system)
    if builder is None:
        _, needs = gradle_facts()
        print(
            f"⏸ no IDE here has what the plugin compiles against ({', '.join(needs)}) and a runtime to build on"
        )
        return 75
    print(f"▸ building the plugin against {builder.label} (a first build downloads Gradle and its plugins)")
    try:
        build = build_plugin(builder)
    except subprocess.CalledProcessError as e:
        print(f"✗ the plugin did not build: gradle exited {e.returncode}, and the lines above say why")
        return 1
    if chosen is None:
        chosen = ask(ides, build)
    if not chosen:
        print("nothing chosen; nothing installed")
        return 0
    return _install_into(chosen, build, explicit=tokens not in ([], ["all"]))


def _builder(ides: list[Ide], system: str) -> Ide | None:
    """The IDE to compile against: one with every bundled plugin the build
    names and a runtime to run Gradle on; IntelliJ IDEA first, newest first."""
    _, needs = gradle_facts()
    java = "bin/java.exe" if system == "Windows" else "bin/java"
    able = [i for i in ides if set(needs) <= i.provides and (i.jbr / java).is_file()]
    able.sort(key=lambda i: (i.code not in ("IU", "IC"), [-n for n in _build_key(i.build)]))
    return able[0] if able else None


def _install_into(chosen: list[Ide], build: Build, explicit: bool) -> int:
    failed = 0
    for ide in chosen:
        if reason := why_not(ide, build):
            print(f"{'✗' if explicit else '!'} {ide.label}: cannot run oku: {reason}")
            failed += explicit
            continue
        try:
            changed = install(ide, build)
        except OSError as e:
            print(f"✗ {ide.label}: {e}. If it is running, quit it and run this again.")
            failed += 1
            continue
        copies = installed(ide, build.plugin_id)
        if [c.digest for c in copies] != [build.digest]:
            print(
                f"✗ {ide.label}: after installing, {ide.plugins} holds {len(copies)} copies, not this build"
            )
            failed += 1
            continue
        if not changed:
            print(f"✓ {ide.label}: oku {build.version} was already this build")
            continue
        alive = running(ide)
        when = {True: "restart it to load it", False: "it loads on the next start"}.get(
            alive, "it loads on the next start, so restart it if it is running"
        )
        print(f"✓ {ide.label}: oku {build.version} in {ide.plugins / build.top}; {when}")
        if disabled(ide, build.plugin_id):
            print(f"! {ide.label}: oku is disabled there; enable it in Settings → Plugins")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    system, env, home = platform.system(), dict(os.environ), Path.home()
    verb, *rest = argv or ["list"]
    if verb == "list":
        ides = _found(system, env, home)
        print(table(ides, last_build(), plugin_id(), numbered=False) if ides else "  no JetBrains IDE found")
        return 0
    if verb == "install":
        return cmd_install(rest, system, env, home)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
