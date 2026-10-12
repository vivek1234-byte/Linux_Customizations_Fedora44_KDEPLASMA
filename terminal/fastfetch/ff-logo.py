#!/usr/bin/python3 -I
"""fastfetch picture logo for kitty: pictures come from a shuffled queue, play a
short intro effect, and double-clicking one switches it to the next picture
with a transition effect.

  ff-logo.py show        run fastfetch with the next picture in the queue
  ff-logo.py next <id>   switch picture <id> to the next one in the queue
                         (run by the kitty kitten ~/.config/kitty/ff_dclick.py)

Pictures: ~/.config/fastfetch/images/*.png (made by ff-images).
The picture is drawn with kitty's Unicode placeholders: the logo is a grid of
U+10EEEE cells whose foreground colour is the image id, so it scrolls like text
and can be swapped in place later by sending new image data for that id.
"""
import json
import math
import os
import random
import re
import select
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import design  # noqa: E402  (the panel + glow generator)
import base64
from PIL import Image, ImageChops, ImageFilter
import fcntl
import itertools
import struct
import termios
import time
from pathlib import Path

HOME = Path.home()
CFG = HOME / ".config/fastfetch"
IMAGES = CFG / "images"
STATE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state") / "ff-logo"
BLOCKS = STATE / "blocks"
TTYS = STATE / "ttys"
FPS = 48                 # animation frame rate
FRAMES = 16              # frames per transition (~0.33 s)
KEEP_IMAGES = 3          # pictures kept alive in kitty per terminal (older ones are freed)
TMP = "/tmp/tty-graphics-protocol-fflogo"
FRAME_NO = itertools.count(1)

# kitty's row/column diacritics (gen/rowcolumn-diacritics.txt): index = number
DIACRITICS = [
    0x0305, 0x030D, 0x030E, 0x0310, 0x0312, 0x033D, 0x033E, 0x033F, 0x0346, 0x034A,
    0x034B, 0x034C, 0x0350, 0x0351, 0x0352, 0x0357, 0x035B, 0x0363, 0x0364, 0x0365,
    0x0366, 0x0367, 0x0368, 0x0369, 0x036A, 0x036B, 0x036C, 0x036D, 0x036E, 0x036F,
    0x0483, 0x0484, 0x0485, 0x0486, 0x0487, 0x0592, 0x0593, 0x0594, 0x0595, 0x0597,
    0x0598, 0x0599, 0x059C, 0x059D, 0x059E, 0x059F, 0x05A0, 0x05A1, 0x05A8, 0x05A9,
    0x05AB, 0x05AC, 0x05AF, 0x05C4, 0x0610, 0x0611, 0x0612, 0x0613, 0x0614, 0x0615,
]


