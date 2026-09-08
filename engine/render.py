"""Card Forge rendering engine.

Refactored 1:1 from card_text.py — same math, same output. Pure functions,
no argparse, no sys.exit. render(spec, base) is the single entry point;
render_card(spec, base) additionally returns fit metadata for the GUI.

Inline markup in body text: **bold**, *italic*, ***bold italic***,
~~strikethrough~~. Line markup (structured/--left mode): '## ' bold header,
'[] ' empty checkbox, '[x] ' checked checkbox, blank line = paragraph break.
Text without inline markup goes through the original code path untouched, so
old cards re-render pixel-identically.
"""
import os
import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DEFAULT = r"C:\Users\Adam\Pictures\Barley\card_base_dark50.png"
FONT_DEFAULT = r"C:\Windows\Fonts\georgia.ttf"
TITLE_FONT_DEFAULT = r"C:\Windows\Fonts\georgiab.ttf"

GOLD_TOP = (252, 228, 150)
GOLD_MID = (222, 178, 74)
GOLD_BOT = (150, 105, 28)
SHADOW = (0, 0, 0, 220)

INLINE_RE = re.compile(
    r"\*\*\*(?P<bi>.+?)\*\*\*"
    r"|\*\*(?P<b>.+?)\*\*"
    r"|\*(?P<i>[^*]+?)\*"
    r"|~~(?P<s>.+?)~~")


class FontNotFound(Exception):
    pass


@dataclass
class CardSpec:
    body: str = ""
    title: str = ""
    checklist: str = ""              # "a;b;c" -> two-column checked list under the body
    font: str = FONT_DEFAULT
    title_font: str = TITLE_FONT_DEFAULT
    left: bool = False               # structured mode: '## ' headers, '[] ' / '[x] ' boxes
    align: str = "center"            # vertical placement of the body block: "center" | "top"
    gap: float = 1.5                 # title-to-body space, in title line heights
    margin: float = 0.08             # side margin, fraction of width
    top: float = 0.08                # text region top, fraction of height
    bottom: float = 0.92             # text region bottom, fraction of height
    max_size: int = 0                # max body px, 0 = auto
    min_size: int = 0                # min body px, 0 = auto
    title_size: int = 0              # max title px, 0 = auto
    check_size: int = 0              # checklist px, 0 = auto
    spacing: float = 1.25            # line height multiplier
    gold_top: tuple = field(default_factory=lambda: GOLD_TOP)
    gold_mid: tuple = field(default_factory=lambda: GOLD_MID)
    gold_bot: tuple = field(default_factory=lambda: GOLD_BOT)


@dataclass
class RenderResult:
    image: Image.Image
    body_px: int
    line_count: int
    overflow: bool                   # body hit the size floor and still doesn't fit


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        raise FontNotFound(f"font not found: {path}")


def _variant(path, suffix):
    """georgia.ttf + 'b' -> georgiab.ttf if it exists (Windows face naming)."""
    root, ext = os.path.splitext(path)
    cand = root + suffix + ext
    return cand if os.path.exists(cand) else None


class FontSet:
    """Regular/bold/italic/bold-italic faces of the body font at one size.

    Missing variant files fall back: bold -> the title font, italic -> regular,
    bold italic -> bold.
    """

    def __init__(self, font_path, title_font_path, size):
        self.size = size
        self.regular = load_font(font_path, size)
        bold_path = _variant(font_path, "b") or title_font_path
        self.bold = load_font(bold_path, size)
        self.italic = load_font(_variant(font_path, "i") or font_path, size)
        self.bold_italic = load_font(_variant(font_path, "z") or bold_path, size)

    def for_style(self, bold, italic):
        if bold and italic:
            return self.bold_italic
        if bold:
            return self.bold
        if italic:
            return self.italic
        return self.regular


def parse_inline(text):
    """-> list of (text, bold, italic, strike) segments."""
    segs, pos = [], 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            segs.append((text[pos:m.start()], False, False, False))
        if m.group("bi") is not None:
            segs.append((m.group("bi"), True, True, False))
        elif m.group("b") is not None:
            segs.append((m.group("b"), True, False, False))
        elif m.group("i") is not None:
            segs.append((m.group("i"), False, True, False))
        else:
            segs.append((m.group("s"), False, False, True))
        pos = m.end()
    if pos < len(text):
        segs.append((text[pos:], False, False, False))
    return segs


