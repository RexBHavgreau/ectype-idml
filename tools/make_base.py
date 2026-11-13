"""Make the generator's base package from an InDesign reference file.

    python tools/make_base.py [reference.idml]

Writes ectype_idml/idml/base/: InDesign's own designmap, preferences, colours, fonts and root
styles with the document's content stripped out (spreads, masters, stories, sections, its
paragraph and character styles, metadata). The generator adds its own content to this, so every
setting InDesign always writes is present, as Affinity may rely on them.

Also writes base/snippets.xml: one Spread, Page, TextFrame, MasterSpread, Story and Section, and
the image frames of reference 11 (anchored in text, placed on a page), as
InDesign wrote them, which the generator clones for their full set of attributes.

Default source: reference/idml/01-footnotes.idml (InDesign 2026, 21.6). Rerun after updating the
reference files for a new InDesign version.
"""

import copy
import os
import shutil
import sys
import zipfile

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "reference", "idml", "01-footnotes.idml")
OUT = os.path.join(ROOT, "ectype_idml", "idml", "base")
PKG = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

KEEP_PARAGRAPH = {"ParagraphStyle/$ID/[No paragraph style]", "ParagraphStyle/$ID/NormalParagraphStyle"}
KEEP_CHARACTER = {"CharacterStyle/$ID/[No character style]"}
DROP_DESIGNMAP = {"{%s}MasterSpread" % PKG, "{%s}Spread" % PKG, "{%s}Story" % PKG, "Section"}


def write(path, root):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    etree.ElementTree(root).write(path, xml_declaration=True, encoding="UTF-8", standalone=True)


def main(src=SRC):
    z = zipfile.ZipFile(src)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    parse = lambda n: etree.fromstring(z.read(n), etree.XMLParser(remove_blank_text=False))

    dm = parse("designmap.xml")
    section = dm.find("Section")
    backing = [el.get("src") for el in dm if el.tag == "{%s}BackingStory" % PKG]
    for el in list(dm):
        if el.tag in DROP_DESIGNMAP:
            dm.remove(el)
    backing_id = None
    if backing:
        bs = parse(backing[0])
        for el in bs.iter():
            if el.get("Self"):
                backing_id = el.get("Self")
                break
    dm.set("StoryList", backing_id or "")
    dm.set("Name", "Untitled.indd")
    write(os.path.join(OUT, "designmap.xml"), dm)

    styles = parse("Resources/Styles.xml")
    for ps in list(styles.iter("ParagraphStyle")):
        if ps.get("Self") not in KEEP_PARAGRAPH:
            ps.getparent().remove(ps)
    for cs in list(styles.iter("CharacterStyle")):
        if cs.get("Self") not in KEEP_CHARACTER:
            cs.getparent().remove(cs)
    for toc in list(styles.iter("TOCStyle")):
        if toc.get("Self") != "TOCStyle/$ID/DefaultTOCStyleName":
            toc.getparent().remove(toc)
    write(os.path.join(OUT, "Resources", "Styles.xml"), styles)

    prefs = parse("Resources/Preferences.xml")
    fo = prefs.find("FootnoteOption")
    fo.set("FootnoteTextStyle", "ParagraphStyle/$ID/NormalParagraphStyle")
    fo.set("FootnoteMarkerStyle", "CharacterStyle/$ID/[No character style]")
    write(os.path.join(OUT, "Resources", "Preferences.xml"), prefs)

    for name in ("Resources/Graphic.xml", "Resources/Fonts.xml", "XML/Tags.xml",
                 "META-INF/container.xml") + tuple(backing):
        write(os.path.join(OUT, *name.split("/")), parse(name))

    # One element of each kind, as InDesign wrote it, for the generator to clone.
    snippets = etree.Element("Snippets")
    names = z.namelist()
    spread = parse([n for n in names if n.startswith("Spreads/")][0]).find("Spread")
    page = spread.find("Page")
    frame = spread.find("TextFrame")
    master = parse([n for n in names if n.startswith("MasterSpreads/")][0]).find("MasterSpread")
    story = None
    for n in names:
        if n.startswith("Stories/"):
            st = parse(n).find("Story")
            if st.find(".//Footnote") is not None:
                story = st
                break
    shell = etree.Element("Spread", spread.attrib)
    for child in spread:
        if child.tag == "FlattenerPreference":
            shell.append(child)
    master_shell = etree.Element("MasterSpread", master.attrib)
    for child in master:
        if child.tag == "Page":
            master_shell.append(child)
            break
    story_shell = etree.Element("Story", story.attrib)
    for child in story:
        if child.tag in ("StoryPreference", "InCopyExportOption"):
            story_shell.append(child)
    for el in (shell, page, frame, master_shell, story_shell, section):
        snippets.append(el)
    # Image frames, from reference 11: one anchored in text, one placed on a page.
    images = os.path.join(os.path.dirname(src), "11-images.idml")
    if os.path.exists(images):
        z11 = zipfile.ZipFile(images)
        for n in z11.namelist():
            root = etree.fromstring(z11.read(n)) if n.endswith(".xml") else None
            if root is None:
                continue
            for rect in root.iter("Rectangle"):
                if rect.find("Image") is None:
                    continue
                kind = "AnchoredImage" if n.startswith("Stories/") else "PlacedImage"
                if snippets.find(kind) is None:
                    holder = etree.SubElement(snippets, kind)
                    holder.append(copy.deepcopy(rect))
    write(os.path.join(OUT, "snippets.xml"), snippets)
    print("base written to %s from %s" % (os.path.relpath(OUT, ROOT), os.path.basename(src)))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
