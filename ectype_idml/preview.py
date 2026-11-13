"""Previews of the generated front pages (half-title, title page, copyright page) for the
window: each page as lines of text with their size and placement, at the book's trim and
margins, so Book Details can be checked before exporting.

The sizes and spacing follow the book's styles as the exporter makes them (Exporter's
paragraph styles: Book Title 2.4 times the body size, and so on); a style template's styles
aren't applied here. Keep the table below in step with the exporter.
"""

from dataclasses import dataclass, field

from . import frontmatter
from .export import TRIMS, body_size, calculated_margins, leading_for
from .layout import _half

# style: (size and leading as multiples of the body size, italic, centered, space before in
# body lines). None = the body leading. The Copyright styles are 2 pt below the body size.
STYLES = {
    "Half Title": (1.6, 2.0, False, True, 0),
    "Series": (1.0, None, True, True, 2),
    "Book Title": (2.4, 2.8, False, True, 0),
    "Book Subtitle": (1.4, 1.8, True, True, 0),
    "Volume": (1.4, 1.8, True, True, 1),
    "Author": (1.3, 1.7, False, True, 2),
    "Publisher": (1.0, None, False, True, 6),
}
SPACE_AFTER = {"Book Title": 1, "Book Subtitle": 1, "Volume": 1, "Author": 1}   # body lines


@dataclass
class Line:
    text: str
    size: float
    lead: float
    italic: bool = False
    centered: bool = False
    space_before: float = 0
    space_after: float = 0


@dataclass
class Page:
    name: str
    width: float                  # points
    height: float
    margins: dict                 # points: top, bottom, inside, outside
    lines: list = field(default_factory=list)
    sink: float = 0               # points below the top margin where the text starts
    bottom: bool = False          # set at the foot of the text area (the copyright page)
    recto: bool = True


def _lines(paras, size, lead):
    out = []
    for p in paras:
        text = "".join(r.text for r in p.runs)
        if p.style.startswith("Copyright"):
            cs = size - 2
            style = Line(text, cs, _half(cs * 1.22), p.style == "Copyright Title",
                         space_after=_half(lead / 2))
        else:
            k, kl, italic, centered, before = STYLES.get(p.style, (1.0, None, False, True, 0))
            style = Line(text, _half(size * k), _half(size * kl) if kl else lead, italic,
                         centered, before * lead, SPACE_AFTER.get(p.style, 0) * lead)
        for n, part in enumerate(text.split("\n")):
            out.append(Line(part, style.size, style.lead, style.italic, style.centered,
                            style.space_before if n == 0 else 0,
                            style.space_after if n == len(text.split("\n")) - 1 else 0))
    return out


def front_pages(info, profile, lang="en"):
    """The generated front pages as Page objects: the half-title (when on), the title page
    and the copyright page."""
    g, _found = calculated_margins(profile)
    page = profile["page"]
    m = dict(g.margins)
    for k, v in (page.get("margins") or {}).items():
        if v:
            m[k] = _half(v * 72)
    if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
        width, height = page["custom_width"] * 72, page["custom_height"] * 72
    else:
        width, height = (v * 72 for v in TRIMS.get(page.get("trim"), TRIMS["6x9"]))
    size = body_size(profile)
    lead = leading_for(profile, size)
    text_height = height - m["top"] - m["bottom"]
    pages = []
    if info.get("half_title", True):
        pages.append(Page("Half-title", width, height, m,
                          _lines(frontmatter.half_title(info, lang), size, lead),
                          sink=_half(text_height / 4)))
    pages.append(Page("Title page", width, height, m,
                      _lines(frontmatter.title_page(info, lang), size, lead),
                      sink=_half(text_height / 5)))
    paras, _notes = frontmatter.copyright_page(info, lang, profile.get("notices"))
    pages.append(Page("Copyright page", width, height, m, _lines(paras, size, lead),
                      bottom=True, recto=False))
    return pages