def _styled_words(segs):
    """Segments -> words; a word is a list of styled runs (handles 'x**y**z')."""
    words, cur = [], []
    for t, b, i, s in segs:
        parts = t.split(" ")
        for j, p in enumerate(parts):
            if j > 0 and cur:
                words.append(cur)
                cur = []
            if p:
                cur.append((p, b, i, s))
    if cur:
        words.append(cur)
    return words


def _word_w(word, fonts, draw):
    return sum(draw.textlength(t, font=fonts.for_style(b, i))
               for t, b, i, s in word)


def wrap(text, font, max_w, draw):
    lines = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def wrap_styled(text, fonts, max_w, draw):
    """Word-wrap honoring inline markup. Returns a list of lines: a plain
    line is a str (drawn exactly as the original code path), a styled line
    is a list of words."""
    lines = []
    for para in text.split("\n"):
        segs = parse_inline(para)
        if not any(b or i or s for _, b, i, s in segs):
            lines.extend(wrap(para, fonts.regular, max_w, draw))
            continue
        words = _styled_words(segs)
        if not words:
            lines.append("")
            continue
        space_w = draw.textlength(" ", font=fonts.regular)
        cur, cur_w = [words[0]], _word_w(words[0], fonts, draw)
        for wd in words[1:]:
            ww = _word_w(wd, fonts, draw)
            if cur_w + space_w + ww <= max_w:
                cur.append(wd)
                cur_w += space_w + ww
            else:
                lines.append(cur)
                cur, cur_w = [wd], ww
        lines.append(cur)
    return lines


def _line_w(line, fonts, draw):
    if isinstance(line, str):
        return draw.textlength(line, font=fonts.regular)
    space_w = draw.textlength(" ", font=fonts.regular)
    return (sum(_word_w(w, fonts, draw) for w in line)
            + space_w * (len(line) - 1))


