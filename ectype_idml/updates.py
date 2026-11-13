"""Check GitHub for a newer release, and save it beside the running copy (as Indicat does).

The check reads the latest release of REPO (its tag, e.g. "v0.3.0") and compares it with the
running version, at every start (unless turned off) and from the Help menu. Nothing is downloaded unless the user says so. Each version's program carries
its version in its name ("docx-to-idml-0.3.0.exe"), so a new version is saved beside the running
one and never overwrites it. The download goes to a temporary name, is checked against the
release's SHA-256 digest and size, then renamed. If the program's folder can't be written (e.g.
under Program Files), the new version goes to Downloads. The new version, at its first start,
offers to delete older copies in its folder and to point shortcuts and taskbar pins at itself.

Settings and profiles live in the settings folder, so they survive updates.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import EXE_BASE, REPO, __version__

API = "https://api.github.com/repos/{repo}/releases/latest"
EXE_RE = re.compile(r"^%s[ ._-]+(\d+(?:\.\d+){1,2})\.exe$" % re.escape(EXE_BASE), re.I)


class UpdateError(Exception):
    """A plain message for the user."""


def parse_version(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def exe_name(version):
    return "%s-%s.exe" % (EXE_BASE, version)


def _pick_asset(assets):
    for a in assets or []:
        if EXE_RE.match(a.get("name") or "") and a.get("browser_download_url"):
            return {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size") or 0,
                    "digest": a.get("digest") or ""}
    return None


def check(timeout=5.0, opener=None):
    """{'status': 'newer'|'current'|'norelease'|'error', 'latest', 'url', 'notes', 'asset',
    'error'}"""
    try:
        req = urllib.request.Request(API.format(repo=REPO),
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "%s/%s" % (EXE_BASE, __version__)})
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("tag_name") or data.get("name") or ""
        status = "newer" if parse_version(latest) > parse_version(__version__) else "current"
        return {"status": status, "latest": latest.lstrip("v"), "url": data.get("html_url", ""),
                "notes": (data.get("body") or "")[:2000], "asset": _pick_asset(data.get("assets"))}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # no release published yet
            return {"status": "norelease"}
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def due(settings):
    """Whether to check at startup: at every start unless turned off. (Once a day, as first
    planned, missed a release made the same day as the last check.)"""
    return bool(settings.get("check_updates", True))


def should_offer(result, settings, manual):
    """Offer a newer version: always when the user asked; at startup, unless the user already
    declined that version."""
    if result.get("status") != "newer":
        return False
    return manual or result.get("latest") != settings.get("declined_version")


# ---- installing ----

def running_exe():
    """The program file of this copy, when it runs as the built .exe (not from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def can_install():
    return sys.platform == "win32" and running_exe() is not None


def downloads_folder():
    return Path.home() / "Downloads"


def download(asset, dest, progress=None, timeout=30.0, opener=None):
    """Download asset to dest (through dest + ".part"), checking its size and SHA-256 digest.
    Raises OSError when dest's folder can't be written, UpdateError otherwise."""
    progress = progress or (lambda fraction, text="": None)
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    with open(part, "wb") as out:      # fails here, before downloading, if the folder is read-only
        try:
            req = urllib.request.Request(asset["url"],
                                         headers={"User-Agent": "%s/%s" % (EXE_BASE, __version__)})
            with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
                total = int(asset.get("size") or r.headers.get("Content-Length") or 0)
                got = 0
                h = hashlib.sha256()
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if total:
                        progress(min(got / total, 1.0), "Downloading %s" % dest.name)
        except Exception as exc:
            out.close()
            part.unlink(missing_ok=True)
            raise UpdateError("The download didn't finish (%s). Nothing was changed; try again "
                              "later." % exc) from exc
    digest = (asset.get("digest") or "").lower()
    bad = (total and got != total) or (digest.startswith("sha256:") and h.hexdigest() != digest[7:])
    if bad:
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file didn't match the release (it may have been damaged "
                          "on the way), so it was deleted. Nothing was changed; try again later.")
    if dest.exists():
        dest.unlink()
    part.rename(dest)
    return dest


