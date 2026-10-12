#!/usr/bin/python3 -I
"""d3 "neon/cyber" fastfetch generator (prototype).

  gen.py PICTURE.png COLS ROWS OUTPREFIX     -> OUTPREFIX.jsonc, OUTPREFIX-logo.png, OUTPREFIX.json (layout)

Pure PIL + stdlib (same constraints as ~/.config/fastfetch/ff-logo.py).
All rules are documented in design.md; the constants below are the knobs.
"""
import json, math, os, sys
from PIL import Image, ImageFilter, ImageChops

CW, CH = 10, 22                      # kitty cell size in px; ff-logo.py sets the real one


def set_cells(cw, ch):
    """Use the terminal's real cell size (from TIOCGWINSZ)."""
    global CW, CH, GLOW_TOP, GLOW_SIDE, GLOW_BOTTOM
    CW, CH = cw, ch
    GLOW_TOP, GLOW_SIDE, GLOW_BOTTOM = round(1.6 * CH), 3 * CW, CH


def glow_gradient(h1, h2):
    """The picture's glow colour at relative height t (same as the panel spine)."""
    return lambda t: oklch(0.70, 0.19, hue_lerp(h1, h2, max(0.0, min(1.0, t))))


def logo_for(picture, W, H, h1, h2):
    """Fit `picture` into an existing W x H slot with the slot's own glow gradient."""
    logo, _ = make_logo(Image.open(picture).convert('RGBA'), W, H, glow_gradient(h1, h2))
    return logo


def analyse_cached(picture, img):
    """analyse() is ~0.3 s; cache it next to the picture, keyed by its mtime."""
    cache = picture[:-4] + '.json' if picture.endswith('.png') else picture + '.json'
    try:
        c = json.load(open(cache))
        if c.get('mtime') == os.path.getmtime(picture):
            return c
    except (OSError, ValueError):
        pass
    an = analyse(img)
    an['mtime'] = os.path.getmtime(picture)
    try:
        json.dump(an, open(cache, 'w'))
    except OSError:
        pass
    return an
BG = (14, 12, 16)
FG = (205, 214, 244)

# ---------------------------------------------------------------- knobs
MARGIN_MIN = 2        # min outer margin (cols) left and right
GAP = 2               # cols between the logo slot and the panel spine
GLOW_TOP = round(1.6 * CH)  # px of glow headroom above the figure inside the slot
GLOW_SIDE = 3 * CW    # px of glow room left/right of the figure inside the slot
GLOW_BOTTOM = 1 * CH  # px of glow room under the figure (when its feet aren't cut by the frame)
GLOW_FEATHER = 0.45   # glow fades to 0 over this share of the room at the slot edges (no box lines)
PANEL_MIN, PANEL_MAX = 54, 62
LABEL_W = 7           # longest key label ("battery", "kernel"...)
H_MIN = 12            # below this many rows: no picture (compact mode)
H_MAX = 30            # tallest picture (rows); bigger windows keep this size instead of filling the screen
SPACER_MAX = 2        # max blank spine rows per spacer slot
BAR_W = 10


# ---------------------------------------------------------------- colour maths (OKLab / OKLCH)
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return c * 255


