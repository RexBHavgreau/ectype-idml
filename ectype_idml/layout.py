"""Page geometry and pagination (build step 5).

Geometry: the measure (line length) is about 30 times the type size (Bringhurst: "usually
around 30 times the size of the type", 20 to 40 within the expectable range), kept between 45
and 80 characters of the body font as measured (his copyfitting table in effect: characters
per line from the font's widths). The margins take the rest of the width, the inside never
smaller than the outside (binding takes some of it), and a share of the height (bottom larger
than top), with floors of 0.5 in and KDP's gutter minimum for the page count. The text height
is a whole number of body lines.

Pagination: display pages (title page...) and front matter in one roman section from i, with
display pages counted but carrying no folio; the first chapter (or part) starts arabic 1.
Title page, front matter, parts and the first chapter open on a recto; later chapters on a
recto or the next page, as the profile says. Blank versos get the E-Blank master.
"""

from dataclasses import dataclass, field

# KDP paperback: minimum inside margin (inches) by page count, up to the page count given.
KDP_GUTTER = [(150, 0.375), (300, 0.5), (500, 0.625), (700, 0.75), (828, 0.875)]
KDP_MAX_PAGES = 828
KDP_MIN_PAGES = 24
FLOOR = 36                  # every margin at least 0.5 in
MEASURE_EMS = 30            # the measure, in times the type size (Bringhurst)
MIN_CPL, MAX_CPL = 45, 80   # characters per line the measure is kept within
TARGET_CPL = 65             # lines of this length take the base leading (longer want more)
VERTICAL_SHARE = 0.15       # of the page height, for top and bottom margins together
TOP_SHARE = 0.45            # of that, for the top
OUTSIDE_SHARE = 0.42        # of the width left over, for the outside margin


def kdp_gutter(pages):
    """KDP's minimum inside margin in points for a page count."""
    for limit, inches in KDP_GUTTER:
        if pages <= limit:
            return inches * 72
    return KDP_GUTTER[-1][1] * 72


def kdp_band(pages):
    for n, (limit, _inches) in enumerate(KDP_GUTTER):
        if pages <= limit:
            return n
    return len(KDP_GUTTER)


def _half(v):
    return round(v * 2) / 2


@dataclass
class Geometry:
    margins: dict
    measure: float
    text_height: float
    lines: int                # body lines per page
    cpl: float                # characters per line at the body size
    notes: list = field(default_factory=list)