def window(fd):
    """(cols, rows, cell_w, cell_h) of the terminal on fd."""
    rows, cols, xpx, ypx = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))
    cw, ch = (xpx // cols, ypx // rows) if rows and cols and xpx and ypx else (10, 22)
    return cols or 80, rows or 24, cw, ch


def tmpfile_write(data):
    """Write a frame file kitty can read and delete (t=t): private, never follows links."""
    path = f"{TMP}-{os.getpid()}-{next(FRAME_NO)}.rgba"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def send(fd, ident, img, cols, rows):
    """Show `img` (RGBA, exactly the block's pixel size) as image `ident`."""
    path = tmpfile_write(img.tobytes())
    data = base64.standard_b64encode(path.encode()).decode()
    os.write(fd, (f"\033_Ga=t,t=t,f=32,s={img.width},v={img.height},i={ident},q=2;{data}\033\\"
                  f"\033_Ga=p,U=1,i={ident},p=1,c={cols},r={rows},q=2\033\\").encode())


def free(fd, ident):
    os.write(fd, f"\033_Ga=d,d=I,i={ident},q=2\033\\".encode())


def placeholder_rows(ident, cols, rows):
    """cols x rows grid of U+10EEEE cells, image id in the 24-bit foreground colour."""
    colour = f"\033[38;2;{ident >> 16 & 255};{ident >> 8 & 255};{ident & 255}m"
    cell = "\U0010EEEE"
    return ["\033[m" + colour + cell + chr(DIACRITICS[y]) + cell * (cols - 1) + "\033[39m" for y in range(rows)]


def play(fd, ident, frames, cols, rows, final):
    """Stream frames at FPS (timed against the start, so slow frames don't add up);
    whatever happens, the picture ends on `final`."""
    t0 = time.monotonic()
    try:
        for k, frame in enumerate(frames, 1):
            delay = t0 + k / FPS - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            send(fd, ident, frame, cols, rows)
    finally:
        send(fd, ident, final, cols, rows)


# ---------------------------------------------------------------- state

def next_picture(exclude=None):
    """Next picture of a shuffled queue shared by all terminals: every picture
    is shown once before any repeats, never the same one twice in a row."""
    pics = sorted(str(p) for p in IMAGES.glob("*.png"))
    if not pics:
        return None
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "queue.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            q = json.loads((STATE / "queue.json").read_text())
        except (OSError, ValueError):
            q = {}
        order, pos, last = q.get("order", []), q.get("pos", 0), q.get("last")
        if sorted(order) != pics:
            order, pos = [], 0
        pick = None
        for _ in range(2):
            if pos >= len(order):
                order = random.sample(pics, len(pics))
                pos = 0
                if len(order) > 1 and order[0] == last:
                    order.append(order.pop(0))
            pick = order[pos]
            pos += 1
            last = pick
            if pick != exclude or len(pics) == 1:
                break
        (STATE / "queue.json").write_text(json.dumps({"order": order, "pos": pos, "last": pick}))
    return pick


def current_picture():
    """The picture shown last (for redraws after a resize or `clear`)."""
    try:
        last = json.loads((STATE / "queue.json").read_text()).get("last")
    except (OSError, ValueError):
        return None
    return last if last and os.path.exists(last) else None


def save_block(ident, **info):
    BLOCKS.mkdir(parents=True, exist_ok=True)
    (BLOCKS / f"{ident}.json").write_text(json.dumps(info))


def load_block(ident):
    return json.loads((BLOCKS / f"{ident}.json").read_text())


def remember_image(fd, tty, ident):
    """Keep at most KEEP_IMAGES pictures alive per terminal; free older ones in kitty."""
    TTYS.mkdir(parents=True, exist_ok=True)
    f = TTYS / tty.replace("/", "_")
    try:
        ids = json.loads(f.read_text())
    except (OSError, ValueError):
        ids = []
    ids.append(ident)
    for old in ids[:-KEEP_IMAGES]:
        free(fd, old)
        for suffix in (".json", ".lock", ".pending"):
            (BLOCKS / f"{old}{suffix}").unlink(missing_ok=True)
    f.write_text(json.dumps(ids[-KEEP_IMAGES:]))


def cleanup():
    import glob
    now = time.time()
    for p in glob.glob(TMP + "-*"):                      # frames kitty never read
        try:
            if now - os.path.getmtime(p) > 30:
                os.unlink(p)
        except OSError:
            pass
    for p in list(BLOCKS.glob("*")) + list(TTYS.glob("*")) + list(STATE.glob("gen-*")):
        if True:                                         # long gone terminals / pictures
            try:
                if now - p.stat().st_mtime > 14 * 86400:
                    p.unlink()
            except OSError:
                pass

# ---------------------------------------------------------------- effects





def ease(t):
    return t * t * (3 - 2 * t)


def ease_out(t):
    return 1 - (1 - t) ** 3


def blank(size):
    return Image.new("RGBA", size)


def faded(img, f):
    if f >= 1:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * max(f, 0) + 0.5)))
    return out


def put(canvas, img, x=0, y=0):
    """alpha_composite that allows negative / out-of-range offsets."""
    sx, sy, dx, dy = max(0, -x), max(0, -y), max(0, x), max(0, y)
    w, h = min(img.width - sx, canvas.width - dx), min(img.height - sy, canvas.height - dy)
    if w > 0 and h > 0:
        canvas.alpha_composite(img, (dx, dy), (sx, sy, sx + w, sy + h))


def is_blank(img):
    return img.getchannel("A").getbbox() is None


def mix(b, a, mask):
    """Image.composite in premultiplied alpha (no dark fringes from transparent pixels)."""
    return Image.composite(b.convert("RGBa"), a.convert("RGBa"), mask).convert("RGBA")


def tinted(alpha, colour, k=1.0):
    """Solid `colour` layer shaped by an alpha mask (scaled by k)."""
    layer = Image.new("RGBA", alpha.size, colour + (255,))
    layer.putalpha(alpha if k >= 1 else alpha.point(lambda v: int(v * k)))
    return layer


