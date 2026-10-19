#!/usr/bin/env python3
"""
build_manual.py — génère les manuels utilisateur PDF de PhantomSDR-ORSAT
(frontend/src/assets/docs/manualFR.pdf, manualEN.pdf, manualES.pdf)
à partir des sources éditables manual_fr.md, manual_en.md, manual_es.md.

Usage :  python3 docs/manual/build_manual.py          (tout : manuels + guides de l'analyseur)
         python3 docs/manual/build_manual.py fr       (un seul manuel)
         python3 docs/manual/build_manual.py analyseur_fr.md   (un guide de l'analyseur audio)
Dépendance : reportlab (pip install reportlab), polices DejaVu.

Syntaxe des sources (volontairement minimale) :
  ---  bloc d'en-tête « clé: valeur » (titre, sous-titre, en-têtes…)  ---
  # 1. Titre de chapitre            ## 1.1 Sous-titre
  Paragraphe, avec **gras** et *italique*.
  - puce          1. élément de liste numérotée
  > [Astuce] texte d'un encadré vert
  ![légende](images/x.jpg){w=410}          image centrée (largeur en points)
  ![légende](images/x.jpg){w=200,side}     image à gauche, la liste qui suit à droite
  | En-tête | En-tête |  puis  | cellule | cellule |      tableau
"""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether,
                                ListFlowable, ListItem, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "frontend" / "src" / "assets" / "docs"

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]


def register_fonts():
    names = {"DejaVuSans": "DejaVuSans.ttf", "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
             "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf"}
    for name, fn in names.items():
        for d in FONT_DIRS:
            p = Path(d) / fn
            if p.is_file():
                pdfmetrics.registerFont(TTFont(name, str(p)))
                break
        else:
            sys.exit("Police introuvable : %s (installez fonts-dejavu)" % fn)
    pdfmetrics.registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
                                  italic="DejaVuSans-Oblique", boldItalic="DejaVuSans-BoldOblique")


NAVY = colors.HexColor("#1f2a44")
BLUE = colors.HexColor("#2e5c8a")
GREEN = colors.HexColor("#1f7a3a")
GREEN_BG = colors.HexColor("#eef7ef")
GREEN_LINE = colors.HexColor("#9fd0a8")
GRAY = colors.HexColor("#6b7280")
GOLD = colors.HexColor("#cfb53b")
TBL_HEAD = colors.HexColor("#e8edf4")
TBL_LINE = colors.HexColor("#c9d2de")

S = {}


def styles():
    S["body"] = ParagraphStyle("body", fontName="DejaVuSans", fontSize=9.6, leading=13.6, alignment=TA_JUSTIFY,
                               spaceAfter=6)
    S["bullet"] = ParagraphStyle("bullet", parent=S["body"], alignment=TA_LEFT, spaceAfter=1.5)
    S["h1"] = ParagraphStyle("h1", fontName="DejaVuSans-Bold", fontSize=19, leading=24, textColor=NAVY,
                             spaceBefore=4, spaceAfter=10)
    S["h2"] = ParagraphStyle("h2", fontName="DejaVuSans-Bold", fontSize=12.5, leading=16, textColor=BLUE,
                             spaceBefore=10, spaceAfter=5, keepWithNext=1)
    S["h1"].keepWithNext = 1
    S["admon"] = ParagraphStyle("admon", fontName="DejaVuSans-Oblique", fontSize=9, leading=12.5,
                                textColor=GREEN)
    S["caption"] = ParagraphStyle("caption", fontName="DejaVuSans-Oblique", fontSize=8, leading=10.5,
                                  textColor=GRAY, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8)
    S["cell"] = ParagraphStyle("cell", fontName="DejaVuSans", fontSize=8.8, leading=11.5)
    S["cellh"] = ParagraphStyle("cellh", parent=S["cell"], fontName="DejaVuSans-Bold")
    S["toc1"] = ParagraphStyle("toc1", fontName="DejaVuSans-Bold", fontSize=10, leading=15)
    S["toc2"] = ParagraphStyle("toc2", fontName="DejaVuSans", fontSize=8.8, leading=12.5, leftIndent=14)
    S["title"] = ParagraphStyle("title", fontName="DejaVuSans-Bold", fontSize=27, leading=33, textColor=NAVY,
                                alignment=TA_CENTER)
    S["subtitle"] = ParagraphStyle("subtitle", fontName="DejaVuSans", fontSize=14, leading=19, textColor=BLUE,
                                   alignment=TA_CENTER)
    S["cover"] = ParagraphStyle("cover", fontName="DejaVuSans", fontSize=10, leading=14, alignment=TA_CENTER)


_GLYPHS = None


