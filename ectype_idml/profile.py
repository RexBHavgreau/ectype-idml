"""Profiles: everything the user sets for a book, saved so the next book in a series is one click.

Profiles live in the tool's settings folder (%APPDATA%\\docx-to-idml\\profiles on Windows), not
beside the program, so they survive updates. Each file carries PROFILE_VERSION; when the layout
changes, bump it and add a step to MIGRATIONS so saved profiles are upgraded rather than lost.
Defaults are neutral, not tied to any publisher.
"""

import copy
import json
import os
import re
import sys
from pathlib import Path

from . import APP_NAME

PROFILE_VERSION = 10

DEFAULT_PROFILE = {
    "profile_version": PROFILE_VERSION,
    "name": "Default",
    # {Word style name: IDML style name, or {"idml": ..., "role": ..., "level": ...}}
    "style_map": {"paragraph": {}, "character": {}},
    "page": {
        "trim": "6x9",                 # a standard size, or "custom"
        "custom_width": None,          # inches, when trim is "custom"
        "custom_height": None,
        "facing": True,
        "bleed": False,
        "margins": {},                 # user overrides, inches: top, bottom, inside, outside
        "measure": 30,                 # line length in times the type size (Bringhurst: 20-40)
        "spare_pages": 0,              # spare pages after each chapter: 0, 1 or 2 (a pair)
        "opener_drop": None,           # points the chapter titles are lowered; None = 6 lines
    },
    "styles_template": None,           # an IDML whose styles replace the tool's of the same name
    "fonts": {"body": None, "headings": None, "notes": None, "display": None,
              "hebrew": None, "greek": None},
    "body_size": 11,                   # points
    # feel: tight, standard or open, used when no value is set; value in pt, multiple or percent
    "leading": {"unit": "pt", "value": None, "feel": "standard"},
    "baseline_grid": False,
    "running_heads": {
        "verso": "book_title",         # book_title, part, chapter, author, custom
        "recto": "chapter_title",      # chapter_title, custom
        "verso_custom": "",
        "recto_custom": "",
        "suppress_on_openers": True,
        "suppress_on_display": True,
        "suppress_on_blanks": True,
        # A head with Hebrew or Greek the head font lacks: on a master of its own, as text
        # in their fonts (a section marker takes one font); off: the report only warns.
        "script_masters": True,
        # The Running Head paragraph style.
        "style": {
            "case": "as_typed",        # as_typed, title, sentence (the letters of the text)
            "caps": "small_caps",      # None, small_caps or all_caps (the type)
            "italic": False,
            "bold": False,
            "underline": False,
            "size": None,              # points; None = 2 pt below the body size
            "tracking": 20,            # letter-spacing, thousandths of an em
            "font": None,              # None = the body font
        },
    },
    "chapters_open": "recto",          # recto or next_page
    "footnotes": {
        "numbering": "per_chapter",    # per_chapter or continuous
        "rule": False,                 # rule above the notes on each page
        "continuation_rule": True,     # rule above a note continued from the previous page
        "space_above": 12,             # points between the body text and the notes (or rule)
        "space_below_rule": 6,         # points between a rule and the note text
        "space_between": 3,            # points between notes
        "rule_length": 72,             # points (1 inch), for both rules
    },
    "front_matter": {"language": "en", "contents_depth": "chapters"},
    "notices": [],                     # the user's own notice library: {"name", "text"}
    "typography": {
        "paragraph_composer": True,
        "optical_margins": True,
        "hyphenation": True,
        "ligatures": True,
        "oldstyle_figures": True,
        "balance_ragged_headings": True,
        "widow_orphan_control": True,  # at least 2 lines of a paragraph at a page's foot or head
        "last_line_min_chars": 10,     # last line of a paragraph at least this long (0 = off):
                                       # the last words are kept together (No Break)
    },
}


class ProfileError(Exception):
    """A profile that can't be used. The message is shown to the user."""


def settings_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def profiles_dir():
    return settings_dir() / "profiles"


