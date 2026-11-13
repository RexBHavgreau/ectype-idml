"""The converter as a tool for other programs: the convert command and its JSON result, the
program's location record (program.json), and the silent once-a-day update. No network and no
real .exe: fakes stand in for GitHub and the running program."""

import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TMP = tempfile.mkdtemp()
os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")

from docx_builder import run_tests  # noqa: E402
from ectype_idml import __version__, appsettings, cli, service, updates  # noqa: E402

MS = os.path.join(ROOT, "reference", "manuscript")


def _frozen(exe):
    """Pretend to be the built .exe at exe."""
    updates.running_exe = lambda: Path(exe)
    updates.can_install = lambda: True


def _restore(saved):
    updates.running_exe, updates.can_install, updates.launch = saved


def test_convert_writes_the_result():
    out = os.path.join(TMP, "out")
    result = os.path.join(TMP, "r", "result.json")
    code = cli.main(["convert", "--result", result, "--out", out, "--name", "e01", MS])
    r = json.load(open(result, encoding="utf-8"))
    assert code == 0 and r["ok"] and r["error"] is None
    assert r["api"] == service.API_VERSION and r["version"] == __version__
    assert os.path.exists(r["idml"]) and r["idml"].endswith("e01.idml")
    assert r["folder"] == os.path.dirname(r["idml"]) and r["report"]
    assert isinstance(r["alerts"], list)


def test_convert_reports_errors_in_the_result():
    result = os.path.join(TMP, "bad.json")
    empty = os.path.join(TMP, "empty")
    os.makedirs(empty, exist_ok=True)
    code = cli.main(["convert", "--result", result, empty])
    r = json.load(open(result, encoding="utf-8"))
    assert code == 2 and not r["ok"] and r["error"] == "No .docx files to export."
    code = cli.main(["convert", "--result", result, "--profile", "No Such Profile", MS])
    r = json.load(open(result, encoding="utf-8"))
    assert code == 2 and not r["ok"] and r["error"]


def test_location_record():
    saved = (updates.running_exe, updates.can_install, updates.launch)
    try:
        updates.running_exe = lambda: None          # from source: nothing recorded
        assert service.record_location() is None
        exe = os.path.join(TMP, "prog", "Ectype-IDML-%s.exe" % __version__)
        _frozen(exe)
        service.record_location()
        data = json.load(open(service.locator_path(), encoding="utf-8"))
        assert data == {"exe": exe, "version": __version__, "api": service.API_VERSION}
    finally:
        _restore(saved)


def test_update_check_once_a_day():
    saved = (updates.running_exe, updates.can_install, updates.launch)
    started = []
    try:
        _frozen(os.path.join(TMP, "prog", "Ectype-IDML-%s.exe" % __version__))
        launch = lambda exe, args: started.append((str(exe), list(args)))  # noqa: E731
        day = datetime.date(2026, 10, 24)
        assert service.daily_check(day, launch) is True
        assert started[-1][1] == ["update", "--quiet"]
        assert service.daily_check(day, launch) is False            # once a day
        assert service.daily_check(day + datetime.timedelta(days=1), launch) is True
        s = appsettings.load()
        s["check_updates"] = False                                   # turned off in the window
        appsettings.save(s)
        assert service.daily_check(day + datetime.timedelta(days=2), launch) is False
        assert len(started) == 2
        s["check_updates"] = True
        appsettings.save(s)
        updates.can_install = lambda: False                          # from source: never
        assert service.daily_check(day + datetime.timedelta(days=3), launch) is False
    finally:
        _restore(saved)


def test_quiet_update_points_program_json_at_the_new_copy():
    saved = (updates.running_exe, updates.can_install, updates.launch)
    try:
        _frozen(os.path.join(TMP, "prog", "Ectype-IDML-%s.exe" % __version__))
        new = os.path.join(TMP, "prog", "Ectype-IDML-99.0.0.exe")
        newer = {"status": "newer", "latest": "99.0.0", "asset": {"name": "x"}}
        got = service.quiet_update(check=lambda timeout: newer,
                                   install=lambda asset, version: (Path(new), False))
        assert got == "installed %s" % new
        data = json.load(open(service.locator_path(), encoding="utf-8"))
        assert data["exe"] == new and data["version"] == "99.0.0"
        assert service.quiet_update(check=lambda timeout: {"status": "current"}) == "current"
        assert service.quiet_update(check=lambda timeout: {"status": "error", "error": "x"}) \
            == "error: x"

        def broken(asset, version):
            raise updates.UpdateError("The download didn't finish.")
        assert service.quiet_update(check=lambda timeout: newer, install=broken).startswith(
            "error")
        assert json.load(open(service.locator_path(), encoding="utf-8"))["exe"] == new
    finally:
        _restore(saved)


def test_old_settings_carried_over():
    """At the first start as Ectype IDML, the docx-to-idml settings folder (profiles, settings)
    is copied to the new one, and the old one stays; nothing is copied once the new one
    exists. program.json is written in both folders while the old one exists."""
    import shutil
    from ectype_idml import profile as profiles
    saved = (updates.running_exe, updates.can_install, updates.launch)
    old, new = profiles.old_settings_dir(), profiles.settings_dir()
    try:
        shutil.rmtree(new, ignore_errors=True)
        (old / "profiles").mkdir(parents=True, exist_ok=True)
        (old / "profiles" / "Series A.json").write_text('{"name": "Series A"}', "utf-8")
        (old / "settings.json").write_text('{"check_updates": false}', "utf-8")
        assert profiles.carry_over_old_settings() is True
        assert (new / "profiles" / "Series A.json").exists() and (old / "settings.json").exists()
        assert appsettings.load()["check_updates"] is False
        assert profiles.carry_over_old_settings() is False            # once
        _frozen(os.path.join(TMP, "prog", "Ectype-IDML-%s.exe" % __version__))
        service.record_location()
        for folder in (new, old):
            data = json.load(open(folder / "program.json", encoding="utf-8"))
            assert data["exe"].endswith("Ectype-IDML-%s.exe" % __version__)
    finally:
        _restore(saved)
        shutil.rmtree(old, ignore_errors=True)
        s = appsettings.load()
        s["check_updates"] = True
        appsettings.save(s)


if __name__ == "__main__":
    run_tests(globals())
