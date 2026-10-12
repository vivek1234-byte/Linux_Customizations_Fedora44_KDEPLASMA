#!@HOME@/.local/share/ff-tools/venv/bin/python -I
"""Enhance + cut out pictures for the fastfetch logo.

  ~/Pictures/ff/*.jpg|png|webp  ->  ~/.config/fastfetch/images/<name>.png

  1. Real-ESRGAN x4plus-anime (GPU, Vulkan): 4x upscale, cleans JPEG noise
  2. isnet-anime (onnxruntime): background -> transparent
  3. gentle colour/contrast boost, soft fade where the picture frame cuts the
     character, trim the empty margins (ff-logo.py fits it into the logo box)
  4. white die-cut sticker border (whole figures)

per-picture hints, ~/Pictures/ff/<name>.json (all optional):
  "erase" / "erase_black"   polygons to remove (see apply_hints)
  "border": false           no sticker border (bust shots cut by the frame)
  "strip_border": true      drop the source's own white border first (we draw a clean one)
  "keep_all": true          keep small separate parts (e.g. brush lettering)
  "align": "left-center"    placement in the logo slot (design.py)

usage: ff-images            process new/changed pictures only
       ff-images --force    redo everything
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cutout  # noqa: E402

HOME = Path.home()
TOOLS = HOME / ".local/share/ff-tools"
ESRGAN = TOOLS / "realesrgan/realesrgan-ncnn-vulkan"
MODEL = TOOLS / "models/isnet-anime.onnx"
SRC = HOME / "Pictures/ff"
OUT = HOME / ".config/fastfetch/images"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

WORK_H = 1400   # px, working height after the x4 upscale (cutout.py is tuned for it)
MAX_H = 1400    # px, plenty for a ~33-row logo while keeping files small
SIZE = 1024     # isnet-anime input size


def upscale(src: Path, dst: Path):
    subprocess.run([str(ESRGAN), "-i", str(src), "-o", str(dst),
                    "-n", "realesrgan-x4plus-anime", "-s", "4",
                    "-m", str(ESRGAN.parent / "models")],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def predict_mask(sess, img: Image.Image) -> np.ndarray:
    """Foreground probability 0..1 at the image's own size (letterboxed like training)."""
    w0, h0 = img.size
    if h0 >= w0:
        h, w = SIZE, max(1, round(SIZE * w0 / h0))
    else:
        w, h = SIZE, max(1, round(SIZE * h0 / w0))
    top, left = (SIZE - h) // 2, (SIZE - w) // 2
    x = np.zeros((SIZE, SIZE, 3), np.float32)
    x[top:top + h, left:left + w] = np.asarray(img.resize((w, h), Image.LANCZOS), np.float32) / 255
    pred = sess.run(None, {"img": x.transpose(2, 0, 1)[None]})[0][0, 0]
    pred = np.clip(pred[top:top + h, left:left + w], 0, 1)
    m = Image.fromarray((pred * 255).astype(np.uint8)).resize((w0, h0), Image.LANCZOS)
    return np.asarray(m, np.float32) / 255


def box_blur(x: np.ndarray, r: int) -> np.ndarray:
    """Separable box blur (edge-clamped) for HxW or HxWxC float arrays."""
    for axis in (0, 1):
        pad = [(0, 0)] * x.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(x, pad, mode="edge"), axis=axis)
        n = x.shape[axis]
        x = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
             - np.take(c, np.arange(n), axis=axis)) / (2 * r + 1)
    return x


def keep_main(a: np.ndarray, s: int = 4, min_part: float = 0.03) -> np.ndarray:
    """Drop small floating bits (specks, glitch bars, watermarks): keep only
    connected parts that are at least `min_part` of the biggest one."""
    h, w = a.shape
    hs, ws = h // s, w // s
    # max-pool so thin hair strands stay connected
    fg = a[:hs * s, :ws * s].reshape(hs, s, ws, s).max(axis=(1, 3)) > 0.5
    lab = np.where(fg, np.arange(fg.size).reshape(fg.shape) + 1, 0)
    while True:                                   # label = max index in component
        m = lab.copy()
        m[1:] = np.maximum(m[1:], lab[:-1])
        m[:-1] = np.maximum(m[:-1], lab[1:])
        m[:, 1:] = np.maximum(m[:, 1:], lab[:, :-1])
        m[:, :-1] = np.maximum(m[:, :-1], lab[:, 1:])
        m = np.where(fg, m, 0)
        if np.array_equal(m, lab):
            break
        lab = m
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    if len(ids) <= 1:
        return a
    keep = np.isin(lab, ids[counts >= counts.max() * min_part])
    keep = np.repeat(np.repeat(keep, s, 0), s, 1)
    full = np.zeros_like(a, dtype=bool)
    full[:hs * s, :ws * s] = keep
    full = box_blur(full.astype(np.float32), 2 * s) > 0   # grow a little: keep soft edges
    return a * full


