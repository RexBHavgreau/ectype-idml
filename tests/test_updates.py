"""The updater: the release check, finding the program, downloading and checking it, the
Downloads fall-back, and older copies. No network: a fake opener stands in for GitHub."""

import hashlib
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import run_tests
from ectype_idml import __version__
from ectype_idml import updates as U

PROGRAM = b"MZ" + bytes(range(256)) * 2000


class Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def release(tag, name=None, digest=None):
    name = name or U.exe_name(tag.lstrip("v"))
    return {"tag_name": tag, "html_url": "https://example/rel", "body": "Notes",
            "assets": [{"name": "notes.txt", "browser_download_url": "x"},
                       {"name": name, "browser_download_url": "https://example/" + name,
                        "size": len(PROGRAM),
                        "digest": digest or "sha256:" + hashlib.sha256(PROGRAM).hexdigest()}]}


def opener_for(data):
    return lambda req, timeout=0: Resp(json.dumps(data).encode() if isinstance(data, dict)
                                       else data)


def test_names_and_versions():
    assert U.exe_name("0.3.0") == "docx-to-idml-0.3.0.exe"
    assert U.version_in_name("docx-to-idml-0.3.0.exe") == (0, 3, 0)
    assert U.version_in_name("docx-to-idml.0.3.1.exe") == (0, 3, 1)   # as GitHub may write it
    assert U.version_in_name("Indicat 0.4.1.exe") is None
    assert U.parse_version("v1.2") == (1, 2, 0)


def test_check():
    r = U.check(opener=opener_for(release("v99.0.0")))
    assert r["status"] == "newer" and r["latest"] == "99.0.0"
    assert r["asset"]["name"] == "docx-to-idml-99.0.0.exe"
    assert U.check(opener=opener_for(release("v" + __version__)))["status"] == "current"

    def missing(req, timeout=0):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    assert U.check(opener=missing)["status"] == "norelease"

    def offline(req, timeout=0):
        raise OSError("no network")
    assert U.check(opener=offline)["status"] == "error"


def test_due_and_offer():
    # At every start unless turned off (once a day missed a release made the same day).
    assert U.due({}) and U.due({"last_update_check": time.time()})
    assert not U.due({"check_updates": False})
    newer = {"status": "newer", "latest": "9.0.0"}
    assert U.should_offer(newer, {}, manual=False)
    assert not U.should_offer(newer, {"declined_version": "9.0.0"}, manual=False)
    assert U.should_offer(newer, {"declined_version": "9.0.0"}, manual=True)
    assert U.should_offer(newer, {"declined_version": "8.0.0"}, manual=False)
    assert not U.should_offer({"status": "current"}, {}, manual=True)


def test_download_checks_digest():
    d = Path(tempfile.mkdtemp())
    asset = U._pick_asset(release("v9.9.9")["assets"])
    path = U.download(asset, d / "x.exe", opener=opener_for(PROGRAM))
    assert path.read_bytes() == PROGRAM and not (d / "x.exe.part").exists()
    bad = dict(asset, digest="sha256:" + "0" * 64)
    try:
        U.download(bad, d / "y.exe", opener=opener_for(PROGRAM))
        assert False, "a bad digest must fail"
    except U.UpdateError:
        pass
    assert not (d / "y.exe").exists() and not (d / "y.exe.part").exists()


def test_install_falls_back_to_downloads():
    asset = U._pick_asset(release("v9.9.9")["assets"])
    good = Path(tempfile.mkdtemp())
    path, fell = U.install(asset, "9.9.9", folder=good, opener=opener_for(PROGRAM))
    assert path == good / "docx-to-idml-9.9.9.exe" and not fell
    fb = Path(tempfile.mkdtemp())
    path, fell = U.install(asset, "9.9.9", folder=good / "missing" / "folder", fallback=fb,
                           opener=opener_for(PROGRAM))
    assert fell and path == fb / "docx-to-idml-9.9.9.exe"


def test_older_copies():
    d = Path(tempfile.mkdtemp())
    names = ["docx-to-idml-0.0.1.exe", "docx-to-idml-%s.exe" % __version__,
             "docx-to-idml-99.0.0.exe", "other.exe"]
    for n in names:
        (d / n).write_bytes(b"x")
    old = U.older_copies(d, d / ("docx-to-idml-%s.exe" % __version__))
    assert [p.name for p in old] == ["docx-to-idml-0.0.1.exe"]
    deleted, left = U.delete_old(old, wait=0)
    assert deleted == old and not left and not (d / "docx-to-idml-0.0.1.exe").exists()


class FakeShortcut:
    def __init__(self, store, path):
        self.store, self.path = store, path
        self.__dict__.update(store[path])

    def Save(self):
        self.store[self.path] = {k: getattr(self, k)
                                 for k in ("TargetPath", "WorkingDirectory", "IconLocation")}


class FakeShell:
    def __init__(self, store):
        self.store = store

    def CreateShortcut(self, path):
        return FakeShortcut(self.store, path)


def test_shortcuts():
    tmp = Path(tempfile.mkdtemp())
    prog, desk, pins = tmp / "Apps", tmp / "Desktop", tmp / "TaskBar"
    for d in (prog, desk, pins):
        d.mkdir()
    old, older = prog / U.exe_name("0.2.0"), prog / U.exe_name("0.1.0")
    new = prog / U.exe_name(__version__)
    store = {
        str(desk / "docx-to-idml.lnk"): {"TargetPath": str(old), "WorkingDirectory": str(prog),
                                         "IconLocation": "%s,0" % old},
        str(pins / "docx-to-idml.lnk"): {"TargetPath": str(older), "WorkingDirectory": "",
                                         "IconLocation": ""},
        str(desk / "Word.lnk"): {"TargetPath": r"C:\Program Files\Word.exe",
                                 "WorkingDirectory": "", "IconLocation": ""},
    }
    for p in store:
        Path(p).write_bytes(b"")
    n = U.retarget_shortcuts([old, older], new, folders=[desk, pins], shell=FakeShell(store))
    d = store[str(desk / "docx-to-idml.lnk")]
    assert n == 2 and d["TargetPath"] == str(new) and d["IconLocation"] == "%s,0" % new
    assert d["WorkingDirectory"] == str(prog)
    assert store[str(pins / "docx-to-idml.lnk")]["TargetPath"] == str(new)
    assert store[str(desk / "Word.lnk")]["TargetPath"] == r"C:\Program Files\Word.exe"
    # Without Windows' shortcut object (here), nothing is changed and nothing fails.
    if sys.platform != "win32":
        assert U.retarget_shortcuts([old], new, folders=[desk]) == 0


if __name__ == "__main__":
    run_tests(globals())