def install(asset, version, progress=None, folder=None, fallback=None, opener=None):
    """Download the new version into the running copy's folder or, when that folder can't be
    written to, into Downloads. Returns (the new program, True if it went to Downloads)."""
    folder = Path(folder or running_exe().parent)
    try:
        return download(asset, folder / exe_name(version), progress, opener=opener), False
    except UpdateError:
        raise
    except OSError:
        fb = Path(fallback or downloads_folder())
        fb.mkdir(parents=True, exist_ok=True)
        return download(asset, fb / exe_name(version), progress, opener=opener), True


def launch(exe, args=()):
    """Start another copy of the program, independent of this one (with command-line
    arguments, e.g. a silent update check)."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"   # the new copy must not reuse this one's files
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe)] + list(args), cwd=str(Path(exe).parent), env=env,
                     close_fds=True,
                     creationflags=flags)


# ---- after an update: older copies ----

def version_in_name(name):
    m = EXE_RE.match(name)
    return parse_version(m.group(1)) if m else None


def older_copies(folder, current):
    """Copies of the program in folder older than this version (never the running one, never a
    newer one)."""
    mine = parse_version(__version__)
    out = []
    for p in sorted(Path(folder).glob("*.exe")):
        v = version_in_name(p.name)
        if v is None or v >= mine:
            continue
        try:
            if p.resolve() == Path(current).resolve():
                continue
        except OSError:
            continue
        out.append(p)
    return out


def delete_old(paths, wait=15.0):
    """Delete older copies; one still closing gets a few more tries. (deleted, not deleted)"""
    deleted, left = [], list(paths)
    end = time.time() + wait
    while left:
        still = []
        for p in left:
            try:
                p.unlink()
                deleted.append(p)
            except FileNotFoundError:
                deleted.append(p)
            except OSError:
                still.append(p)
        left = still
        if not left or time.time() >= end:
            break
        time.sleep(1.0)
    return deleted, left


# ---- after an update: shortcuts (as Indicat's) ----

def shortcut_folders():
    """Where Windows keeps shortcuts to programs: the desktop, the Start menu, taskbar pins."""
    out = []
    try:
        import win32com.client
        sh = win32com.client.Dispatch("WScript.Shell")
        for name in ("Desktop", "AllUsersDesktop", "Programs", "AllUsersPrograms"):
            try:
                p = sh.SpecialFolders(name)
                if p:
                    out.append(Path(p))
            except Exception:
                pass
    except Exception:
        out.append(Path.home() / "Desktop")
    appdata = os.environ.get("APPDATA")
    if appdata:
        pinned = Path(appdata) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned"
        out += [pinned / "TaskBar", pinned / "StartMenu"]
    return [p for p in out if p.is_dir()]


def retarget_shortcuts(old, new, folders=None, shell=None):
    """Point shortcuts (.lnk) that open one of the old copies to new. Returns how many were
    changed; shortcuts to anything else, and ones that can't be written (e.g. all users'
    without admin rights), are left alone."""
    if shell is None:
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
        except Exception:
            return 0
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))     # noqa: E731
    olds = {norm(p) for p in old}
    old_dirs = {norm(Path(p).parent) for p in old}
    changed = 0
    for folder in (folders if folders is not None else shortcut_folders()):
        for lnk in Path(folder).rglob("*.lnk"):
            try:
                sc = shell.CreateShortcut(str(lnk))
                if norm(sc.TargetPath) not in olds:
                    continue
                sc.TargetPath = str(new)
                if sc.WorkingDirectory and norm(sc.WorkingDirectory) in old_dirs:
                    sc.WorkingDirectory = str(Path(new).parent)
                icon = (sc.IconLocation or "").rsplit(",", 1)[0]
                if icon and norm(icon) in olds:
                    sc.IconLocation = "%s,0" % new
                sc.Save()
                changed += 1
            except Exception:
                continue
    return changed