def fade_cut_edges(a: np.ndarray, frac: float = 0.06) -> np.ndarray:
    """Where the subject runs into the picture frame (bust cut at the bottom,
    head cut at the top ...) fade it out softly instead of a hard straight edge."""
    h, w = a.shape
    out = a.copy()
    for side, edge in (("top", a[0]), ("bottom", a[-1]), ("left", a[:, 0]), ("right", a[:, -1])):
        if (edge > 0.5).mean() < 0.03:
            continue                              # subject doesn't touch this side
        n = max(2, int((h if side in ("top", "bottom") else w) * frac))
        t = (np.arange(n) + 0.5) / n
        ramp = t * t * (3 - 2 * t)                # smoothstep 0 -> 1
        if side == "top":
            out[:n] *= ramp[:, None]
        elif side == "bottom":
            out[-n:] *= ramp[::-1, None]
        elif side == "left":
            out[:, :n] *= ramp[None, :]
        else:
            out[:, -n:] *= ramp[None, ::-1]
    return out


def defringe(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Give half-transparent edge pixels the colour of the nearby solid subject,
    so no halo of the old background shows against the terminal."""
    solid = (a > 0.97).astype(np.float32)
    out = rgb.copy()
    todo = solid < 1
    for r in (3, 10, 30):
        wsum = box_blur(solid, r)
        csum = box_blur(rgb * solid[..., None], r)
        ok = todo & (wsum > 1e-3)
        out[ok] = csum[ok] / wsum[ok][:, None]
        todo &= ~ok
    return out


def apply_hints(src: Path, a: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """Optional ~/Pictures/ff/<name>.json, polygons in fractions of the picture size,
    for things the model keeps by mistake:
      "erase":       [[[x, y], ...], ...]  remove everything inside
      "erase_black": [[[x, y], ...], ...]  remove only black/grey ink inside (e.g.
                                           brush lettering touching coloured hair)"""
    hints = src.with_suffix(".json")
    if not hints.exists():
        return a
    h, w = a.shape
    data = json.loads(hints.read_text())

    def region(key, soft):
        m = Image.new("L", (w, h), 0)
        for poly in data.get(key, []):
            ImageDraw.Draw(m).polygon([(x * w, y * h) for x, y in poly], fill=255)
        return np.asarray(m.filter(ImageFilter.GaussianBlur(soft)), np.float32) / 255

    a = a * (1 - region("erase", 4))
    if data.get("erase_black"):
        hi, lo = rgb.max(axis=2), rgb.min(axis=2)
        ink = np.clip((190 - hi) / 40, 0, 1) * np.clip((40 - (hi - lo)) / 15, 0, 1)
        ink = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)),
                         np.float32) / 255
        a = a * (1 - region("erase_black", 1) * ink)
    return a


def strip_border(a: np.ndarray, rgb: np.ndarray, steps: int = 90) -> np.ndarray:
    """Remove a white sticker border that is already in the source picture: grow
    from the transparent outside through near-white pixels only, so it stops at
    the character's dark outline (white hair inside the outline is kept)."""
    hi, lo = rgb.max(axis=2), rgb.min(axis=2)
    white = (lo > 185) & (hi - lo < 40)
    reach = a < 0.5
    passable = reach | white
    for _ in range(steps):
        g = reach.copy()
        g[1:] |= reach[:-1]; g[:-1] |= reach[1:]
        g[:, 1:] |= reach[:, :-1]; g[:, :-1] |= reach[:, 1:]
        g &= passable
        if np.array_equal(g, reach):
            break
        reach = g
    gone = box_blur(reach.astype(np.float32), 1) > 0.5     # eat the anti-aliased rim too
    return a * ~gone


def hint(src: Path, key: str, default):
    h = src.with_suffix(".json")
    return json.loads(h.read_text()).get(key, default) if h.exists() else default


def sticker(img: Image.Image, frac: float = 0.024) -> Image.Image:
    """Die-cut sticker look: a smooth, rounded white border around the whole
    figure (small gaps and loose bits get bridged like a real cut line)."""
    r = max(6, round(max(img.size) * frac))
    pad = 2 * r
    w, h = img.width + 2 * pad, img.height + 2 * pad
    a = np.zeros((h, w), np.float32)
    a[pad:pad + img.height, pad:pad + img.width] = np.asarray(img.getchannel("A"), np.float32) / 255
    solid = (a > 0.4).astype(np.float32)
    d = solid
    for _ in range(3):                            # ~gaussian of sigma ~r/2: round dilation
        d = box_blur(d, max(1, r // 2))
    edge = np.clip((d - 0.035) / 0.05, 0, 1)      # threshold low = grow by ~r, antialiased
    edge = edge * edge * (3 - 2 * edge)
    border = np.dstack([np.full((h, w, 3), (250, 248, 252), np.float32), edge * 255])
    out = Image.fromarray(border.astype(np.uint8), "RGBA")
    out.alpha_composite(img, (pad, pad))
    return out


def process(src: Path, dst: Path, sess):
    with tempfile.TemporaryDirectory() as tmp:
        up = Path(tmp) / "up.png"
        upscale(src, up)
        big = Image.open(up)
        big.load()
    if big.height > WORK_H:                            # hi-res sources: keep the work size sane
        big = big.resize((round(big.width * WORK_H / big.height), WORK_H), Image.LANCZOS)
    rgb_img = big.convert("RGB")

    out = cutout.cutout(rgb_img, predict_mask(sess, rgb_img), sess)
    a = np.asarray(out.getchannel("A"), np.float32) / 255
    if big.mode in ("RGBA", "LA", "PA"):              # keep any existing transparency
        a = np.minimum(a, np.asarray(big.getchannel("A"), np.float32) / 255)
    a = apply_hints(src, a, np.asarray(rgb_img, np.float32))
    if hint(src, "strip_border", False):          # source already had a (messy) sticker border
        a = strip_border(a, np.asarray(rgb_img, np.float32))
    if not hint(src, "keep_all", False):          # keep_all: lettering etc. made of small separate parts
        a = keep_main(a)
    rgb = np.asarray(ImageEnhance.Color(out.convert("RGB")).enhance(1.08), np.float32)

    rgba = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")

    # trim only the empty (transparent) margins, nothing visible is cut
    ys, xs = np.nonzero(rgba[..., 3] > 10)
    img = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    if hint(src, "border", True):
        img = sticker(img)
        ys, xs = np.nonzero(np.asarray(img.getchannel("A")) > 10)
        img = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    if img.height > MAX_H:
        img = img.resize((round(img.width * MAX_H / img.height), MAX_H), Image.LANCZOS)
    meta = PngImagePlugin.PngInfo()                # "align" hint -> read by design.py
    meta.add_text("ff-align", str(hint(src, "align", "")))
    meta.add_text("ff-sticker", "1" if hint(src, "border", True) else "0")
    img.save(dst, optimize=True, pnginfo=meta)
    return img.size


def main():
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in SRC.iterdir() if p.suffix.lower() in EXTS)
    if not sources:
        sys.exit(f"no pictures in {SRC}")

    # forget logos whose source picture was removed
    keep = {p.stem for p in sources}
    for old in OUT.glob("*.png"):
        if old.stem not in keep:
            old.unlink()
            print(f"removed  {old.name}")

    todo = [p for p in sources
            if force or not (OUT / f"{p.stem}.png").exists()
            or (OUT / f"{p.stem}.png").stat().st_mtime < max(
                p.stat().st_mtime, p.with_suffix(".json").stat().st_mtime if p.with_suffix(".json").exists() else 0)]
    if not todo:
        print(f"all {len(sources)} pictures already done (use --force to redo)")
        return

    sess = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
    for i, p in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {p.name} ...", end=" ", flush=True)
        w, h = process(p, OUT / f"{p.stem}.png", sess)
        print(f"{w}x{h}")
    print(f"done -> {OUT}")


if __name__ == "__main__":
    main()