def supported(t):
    """Retire les caractères absents de DejaVu (émojis des boutons) pour éviter les carrés vides."""
    global _GLYPHS
    if _GLYPHS is None:
        _GLYPHS = set(pdfmetrics.getFont("DejaVuSans").face.charToGlyph.keys())
    ok = lambda c: ord(c) < 128 or ord(c) in _GLYPHS
    if all(ok(c) for c in t):
        return t
    out = re.sub(r"[^\x00-\x7f](?: |\ufe0f)?", lambda m: m.group(0) if ok(m.group(0)[0]) else "", t)
    out = out.replace("****", "").replace("** **", " ")
    return re.sub(r"  +", " ", out).replace("( ", "(")


def inline(t):
    """**gras** / *italique* → balises ReportLab (le texte est déjà échappé pour & < >)."""
    t = supported(t)
    t = re.sub(r"(?<!&)&(?![a-zA-Z#]+;)", "&amp;", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    return t


class GoldRule(Flowable):
    def __init__(self, width=None, thick=1.4):
        super().__init__()
        self.w, self.thick = width, thick

    def wrap(self, aw, ah):
        self.aw = self.w or aw
        return self.aw, 4

    def draw(self):
        self.canv.setStrokeColor(GOLD)
        self.canv.setLineWidth(self.thick)
        self.canv.line(0, 2, self.aw, 2)


class H1(Paragraph):
    pass


class H2(Paragraph):
    pass


class Doc(BaseDocTemplate):
    def __init__(self, path, meta, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm,
                         bottomMargin=20 * mm, title=meta.get("pdf_title", ""), author="SV1BTL & F1NSK",
                         subject=meta.get("subtitle", ""), **kw)
        self.meta = meta
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [frame], onPage=lambda c, d: None),
                               PageTemplate("main", [frame], onPage=self.decorate)])

    def decorate(self, c, d):
        m = self.meta
        w, h = A4
        c.saveState()
        c.setFont("DejaVuSans", 8)
        c.setFillColor(GRAY)
        c.drawString(self.leftMargin, h - 14 * mm, m["header_left"])
        c.drawRightString(w - self.rightMargin, h - 14 * mm, m["header_right"])
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.8)
        c.line(self.leftMargin, h - 15.6 * mm, w - self.rightMargin, h - 15.6 * mm)
        c.line(self.leftMargin, 13.5 * mm, w - self.rightMargin, 13.5 * mm)
        c.drawCentredString(w / 2, 9.5 * mm, "%s %d" % (m["page"], d.page))
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, H1):
            key = "h1-%d" % id(f)
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, f.getPlainText(), self.page, key))
            self.canv.addOutlineEntry(f.getPlainText(), key, level=0)
        elif isinstance(f, H2):
            key = "h2-%d" % id(f)
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (1, f.getPlainText(), self.page, key))
            self.canv.addOutlineEntry(f.getPlainText(), key, level=1)


