"""Forms of the window (moved out of gui.py, 1.1.0): fields declared as tables of
(path, label, kind, choices), bound to a profile or the book settings; points fields."""

import re
import tkinter as tk
from tkinter import filedialog, ttk

TITLE = "Ectype IDML"

def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _set(d, path, value):
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def parse_points(text):
    """Points from what was typed: "72", "72 pt", "72 pt (1\")", or inches: "1\"", "1 in".
    None when blank or not a measure."""
    text = (text or "").strip().lower().replace("\u2033", '"')
    m = re.match(r'^(\d+(?:\.\d*)?|\.\d+)\s*(pt|p|"|in|inch|inches)?', text)
    if not m:
        return None
    value = float(m.group(1))
    return value * 72 if m.group(2) in ('"', "in", "inch", "inches") else value


def format_points(value):
    """72 -> '72 pt (1")'; 84 -> '84 pt (1.17")'."""
    if value is None:
        return ""
    inches = ("%.2f" % (value / 72)).rstrip("0").rstrip(".")
    return '%g pt (%s")' % (round(value * 2) / 2, inches)


def _num(text, kind):
    text = (text or "").strip()
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    return int(v) if kind == "int" else v


class Form:
    """Widgets for a list of fields, bound to a dict (read with load(), written with save())."""

    def __init__(self, parent, fields, columns=1, by_column=False):
        """by_column: fill each column top to bottom (fields listed in reading order down the
        first column, then the second), instead of row by row."""
        self.fields, self.vars, self.font_boxes, self.labels = fields, {}, [], {}
        self.points_start = {}      # path -> function: a blank points field's arrows start there
        for n, (path, label, kind, choices) in enumerate(fields):
            rows = -(-len(fields) // columns)
            if by_column:
                row, col = n % rows, (n // rows) * 2
            else:
                row, col = n // columns, (n % columns) * 2
            if kind == "bool":
                var = tk.BooleanVar()
                ttk.Checkbutton(parent, text=label, variable=var).grid(
                    row=row, column=col, columnspan=2, sticky="w", padx=6, pady=2)
            elif kind in ("radio", "one_of"):
                # radio: one of the choices [(value, label)]; one_of: check boxes of which at
                # most one is on (the value is None when none is).
                var = tk.StringVar()
                box = ttk.Frame(parent)
                box.grid(row=row, column=col, columnspan=2, sticky="w", padx=6, pady=2)
                if label:
                    ttk.Label(box, text=label).pack(side="left", padx=(0, 6))
                for value, text in choices:
                    if kind == "radio":
                        ttk.Radiobutton(box, text=text, value=value, variable=var).pack(
                            side="left", padx=(0, 8))
                        continue
                    check = tk.BooleanVar()

                    def toggled(var=var, check=check, value=value):
                        var.set(value if check.get() else "")
                    ttk.Checkbutton(box, text=text, variable=check, command=toggled).pack(
                        side="left", padx=(0, 8))

                    def follow(*_a, var=var, check=check, value=value):
                        check.set(var.get() == value)
                    var.trace_add("write", follow)
            else:
                var = tk.StringVar()
                lab = ttk.Label(parent, text=label)
                lab.grid(row=row, column=col, sticky="w", padx=6, pady=2)
                self.labels[path] = (lab, label)
                if kind == "size":
                    w = ttk.Combobox(parent, textvariable=var, values=choices, width=24)
                elif kind in ("choice", "int_choice"):
                    w = ttk.Combobox(parent, textvariable=var, values=choices, state="readonly",
                                     width=24)
                elif kind == "file":
                    w = ttk.Frame(parent)
                    ttk.Entry(w, textvariable=var, width=14).pack(side="left", fill="x",
                                                                   expand=True)

                    def browse(var=var):
                        path = filedialog.askopenfilename(
                            title="IDML file whose styles the book should use",
                            filetypes=[("InDesign Markup", "*.idml")])
                        if path:
                            var.set(path)
                    ttk.Button(w, text="Browse...", command=browse).pack(side="left", padx=2)
                elif kind == "points":
                    w = ttk.Spinbox(parent, textvariable=var, width=24)

                    def step(direction, var=var, path=path, size=choices[0]):
                        value = parse_points(var.get())
                        if value is None:
                            start = self.points_start.get(path)
                            value = start() if start else 72
                        else:
                            value = max(0, value + direction * size)
                        var.set(format_points(value))
                        return "break"

                    def tidy(_e=None, var=var):
                        if var.get().strip():
                            var.set(format_points(parse_points(var.get())))
                    w.bind("<<Increment>>", lambda e, s=step: s(1))
                    w.bind("<<Decrement>>", lambda e, s=step: s(-1))
                    w.bind("<FocusOut>", tidy)
                    w.bind("<Return>", tidy)
                elif kind == "font":
                    w = ttk.Combobox(parent, textvariable=var, width=24, height=20,
                                     values=["(reading the installed fonts...)"])
                    self.font_boxes.append((w, choices))
                else:
                    w = ttk.Entry(parent, textvariable=var, width=26)
                w.grid(row=row, column=col + 1, sticky="we", padx=6, pady=2)
            self.vars[path] = (var, kind)

    def _unit(self, path):
        """The unit a points field is saved in ("pt" or "in")."""
        for p, _label, kind, choices in self.fields:
            if p == path and kind == "points":
                return (choices or (6, "pt"))[1]
        return "pt"

    def set_fonts(self, lists):
        """Fill the font dropdowns: lists = {None: all families, "hebrew": [...], ...}."""
        for box, script in self.font_boxes:
            box["values"] = lists.get(script) or lists.get(None) or []

    def load(self, data):
        for path, (var, kind) in self.vars.items():
            v = _get(data, path)
            if kind == "bool":
                var.set(bool(v))
            elif kind == "points":
                scale = 72 if self._unit(path) == "in" else 1
                var.set(format_points(None if v is None else v * scale))
            else:
                var.set("" if v is None else (("%g" % v) if isinstance(v, float) else str(v)))

    def save(self, data):
        for path, (var, kind) in self.vars.items():
            if kind == "bool":
                value = bool(var.get())
            elif kind == "size":
                value = _num(var.get(), "number") or 11
            elif kind == "int_choice":
                value = _num(var.get(), "int") or 0
            elif kind == "one_of":
                value = var.get() or None
            elif kind == "points":
                value = parse_points(var.get())
                if value is not None and self._unit(path) == "in":
                    value = round(value / 72, 4)
            elif kind in ("number", "int"):
                value = _num(var.get(), kind)
                if value is None and kind == "int":
                    value = 0
            else:
                value = var.get().strip() or None
                if kind == "font" and value and value.startswith("("):
                    value = None          # the placeholder shown while fonts are read
                if kind == "choice" and value is None:
                    continue
            _set(data, path, value)