def rgb2lab(rgb):
    r, g, b = (_lin(x) for x in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def lab2rgb_raw(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch(L, C, h):
    """OKLCH -> sRGB tuple, reducing chroma until it is inside the gamut."""
    for _ in range(40):
        a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
        lin = lab2rgb_raw(L, a, b)
        if all(-1e-4 <= x <= 1.0001 for x in lin):
            break
        C *= 0.93
    return tuple(max(0, min(255, round(_gam(max(0.0, min(1.0, x)))))) for x in lin)


def lch(rgb):
    L, a, b = rgb2lab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def hue_lerp(h1, h2, t):
    d = ((h2 - h1 + 180) % 360) - 180          # shorter arc
    return (h1 + d * t) % 360


def mix(c1, c2, t):
    """perceptual mix in OKLab"""
    a, b = rgb2lab(c1), rgb2lab(c2)
    L, A, B = (x + (y - x) * t for x, y in zip(a, b))
    return tuple(max(0, min(255, round(_gam(max(0.0, min(1.0, v)))))) for v in lab2rgb_raw(L, A, B))


def lum(c):
    r, g, b = (_lin(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    a, b = sorted((lum(c1), lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def hexc(c):
    return '#%02X%02X%02X' % c


def fg(c):
    return '\u001b[38;2;%d;%d;%dm' % c


def bg(c):
    return '\u001b[48;2;%d;%d;%dm' % c


def col(n0):                   # 0-based column -> CHA (1-based, relative to the WINDOW)
    return '\u001b[%dG' % (n0 + 1)


RST, BOLD, NOBOLD, BGRST = '\u001b[0m', '\u001b[1m', '\u001b[22m', '\u001b[49m'


# ---------------------------------------------------------------- picture analysis
def analyse(img):
    """-> dict(h1, h2, palette[8]) from the opaque pixels of the cut-out."""
    small = img.copy()
    small.thumbnail((120, 160), Image.BOX)
    px = [p for p in (small.get_flattened_data() if hasattr(small, 'get_flattened_data') else small.getdata()) if p[3] > 200]
    hist = [0.0] * 36
    pts = []
    for r, g, b, _ in px:
        L, C, h = lch((r, g, b))
        pts.append(rgb2lab((r, g, b)))
        skin = 20 <= h <= 85 and C < 0.10 and L > 0.62
        if C < 0.035 or skin:
            continue
        hist[int(h // 10) % 36] += C * C * (0.4 + L)
    sm = [sum(hist[(i + k) % 36] * w for k, w in ((-2, 1), (-1, 2), (0, 3), (1, 2), (2, 1))) for i in range(36)]
    p1 = max(range(36), key=lambda i: sm[i])

    def centre(pk):            # weighted circular mean hue around a peak
        x = y = 0.0
        for k in range(-2, 3):
            i = (pk + k) % 36
            a = math.radians(i * 10 + 5)
            x += hist[i] * math.cos(a); y += hist[i] * math.sin(a)
        return math.degrees(math.atan2(y, x)) % 360

    far = [i for i in range(36) if min(abs(i - p1), 36 - abs(i - p1)) >= 5]
    p2 = max(far, key=lambda i: sm[i])
    h1 = centre(p1)
    if sm[p2] >= 0.10 * sm[p1]:
        h2 = centre(p2)
    else:                      # one-colour picture: partner = h1 rotated 100 deg towards violet (280)
        h2 = (h1 - 100) % 360 if ((280 - h1) % 360) > 180 else (h1 + 100) % 360
    total = sum(hist) / max(1, len(px))
    # 8-colour palette: chroma-weighted k-means in OKLab (colourful clusters win over large grey areas)
    pts = pts[::max(1, len(pts) // 4000)]
    wts = [0.15 + 8 * math.hypot(p[1], p[2]) for p in pts]
    cents = [max(pts, key=lambda p: math.hypot(p[1], p[2]))]
    while len(cents) < 8:                                   # farthest-point seeding
        cents.append(max(pts, key=lambda p: min(sum((p[q] - c[q]) ** 2 for q in range(3)) for c in cents)))
    for _ in range(12):
        acc = [[0.0, 0.0, 0.0, 0.0] for _ in cents]
        for p, wt in zip(pts, wts):
            j = min(range(len(cents)), key=lambda k: sum((p[q] - cents[k][q]) ** 2 for q in range(3)))
            a_ = acc[j]; a_[0] += p[0] * wt; a_[1] += p[1] * wt; a_[2] += p[2] * wt; a_[3] += wt
        cents = [(a_[0] / a_[3], a_[1] / a_[3], a_[2] / a_[3]) if a_[3] else cents[i] for i, a_ in enumerate(acc)]
    pal = []
    for L, a_, b_ in cents:
        C, h = math.hypot(a_, b_) * 1.15, math.degrees(math.atan2(b_, a_)) % 360
        pal.append((min(0.88, max(0.45, L)), C, h))
    d = ((h2 - h1 + 180) % 360) - 180
    def along(t):                       # position on the h1->h2 arc; neutrals go to the ends by lightness
        if t[1] < 0.04:
            return (-1 if t[0] < 0.6 else 2) + t[0] * 0.01
        return (((t[2] - h1 + 180) % 360) - 180) / (d or 1)
    pal.sort(key=along)
    return dict(h1=h1, h2=h2, colourfulness=total, palette=[hexc(oklch(*t)) for t in pal])


# ---------------------------------------------------------------- layout rules
def layout(cols, rows, aspect):
    H = min(rows - 4, H_MAX)           # T=0 pad + H logo rows + fastfetch's blank row + starship newline + 2 prompt rows
    while True:
        fig_h = H * CH - GLOW_TOP - GLOW_BOTTOM
        W = math.ceil((fig_h * aspect + 2 * GLOW_SIDE) / CW)
        avail = cols - 2 * MARGIN_MIN - W - GAP
        if avail >= PANEL_MIN or H <= H_MIN:
            break
        H -= 1
    Pw = max(PANEL_MIN, min(PANEL_MAX, avail))
    total = W + GAP + Pw
    # keep the composition at the left edge (not centred): the slot already carries
    # GLOW_SIDE/CW blank-ish cols on the left, so only top that up to MARGIN_MIN
    gs = GLOW_SIDE // CW
    ML = max(0, MARGIN_MIN - gs)
    return dict(H=H, W=W, Pw=Pw, ML=ML, spine=ML + W + GAP, value_w=Pw - (LABEL_W + 9) - 1)


# ---------------------------------------------------------------- logo with neon rim + bloom
def cut_fade(fw, fh, sides, n=96):
    """Alpha mask that fades the figure out towards every side the picture frame
    cut it on, deeper towards the corners, so the outline there becomes a soft
    curve instead of a straight (boxy) edge."""
    m = Image.new('L', (n, n))
    px = m.load()
    def ss(f):
        f = max(0.0, min(1.0, f)); return f * f * (3 - 2 * f)
    for j in range(n):
        v = (j + 0.5) / n                           # 0 top .. 1 bottom
        for i in range(n):
            u = (i + 0.5) / n                       # 0 left .. 1 right
            cu, cv = (2 * u - 1) ** 2, (2 * v - 1) ** 2
            k = 1.0
            sv = max(0.5 * cv, v ** 3)              # side fades: deepest towards the bottom corners
            if sides['bottom']: k *= ss((1 - v) / (0.07 + 0.42 * cu ** 1.5))
            if sides['top']:    k *= ss(v / (0.05 + 0.25 * cu ** 1.5))
            if sides['left']:   k *= ss(u / (0.06 + 0.38 * sv))
            if sides['right']:  k *= ss((1 - u) / (0.06 + 0.38 * sv))
            px[i, j] = int(255 * k)
    return m.resize((fw, fh), Image.BICUBIC)


def make_logo(img, W, H, gradient):
    SW, SH = W * CW, H * CH
    align = img.info.get('ff-align', '')            # per-picture placement, set by make-images.py
    sticker = img.info.get('ff-sticker') == '1'     # whole figure with a die-cut border
    bbox = img.getchannel('A').getbbox()
    img = img.crop(bbox)
    def coverage(line):
        d = line.get_flattened_data() if hasattr(line, 'get_flattened_data') else line.getdata()
        return sum(1 for v in d if v > 8) / max(line.size)
    sa = img.getchannel('A'); iw0, ih0 = sa.size
    dx, dy = max(2, iw0 // 100), max(2, ih0 // 100)     # look 1% inside each edge of the source
    cut = 2.0 if sticker else 0.12                 # die-cut stickers are whole figures: never "cut"
    sides = dict(top=coverage(sa.crop((0, dy, iw0, dy + 1))) > cut, bottom=coverage(sa.crop((0, ih0 - 1 - dy, iw0, ih0 - dy))) > cut,
                 left=coverage(sa.crop((dx, 0, dx + 1, ih0))) > cut, right=coverage(sa.crop((iw0 - 1 - dx, 0, iw0 - dx, ih0))) > cut)
    gb = 0 if sides['bottom'] else GLOW_BOTTOM     # whole figures (stickers) get glow room under the feet too
    iw, ih = SW - 2 * GLOW_SIDE, SH - GLOW_TOP - gb
    s = min(iw / img.width, ih / img.height)
    fw, fh = max(1, round(img.width * s)), max(1, round(img.height * s))
    fig = img.resize((fw, fh), Image.LANCZOS)
    if any(sides.values()):                        # round off where the frame cut the subject
        fig.putalpha(ImageChops.multiply(fig.getchannel('A'), cut_fade(fw, fh, sides)))
    x = SW - GLOW_SIDE - fw                        # hug the panel side (constant gap)
    y = SH - gb - fh                               # cut edge sits on the slot bottom; head gets the glow headroom
    if align == 'left-center':                     # left edge of the slot, centred top-to-bottom
        x, y = GLOW_SIDE, GLOW_TOP + (ih - fh) // 2
    canvas = Image.new('RGBA', (SW, SH))
    A = Image.new('L', (SW, SH)); A.paste(fig.getchannel('A'), (x, y))
    # cut-edge weight: no glow where the picture was cut by its frame (bottom, and any side the subject touches)
    w = Image.new('L', (SW, SH), 255)
    ramp = max(8, round(0.07 * fh))
    def ramp_img(length, horizontal, rising):
        # smoothstep ramp 0->255 over `ramp` px, as a 1-px strip stretched to the slot
        vals = []
        for i in range(length):
            f = max(0.0, min(1.0, i / ramp))
            vals.append(int(255 * f * f * (3 - 2 * f)))
        if not rising: vals = vals[::-1]
        strip = Image.new('L', (length, 1) if horizontal else (1, length))
        strip.putdata(vals)
        return strip.resize((length, SH) if horizontal else (SW, length))
    if sides['bottom']:
        r = Image.new('L', (SW, SH), 0); r.paste(ramp_img(fh, False, False), (0, y)); w = ImageChops.darker(w, r)
    if sides['top']:
        r = Image.new('L', (SW, SH), 0); r.paste(ramp_img(fh, False, True), (0, y)); w = ImageChops.darker(w, r)
    if sides['left']:
        r = Image.new('L', (SW, SH), 0); r.paste(ramp_img(fw, True, True), (x, 0)); w = ImageChops.darker(w, r)
    if sides['right']:
        r = Image.new('L', (SW, SH), 0); r.paste(ramp_img(fw, True, False), (x, 0)); w = ImageChops.darker(w, r)
    src = ImageChops.multiply(A, w)
    # colour field: vertical gradient top colour -> bottom colour (same as the panel spine)
    grad = Image.new('RGB', (1, SH))
    for yy in range(SH):
        grad.putpixel((0, yy), gradient(max(0.0, min(1.0, (yy - y) / max(1, fh)))))
    grad = grad.resize((SW, SH))
    bloom = src.filter(ImageFilter.GaussianBlur(max(6, round(GLOW_SIDE * 0.42)))).point(lambda v: min(255, int(v * 1.6)))
    halo = src.filter(ImageFilter.GaussianBlur(4)).point(lambda v: min(255, int(v * 1.6)))
    rim = ImageChops.subtract(src.filter(ImageFilter.MaxFilter(5)), A)          # 2 px outer stroke
    glowA = ImageChops.lighter(bloom.point(lambda v: min(255, int(v * 0.8))), halo.point(lambda v: int(v * 0.75)))
    glowA = ImageChops.lighter(glowA, rim.point(lambda v: int(v * 0.95)))
    # soft vignette on the glow at the slot edges, so it never ends in a straight (boxy) line
    def edge_fade(n, a, b):
        vals = []
        for i in range(n):
            f = min(1.0, i / a if a else 1.0, (n - 1 - i) / b if b else 1.0)
            f = max(0.0, f); vals.append(int(255 * f * f * (3 - 2 * f)))
        return vals
    fx = Image.new('L', (SW, 1)); fx.putdata(edge_fade(SW, max(1, round(GLOW_SIDE * GLOW_FEATHER)), max(1, round(GLOW_SIDE * GLOW_FEATHER))))
    fy = Image.new('L', (1, SH)); fy.putdata(edge_fade(SH, max(1, round(GLOW_TOP * GLOW_FEATHER)), round(gb * GLOW_FEATHER)))
    glowA = ImageChops.multiply(glowA, ImageChops.multiply(fx.resize((SW, SH)), fy.resize((SW, SH))))
    glow = grad.copy(); glow.putalpha(glowA)
    canvas.alpha_composite(glow)
    canvas.alpha_composite(fig, (x, y))
    return canvas, dict(fig_x=x, fig_y=y, fig_w=fw, fig_h=fh, cut=sides)


# ---------------------------------------------------------------- config
ICONS = dict(os=0xF08DB, kernel=0xF033D, de=0xF0379, wm=0xF05B2, theme=0xF027C, icons=0xF003B, cursor=0xF01C0,
             term=0xF018D, font=0xF0281, shell=0xF1183, pkgs=0xF03D6, cpu=0xF061A, gpu=0xF08AE, display=0xF108,
             ram=0xF035B, swap=0xF04E1, disk=0xF02CA, battery=0xF0079, uptime=0xF0150)


def kitty_font():
    fam, size = 'JetBrainsMono Nerd Font', '12.5'
    try:
        for line in open(os.path.expanduser('~/.config/kitty/kitty.conf')):
            p = line.split(None, 1)
            if len(p) == 2 and p[0] == 'font_family': fam = p[1].strip()
            if len(p) == 2 and p[0] == 'font_size': size = p[1].strip()
    except OSError:
        pass
    return fam, size


BAR_STYLE = os.environ.get('BAR', 'block')


def bar_cfg(track):
    """percentage bar (fastfetch display.bar); BAR_W cells including the caps"""
    if BAR_STYLE == 'capsule':          # Fira Code progress glyphs (in JetBrainsMono NF; kitty draws them natively)
        return {'width': BAR_W - 2, 'char': {'elapsed': '\uee04', 'total': '\uee01'},
                'border': {'left': '\uee00', 'leftElapsed': '\uee03', 'right': '\uee02', 'rightElapsed': '\uee05'},
                'color': {'total': hexc(track), 'border': hexc(track)}}
    ch = {'line': ('━', '━'), 'block': ('■', '■'), 'braille': ('⣿', '⣀')}[BAR_STYLE]
    return {'width': BAR_W, 'char': {'elapsed': ch[0], 'total': ch[1]}, 'border': None, 'color': {'total': hexc(track)}}


# 3x5 pixel font for the hero clock ('#' = lit)
FONT = {
    '0': ['###', '#.#', '#.#', '#.#', '###'], '1': ['.#.', '##.', '.#.', '.#.', '###'],
    '2': ['###', '..#', '###', '#..', '###'], '3': ['###', '..#', '.##', '..#', '###'],
    '4': ['#.#', '#.#', '###', '..#', '..#'], '5': ['###', '#..', '###', '..#', '###'],
    '6': ['###', '#..', '###', '#.#', '###'], '7': ['###', '..#', '.#.', '.#.', '.#.'],
    '8': ['###', '#.#', '###', '#.#', '###'], '9': ['###', '#.#', '###', '..#', '###'],
    ':': ['.', '#', '.', '#', '.'],
}


# 5x9 pixel font for the big hero clock
FONT_BIG = {
    '0': ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    '1': ['..#..', '.##..', '#.#..', '..#..', '..#..', '..#..', '..#..', '..#..', '#####'],
    '2': ['.###.', '#...#', '....#', '....#', '...#.', '..#..', '.#...', '#....', '#####'],
    '3': ['.###.', '#...#', '....#', '....#', '..##.', '....#', '....#', '#...#', '.###.'],
    '4': ['...#.', '..##.', '.#.#.', '#..#.', '#..#.', '#####', '...#.', '...#.', '...#.'],
    '5': ['#####', '#....', '#....', '####.', '....#', '....#', '....#', '#...#', '.###.'],
    '6': ['.###.', '#...#', '#....', '#....', '####.', '#...#', '#...#', '#...#', '.###.'],
    '7': ['#####', '....#', '....#', '...#.', '...#.', '..#..', '..#..', '..#..', '..#..'],
    '8': ['.###.', '#...#', '#...#', '#...#', '.###.', '#...#', '#...#', '#...#', '.###.'],
    '9': ['.###.', '#...#', '#...#', '#...#', '.####', '....#', '....#', '#...#', '.###.'],
    ':': ['.', '.', '#', '.', '.', '.', '#', '.', '.'],
}


def clock_rows(text, big, colour_at):
    """Render text as half-block pixel art (1 cell wide, 2 pixels tall per cell).
    small: 3x5 font + 1 blank pixel row on top = 3 cell rows.  big: 5x9 font + 1 blank row on top = 5 cell rows.
    colour_at(u) gives the colour at u in [0,1] across the width. Returns (rows as escape strings, width in cells)."""
    font = FONT_BIG if big else FONT
    glyphs = [font[ch] for ch in text]
    ph = len(glyphs[0])
    bitmap = []
    for y in range(ph):
        row = []
        for gi, g in enumerate(glyphs):
            row += [1 if c == '#' else 0 for c in g[y]]
            if gi < len(glyphs) - 1: row.append(0)
        bitmap.append(row)
    width = len(bitmap[0])
    pr = [[0] * width] + bitmap
    if len(pr) % 2: pr.append([0] * width)
    out = []
    for r in range(len(pr) // 2):
        top, bot = pr[2 * r], pr[2 * r + 1]
        line = ''
        for x in range(width):
            ch = {(1, 1): '█', (1, 0): '▀', (0, 1): '▄', (0, 0): ' '}[(top[x], bot[x])]
            line += (fg(colour_at(x / max(1, width - 1))) + ch) if ch != ' ' else ' '
        out.append(line)
    return out, width


def build(picture, cols, rows, out, now=None):
    import time
    now = now or time.localtime()
    img = Image.open(picture).convert('RGBA')
    bb = img.getchannel('A').getbbox()
    aspect = (bb[2] - bb[0]) / (bb[3] - bb[1])
    an = analyse_cached(picture, img)
    L = layout(cols, rows, aspect)
    H, W, Pw, s, Vw = L['H'], L['W'], L['Pw'], L['spine'], L['value_w']
    h1, h2 = an['h1'], an['h2']

    def hue(t): return hue_lerp(h1, h2, max(0.0, min(1.0, t)))
    def key_c(t):   return oklch(0.80, 0.135, hue(t))
    def spine_c(t): return oklch(0.68, 0.15, hue(t))
    def glow_c(t):  return oklch(0.70, 0.19, hue(t))
    def dim_c(t):   return oklch(0.60, 0.035, hue(t))
    def track_c(t): return oklch(0.30, 0.035, hue(t))
    def fade_c(t):  return oklch(0.24, 0.03, hue(t))
    def neon_c(t):  return oklch(0.82, 0.16, hue(t))

    logo, geo = make_logo(img, W, H, glow_c)

    # ------------------------------------------------ vertical plan (rows relative to the logo top)
    r_top = geo['fig_y'] // CH                       # header on the first row the figure occupies
    r_bot = H - 1                                    # footer on the last logo row (the cut edge)
    span = r_bot - r_top + 1
    sys_rows = ['os', 'kernel', 'de', 'wm', 'theme', 'icons', 'cursor', 'term', 'font', 'shell', 'pkgs']
    hw_rows = ['cpu', 'gpu', 'ram', 'disk', 'battery']
    hero = 3                                          # small clock; 5 = big clock; 0 = none (uptime goes to hw)
    spacers = [1, 1, 1, 1]                            # after head, after hero, between sections, before foot
    def need():
        return 1 + hero + 1 + len(sys_rows) + 1 + len(hw_rows) + 1 + sum(spacers) + (0 if hero else 1)
    while need() > span and sum(spacers):             # short windows: drop spacers, then the hero
        i = spacers.index(max(spacers)); spacers[i] -= 1
    if need() > span:
        hero = 0; spacers[1] = 0
    for victim in ('icons', 'cursor', 'theme', 'wm', 'font'):    # still too tall: drop the least useful rows
        if need() > span and victim in sys_rows: sys_rows.remove(victim)
    for name, after in (('display', 'gpu'), ('swap', 'ram')):
        if need() < span:
            hw_rows.insert(hw_rows.index(after) + 1, name)
    big_w = 4 * 5 + 1 + 4                                # big "HH:MM" width in cells (5x9 font)
    if hero and need() + 2 <= span and big_w + 3 + 16 <= Pw - 3:
        hero = 5
    i = 0
    while need() < span and min(spacers) < SPACER_MAX:
        if spacers[i % 4] < SPACER_MAX: spacers[i % 4] += 1
        i += 1
    leftover = span - need()
    r0 = r_top + max(0, leftover) // 2                # leftover rows: centre the panel on the figure
    seq = (['HEAD'] + ['SP'] * spacers[0] + ['HERO%d' % k for k in range(hero)] + ['SP'] * spacers[1] +
           ['SEC:SYSTEM:01'] + sys_rows + ['SP'] * spacers[2] + ['SEC:HARDWARE:02'] + hw_rows + ([] if hero else ['uptime']) +
           ['SP'] * spacers[3] + ['FOOT'])
    n = len(seq)
    end = s + Pw - 1                                  # last panel column (0-based, window-relative)

    def fade_rule(c0, c1, t, ch='━', start=None):
        """neon tube: bright at c0, fading towards the background at c1"""
        base_c = start or spine_c(t)
        return ''.join(fg(mix(base_c, fade_c(t), ((c - c0) / max(1, c1 - c0)) ** 0.8)) + ch for c in range(c0, c1 + 1))

    fam, fsize = kitty_font()
    D = '%s'                                          # placeholder for the row's dim colour
    # meters: bar(BAR_W) + ' ' + pct(4) + gap + 'used / total' (<= 21 cells) must fit in Vw
    SEP, SL = ('  %s', ' / ') if Vw >= BAR_W + 5 + 2 + 21 else (' %s', '/')
    vfmt = {
        'os': '{pretty-name:-%d}' % Vw,
        'kernel': '{sysname} {release:-%d}' % (Vw - 6),
        'de': '{pretty-name:-%d} {version}' % (Vw - 8),
        'wm': '{pretty-name:-%d} %s{protocol-name}' % (Vw - 10, D),
        'theme': '{theme1:-%d}' % Vw,
        'icons': '{icons1:-%d}' % Vw,
        'cursor': '{theme:-%d} %s{size}px' % (Vw - 6, D),
        'term': '{pretty-name:-%d} %s{version}' % (Vw - 10, D),
        'shell': '{pretty-name:-%d} %s{version}' % (Vw - 10, D),
        'pkgs': '{all} %srpm{?flatpak-all} · {flatpak-all} flatpak{?}' % D,
        'cpu': '{name:-%d} %s{cores-logical}t' % (Vw - 4, D),
        'gpu': '%s{vendor} \u001b[39m{name:-%d}' % (D, Vw - 8),
        'display': '{width}x{height} %s@ {refresh-rate} Hz' % D,
        'ram': ('{percentage-bar} {percentage}' + SEP + '{used}' + SL + '{total}') % D,
        'swap': ('{percentage-bar} {percentage}' + SEP + '{used}' + SL + '{total}') % D,
        'disk': ('{size-percentage-bar} {size-percentage}' + SEP + '{size-used}' + SL + '{size-total}') % D,
        'battery': '{capacity-bar} {capacity}  %s{status:-%d}' % (D, Vw - BAR_W - 7),
        'uptime': '{?days}{days}d {?}{hours}h {minutes}m',
    }
    mtype = dict(os='os', kernel='kernel', de='de', wm='wm', theme='theme', icons='icons', cursor='cursor',
                 term='terminal', shell='shell', pkgs='packages', cpu='cpu', gpu='gpu', display='display',
                 ram='memory', swap='swap', disk='disk', battery='battery', uptime='uptime')

    # hero clock (time of generation = launch time; the text next to it is live fastfetch data)
    hhmm = time.strftime('%H:%M', now)
    if hero:
        crow, cw = clock_rows(hhmm, hero == 5, lambda u: neon_c(0.0 + 0.45 * u))
        text_col = s + 3 + cw + 3
        text_rows = {3: [0, 1, 2], 5: [1, 2, 3]}[hero]

    modules = ['break'] * r0
    user = os.environ.get('USER') or 'user'
    host = os.uname().nodename.split('.')[0]
    for i, kind in enumerate(seq):
        t = i / max(1, n - 1)
        sc, kc, dc = spine_c(t), key_c(t), dim_c(t)
        lead = col(s) + fg(sc)
        if kind == 'SP':
            modules.append({'type': 'custom', 'format': lead + '┃'})
        elif kind == 'HEAD':
            c1, c2, t2 = oklch(0.80, 0.13, h1), oklch(0.36, 0.075, h1), oklch(0.90, 0.05, h1)
            pill = (fg(c1) + '' + bg(c1) + fg(BG) + BOLD + '  {user-name} ' + NOBOLD +
                    fg(c1) + bg(c2) + '' + fg(t2) + ' \U000f0322 {host-name} ' + BGRST + fg(c2) + '')
            pill_w = 1 + 3 + len(user) + 1 + 1 + 3 + len(host) + 1 + 1
            modules.append({'type': 'title', 'format': lead + '┏━' + pill + ' ' + fade_rule(s + 2 + pill_w + 1, end, t)})
        elif kind.startswith('HERO'):
            k = int(kind[4:])
            key = lead + '┃' + col(s + 3) + crow[k] + col(text_col)
            j = text_rows.index(k) if k in text_rows else -1
            if j == 0:
                modules.append({'type': 'datetime', 'key': key, 'format': BOLD + fg(neon_c(t)) + '{weekday}' + NOBOLD})
            elif j == 1:
                modules.append({'type': 'datetime', 'key': key, 'format': fg(FG) + '{day-in-month} {month-name} {year}'})
            elif j == 2:
                modules.append({'type': 'uptime', 'key': key, 'format': fg(dc) + 'up ' + fg(FG) + vfmt['uptime']})
            else:
                modules.append({'type': 'custom', 'format': key})
        elif kind.startswith('SEC:'):
            _, name, idx = kind.split(':')
            label = ' '.join(name)
            c0 = s + 4 + len(label) + 1
            rule = fade_rule(c0, end - 4, t, '─', start=mix(sc, fade_c(t), 0.35))
            modules.append({'type': 'custom', 'format': lead + '┣━━ ' + BOLD + fg(kc) + label + NOBOLD + ' ' + rule +
                                                         col(end - 1) + fg(dc) + idx})
        elif kind == 'FOOT':
            pal = [tuple(int(h[k:k + 2], 16) for k in (1, 3, 5)) for h in an['palette']]
            pill = fg(pal[0]) + '' + ''.join(bg(c) + '   ' for c in pal) + BGRST + fg(pal[-1]) + ''
            rule = fade_rule(s + 4 + 3 * len(pal) + 3, end, t)
            modules.append({'type': 'custom', 'format': lead + '┗━━ ' + pill + ' ' + rule})
        else:
            key = (lead + '┃' + col(s + 3) + fg(neon_c(t)) + chr(ICONS[kind]) + col(s + 6) + BOLD + fg(kc) + kind + NOBOLD +
                   col(s + 6 + LABEL_W + 3) + fg(FG))
            if kind == 'font':
                name = fam if len(fam) <= Vw - 7 else fam[:Vw - 8] + '…'
                modules.append({'type': 'custom', 'format': key + name + ' ' + fg(dc) + fsize + 'pt'})
                continue
            f = vfmt[kind]
            if '%s' in f: f = f % fg(dc)
            m = {'type': mtype[kind], 'key': key, 'format': f}
            if kind == 'gpu': m['hideType'] = 'integrated'
            if kind == 'disk': m['folders'] = '/'
            modules.append(m)
    cfg = {
        '$schema': 'https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json',
        'display': {
            'separator': '',
            'disableLinewrap': True,
            'key': {'width': 0},
            'size': {'ndigits': 1},
            'bar': bar_cfg(track_c(0.75)),
            'percent': {'type': ['bar', 'num', 'num-color', 'bar-monochrome'], 'ndigits': 0, 'width': 3,
                        'color': {'green': hexc(key_c(0.85)), 'yellow': '#F9C97C', 'red': '#FF4D6A'}},
        },
        'modules': modules,
    }
    with open(out + '.jsonc', 'w') as f:
        f.write('// d3 "neon/cyber" - generated by gen.py for %s at %dx%d (logo %dx%d cells, pad left %d right %d top 0)\n'
                % (os.path.basename(picture), cols, rows, W, H, L['ML'], GAP))
        json.dump(cfg, f, indent=1)
    meta = dict(L, seq=seq, r0=r0, spacers=spacers, hero=hero, leftover=leftover, accent=an, geo=geo, aspect=aspect,
                key_top=hexc(key_c(0)), key_bot=hexc(key_c(1)),
                contrast_key=round(min(contrast(key_c(x / 10), BG) for x in range(11)), 2),
                contrast_dim=round(contrast(dim_c(0.5), BG), 2), contrast_value=round(contrast(FG, BG), 2))
    meta['logo'] = logo
    return meta


if __name__ == '__main__':
    pic, c, r, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    m = build(pic, c, r, out)
    m['logo'].save(out + '-logo.png'); del m['logo']
    print(json.dumps({k: m[k] for k in ('H', 'W', 'Pw', 'ML', 'spine', 'value_w', 'r0', 'spacers', 'hero', 'leftover',
                                        'key_top', 'key_bot', 'contrast_key', 'contrast_dim')}))
    print(m['accent'])
