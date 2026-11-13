"""The book: its input files, in the order the user chose.

Files can be added one by one or as a folder. The order starts as natural filename order
("Chapter 2" before "Chapter 10") and is saved with the book's settings, so a re-export after
corrections keeps it; a corrected file saved under the same name keeps its place.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BOOK_VERSION = 2       # 2: book details' single "author" became a list of creators


def natural_key(path):
    name = Path(path).name.casefold()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def natural_sort(paths):
    return sorted(paths, key=natural_key)


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def collect(paths, existing=()):
    """Expand dropped or chosen paths into .docx files.

    Returns (files, skipped): files in the order given, a folder's files in natural order;
    skipped is [(path, reason)] for everything left out, to tell the user.
    """
    files, skipped = [], []
    seen = list(existing)
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            inner = [c for c in p.iterdir() if c.is_file()]
            candidates = natural_sort(inner)
        else:
            candidates = [p]
        for c in candidates:
            name = c.name
            if name.startswith("~$"):
                skipped.append((str(c), "Word's temporary lock file, not a document"))
            elif c.suffix.lower() != ".docx":
                reason = ("an older Word file: save it as .docx from Word"
                          if c.suffix.lower() == ".doc" else "not a .docx file")
                skipped.append((str(c), reason))
            elif not c.exists():
                skipped.append((str(c), "file not found"))
            elif any(_same(c, s) for s in seen):
                skipped.append((str(c), "already in the list"))
            else:
                files.append(str(c))
                seen.append(str(c))
    return files, skipped


@dataclass
class Book:
    files: list = field(default_factory=list)
    profile: str = None
    settings: dict = field(default_factory=dict)   # book-specific choices (later stages)

    def add(self, paths, at=None):
        files, skipped = collect(paths, self.files)
        if at is None:
            self.files.extend(files)
        else:
            self.files[at:at] = files
        return files, skipped

    def remove(self, path):
        self.files = [f for f in self.files if not _same(f, path)]

    def move(self, index, new_index):
        f = self.files.pop(index)
        self.files.insert(max(0, min(new_index, len(self.files))), f)

    def sort_by_filename(self):
        self.files = natural_sort(self.files)

    def save(self, path):
        path = Path(path)
        base = path.parent.resolve()

        def rel(f):
            try:
                return os.path.relpath(Path(f).resolve(), base)
            except ValueError:      # another drive on Windows
                return str(Path(f).resolve())
        data = {"book_version": BOOK_VERSION, "profile": self.profile,
                "files": [rel(f) for f in self.files], "settings": self.settings}
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        base = path.parent
        files = [os.path.normpath(str(base / f)) if not Path(f).is_absolute() else f
                 for f in data.get("files", [])]
        return cls(files=files, profile=data.get("profile"),
                   settings=migrate_settings(data.get("settings", {}),
                                             data.get("book_version", 1)))


def migrate_settings(settings, version):
    """Book settings saved by an older version, brought up to BOOK_VERSION."""
    settings = dict(settings or {})
    if version < 2:
        front = dict(settings.get("front") or {})
        author = front.pop("author", None)
        if author and not front.get("creators"):
            from .frontmatter import split_names
            front["creators"] = [{"role": "author", "name": n} for n in split_names(author)]
        settings["front"] = front
    return settings


def apply_saved_order(saved, found):
    """Order the files found now by a saved order, matching by filename.

    A file still present (or replaced by a corrected copy with the same name) keeps its place;
    new files follow in natural order; files no longer present are dropped.
    """
    by_name = {}
    for f in found:
        by_name.setdefault(Path(f).name.casefold(), f)
    out = []
    for s in saved:
        f = by_name.pop(Path(s).name.casefold(), None)
        if f:
            out.append(f)
    return out + natural_sort(by_name.values())