def _draw_line(md, line, x, y, fonts):
    if isinstance(line, str):
        md.text((x, y), line, font=fonts.regular, fill=255)
        return
    space_w = md.textlength(" ", font=fonts.regular)
    size = fonts.size
    for word in line:
        for t, b, i, s in word:
            f = fonts.for_style(b, i)
            w = md.textlength(t, font=f)
            md.text((x, y), t, font=f, fill=255)
            if s:
                sy = y + int(size * 0.52)
                md.line([(x, sy), (x + w, sy)], fill=255,
                        width=max(2, size // 16))
            x += w
        x += space_w


def fit(text, font_path, max_w, max_h, start, floor, draw, spacing):
    size = start
    while size >= floor:
        font = load_font(font_path, size)
        lines = wrap(text, font, max_w, draw)
        line_h = int(size * spacing)
        total_h = line_h * len(lines)
        widest = max(draw.textlength(l, font=font) for l in lines) if lines else 0
        if total_h <= max_h and widest <= max_w:
            return font, lines, line_h
        size -= 4
    font = load_font(font_path, floor)
    lines = wrap(text, font, max_w, draw)
    return font, lines, int(floor * spacing)


def fit_styled(text, font_path, title_font_path, max_w, max_h, start, floor,
               draw, spacing):
    """fit() with inline-markup awareness; identical to fit() on plain text."""
    size = start
    while size >= floor:
        fonts = FontSet(font_path, title_font_path, size)
        lines = wrap_styled(text, fonts, max_w, draw)
        line_h = int(size * spacing)
        total_h = line_h * len(lines)
        widest = max((_line_w(l, fonts, draw) for l in lines), default=0)
        if total_h <= max_h and widest <= max_w:
            return fonts, lines, line_h
        size -= 4
    fonts = FontSet(font_path, title_font_path, floor)
    lines = wrap_styled(text, fonts, max_w, draw)
    return fonts, lines, int(floor * spacing)


def gold_gradient(w, h, gold=(GOLD_TOP, GOLD_MID, GOLD_BOT)):
    top, mid, bot = gold
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if t < 0.5:
            a, b, u = top, mid, t / 0.5
        else:
            a, b, u = mid, bot, (t - 0.5) / 0.5
        px[0, y] = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
    # every row is a single color, so NEAREST widening reproduces the
    # original per-pixel loop exactly at a fraction of the cost
    return col.resize((w, h), Image.NEAREST)


def render_block(canvas, lines, font, line_h, top, center_x, gold, fonts=None):
    """Draw lines centered on center_x starting at top, with shadow + gold
    gradient. Plain lines are strs; styled lines (lists) need fonts."""
    w, h = canvas.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    y = top
    for line in lines:
        if isinstance(line, str):
            lw = md.textlength(line, font=font)
            md.text((center_x - lw / 2, y), line, font=font, fill=255)
        else:
            lw = _line_w(line, fonts, md)
            _draw_line(md, line, center_x - lw / 2, y, fonts)
        y += line_h

    # shadow: offset, blurred
    off = max(2, font.size // 22)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (w, h), SHADOW)
    shadow.paste(shadow_layer, (off, off), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(off * 1.5))
    canvas.alpha_composite(shadow)

    # soft warm glow behind letters
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow.paste(Image.new("RGBA", (w, h), (255, 200, 90, 90)), (0, 0), mask)
    glow = glow.filter(ImageFilter.GaussianBlur(off * 3))
    canvas.alpha_composite(glow)

    # gold fill, gradient runs per line
    fill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = top
    for _ in lines:
        grad = gold_gradient(w, line_h, gold).convert("RGBA")
        fill.paste(grad, (0, y))
        y += line_h
    fill.putalpha(mask)
    canvas.alpha_composite(fill)
    return y


def render_checklist(canvas, items, font, top, margin, W, spacing, gap, gold):
    """Two-column checklist, every box checked, gold styling."""
    size = font.size
    box = int(size * 0.85)
    line_h = int(size * spacing)
    col_w = (W - 2 * margin) // 2
    rows = (len(items) + 1) // 2
    mask = Image.new("L", canvas.size, 0)
    md = ImageDraw.Draw(mask)
    stroke = max(3, size // 14)
    for i, item in enumerate(items):
        col, row = i // rows, i % rows
        x = margin + col * col_w
        y = top + row * line_h
        by = y + (line_h - box) // 2
        # box outline
        md.rounded_rectangle([x, by, x + box, by + box], radius=box // 6,
                             outline=255, width=stroke)
        # check mark
        md.line([(x + box * 0.22, by + box * 0.55),
                 (x + box * 0.42, by + box * 0.75),
                 (x + box * 0.80, by + box * 0.25)],
                fill=255, width=stroke + 2, joint="curve")
        md.text((x + box + int(size * 0.45), y), item, font=font, fill=255)
    # shadow + gold, same treatment as text
    off = max(2, size // 22)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", canvas.size, SHADOW), (off, off), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(off * 1.5))
    canvas.alpha_composite(shadow)
    fill = gold_gradient(canvas.size[0], canvas.size[1], gold).convert("RGBA")
    fill.putalpha(mask)
    canvas.alpha_composite(fill)
    return top + rows * line_h


def render_structured(canvas, body, fonts, bold_font, max_w, top, margin,
                      spacing, gold):
    """Left-aligned body. Lines starting with '## ' are bold headers, '[] '
    gets an empty box, '[x] ' a checked box, each with hanging indent. Blank
    lines are paragraph breaks. Inline **bold**/*italic*/~~strike~~ works in
    item and paragraph lines. Returns bottom y."""
    w, h = canvas.size
    size = fonts.size
    line_h = int(size * spacing)
    box = int(size * 0.8)
    indent = box + int(size * 0.45)
    stroke = max(3, size // 14)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    y = top
    for raw in body.split("\n"):
        if not raw.strip():
            y += line_h // 2
            continue
        if raw.startswith("## "):
            for ln in wrap(raw[3:], bold_font, max_w, md):
                md.text((margin, y), ln, font=bold_font, fill=255)
                y += line_h
            continue
        if raw.startswith("[] ") or raw.startswith("[x] "):
            checked = raw.startswith("[x] ")
            text = raw[4:] if checked else raw[3:]
            by = y + (line_h - box) // 2
            md.rounded_rectangle([margin, by, margin + box, by + box],
                                 radius=box // 6, outline=255, width=stroke)
            if checked:
                md.line([(margin + box * 0.22, by + box * 0.55),
                         (margin + box * 0.42, by + box * 0.75),
                         (margin + box * 0.80, by + box * 0.25)],
                        fill=255, width=stroke + 2, joint="curve")
            for ln in wrap_styled(text, fonts, max_w - indent, md):
                _draw_line(md, ln, margin + indent, y, fonts)
                y += line_h
            continue
        for ln in wrap_styled(raw, fonts, max_w, md):
            _draw_line(md, ln, margin, y, fonts)
            y += line_h
    off = max(2, size // 22)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", (w, h), SHADOW), (off, off), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(off * 1.5))
    canvas.alpha_composite(shadow)
    fill = gold_gradient(w, h, gold).convert("RGBA")
    fill.putalpha(mask)
    canvas.alpha_composite(fill)
    return y


def structured_height(body, fonts, bold_font, max_w, spacing, draw):
    size = fonts.size
    line_h = int(size * spacing)
    indent = int(size * 0.8) + int(size * 0.45)
    y = 0
    for raw in body.split("\n"):
        if not raw.strip():
            y += line_h // 2
        elif raw.startswith("## "):
            y += line_h * len(wrap(raw[3:], bold_font, max_w, draw))
        elif raw.startswith("[] ") or raw.startswith("[x] "):
            text = raw[4:] if raw.startswith("[x] ") else raw[3:]
            y += line_h * len(wrap_styled(text, fonts, max_w - indent, draw))
        else:
            y += line_h * len(wrap_styled(raw, fonts, max_w, draw))
    return y


def render_card(spec: CardSpec, base: Image.Image) -> RenderResult:
    """Full render with fit metadata. Mirrors the original CLI main() exactly."""
    base = base.convert("RGBA")
    W, H = base.size
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    gold = (tuple(spec.gold_top), tuple(spec.gold_mid), tuple(spec.gold_bot))

    margin = int(W * spec.margin)
    max_w = W - 2 * margin
    region_top = int(H * spec.top)
    region_bot = int(H * spec.bottom)
    cx = W / 2

    max_size = spec.max_size or int(W * 0.11)
    min_size = spec.min_size or int(W * 0.03)
    body = spec.body
    overflow = False

    y_cursor = region_top
    if spec.title:
        tmax = spec.title_size or int(W * 0.10)
        tfont, tlines, tlh = fit(spec.title, spec.title_font, max_w, int(H * 0.18),
                                 tmax, int(W * 0.05), draw, 1.1)
        y_cursor = render_block(canvas, tlines, tfont, tlh, region_top, cx, gold)
        y_cursor += int(tlh * spec.gap)

    items = [i.strip() for i in spec.checklist.split(";") if i.strip()] if spec.checklist else []
    check_size = spec.check_size or int(W * 0.045)
    check_h = 0
    if items:
        col_w = max_w // 2
        while check_size > int(W * 0.02):
            f = load_font(spec.font, check_size)
            widest = max(draw.textlength(i, font=f) for i in items)
            if widest + check_size * 1.4 <= col_w:
                break
            check_size -= 2
        rows = (len(items) + 1) // 2
        check_h = rows * int(check_size * spec.spacing) + int(check_size * 1.2)

    avail_h = region_bot - y_cursor - check_h
    if body and spec.left:
        size = max_size
        while size > min_size:
            fonts = FontSet(spec.font, spec.title_font, size)
            bfont = load_font(spec.title_font, size)
            if structured_height(body, fonts, bfont, max_w, spec.spacing, draw) <= avail_h:
                break
            size -= 4
        fonts = FontSet(spec.font, spec.title_font, size)
        bfont = load_font(spec.title_font, size)
        overflow = structured_height(body, fonts, bfont, max_w,
                                     spec.spacing, draw) > avail_h
        font = fonts.regular
        lines = body.split("\n")
        y_cursor = render_structured(canvas, body, fonts, bfont, max_w,
                                     y_cursor, margin, spec.spacing, gold)
    elif body:
        fonts, lines, line_h = fit_styled(body, spec.font, spec.title_font,
                                          max_w, avail_h, max_size, min_size,
                                          draw, spec.spacing)
        font = fonts.regular
        block_h = line_h * len(lines)
        widest = max((_line_w(l, fonts, draw) for l in lines), default=0)
        overflow = block_h > avail_h or widest > max_w
        if spec.align == "center":
            top = y_cursor + (avail_h - block_h) // 2
        else:
            top = y_cursor
        y_cursor = render_block(canvas, lines, font, line_h, top, cx, gold, fonts)
    else:
        font = load_font(spec.font, check_size)
        lines = []

    if items:
        cfont = load_font(spec.font, check_size)
        y_cursor += int(check_size * 1.2)
        render_checklist(canvas, items, cfont, y_cursor, margin, W,
                         spec.spacing, spec.gap, gold)

    out = Image.alpha_composite(base, canvas).convert("RGB")
    return RenderResult(out, font.size, len(lines), overflow)


def render(spec: CardSpec, base: Image.Image) -> Image.Image:
    """Single entry point: render a card spec onto a base plate."""
    return render_card(spec, base).image
