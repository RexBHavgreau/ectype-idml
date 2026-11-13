"""The program's own settings (not a profile, not a book): the last profile and output folder,
update checks. Saved as settings.json in the settings folder, beside the profiles, so they
survive updates."""

import json
import os

from .profile import settings_dir

DEFAULTS = {"profile": None, "out_dir": None, "last_book": None, "check_updates": True,
            "last_update_check": 0, "last_service_check": None}


def path():
    return settings_dir() / "settings.json"


def load():
    data = dict(DEFAULTS)
    try:
        with open(path(), encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            data.update(saved)
    except (OSError, ValueError):
        pass
    return data


def save(data):
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except OSError:
        pass                    # settings are a convenience; never stop the program for them