def fx_fade(a, b, n, accent):
    """crossfade while the new picture rises into place"""
    for i in range(1, n + 1):
        if i == n:
            yield b
            break
        t = ease(i / n)
        c = blank(a.size)
        put(c, faded(a, 1 - t))
        put(c, faded(b, t), 0, round(a.height * 0.035 * (1 - t)))
        yield c


def fx_slide(a, b, n, accent):
    """old picture slides out, new one slides in"""
    d, W = random.choice((-1, 1)), a.width
    for i in range(1, n + 1):
        if i == n:
            yield b
            break
        t = ease(i / n)
        c = blank(a.size)
        put(c, faded(a, 1 - t), round(-d * W * 0.45 * t))
        put(c, faded(b, t), round(d * W * 0.45 * (1 - t)))
        yield c


def fx_zoom(a, b, n, accent):
    """old picture swells and fades, new one zooms in from smaller"""
    W, H = a.size

    def scaled(img, s):
        w, h = max(1, round(W * s)), max(1, round(H * s))
        return img.resize((w, h), Image.BILINEAR), (W - w) // 2, round((H - h) * 0.3)

    for i in range(1, n + 1):
        t = ease(i / n)
        c = blank(a.size)
        if t < 1:
            im, x, y = scaled(a, 1 + 0.1 * t)
            put(c, faded(im, 1 - t), x, y)
            im, x, y = scaled(b, 0.9 + 0.1 * t)
            put(c, faded(im, t), x, y)
        else:
            c = b
        yield c