def geometry(width, height, size, lead, avg_width, pages, overrides=None, measure_ems=None):
    """Margins (points) for a trim, body size and leading, the body font's average character
    width (ems) and the estimated page count. overrides: the user's margins in inches.
    measure_ems: the line length in times the type size (default 30)."""
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    notes = []
    char = size * avg_width
    gutter = max(FLOOR, kdp_gutter(pages))
    measure = (measure_ems or MEASURE_EMS) * size
    measure = min(max(measure, MIN_CPL * char), MAX_CPL * char)
    left_over = width - measure
    outside = max(FLOOR, left_over * OUTSIDE_SHARE)
    inside = max(gutter, outside, left_over - outside)
    if inside + outside > left_over:
        # The floors win: the measure gives way.
        measure = width - inside - outside
        if measure < MIN_CPL * char:
            notes.append("The text width is under %d characters per line at %g pt on this trim. "
                         "Choose a smaller type size or a larger trim." % (MIN_CPL, size))
    if "inside" in overrides:
        inside = _half(overrides["inside"] * 72)
        if inside < kdp_gutter(pages):
            notes.append("The inside margin (%.3g in) is below KDP's minimum of %.3g in for %d "
                          "pages." % (inside / 72, kdp_gutter(pages) / 72, pages))
    if "outside" in overrides:
        outside = _half(overrides["outside"] * 72)
    measure = width - inside - outside
    if outside > 1.25 * 72 and "outside" not in overrides:
        notes.append("The margins are wide (%.2g in outside) for %g pt type on this trim. A "
                     "larger type size, or two columns, would fill the page better."
                     % (outside / 72, size))
    vertical = height * VERTICAL_SHARE
    top = max(FLOOR, _half(vertical * TOP_SHARE))
    bottom = max(FLOOR, vertical - top)
    if "top" in overrides:
        top = _half(overrides["top"] * 72)
    if "bottom" in overrides:
        bottom = _half(overrides["bottom"] * 72)
    # A whole number of body lines; what's left over goes to the bottom margin.
    lines = max(1, int((height - top - bottom) // lead))
    if "bottom" not in overrides:
        bottom = height - top - lines * lead
    m = {"top": _half(top), "bottom": _half(bottom), "inside": _half(inside),
         "outside": _half(outside)}
    measure = width - m["inside"] - m["outside"]
    return Geometry(m, measure, height - m["top"] - m["bottom"], lines,
                    measure / char, notes)


@dataclass
class Placed:
    start: int                # first page index
    pages: int                # pages the story is threaded through
    blank_before: bool = False


def plan_pages(units, chapters_open="recto"):
    """Where each unit goes. units: [(kind, estimated pages, spare pages)] or [(kind, pages,
    spare, opens)] in book order, kind as in the outline (display, front, part, chapter, back);
    opens: "recto", "next" (the next page, e.g. a copyright page after the title page), or None
    for the rule by kind.

    Returns ([Placed], page_count, masters {page index: master name}, first body unit index).
    """
    placed, masters = [], {}
    page = 0
    first_body = None
    for n, unit in enumerate(units):
        kind, est, spare = unit[:3]
        opens = unit[3] if len(unit) > 3 else None
        front = kind in ("display", "front")
        if not front and first_body is None:
            first_body = n
        if opens:
            recto = opens == "recto"
        elif front or kind == "part" or n == first_body or chapters_open == "recto":
            recto = True
        else:
            recto = False
        blank = False
        if recto and page % 2 == 1:
            masters[page] = "E-Blank"
            page += 1
            blank = True
        count = max(1, est + spare)
        placed.append(Placed(page, count, blank))
        for i in range(page, page + count):
            if kind == "display":
                masters[i] = "D-Display"
            elif i == page:
                masters[i] = "B-Opener" if kind != "part" else "D-Display"
            elif front:
                masters[i] = "C-Front"
            else:
                masters[i] = "A-Body"
        page += count
    return placed, page, masters, first_body


def page_count_notes(pages):
    notes = []
    if pages < KDP_MIN_PAGES:
        notes.append("%d pages is under KDP's minimum of %d for a paperback." % (pages, KDP_MIN_PAGES))
    if pages > KDP_MAX_PAGES:
        notes.append("%d pages is over KDP's maximum of %d for a paperback." % (pages, KDP_MAX_PAGES))
    for limit, _inches in KDP_GUTTER[:-1]:
        if abs(pages - limit) <= 8:
            notes.append("The page count (%d) is near KDP's %d-page step for the inside margin; "
                         "if the final count crosses it, check the inside margin "
                         "(%.3g in up to %d pages, %.3g in above)."
                         % (pages, limit, kdp_gutter(limit) / 72, limit,
                            kdp_gutter(limit + 1) / 72))
    return notes


# Leading as a share of the body size, for tight, standard and open setting (at 11 pt about
# 12.5-13, 13.5-14 and 14.5-15), before the shifts for x-height and measure.
LEADING_RATIOS = {"tight": (1.14, 1.18), "standard": (1.23, 1.27), "open": (1.32, 1.36)}
TYPICAL_X_HEIGHT = 0.46     # ems: a book serif's


def leading_suggestions(size, x_height=None, cpl=TARGET_CPL, font=None):
    """({feel: (low, high, pick)}, explanation). A large x-height and long lines want more
    leading; a small x-height and short lines can take less."""
    shift, why = 0.0, []
    if x_height:
        shift += (x_height - TYPICAL_X_HEIGHT) * 1.0
        if x_height >= TYPICAL_X_HEIGHT + 0.03:
            why.append("%s has a large x-height, so a little more leading" % (font or "the font"))
        elif x_height <= TYPICAL_X_HEIGHT - 0.03:
            why.append("%s has a small x-height, so a little less leading" % (font or "the font"))
    if cpl:
        shift += (cpl - TARGET_CPL) * 0.002
        if cpl >= TARGET_CPL + 6:
            why.append("long lines (%d characters) want more leading" % round(cpl))
        elif cpl <= TARGET_CPL - 6:
            why.append("short lines (%d characters) can take less" % round(cpl))
    out = {}
    for feel, (lo, hi) in LEADING_RATIOS.items():
        a, b = _half(size * (lo + shift)), _half(size * (hi + shift))
        out[feel] = (a, b, _half(size * ((lo + hi) / 2 + shift)))
    return out, "; ".join(why)
