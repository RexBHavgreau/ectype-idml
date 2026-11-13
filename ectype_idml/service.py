"""The converter as a tool for other programs (Ectype OCR and others): see docs/ENGINE.md.

Another program runs the installed docx-to-idml .exe with the `convert` command and reads the
result from a JSON file (the .exe has no console). To find the current .exe, whose name
changes with each version, it reads `program.json` in the settings folder, which every start
of the program (window or command) rewrites with its own location.

The first `convert` of each day also starts a silent update check in a separate, detached
copy of the program (`update --quiet`), so the call itself isn't slowed down: when a newer
release exists, it is downloaded beside the running copy (checked against its digest, as from
the window) and `program.json` is pointed at it, so the next call uses it. Older copies are
left for the new version's window to offer to delete. Turning off "Check for updates at
startup" in the window turns this off too.
"""

import datetime
import json
import os
import traceback
from pathlib import Path

from . import __version__
from . import appsettings, updates
from .profile import settings_dir

API_VERSION = 1          # the command and result format; raised only for changes callers see


def locator_path():
    return settings_dir() / "program.json"


def record_location(exe=None, version=None):
    """Write program.json: this copy's .exe (or the given one), its version and the API
    version. Only for the built .exe; running from source records nothing."""
    exe = exe or updates.running_exe()
    if exe is None:
        return None
    data = {"exe": str(exe), "version": version or __version__, "api": API_VERSION}
    p = locator_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, p)
    except OSError:
        return None
    return data


def convert(files, out_dir, profile=None, name=None, book=None):
    """Export and return the result as a dict (never raises): ok, idml, folder, report,
    alerts, error, version, api."""
    from . import profile as profiles
    from .book import Book, apply_saved_order, collect
    from .export import ExportError, export
    from .pagination import Alert
    result = {"api": API_VERSION, "version": __version__, "ok": False, "idml": None,
              "folder": None, "report": [], "alerts": [], "error": None}
    try:
        b = Book.load(book) if book else None
        paths, skipped = collect(files) if files else ([], [])
        if b:
            paths = apply_saved_order(b.files, paths) if paths else b.files
        result["report"] += ["Skipped %s: %s" % (p, why) for p, why in skipped]
        if not paths:
            result["error"] = "No .docx files to export."
            return result
        prof = profiles.load(profile or (b.profile if b else None))
        idml, report = export(paths, out_dir, prof, name, b.settings if b else None)
        result.update(ok=True, idml=str(idml), folder=str(Path(idml).parent))
        result["report"] += [str(line) for line in report]
        result["alerts"] = [str(line) for line in report if isinstance(line, Alert)]
    except (ExportError, profiles.ProfileError) as e:
        result["error"] = str(e)
    except Exception as e:                       # report it rather than fail silently
        result["error"] = "The export failed: %s" % e
        result["traceback"] = traceback.format_exc()
    return result


def write_result(result, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def daily_check(today=None, launch=None):
    """The first call of the day starts a detached `update --quiet`. Returns True if it
    started one."""
    settings = appsettings.load()
    if not settings.get("check_updates", True) or not updates.can_install():
        return False
    today = (today or datetime.date.today()).isoformat()
    if settings.get("last_service_check") == today:
        return False
    settings["last_service_check"] = today
    appsettings.save(settings)
    (launch or updates.launch)(updates.running_exe(), ["update", "--quiet"])
    return True


def quiet_update(check=None, install=None):
    """Check for a newer release and, if there is one, download it beside this copy and point
    program.json at it. Returns what happened, for the log: "current", "installed <path>",
    or "error: ...". Never asks anything."""
    r = (check or updates.check)(timeout=10.0)
    if r.get("status") != "newer" or not r.get("asset"):
        return r.get("status") if r.get("status") != "error" else "error: %s" % r.get("error")
    try:
        path, _in_downloads = (install or updates.install)(r["asset"], r["latest"])
    except Exception as e:
        return "error: %s" % e
    record_location(Path(path), r["latest"])
    return "installed %s" % path