def fx_pixel(a, b, n, accent):
    """pixelate the old picture, then sharpen the new one out of the blocks"""
    W, H = a.size
    steps = [(a, k) for k in range(1, n // 2 + 1)] if not is_blank(a) else []
    rest = n - len(steps)
    steps += [(b, rest - k) for k in range(1, rest + 1)]
    half = max(1, n // 2)
    for src, k in steps:
        block = max(1, round(1 + 22 * ease(min(1, k / half))))
        if block == 1:
            yield src
            continue
        small = src.resize((max(1, W // block), max(1, H // block)), Image.BOX)
        yield small.resize((W, H), Image.NEAREST)


def fx_wipe(a, b, n, accent):
    """glowing scan line sweeps down and reveals the new picture"""
    W, H = a.size
    soft = max(1, H // 16)
    union = ImageChops.lighter(a.getchannel("A"), b.getchannel("A"))
    glow = union.filter(ImageFilter.GaussianBlur(3))
    for i in range(1, n + 1):
        pos = round(-soft + (H + 2 * soft) * ease(i / n))
        if i == n:
            yield b
            break
        col = Image.new("L", (1, H))
        col.putdata([max(0, min(255, round(255 * (pos - y) / soft + 128))) for y in range(H)])
        c = mix(b, a, col.resize((W, H), Image.NEAREST))
        band = Image.new("L", (1, H))
        band.putdata([max(0, 255 - abs(pos - y) * 255 // 5) for y in range(H)])
        line = ImageChops.multiply(band.resize((W, H), Image.NEAREST), glow)
        put(c, tinted(line, accent))
        put(c, tinted(ImageChops.multiply(band.resize((W, H), Image.NEAREST), union), (255, 255, 255), 0.55))
        yield c


def fx_glitch(a, b, n, accent):
    """digital glitch: sliced, shifted, tinted bands and RGB split"""
    W, H = a.size
    zero = Image.new("L", (W, H))
    tints = [(0.35, 1.0, 1.0), (1.0, 0.3, 1.0), (1.0, 1.0, 0.4)]
    for i in range(1, n):
        t = i / n
        base, other = (a, b) if t < 0.5 else (b, a)
        if is_blank(base):
            base, other = other, base
        frame = base.copy()
        for _ in range(random.randint(3, 8)):
            y = random.randrange(H)
            h = random.randint(H // 60, H // 11)
            band = (other if random.random() < 0.35 else base).crop((0, y, W, min(H, y + h)))
            if random.random() < 0.6:
                m = random.choice(tints)
                r, g, bl, al = band.split()
                band = Image.merge("RGBA", [ch.point(lambda v, k=k: int(v * k)) for ch, k in
                                            zip((r, g, bl), m)] + [al])
            frame.paste(Image.new("RGBA", band.size), (0, y))
            put(frame, band, random.randint(-W // 9, W // 9), y)
        d = max(1, round(W * 0.022 * (1 - abs(t - 0.5) * 1.4)))
        r, g, bl, al = frame.split()
        split = blank(a.size)
        put(split, faded(Image.merge("RGBA", (r, zero, zero, al)), 0.8), -d)
        put(split, faded(Image.merge("RGBA", (zero, zero, bl, al)), 0.8), d)
        put(split, frame)
        yield split
    yield b


def _noise(size, seed):
    rnd = random.Random(seed)
    w, h = max(2, size[0] // 24), max(2, size[1] // 24)
    small = Image.new("L", (w, h))
    small.putdata([rnd.randrange(256) for _ in range(w * h)])
    big = small.resize(size, Image.BICUBIC)
    fine = Image.new("L", (max(2, size[0] // 4), max(2, size[1] // 4)))
    fine.putdata([rnd.randrange(256) for _ in range(fine.width * fine.height)])
    return Image.blend(big, fine.resize(size, Image.BILINEAR), 0.25)


def fx_dissolve(a, b, n, accent):
    """ember burn: the old picture burns away through smooth noise with a glowing
    edge, then the new one burns in the same way"""
    noise = _noise(a.size, random.random())
    stages = ([(a, False, k) for k in range(1, n // 2 + 1)] if not is_blank(a) else [])
    rest = n - len(stages)
    stages += [(b, True, k / rest) for k in range(1, rest + 1)]
    half = max(1, n // 2)
    for src, appear, k in stages:
        t = k if appear else k / half
        if appear and t >= 1:
            yield b
            break
        thr = -30 + 310 * ease(t)
        if appear:                                   # visible where noise < thr
            mask = noise.point(lambda v: max(0, min(255, int((thr - v) * 9))))
        else:                                        # gone where noise < thr
            mask = noise.point(lambda v: max(0, min(255, int((v - thr) * 9))))
        edge = noise.point(lambda v: max(0, 255 - int(abs(thr - v) * 16)))
        alpha = src.getchannel("A")
        c = src.copy()
        c.putalpha(ImageChops.multiply(alpha, mask))
        rim = ImageChops.multiply(edge, alpha)
        put(c, tinted(rim.filter(ImageFilter.GaussianBlur(3)), accent))
        put(c, tinted(rim, (255, 244, 228), 0.75))
        yield c


def sheen(img, n, accent):
    """a soft diagonal light sweep across the subject (played after intros)"""
    W, H = img.size
    alpha = img.getchannel("A")
    bw = max(8, W // 4)
    col = Image.new("L", (bw, 1))
    col.putdata([int(170 * max(0.0, 1 - abs(2 * x / (bw - 1) - 1)) ** 2) for x in range(bw)])
    stripe = col.resize((bw, H * 2), Image.NEAREST).rotate(-20, expand=True, resample=Image.BILINEAR)
    for i in range(1, n + 1):
        if i == n:
            yield img
            break
        x = round(-stripe.width + (W + stripe.width) * ease(i / n))
        band = Image.new("L", (W, H))
        band.paste(stripe, (x, (H - stripe.height) // 2))
        c = img.copy()
        put(c, tinted(ImageChops.multiply(band, alpha), (255, 250, 245), 0.85))
        yield c


def _soft(img, r):
    """fast big blur: blur at half size, scale back up"""
    if r < 1:
        return img
    w, h = img.size
    small = img.convert("RGBa").resize((max(1, w // 2), max(1, h // 2)), Image.BILINEAR)
    return small.filter(ImageFilter.GaussianBlur(r / 2)).resize((w, h), Image.BILINEAR).convert("RGBA")


def fx_bloom(a, b, n, accent):
    """dreamy bloom: the old picture melts into a soft glow of the accent colour,
    the new one comes into focus out of it"""
    intro = is_blank(a)
    for i in range(1, n + 1):
        if i == n:
            yield b
            break
        t = i / n
        k = 1 - abs(2 * t - 1)                       # 0 -> 1 -> 0, peak in the middle
        src = a if t < 0.5 else b
        c = _soft(src, 18 * ease(k))
        alpha = c.getchannel("A")
        put(c, tinted(_soft(src, 26).getchannel("A"), accent, 0.55 * k))
        put(c, tinted(alpha, (255, 246, 250), 0.35 * k))
        yield faded(c, t) if intro else faded(c, 1 - 0.3 * k)


def _star(size):
    """4-point twinkle (L mask), `size` px wide"""
    s = max(3, size | 1)
    m = Image.new("L", (s, s))
    c = s // 2
    px = m.load()
    for y in range(s):
        for x in range(s):
            dx, dy = abs(x - c) / c, abs(y - c) / c
            v = max(0.0, 1 - (dx * 6 + dy) ** 0.8, 1 - (dy * 6 + dx) ** 0.8, 1 - math.hypot(dx, dy) * 2.2)
            px[x, y] = int(255 * min(1.0, v))
    return m


def fx_sparkle(a, b, n, accent):
    """crossfade under a shower of twinkling stars along the picture's outline"""
    W, H = a.size
    union = ImageChops.lighter(a.getchannel("A"), b.getchannel("A"))
    edge = ImageChops.subtract(union.filter(ImageFilter.MaxFilter(9)), union.filter(ImageFilter.MinFilter(9)))
    pts = [(x, y) for y in range(0, H, 6) for x in range(0, W, 6) if edge.getpixel((x, y)) > 60]
    if not pts:
        pts = [(random.randrange(W), random.randrange(H)) for _ in range(40)]
    rnd = random.Random()
    stars = [(*rnd.choice(pts), rnd.uniform(0, 0.7), rnd.randint(max(15, W // 18), max(25, W // 8)),
              rnd.random() < 0.4) for _ in range(34)]
    shapes = {}
    for i in range(1, n + 1):
        if i == n:
            yield b
            break
        t = ease(i / n)
        c = blank(a.size)
        put(c, faded(a, 1 - t))
        put(c, faded(b, t))
        for x, y, start, size, white in stars:
            u = (i / n - start) / 0.3                  # each star lives 30% of the effect
            if not 0 < u < 1:
                continue
            k = math.sin(math.pi * u)
            sz = max(3, round(size * (0.4 + 0.6 * k)))
            if sz not in shapes:
                shapes[sz] = _star(sz)
            m = shapes[sz].point(lambda v, k=k: int(v * k))
            put(c, tinted(m, (255, 255, 255) if white else accent), x - sz // 2, y - sz // 2)
        yield c


EFFECTS = [fx_fade, fx_slide, fx_zoom, fx_pixel, fx_wipe, fx_glitch, fx_dissolve, fx_bloom, fx_sparkle]
INTROS = [fx_fade]      # new terminal: a clean, gentle fade-in only (no glitchy intros)


def next_effect(pool, name):
    """Effects take turns: a shuffled rotation (all of them before any repeats,
    never the same one twice in a row), shared by all terminals."""
    STATE.mkdir(parents=True, exist_ok=True)
    names = [f.__name__ for f in pool]
    with open(STATE / "queue.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            q = json.loads((STATE / f"{name}.json").read_text())
        except (OSError, ValueError):
            q = {}
        order, pos, last = q.get("order", []), q.get("pos", 0), q.get("last")
        if sorted(order) != sorted(names) or pos >= len(order):
            order, pos = random.sample(names, len(names)), 0
            if len(order) > 1 and order[0] == last:
                order.append(order.pop(0))
        pick = order[pos]
        (STATE / f"{name}.json").write_text(json.dumps({"order": order, "pos": pos + 1, "last": pick}))
    return pool[names.index(pick)]


# ---------------------------------------------------------------- layout

LOGO_COLS, LOGO_ROWS = 48, 33   # largest logo area; the info box sits at fixed columns after it
INFO_ROWS = 22                  # rows of the info block without the leading breaks


def fit(path, W, H):
    """Picture scaled to fit W x H: at the top, centred left/right."""
    img = Image.open(path).convert("RGBA")
    s = min(W / img.width, H / img.height)
    w, h = max(1, round(img.width * s)), max(1, round(img.height * s))
    canvas = Image.new("RGBA", (W, H))
    canvas.paste(img.resize((w, h), Image.LANCZOS), ((W - w) // 2, 0))
    return canvas


# ---------------------------------------------------------------- commands

def show():
    fd = sys.stdout.fileno()
    fastfetch = ["fastfetch", "-c", str(CFG / "config.jsonc")]
    try:
        same = os.environ.get("FF_SAME") == "1"        # resize/clear redraw: keep the picture, no intro
        pic = (current_picture() if same else None) or (next_picture() if os.isatty(fd) else None)
        if pic is None:
            raise FileNotFoundError("no pictures")
        cleanup()
        win_cols, win_rows, cw, ch = window(fd)
        design.set_cells(cw, ch)
        ident = random.randrange(1 << 16, 1 << 24)    # 24-bit id = the cells' colour
        STATE.mkdir(parents=True, exist_ok=True)
        meta = design.build(pic, win_cols, win_rows, str(STATE / f"gen-{ident}"))
        cols, rows, final = meta["W"], meta["H"], meta["logo"]
        h1, h2 = meta["accent"]["h1"], meta["accent"]["h2"]
        accent = design.oklch(0.82, 0.16, h1)
        intro = iter(()) if same else next_effect(INTROS, "intros")(blank(final.size), final, FRAMES, accent)
        first = next(intro, final)
        tty = os.ttyname(fd)
        save_block(ident, tty=tty, picture=pic, cols=cols, rows=rows, h1=h1, h2=h2)
        remember_image(fd, tty, ident)
        send(fd, ident, first, cols, rows)             # image exists before its cells
        fastfetch = ["fastfetch", "-c", str(STATE / f"gen-{ident}.jsonc"),
                     "--logo-padding-left", str(meta["ML"]), "--logo-padding-right", str(design.GAP),
                     "--logo-padding-top", "0"]
    except Exception:
        os.execvp(fastfetch[0], fastfetch)             # plain braille logo instead
    parent = os.getpid()
    try:
        child = os.fork()
    except OSError:
        child = -1
        send(fd, ident, final, cols, rows)
    if child == 0:
        # child: play the intro once fastfetch has finished printing (the shell
        # is then idle at its prompt, so the escape codes can't interleave)
        try:
            os.setsid()
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, 2)
            try:
                pidfd = os.pidfd_open(parent)
                select.select([pidfd], [], [], 10)
            except OSError:
                pass
            with open(BLOCKS / f"{ident}.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                play(fd, ident, intro, cols, rows, final)
        finally:
            os._exit(0)
    # become fastfetch, so its parent stays the shell (for its shell/terminal lines)
    os.execvp(fastfetch[0], fastfetch + [
        "--logo-type", "data-raw", "--logo", "\n".join(placeholder_rows(ident, cols, rows)),
        "--logo-width", str(cols), "--logo-height", str(rows)])


def next_(arg):
    ident = int(arg)
    if not 0 < ident < 1 << 24 or not (BLOCKS / f"{ident}.json").exists():
        return
    pending = BLOCKS / f"{ident}.pending"
    lock = open(BLOCKS / f"{ident}.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        pending.touch()                                # at most one queued switch
        return
    while True:
        pending.unlink(missing_ok=True)
        block = load_block(ident)
        tty = block["tty"]
        if not re.fullmatch(r"/dev/pts/\d+", tty) or os.stat(tty).st_uid != os.getuid():
            return
        fd = os.open(tty, os.O_WRONLY | os.O_NOCTTY)
        _, _, cw, ch = window(fd)
        cols, rows = block.get("cols", LOGO_COLS), block.get("rows", LOGO_ROWS)
        W, H = cols * cw, rows * ch
        cur = block["picture"]
        h1, h2 = block.get("h1", 330), block.get("h2", 280)
        design.set_cells(cw, ch)
        old = design.logo_for(cur, cols, rows, h1, h2) if os.path.exists(cur) else blank((W, H))
        new = next_picture(exclude=cur)
        if new is None:
            return
        target = design.logo_for(new, cols, rows, h1, h2)
        play(fd, ident, next_effect(EFFECTS, "effects")(old, target, FRAMES, design.oklch(0.82, 0.16, h1)), cols, rows, target)
        save_block(ident, tty=tty, picture=new, cols=cols, rows=rows, h1=h1, h2=h2)
        os.close(fd)
        if not pending.exists():
            break
    cleanup()


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["show"]:
        show()
    elif cmd == ["next"] and len(sys.argv) == 3:
        next_(sys.argv[2])
    else:
        sys.exit(__doc__)