def _merge(defaults, data):
    """Fill what's missing in data from defaults; keep the user's values and unknown keys."""
    out = copy.deepcopy(data)
    for k, v in defaults.items():
        if k not in out:
            out[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(out[k], dict) and k != "style_map":
            out[k] = _merge(v, out[k])
    if "style_map" in defaults and isinstance(out.get("style_map"), dict):
        out["style_map"].setdefault("paragraph", {})
        out["style_map"].setdefault("character", {})
    return out


def _from_0(data):
    """Version 0: a profile written before versions existed, with the style map flat."""
    sm = data.get("style_map")
    if isinstance(sm, dict) and "paragraph" not in sm and "character" not in sm:
        data["style_map"] = {"paragraph": sm, "character": {}}
    return data


def _from_1(data):
    """Version 1: footnote numbering at the top level and the rule under typography."""
    fn = data.setdefault("footnotes", {})
    if "footnote_numbering" in data:
        fn.setdefault("numbering", data.pop("footnote_numbering"))
    typo = data.get("typography")
    if isinstance(typo, dict) and "footnote_rule" in typo:
        fn.setdefault("rule", typo.pop("footnote_rule"))
    return data


def _from_2(data):
    """Version 2: no setting for the last line of a paragraph (it was off)."""
    typo = data.setdefault("typography", {})
    if isinstance(typo, dict):
        typo.setdefault("last_line_min_chars", 10)
    return data


def _from_3(data):
    """Version 3: one spare page after each chapter, always; no style template."""
    page = data.setdefault("page", {})
    if isinstance(page, dict):
        page.setdefault("spare_pages", 0)
    data.setdefault("styles_template", None)
    return data


def _from_4(data):
    """Version 4: the body size was always 11 pt; automatic leading was about 1.27 times it
    (now "standard", about 1.25)."""
    data.setdefault("body_size", 11)
    lead = data.setdefault("leading", {})
    if isinstance(lead, dict):
        lead.setdefault("feel", "standard")
    return data


def _from_5(data):
    """Version 5: the measure was set for 65 characters (now 30 times the type size); the
    running heads' style was fixed (small caps, tracked 20). Two settings nothing used are
    dropped: typography.small_caps_opentype and endnotes (endnotes are always converted)."""
    data.pop("endnotes", None)
    if isinstance(data.get("typography"), dict):
        data["typography"].pop("small_caps_opentype", None)
    data.setdefault("page", {}).setdefault("measure", 30)
    data.setdefault("running_heads", {}).setdefault("style", {
        "case": "small_caps", "italic": False, "size": None, "tracking": 20, "font": None})
    return data


def _from_6(data):
    """Version 6: no choice about running heads with Hebrew or Greek (0.6.0 adds
    running_heads.script_masters, off)."""
    data.setdefault("running_heads", {}).setdefault("script_masters", False)
    return data


def _from_7(data):
    """Version 7: the running-head style's "case" was small_caps, all_caps or as_typed (the
    type); now case is the letters (as_typed, title, sentence) and caps the type."""
    style = data.setdefault("running_heads", {}).setdefault("style", {})
    old = style.get("case", "small_caps")
    if old in ("small_caps", "all_caps", "as_typed"):
        style["caps"] = None if old == "as_typed" else old
        style["case"] = "as_typed"
    return data


def _from_8(data):
    """Version 8: chapter openings always dropped six body lines (0.7.0 adds
    page.opener_drop, None = that)."""
    data.setdefault("page", {}).setdefault("opener_drop", None)
    return data


def _from_9(data):
    """Version 9: separate masters for Hebrew/Greek running heads were off by default and
    only a warning was given (heads printed as boxes); 0.8.0 turns them on, also in saved
    profiles (where off was only the old default)."""
    data.setdefault("running_heads", {})["script_masters"] = True
    return data


MIGRATIONS = {0: _from_0, 1: _from_1, 2: _from_2, 3: _from_3, 4: _from_4, 5: _from_5,
              6: _from_6, 7: _from_7, 8: _from_8, 9: _from_9}   # version n -> function that upgrades it to n + 1


def migrate(data):
    if not isinstance(data, dict):
        raise ProfileError("This file is not a profile.")
    version = data.get("profile_version", 0)
    if not isinstance(version, int) or version > PROFILE_VERSION:
        raise ProfileError("This profile was saved by a newer version of the tool. "
                           "Update the tool to use it.")
    while version < PROFILE_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
    data["profile_version"] = PROFILE_VERSION
    return _merge(DEFAULT_PROFILE, data)


def default_profile():
    return copy.deepcopy(DEFAULT_PROFILE)


def _safe_name(name):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return s or "Profile"


def load_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ProfileError("Can't open the profile %s: %s" % (path, e.strerror)) from None
    except json.JSONDecodeError:
        raise ProfileError("%s is not a profile (it isn't valid JSON)." % Path(path).name) from None
    return migrate(data)


def save_file(profile, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def profile_path(name):
    return profiles_dir() / (_safe_name(name) + ".json")


def list_profiles():
    d = profiles_dir()
    names = []
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                names.append(load_file(p)["name"])
            except ProfileError:
                continue
    return names


def load(name_or_path=None):
    """A saved profile by name, a profile file by path, or the defaults (None)."""
    if not name_or_path:
        return default_profile()
    p = Path(name_or_path)
    if p.suffix.lower() == ".json" and p.exists():
        return load_file(p)
    path = profile_path(name_or_path)
    if not path.exists():
        raise ProfileError('There is no profile named "%s".' % name_or_path)
    return load_file(path)


def save(profile):
    save_file(profile, profile_path(profile["name"]))


def export_profile(name, dest):
    save_file(load(name), dest)


def import_profile(src):
    """Copy a profile file into the settings folder (upgraded if it's older). Returns its name."""
    profile = load_file(src)
    save(profile)
    return profile["name"]