def admon_box(label, text, width):
    p = Paragraph("<b>%s :</b> %s" % (label, inline(text)), S["admon"])
    t = Table([[p]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN_BG), ("BOX", (0, 0), (-1, -1), 0.8, GREEN_LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [Spacer(1, 2), t, Spacer(1, 8)]


def image(path, w, maxw, maxh=None):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    w = min(w, maxw)
    h = w * ih / iw
    if maxh and h > maxh:
        h = maxh
        w = h * iw / ih
    img = Image(str(path), width=w, height=h)
    return img


def bullets(items, width=None):
    return ListFlowable([ListItem(Paragraph(inline(t), S["bullet"]), leftIndent=12, value="•") for t in items],
                        bulletType="bullet", start="•", leftIndent=12, bulletFontName="DejaVuSans",
                        bulletFontSize=9, spaceAfter=6)


def table(rows, width):
    head = [Paragraph(inline(c), S["cellh"]) for c in rows[0]]
    body = [[Paragraph(inline(c), S["cell"]) for c in r] for r in rows[1:]]
    n = len(rows[0])
    if n == 3:
        cw = [width * 0.22, width * 0.33, width * 0.45]
    elif n == 2:
        cw = [width * 0.3, width * 0.7]
    else:   # 4 colonnes et plus : la 2e (souvent la description) prend la place restante
        rest = width * 0.18 * (n - 2)
        cw = [width * 0.2, width - width * 0.2 - rest] + [width * 0.18] * (n - 2)
        if cw[1] < width * 0.2:
            cw = [width / n] * n
    t = Table([head] + body, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TBL_HEAD), ("GRID", (0, 0), (-1, -1), 0.5, TBL_LINE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [t, Spacer(1, 8)]


def parse(md_path):
    txt = md_path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\n(.*?)\n---\n", txt, re.S)
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        txt = txt[m.end():]
    return meta, txt


def story_for(meta, txt, width):
    story = []
    # ── Couverture ──
    story += [Spacer(1, 20 * mm), Paragraph(meta["title"], S["title"]), Spacer(1, 6),
              Paragraph(meta["subtitle"], S["subtitle"]), Paragraph(meta["url"], S["subtitle"]), Spacer(1, 4),
              GoldRule(width * 0.45), Spacer(1, 10)]
    cov = HERE / "images" / meta.get("cover", "cover.jpg")
    if cov.is_file():
        story += [image(cov, 300, width, 105 * mm), Paragraph(meta.get("cover_caption", ""), S["caption"])]
    story += [Spacer(1, 6), Paragraph(meta.get("summary", ""), S["cover"]), Spacer(1, 8),
              Paragraph("<b>%s</b>" % meta.get("edition", ""), S["cover"]),
              Paragraph(inline(meta.get("credits", "")), S["cover"])]
    if meta.get("cover_note"):
        story += [Spacer(1, 6), Paragraph(meta["cover_note"], S["cover"])]
    # ── Sommaire ──
    from reportlab.platypus.doctemplate import NextPageTemplate
    story += [NextPageTemplate("main"), PageBreak(), Paragraph(meta["toc"], S["h1"])]
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    toc.dotsMinLevel = 0
    story += [toc, PageBreak()]

    lines = txt.split("\n")
    i, n = 0, len(lines)
    para = []
    first_h1 = True

    def flush():
        if para:
            story.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    while i < n:
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
            i += 1
            continue
        if ln.startswith("# "):
            flush()
            if not first_h1:
                story.append(CondPageBreak(95 * mm))
            first_h1 = False
            story += [GoldRule(), Spacer(1, 3), H1(inline(ln[2:].strip()), S["h1"])]
            i += 1
            continue
        if ln.startswith("## "):
            flush()
            story += [CondPageBreak(60 * mm), H2(inline(ln[3:].strip()), S["h2"])]
            i += 1
            continue
        if ln.startswith("> "):
            flush()
            mm_ = re.match(r">\s*\[([^\]]+)\]\s*(.*)", ln)
            label, text = (mm_.group(1), mm_.group(2)) if mm_ else ("Note", ln[2:])
            story += admon_box(label, text, width)
            i += 1
            continue
        if ln.startswith("|"):
            flush()
            rows = []
            while i < n and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            story += table(rows, width)
            continue
        im = re.match(r"!\[(.*?)\]\((.*?)\)(?:\{(.*?)\})?\s*$", ln)
        if im:
            flush()
            cap, path, opts = im.group(1), HERE / im.group(2), (im.group(3) or "")
            o = dict(kv.split("=") if "=" in kv else (kv, "1") for kv in opts.split(",") if kv)
            w = float(o.get("w", width))
            if "side" in o:
                i += 1
                items = []
                while i < n and (lines[i].startswith("- ") or not lines[i].strip()):
                    if lines[i].startswith("- "):
                        items.append(lines[i][2:].strip())
                    elif items:
                        break
                    i += 1
                if not items:
                    blk = [image(path, w, width, 110 * mm), Paragraph(cap, S["caption"]) if cap else Spacer(1, 8)]
                    story.append(KeepTogether(blk))
                    continue
                lw = min(w, width * 0.45)
                pic = image(path, lw, lw, 120 * mm)
                left = [pic, Paragraph(supported(cap), S["caption"])] if cap else [pic]
                t = Table([[left, bullets(items)]], colWidths=[lw + 12, width - lw - 12])
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                       ("RIGHTPADDING", (0, 0), (0, 0), 12)]))
                story += [t, Spacer(1, 6)]
                continue
            blk = [image(path, w, width, 150 * mm)]
            if cap:
                blk.append(Paragraph(supported(cap), S["caption"]))
            else:
                blk.append(Spacer(1, 8))
            story.append(KeepTogether(blk))
            i += 1
            continue
        if ln.startswith("- "):
            flush()
            items = []
            while i < n and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            story.append(bullets(items))
            continue
        if re.match(r"\d+\. ", ln):                      # liste numérotée « 1. … »
            flush()
            items = []
            while i < n and re.match(r"\d+\. ", lines[i]):
                items.append(lines[i].split(". ", 1)[1].strip())
                i += 1
            story.append(ListFlowable([ListItem(Paragraph(inline(t), S["bullet"]), leftIndent=16) for t in items],
                                      bulletType="1", leftIndent=16, bulletFontName="DejaVuSans",
                                      bulletFontSize=9, spaceAfter=6))
            continue
        para.append(ln.strip())
        i += 1
    flush()
    return story


def build(lang):
    # « fr » → manual_fr.md ; un nom de fichier .md (ex. analyseur_fr.md) est pris tel quel.
    src = HERE / lang if lang.endswith(".md") else HERE / ("manual_%s.md" % lang)
    meta, txt = parse(src)
    out = OUT / meta["pdf"]
    doc = Doc(out, meta)
    doc.multiBuild(story_for(meta, txt, doc.width))
    print("✓", out.relative_to(ROOT))


if __name__ == "__main__":
    register_fonts()
    styles()
    for lang in (sys.argv[1:] or ["fr", "en", "es", "analyseur_fr.md", "analyseur_en.md", "analyseur_es.md"]):
        build(lang)
