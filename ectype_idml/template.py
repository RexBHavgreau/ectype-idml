"""House styles from an IDML file: the paragraph and character styles of a template the user
chooses (exported from InDesign, from an earlier book of the series say) replace the tool's
styles of the same name, and the template's other styles are added for use by hand.

Only what can't break the file is taken: the styles' own settings, font, leading, based-on,
next style and tabs. Settings that point at things the export doesn't carry (colour swatches
other than InDesign's standard ones, lists, nested and GREP styles, rules' colours) are left
out and named in the report. Page size, margins and masters stay the tool's.
"""

import posixpath
import zipfile

from lxml import etree

from .idml.model import Style

# Attributes of a style element that are bookkeeping, not settings.
HOUSEKEEPING = {"Self", "Name", "Imported", "NextStyle", "KeyboardShortcut",
                "ExtendedKeyboardShortcut", "SplitDocument", "EmitCss", "StyleUniqueId",
                "IncludeClass", "EpubAriaRole", "EmptyNestedStyles", "EmptyLineStyles",
                "EmptyGrepStyles"}
# Values that refer to other objects in the document.
REFERENCES = ("Color/", "Swatch/", "Tint/", "Gradient/", "MixedInk/", "MixedInkGroup/",
              "StrokeStyle/", "CharacterStyle/", "ParagraphStyle/", "NumberingList/",
              "ObjectStyle/", "CellStyle/", "TableStyle/", "Font/")
# The swatches every IDML the tool writes has (from InDesign's own base).
STANDARD = {"Color/Black", "Color/Paper", "Color/Registration", "Color/Cyan", "Color/Magenta",
            "Color/Yellow", "Swatch/None", "StrokeStyle/$ID/Solid", "StrokeStyle/$ID/Dashed",
            "StrokeStyle/$ID/Dotted"}


class TemplateError(Exception):
    """A template that can't be used. The message is shown to the user."""


def _value(v):
    """An attribute's text as the model holds it: numbers and true/false converted."""
    if v in ("true", "false"):
        return v == "true"
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() and "." not in v else f


def _name_map(root, tag):
    return {el.get("Self"): el.get("Name") for el in root.iter(tag)}


def read_template(path):
    """({paragraph style name: Style}, {character style name: Style}, notes) from an IDML."""
    try:
        with zipfile.ZipFile(path) as z:
            root = etree.fromstring(z.read("Resources/Styles.xml"),
                                    etree.XMLParser(resolve_entities=False, huge_tree=True))
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError):
        raise TemplateError("%s can't be read as an IDML file. Export the template from "
                            "InDesign as IDML (File > Save a Copy > InDesign Markup)."
                            % posixpath.basename(str(path).replace("\\", "/"))) from None
    dropped = {}
    out = {}
    for tag in ("ParagraphStyle", "CharacterStyle"):
        names = _name_map(root, tag)
        styles = {}
        for el in root.iter(tag):
            name = el.get("Name") or ""
            if not name or name.startswith(("$ID/", "[")):
                continue
            st = Style(name)
            for k, v in el.attrib.items():
                if k in HOUSEKEEPING:
                    continue
                if v.startswith(REFERENCES) and v not in STANDARD:
                    dropped.setdefault(k, set()).add(name)
                    continue
                st.attrs[k] = _value(v)
            nxt = el.get("NextStyle")
            if nxt and names.get(nxt) and not names[nxt].startswith("$ID/"):
                st.next_style = names[nxt]
            props = el.find("Properties")
            for child in (props if props is not None else ()):
                kind = etree.QName(child).localname
                if kind == "BasedOn":
                    ref = (child.text or "").strip()
                    based = names.get(ref)
                    st.based_on = based if based and not based.startswith(("$ID/", "[")) \
                        else None
                elif kind == "AppliedFont":
                    st.font = (child.text or "").strip() or None
                elif kind == "Leading":
                    text = (child.text or "").strip()
                    try:
                        st.leading = float(text)
                    except ValueError:
                        st.leading = "Auto" if text == "Auto" else None
                elif kind == "TabList":
                    for item in child.findall("ListItem"):
                        get = lambda n: (item.findtext(n) or "")  # noqa: E731
                        try:
                            st.tabs.append((get("Alignment") or "LeftAlign",
                                            float(get("Position") or 0), get("Leader")))
                        except ValueError:
                            pass
                elif kind == "BalanceRaggedLines":
                    st.props[kind] = (child.get("type", "enumeration"), (child.text or "").strip())
                elif kind in ("AllNestedStyles", "AllLineStyles", "AllGREPStyles") and len(child):
                    dropped.setdefault(kind, set()).add(name)
                elif kind not in ("PreviewColor",) and (len(child) or child.text):
                    dropped.setdefault(kind, set()).add(name)
            styles[name] = st
        out[tag] = styles
    notes = []
    if dropped:
        labels = {"AllNestedStyles": "nested styles", "AllLineStyles": "line styles",
                  "AllGREPStyles": "GREP styles"}
        parts = ["%s (%s)" % (labels.get(k, k), ", ".join(sorted(v))[:120])
                 for k, v in sorted(dropped.items())]
        notes.append("From the template, these settings were left out (they point at things "
                     "the export doesn't carry); set them again in InDesign if you need them: "
                     + "; ".join(parts) + ".")
    return out["ParagraphStyle"], out["CharacterStyle"], notes


def apply_template(styles, template, keep_names=()):
    """Replace styles (a list of Style) with the template's of the same name, in place.
    Returns the names replaced. keep_names: never replaced."""
    replaced = []
    for n, st in enumerate(styles):
        t = template.get(st.name)
        if t is not None and st.name not in keep_names:
            styles[n] = Style(t.name, t.based_on, dict(t.attrs), t.font, t.leading,
                              t.next_style, dict(t.props), list(t.tabs))
            replaced.append(st.name)
    return replaced
