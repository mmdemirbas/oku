"""`./ctl deploy ide`: the plugin goes where each IDE reads plugins from.

The rules are the IDE's own (PathManager, util-8.jar, 2026.2) and differ per
platform, so each platform is laid out here as a directory tree and asked
where its plugins go — a Linux or Windows machine is not needed to know
that the answer for one is right.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("oku_ide_install", REPO / "ide/intellij/install.py")
assert _spec and _spec.loader
installer = importlib.util.module_from_spec(_spec)
sys.modules["oku_ide_install"] = installer  # dataclasses resolve their module by name
_spec.loader.exec_module(installer)

PLUGIN_ID = "io.github.mmdemirbas.oku"
NEEDS = ["com.intellij.modules.jcef", "org.intellij.plugins.markdown", "com.intellij.modules.json"]


def _product(
    home: Path,
    *,
    mac: bool,
    name="IntelliJ IDEA",
    code="IU",
    build="262.10968.63",
    data_dir="IntelliJIdea2026.2",
    vendor="JetBrains",
    bundled=NEEDS,
    env_base="IDEA",
) -> Path:
    info = home / "Contents/Resources/product-info.json" if mac else home / "product-info.json"
    info.parent.mkdir(parents=True, exist_ok=True)
    info.write_text(
        json.dumps(
            {
                "name": name,
                "version": "2026.2.3",
                "productCode": code,
                "buildNumber": build,
                "dataDirectoryName": data_dir,
                "productVendor": vendor,
                "envVarBaseName": env_base,
                "bundledPlugins": list(bundled),
                "modules": ["com.intellij.modules.platform"],
            }
        )
    )
    (home / ("Contents/bin" if mac else "bin")).mkdir(parents=True, exist_ok=True)
    return home


def _jar(
    version: str,
    plugin_id: str = PLUGIN_ID,
    since="262",
    requires=("com.intellij.modules.platform", "com.intellij.modules.jcef"),
) -> bytes:
    depends = "".join(f"<depends>{r}</depends>" for r in requires)
    xml = (
        f"<idea-plugin><id>{plugin_id}</id><version>{version}</version>"
        f'<idea-version since-build="{since}"/>{depends}'
        '<depends optional="true" config-file="m.xml">org.intellij.plugins.markdown</depends></idea-plugin>'
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("META-INF/plugin.xml", xml)
        z.writestr("io/github/A.class", f"code of {version}")
    return out.getvalue()


def _zip(path: Path, version: str, **kw) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("oku-intellij/", "")
        z.writestr(f"oku-intellij/lib/oku-intellij-{version}.jar", _jar(version, **kw))
    return path


def _ide(tmp_path: Path, **kw):
    home = _product(tmp_path / "IDE.app", mac=True, **kw)
    return installer.read_ide(home, "Darwin", {}, tmp_path / "home")


# --- where the plugins go ---------------------------------------------------

PLATFORMS = [
    # system, the installation, environment, where the plugins go
    (
        "Darwin",
        "Applications/IntelliJ IDEA.app",
        {},
        "Library/Application Support/JetBrains/IntelliJIdea2026.2/plugins",
    ),
    (
        "Darwin",
        "Library/Application Support/JetBrains/Toolbox/apps/IDEA-U/ch-0/262.1/IntelliJ IDEA.app",
        {},
        "Library/Application Support/JetBrains/IntelliJIdea2026.2/plugins",
    ),
    # Linux keeps plugins in the data directory itself, with no /plugins.
    (
        "Linux",
        ".local/share/JetBrains/Toolbox/apps/intellij-idea-ultimate",
        {},
        ".local/share/JetBrains/IntelliJIdea2026.2",
    ),
    (
        "Linux",
        "xdg/JetBrains/Toolbox/apps/intellij-idea-ultimate",
        {"XDG_DATA_HOME": "{home}/xdg"},
        "xdg/JetBrains/IntelliJIdea2026.2",
    ),
    (
        "Windows",
        "AppData/Local/Programs/IntelliJ IDEA Ultimate",
        {"LOCALAPPDATA": "{home}/AppData/Local", "APPDATA": "{home}/AppData/Roaming"},
        "AppData/Roaming/JetBrains/IntelliJIdea2026.2/plugins",
    ),
]


@pytest.mark.parametrize(
    ("system", "where", "env", "plugins"), PLATFORMS, ids=[f"{p[0]}:{p[1]}" for p in PLATFORMS]
)
def test_each_platform_puts_the_plugin_where_the_ide_reads_it(tmp_path, system, where, env, plugins):
    home = tmp_path / "home"
    env = {k: v.format(home=home) for k, v in env.items()}
    _product(home / where, mac=system == "Darwin")
    found = [i for i in installer.discover(system, env, home) if str(i.home).startswith(str(tmp_path))]
    assert [i.plugins for i in found] == [home / plugins]


def test_the_vendor_directory_is_the_products_company(tmp_path):
    home = tmp_path / "home"
    _product(
        home / "Applications/Android Studio.app",
        mac=True,
        name="Android Studio",
        code="AI",
        data_dir="AndroidStudio2026.2.1",
        vendor="Google",
    )
    (ide,) = [i for i in installer.discover("Darwin", {}, home) if str(i.home).startswith(str(tmp_path))]
    assert ide.plugins == home / "Library/Application Support/Google/AndroidStudio2026.2.1/plugins"


def test_idea_properties_moves_the_plugins_the_way_the_ide_reads_it(tmp_path):
    home = tmp_path / "home"
    app = _product(tmp_path / "IDE.app", mac=True)
    config = home / "Library/Application Support/JetBrains/IntelliJIdea2026.2"
    config.mkdir(parents=True)
    read = lambda env={}: installer.read_ide(app, "Darwin", env, home).plugins  # noqa: E731

    # The IDE's own bin/idea.properties moving the config takes the plugins with it.
    (app / "Contents/bin/idea.properties").write_text("idea.config.path=${user.home}/cfg\n")
    assert read() == home / "cfg/plugins"
    # The config directory's file sets the plugins outright, and is read first.
    (config / "idea.properties").write_text("# moved\nidea.plugins.path=${user.home}/my-plugins\n")
    assert read() == home / "my-plugins"
    # <ENV>_PROPERTIES is read before either.
    named = tmp_path / "named.properties"
    named.write_text(f"idea.plugins.path={tmp_path}/named\n")
    assert read({"IDEA_PROPERTIES": str(named)}) == tmp_path / "named"


def test_an_installation_that_cannot_be_read_is_named_not_passed_over(tmp_path):
    home = tmp_path / "home"
    app = _product(home / "Applications/IntelliJ IDEA.app", mac=True)
    (app / "Contents/bin/idea.properties").write_text("idea.plugins.path=${some.property}/p\n")
    problems: list[str] = []
    found = [
        i for i in installer.discover("Darwin", {}, home, problems) if str(i.home).startswith(str(tmp_path))
    ]
    assert found == []
    assert any(str(app) in p and "some.property" in p for p in problems), problems


# --- which IDEs can take it -------------------------------------------------


def test_an_ide_that_cannot_load_the_plugin_is_refused_with_the_reason(tmp_path):
    build = installer.read_build(_zip(tmp_path / "p.zip", "0.2.0", since="262"))
    ok = _ide(tmp_path / "a")
    assert installer.why_not(ok, build) is None
    assert "older than 262" in installer.why_not(_ide(tmp_path / "b", build="261.9999"), build)
    assert "com.intellij.modules.jcef" in installer.why_not(_ide(tmp_path / "c", bundled=[]), build)
    # The markdown dependency is optional: an IDE without it still takes the plugin.
    assert installer.why_not(_ide(tmp_path / "d", bundled=["com.intellij.modules.jcef"]), build) is None
    capped = installer.Build(**{**build.__dict__, "until": "262.*"})
    assert installer.why_not(ok, capped) is None
    assert "newer than 261.*" in installer.why_not(
        ok, installer.Build(**{**build.__dict__, "until": "261.*"})
    )


def test_an_ide_is_chosen_by_code_name_data_directory_or_path(tmp_path):
    home = tmp_path / "home"
    _product(home / "Applications/IntelliJ IDEA.app", mac=True)
    _product(
        home / "Applications/Rider.app", mac=True, name="JetBrains Rider", code="RD", data_dir="Rider2026.2"
    )
    ides = [i for i in installer.discover("Darwin", {}, home) if str(i.home).startswith(str(tmp_path))]
    pick = lambda *t: [i.code for i in installer.select(ides, list(t), "Darwin", {}, home)]  # noqa: E731
    assert pick("all") == ["IU", "RD"]
    assert pick("rider") == ["RD"]
    assert pick("iu") == ["IU"]
    assert pick("IntelliJIdea2026.2", "RD", "IU") == ["IU", "RD"]
    elsewhere = _product(tmp_path / "opt/Other IDE.app", mac=True, code="IC", data_dir="IdeaIC2026.2")
    assert pick(str(elsewhere)) == ["IC"]
    with pytest.raises(SystemExit, match="no IDE here matches 'goland'.*IntelliJ IDEA"):
        pick("goland")
    with pytest.raises(SystemExit, match="not an IDE installation"):
        pick(str(tmp_path))


def test_asked_which_the_answer_is_numbers_or_all_of_those_that_can(tmp_path, capsys):
    build = installer.read_build(_zip(tmp_path / "p.zip", "0.2.0"))
    ides = [
        _ide(tmp_path / "a"),
        _ide(tmp_path / "b", code="AI", bundled=[], data_dir="AndroidStudio2026.2.1"),
    ]
    assert installer.ask(ides, build, prompt=lambda _: "2") == [ides[1]]
    assert installer.ask(ides, build, prompt=lambda _: "a") == [ides[0]]
    assert installer.ask(ides, build, prompt=lambda _: "") == []
    with pytest.raises(SystemExit, match="not one of the numbers"):
        installer.ask(ides, build, prompt=lambda _: "3")


def test_the_list_reads_down_its_columns(tmp_path):
    build = installer.read_build(_zip(tmp_path / "p.zip", "0.2.0"))
    ides = [
        _ide(tmp_path / "a"),
        _ide(tmp_path / "b", name="JetBrains Rider Long Name", code="RD", bundled=[]),
    ]
    rows = installer.table(ides, build, PLUGIN_ID, numbered=True).splitlines()
    assert len({r.index(" IU-") if " IU-" in r else r.index(" RD-") for r in rows}) == 1
    assert (
        len({r.index("not installed") if "not installed" in r else r.index("cannot run") for r in rows}) == 1
    )


# --- putting it there -------------------------------------------------------


def test_installing_leaves_exactly_one_copy_and_touches_no_other_plugin(tmp_path):
    ide = _ide(tmp_path)
    plugins = ide.plugins
    (plugins / "oku-intellij/lib").mkdir(parents=True)
    (plugins / "oku-intellij/lib/oku-intellij-0.1.0.jar").write_bytes(_jar("0.1.0"))
    (plugins / "oku-by-hand.jar").write_bytes(_jar("0.0.9"))  # an old single-jar install
    (plugins / "other/lib").mkdir(parents=True)
    (plugins / "other/lib/other.jar").write_bytes(_jar("1.0", plugin_id="com.example.other"))
    build = installer.read_build(_zip(tmp_path / "p.zip", "0.2.0"))

    assert installer.install(ide, build) is True
    copies = installer.installed(ide, PLUGIN_ID)
    assert [(c.path, c.version, c.digest) for c in copies] == [
        (plugins / "oku-intellij", "0.2.0", build.digest)
    ]
    assert sorted(p.name for p in plugins.iterdir()) == ["oku-intellij", "other"]
    assert [p.name for p in plugins.parent.iterdir() if p.name.startswith(".oku-install")] == []
    # The same build again is not written again.
    stamp = (plugins / "oku-intellij/lib/oku-intellij-0.2.0.jar").stat().st_mtime_ns
    assert installer.install(ide, build) is False
    assert (plugins / "oku-intellij/lib/oku-intellij-0.2.0.jar").stat().st_mtime_ns == stamp
    # Same version, other code: the version string is not what decides.
    rebuilt = installer.read_build(_zip(tmp_path / "q.zip", "0.2.0", since="261"))
    assert rebuilt.digest != build.digest
    assert installer.install(ide, rebuilt) is True
    assert [c.digest for c in installer.installed(ide, PLUGIN_ID)] == [rebuilt.digest]


def test_a_failed_install_leaves_the_plugin_the_ide_had(tmp_path, monkeypatch):
    ide = _ide(tmp_path)
    (ide.plugins / "oku-intellij/lib").mkdir(parents=True)
    (ide.plugins / "oku-intellij/lib/oku-intellij-0.1.0.jar").write_bytes(_jar("0.1.0"))
    before = installer.installed(ide, PLUGIN_ID)
    build = installer.read_build(_zip(tmp_path / "p.zip", "0.2.0"))
    real = Path.rename

    def refuse_the_new_copy(self, target):
        if Path(target) == ide.plugins / "oku-intellij" and self.parent.name == "new":
            raise PermissionError("in use")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", refuse_the_new_copy)
    with pytest.raises(PermissionError):
        installer.install(ide, build)
    assert installer.installed(ide, PLUGIN_ID) == before
    assert [p.name for p in ide.plugins.parent.iterdir() if p.name.startswith(".oku-install")] == []


def test_the_installer_takes_its_facts_from_the_build_files():
    version, needs = installer.gradle_facts()
    text = (REPO / "ide/intellij/build.gradle.kts").read_text()
    assert f'version = "{version}"' in text
    assert set(needs) == set(NEEDS)
    assert installer.plugin_id() == PLUGIN_ID


def test_the_build_reads_the_sources_from_disk_rather_than_from_the_watcher(tmp_path, monkeypatch):
    # A Gradle daemon watching the file system reported compileKotlin
    # UP-TO-DATE over an edited source, and the tests ran the old class.
    # The same miss in a deploy builds a zip of the old code, installs it,
    # and reports success: the IDE runs code nobody is reading.
    ran: list[list[str]] = []
    monkeypatch.setattr(installer.subprocess, "run", lambda cmd, **kw: ran.append(cmd))
    monkeypatch.setattr(installer, "read_build", lambda path: path)
    installer.build_plugin(_ide(tmp_path))
    assert "--no-watch-fs" in ran[0], ran


@pytest.mark.skipif(os.name == "nt", reason="ps")
def test_the_ide_is_running_when_its_launcher_is_and_not_when_its_runtime_is(tmp_path):
    ide = _ide(tmp_path)
    assert installer.running(ide) is False

    def started(relative: str) -> subprocess.Popen:
        program = ide.home / relative
        program.parent.mkdir(parents=True, exist_ok=True)
        program.symlink_to(shutil.which("sleep"))
        return subprocess.Popen([str(program), "30"])

    # What `deploy ide` itself leaves behind: a Gradle daemon on the IDE's JBR.
    daemon = started("Contents/jbr/Contents/Home/bin/java")
    try:
        assert installer.running(ide) is False
        launcher = started("Contents/MacOS/idea")
        try:
            assert installer.running(ide) is True
        finally:
            launcher.kill()
    finally:
        daemon.kill()
