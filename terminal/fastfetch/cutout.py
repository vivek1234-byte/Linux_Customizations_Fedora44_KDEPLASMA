# Cut-out method "m1" (refined ensemble): TTA + colour-arbitrated mask, glitch-bar inpainting,
# band matting, blur-fusion colour decontamination, curved frame-edge fades. Used by make-images.py.
"""m1 'refined ensemble' cut-out (numpy + onnxruntime + Pillow only)."""
import numpy as np
from PIL import Image

F32 = np.float32


# ----------------------------------------------------------------------------- basic filters
def box(x, r):
    """Separable box mean with edge clamping. x: HxW or HxWxC. r may be float (rounded)."""
    r = int(round(r))
    if r <= 0:
        return x.astype(F32, copy=True)
    x = x.astype(F32, copy=False)
    for axis in (0, 1):
        n = x.shape[axis]
        pad = [(0, 0)] * x.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(x, pad, mode='edge'), axis=axis, dtype=np.float64)
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(n), axis=axis)
        x = ((hi - lo) / (2 * r + 1)).astype(F32)
    return x


def blur(x, sigma):
    """~Gaussian blur (3 box passes)."""
    if sigma <= 0.3:
        return x.astype(F32, copy=True)
    r = max(1, int(round(np.sqrt(4 * sigma * sigma + 1) / 2 - 0.5 + 0.5)))
    # 3 passes of radius r give variance 3*((2r+1)^2-1)/12 ; pick r for sigma
    r = max(1, int(round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    for _ in range(3):
        x = box(x, r)
    return x


def shift(a, dy, dx, fill=0):
    """shift array content by (dy, dx) (positive = down/right), filling with `fill`."""
    out = np.full_like(a, fill)
    H, W = a.shape[:2]
    ys0, ys1 = max(0, dy), min(H, H + dy)
    xs0, xs1 = max(0, dx), min(W, W + dx)
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def edt(mask, cap=64):
    """Euclidean distance (px) to the nearest True pixel, capped at `cap` (exact below the cap)."""
    H, W = mask.shape
    INF = F32(1e6)
    g = np.where(mask, F32(0), INF).astype(F32)
    for y in range(1, H):
        np.minimum(g[y], g[y - 1] + 1, out=g[y])
    for y in range(H - 2, -1, -1):
        np.minimum(g[y], g[y + 1] + 1, out=g[y])
    np.minimum(g, cap + 1, out=g)
    g2 = g * g
    d2 = g2.copy()
    c = int(cap)
    for k in range(1, c + 1):
        k2 = F32(k * k)
        np.minimum(d2[:, k:], g2[:, :-k] + k2, out=d2[:, k:])
        np.minimum(d2[:, :-k], g2[:, k:] + k2, out=d2[:, :-k])
    return np.minimum(np.sqrt(d2), F32(cap))


def dilate(mask, r):
    return edt(mask, cap=int(np.ceil(r)) + 1) <= r


def erode(mask, r):
    return ~dilate(~mask, r)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def resize_f(a, size, resample=Image.BILINEAR):
    """resize a float HxW array to (w, h)."""
    return np.asarray(Image.fromarray(a.astype(F32), 'F').resize(size, resample), F32)


# ----------------------------------------------------------------------------- colour
def rgb2lab(rgb):
    """rgb: ...x3 float 0..1 sRGB -> Lab (D65)."""
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], F32)
    xyz = c @ M.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883], F32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1).astype(F32)


# ----------------------------------------------------------------------------- connected components
def label(mask):
    """8-connected labelling. Returns (labels int32 HxW with 0=background, sizes array indexed by label)."""
    H, W = mask.shape
    m = np.zeros((H, W + 2), np.int8)
    m[:, 1:-1] = mask
    d = np.diff(m, axis=1)
    sr, sc = np.nonzero(d == 1)
    er, ec = np.nonzero(d == -1)
    n = len(sr)
    if n == 0:
        return np.zeros((H, W), np.int32), np.zeros(1, np.int64)
    BIG = W + 8
    ks = sr.astype(np.int64) * BIG + sc
    ke = er.astype(np.int64) * BIG + ec          # exclusive end
    # runs of the previous row overlapping (8-conn): s' <= e  and e' >= s
    lo = np.searchsorted(ke, (sr.astype(np.int64) - 1) * BIG + sc, side='left')
    hi = np.searchsorted(ks, (sr.astype(np.int64) - 1) * BIG + ec, side='right')
    cnt = np.maximum(hi - lo, 0)
    src = np.repeat(np.arange(n), cnt)
    off = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    dst = np.repeat(lo, cnt) + off
    ok = (dst < n)
    src, dst = src[ok], dst[ok]
    ok = sr[dst] == sr[src] - 1
    src, dst = src[ok], dst[ok]
    lab = np.arange(n)
    while True:
        old = lab
        mn = np.minimum(lab[src], lab[dst])
        lab = lab.copy()
        np.minimum.at(lab, src, mn)
        np.minimum.at(lab, dst, mn)
        lab = lab[lab]
        lab = lab[lab]
        if np.array_equal(lab, old):
            break
    uniq, inv = np.unique(lab, return_inverse=True)
    rl = (inv + 1).astype(np.int32)
    out = np.zeros(H * W, np.int32)
    lens = ec - sc
    starts = sr.astype(np.int64) * W + sc
    idx = np.repeat(starts, lens) + (np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens))
    out[idx] = np.repeat(rl, lens)
    sizes = np.bincount(out, minlength=len(uniq) + 1)
    sizes[0] = 0
    return out.reshape(H, W), sizes


# ----------------------------------------------------------------------------- glitch bars
def _runs(row_mask):
    m = np.concatenate([[0], row_mask.astype(np.int8), [0]])
    d = np.diff(m)
    return np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]


def find_bars(I, debug=False):
    """Detect digital 'glitch bars': axis-aligned rectangles bounded by straight horizontal edges
    (top & bottom, opposite polarity), uniform interior and sharp (or frame) ends.
    Returns list of (y0, y1, x0, x1): inclusive bar rows and [x0, x1) columns."""
    H, W, _ = I.shape
    J = I * 255
    Y = J @ np.array([0.299, 0.587, 0.114], F32)
    Dv = np.zeros((H, W), F32)
    Dv[1:H - 2] = np.linalg.norm(J[3:] - J[:-3], axis=2)      # edge between rows y and y+1
    Sv = np.zeros((H, W), F32)
    Sv[1:H - 2] = Y[3:] - Y[:-3]
    Dh = np.zeros((H, W), F32)
    Dh[:, 1:W - 2] = np.linalg.norm(J[:, 3:] - J[:, :-3], axis=2)
    Dh2 = np.maximum(Dh, np.maximum(shift(Dh, 1, 0), shift(Dh, -1, 0)))
    nms = (Dv >= shift(Dv, 1, 0)) & (Dv >= shift(Dv, -1, 0))
    E = (Dv > 28) & (Dv > 1.2 * Dh2) & nms
    E3 = E | shift(E, 1, 0) | shift(E, -1, 0)
    for g in (1, 2):
        E3 = E3 | (shift(E3, 0, g) & shift(E3, 0, -g))
    Lmin = max(28, int(0.035 * W))
    cand = []
    for y in range(2, H - 3):
        if not E[y].any():
            continue
        s, e = _runs(E3[y])
        for a, b in zip(s, e):
            if b - a < Lmin:
                continue
            if E[y, a:b].mean() < 0.3:
                continue
            sg = Sv[y - 1:y + 2, a:b]
            sg = sg[np.abs(sg).argmax(0), np.arange(b - a)]
            sgn = np.sign(np.median(sg))
            if sgn == 0 or (np.sign(sg) == sgn).mean() < 0.85:
                continue
            cand.append([y, int(a), int(b), float(sgn), float(Dv[y, a:b].mean() * E[y, a:b].mean())])
    # merge collinear candidates (same polarity, rows within 3, touching / overlapping in x)
    n = len(cand)
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if cand[j][0] - cand[i][0] > 3:
                break
            if cand[i][3] == cand[j][3] and cand[j][1] <= cand[i][2] + 6 and cand[i][1] <= cand[j][2] + 6:
                par[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(cand[i])
    segs = []
    for g in groups.values():
        best = max(g, key=lambda s: (s[2] - s[1]) * s[4])
        y, a, b = best[0], min(s[1] for s in g), max(s[2] for s in g)
        rows = Dv[max(0, y - 4):y + 5, a:b].argmax(0).astype(F32)
        med = np.median(rows)
        straight = float((np.abs(rows - med) <= 1).mean())
        slope = float(np.polyfit(np.arange(b - a, dtype=F32), rows, 1)[0]) if b - a > 2 else 0.0
        segs.append([y, a, b, best[3], best[4], straight >= 0.8 and abs(slope) < 0.06, abs(slope) < 0.12])
    segs.sort(key=lambda s: s[0])
    bars = []
    Hmax = max(40, int(0.05 * H))
    for i, a in enumerate(segs):
        for b in segs[i + 1:]:
            dy = b[0] - a[0]
            if dy < 5 or dy > Hmax or a[3] == b[3] or not (a[5] and b[5]):
                continue
            x0, x1 = max(a[1], b[1]), min(a[2], b[2])
            longer = max(a[2] - a[1], b[2] - b[1])
            if x1 - x0 < max(Lmin, 0.6 * longer):
                continue
            y0, y1 = a[0] + 3, b[0] - 2
            if y1 < y0:
                y0, y1 = a[0] + 2, b[0] - 1
            if y1 < y0:
                continue
            inner = J[y0:y1 + 1, x0:x1]
            hvar = float(np.median(np.abs(inner[:, 4:] - inner[:, :-4]).max(axis=2)))
            above = J[max(0, a[0] - 3):a[0] - 1, x0:x1].reshape(-1, 3).mean(0)
            below = J[b[0] + 3:min(H, b[0] + 6), x0:x1].reshape(-1, 3).mean(0)
            im = inner.reshape(-1, 3).mean(0)
            contrast = float(min(np.linalg.norm(im - above), np.linalg.norm(im - below)))

            def end_ok(x):
                if x <= 3 or x >= W - 4:
                    return True
                return float(np.median(Dh[y0:y1 + 1, max(0, x - 4):x + 4].max(axis=1))) > 25
            ux0, ux1 = min(a[1], b[1]), max(a[2], b[2])
            ends = int(end_ok(x0) or end_ok(ux0)) + int(end_ok(x1) or end_ok(ux1))
            ok = hvar < 6 and contrast > 25 and dy >= 10 and (ends == 2 or (ends == 1 and contrast >= 45))
            if debug:
                print('  cand y%d-%d x%d-%d hvar=%.1f contrast=%.1f ends=%d %s' % (a[0], b[0], x0, x1, hvar, contrast, ends, ok))
            if ok:
                bx0 = ux0 if end_ok(ux0) or abs(a[1] - b[1]) < 12 else x0
                bx1 = ux1 if end_ok(ux1) or abs(a[2] - b[2]) < 12 else x1
                # extend an end that runs into similar-coloured (hidden) structure while an edge persists
                ext = int(0.03 * W)
                for _ in range(ext):
                    if bx0 <= 0:
                        break
                    col = J[y0:y1 + 1, bx0 - 1].mean(0)
                    if np.linalg.norm(col - im) > 30 or max(Dv[a[0], bx0 - 1], Dv[b[0], bx0 - 1]) < 28:
                        break
                    bx0 -= 1
                for _ in range(ext):
                    if bx1 >= W:
                        break
                    col = J[y0:y1 + 1, bx1].mean(0)
                    if np.linalg.norm(col - im) > 30 or max(Dv[a[0], bx1], Dv[b[0], bx1]) < 28:
                        break
                    bx1 += 1
                bars.append((a[0] + 1, b[0], bx0, bx1))
    # thin stripes (e.g. coloured underlines) are accepted only when glued to an accepted bar
    for i, a in enumerate(segs):
        for b in segs[i + 1:]:
            dy = b[0] - a[0]
            if dy < 3 or dy >= 12 or not (a[6] and b[6]):
                continue
            x0, x1 = max(a[1], b[1]), min(a[2], b[2])
            if x1 - x0 < Lmin:
                continue
            glued = any((abs(a[0] + 1 - B[1]) <= 3 or abs(b[0] - B[0]) <= 3) and min(x1, B[3]) - max(x0, B[2]) > 0.5 * (x1 - x0)
                        for B in bars)
            if glued:
                bars.append((a[0] + 1, b[0], min(a[1], b[1]), max(a[2], b[2])))
    if debug:
        return [(s[0], s[1], s[2], s[3]) for s in segs], bars
    return bars


def _interp_row(row, xs):
    """linear interpolation of row (W x 3) at fractional positions xs (clamped)."""
    W = row.shape[0]
    xs = np.clip(xs, 0, W - 1)
    x0 = np.floor(xs).astype(int)
    x1 = np.minimum(x0 + 1, W - 1)
    f = (xs - x0)[..., None]
    return row[x0] * (1 - f) + row[x1] * f


def inpaint_bars(I, bars, margin=3):
    """Fill bar rectangles by interpolating between the rows just above and below, along the local
    direction that best matches the two boundary rows (hair strands crossing a bar continue)."""
    if not bars:
        return I, np.zeros(I.shape[:2], bool)
    H, W, _ = I.shape
    M = np.zeros((H, W), bool)
    for (y0, y1, x0, x1) in bars:
        M[max(0, y0 - margin):min(H, y1 + margin + 1), max(0, x0 - margin):min(W, x1 + margin)] = True
    out = I.copy()
    ks = np.linspace(-1.2, 1.2, 49)
    k0 = len(ks) // 2
    for x in np.nonzero(M.any(axis=0))[0]:
        s, e = _runs(M[:, x])
        for a, b in zip(s, e):
            ya, yb = a - 1, b
            h = yb - ya
            if ya < 0 or yb >= H:
                c = I[yb] if ya < 0 else I[ya]
                out[a:b, x] = c[x]
                continue
            rowA = (I[ya] + I[max(0, ya - 1)]) / 2
            rowB = (I[yb] + I[min(H - 1, yb + 1)]) / 2
            xs = np.arange(max(0, x - 40), min(W, x + 41), dtype=F32)
            errs = np.array([np.abs(_interp_row(rowA, xs - k * h / 2) - _interp_row(rowB, xs + k * h / 2)).sum(1).mean()
                             for k in ks])
            kb = int(errs.argmin())
            kg = ks[kb] if errs[k0] - errs[kb] > 0.03 else 0.0
            xs = np.arange(max(0, x - 10), min(W, x + 11), dtype=F32)
            kl = ks[np.abs(ks - kg) <= 0.151]
            errs = np.array([np.abs(_interp_row(rowA, xs - k * h / 2) - _interp_row(rowB, xs + k * h / 2)).sum(1).mean()
                             for k in kl])
            k = kl[int(errs.argmin())] if kg != 0.0 else 0.0
            ys = np.arange(a, b, dtype=F32)
            t = ((ys - ya) / h)[:, None]
            ca = _interp_row(rowA, x - k * (ys - ya))
            cb = _interp_row(rowB, x + k * (yb - ys))
            out[a:b, x] = ca * (1 - t) + cb * t
    sm = box(out, 1)
    Mf = M.astype(F32)[..., None]
    out = out * (1 - Mf) + (0.6 * out + 0.4 * sm) * Mf
    return out, M


# ----------------------------------------------------------------------------- model / TTA
SIZE = 1024


def predict(sess, I, scale=1.0, flip=False, pad=0.0):
    """isnet-anime foreground probability at I's size. The image is letterboxed into the 1024 canvas
    with its long side = 1024*scale (scale<1 gives the model context margin)."""
    H, W = I.shape[:2]
    k = SIZE * scale / max(H, W)
    w, h = max(1, round(W * k)), max(1, round(H * k))
    t, l = (SIZE - h) // 2, (SIZE - w) // 2
    img = Image.fromarray((np.clip(I, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    a = np.asarray(img, F32) / 255
    if flip:
        a = a[:, ::-1]
    x = np.full((SIZE, SIZE, 3), pad, F32)
    x[t:t + h, l:l + w] = a
    p = sess.run(None, {'img': np.ascontiguousarray(x.transpose(2, 0, 1)[None])})[0][0, 0][t:t + h, l:l + w]
    if flip:
        p = p[:, ::-1]
    return np.clip(resize_f(np.clip(p, 0, 1), (W, H)), 0, 1)


def predict_tiles(sess, I, base):
    """Two overlapping tiles along the long axis (each gets ~1.5-1.8x more model resolution).
    Returns a full-size map (NaN-free) blended in the overlap; outside the tiles = base."""
    H, W = I.shape[:2]
    out = np.zeros((H, W), F32)
    wsum = np.zeros((H, W), F32)
    if H >= W:
        n = int(H * 0.6)
        boxes = [(0, 0, W, n), (0, H - n, W, H)]
    else:
        n = int(W * 0.6)
        boxes = [(0, 0, n, H), (W - n, 0, W, H)]
    for (x0, y0, x1, y1) in boxes:
        p = predict(sess, I[y0:y1, x0:x1])
        # feather weight: ramps down towards the tile's interior cut lines
        wy = np.ones(y1 - y0, F32)
        wx = np.ones(x1 - x0, F32)
        r = max(8, int(0.08 * max(H, W)))
        ramp = np.linspace(0.02, 1, r, dtype=F32)
        if y0 > 0:
            wy[:r] = np.minimum(wy[:r], ramp)
        if y1 < H:
            wy[-r:] = np.minimum(wy[-r:], ramp[::-1])
        if x0 > 0:
            wx[:r] = np.minimum(wx[:r], ramp)
        if x1 < W:
            wx[-r:] = np.minimum(wx[-r:], ramp[::-1])
        wgt = wy[:, None] * wx[None, :]
        out[y0:y1, x0:x1] += p * wgt
        wsum[y0:y1, x0:x1] += wgt
    return np.where(wsum > 0, out / np.maximum(wsum, 1e-6), base)


def iou(a, b):
    return float((a & b).sum()) / max(1.0, float((a | b).sum()))


# ----------------------------------------------------------------------------- colour models
def fill(vals, w, radii=(3, 10, 30, 90)):
    """Multi-scale normalized convolution: spread the weighted samples `vals` (HxWxC) into the whole
    image, preferring the smallest scale that has support."""
    H, W = w.shape
    w = w.astype(F32)
    tot = float(w.sum())
    if tot < 1:
        return np.repeat(vals.reshape(-1, vals.shape[-1]).mean(0)[None, None], H, 0).repeat(W, 1).astype(F32)
    gmean = (vals * w[..., None]).reshape(-1, vals.shape[-1]).sum(0) / tot
    est = np.broadcast_to(gmean.astype(F32), vals.shape).copy()
    vw = vals * w[..., None]
    for r in reversed(radii):
        if r >= 12:   # coarse levels on a 1/4 grid
            s = 4
            hs, ws = H // s, W // s
            wd = w[:hs * s, :ws * s].reshape(hs, s, ws, s).mean((1, 3))
            vd = vw[:hs * s, :ws * s].reshape(hs, s, ws, s, -1).mean((1, 3))
            rr = max(1, r // s)
            wb = box(box(wd, rr), rr)
            vb = box(box(vd, rr), rr)
            fine_d = vb / np.maximum(wb, 1e-6)[..., None]
            fine = np.stack([resize_f(fine_d[..., c], (W, H)) for c in range(vals.shape[-1])], -1)
            wbf = resize_f(wb, (W, H))
        else:
            wbf = box(box(w, r), r)
            fine = box(box(vw, r), r) / np.maximum(wbf, 1e-6)[..., None]
        conf = np.clip(wbf / 0.12, 0, 1)[..., None]
        est = conf * fine + (1 - conf) * est
    return est.astype(F32)


def kmeans(X, k, iters=12, seed=0, max_n=20000):
    rng = np.random.default_rng(seed)
    if len(X) > max_n:
        X = X[rng.choice(len(X), max_n, replace=False)]
    k = min(k, len(X))
    C = [X[rng.integers(len(X))]]
    d = ((X - C[0]) ** 2).sum(1)
    for _ in range(1, k):
        if d.sum() <= 0:
            break
        C.append(X[rng.choice(len(X), p=d / d.sum())])
        d = np.minimum(d, ((X - C[-1]) ** 2).sum(1))
    C = np.array(C, F32)
    for _ in range(iters):
        D = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        lab = D.argmin(1)
        for j in range(len(C)):
            sel = lab == j
            if sel.any():
                C[j] = X[sel].mean(0)
    D = ((X[:, None, :] - C[None]) ** 2).sum(-1)
    cnt = np.bincount(D.argmin(1), minlength=len(C))
    return C, cnt / cnt.sum()


def palette_dist(lab, C):
    """min Euclidean (Delta E 76) distance from every pixel to the palette colours."""
    d = None
    for c in C:
        dc = np.sqrt(((lab - c) ** 2).sum(-1))
        d = dc if d is None else np.minimum(d, dc)
    return d


# ----------------------------------------------------------------------------- guided filter
def guided_filter(I, p, r, eps, s=1):
    """He et al. colour guided filter (fast version with subsampling factor s)."""
    H, W = p.shape
    if s > 1:
        hs, ws = max(1, H // s), max(1, W // s)
        Is = np.stack([resize_f(I[..., c], (ws, hs)) for c in range(3)], -1)
        ps = resize_f(p, (ws, hs))
        rs = max(1, int(round(r / s)))
    else:
        Is, ps, rs = I, p, r
    mI = box(Is, rs)
    mp = box(ps, rs)
    mIp = box(Is * ps[..., None], rs)
    cov = mIp - mI * mp[..., None]
    v = {}
    for i in range(3):
        for j in range(i, 3):
            v[i, j] = box(Is[..., i] * Is[..., j], rs) - mI[..., i] * mI[..., j]
    a11, a12, a13 = v[0, 0] + eps, v[0, 1], v[0, 2]
    a22, a23, a33 = v[1, 1] + eps, v[1, 2], v[2, 2] + eps
    # inverse of the symmetric 3x3 via adjugate
    i11 = a22 * a33 - a23 * a23
    i12 = a13 * a23 - a12 * a33
    i13 = a12 * a23 - a13 * a22
    i22 = a11 * a33 - a13 * a13
    i23 = a13 * a12 - a11 * a23
    i33 = a11 * a22 - a12 * a12
    det = a11 * i11 + a12 * i12 + a13 * i13
    c0, c1, c2 = cov[..., 0], cov[..., 1], cov[..., 2]
    A0 = (i11 * c0 + i12 * c1 + i13 * c2) / det
    A1 = (i12 * c0 + i22 * c1 + i23 * c2) / det
    A2 = (i13 * c0 + i23 * c1 + i33 * c2) / det
    b = mp - A0 * mI[..., 0] - A1 * mI[..., 1] - A2 * mI[..., 2]
    A = np.stack([box(A0, rs), box(A1, rs), box(A2, rs)], -1)
    b = box(b, rs)
    if s > 1:
        A = np.stack([resize_f(A[..., c], (W, H)) for c in range(3)], -1)
        b = resize_f(b, (W, H))
    return (A * I).sum(-1) + b


# ----------------------------------------------------------------------------- foreground colour
def fb_blur_fusion(I, F, B, a, r):
    a3 = a[..., None]
    ba = box(a, r)[..., None]
    bF = box(F * a3, r) / (ba + 1e-5)
    bB = box(B * (1 - a3), r) / ((1 - ba) + 1e-5)
    Fn = bF + a3 * (I - a3 * bF - (1 - a3) * bB)
    return np.clip(Fn, 0, 1), bB


def estimate_fg(I, a):
    """Approximate fast foreground colour estimation (Forte & Pitie 2020), two levels."""
    F, bB = fb_blur_fusion(I, I, I, a, 45)
    F, _ = fb_blur_fusion(I, F, bB, a, 3)
    return F


# ----------------------------------------------------------------------------- morphology helpers
def geodesic_steps(seed, allowed, n):
    """BFS distance (8-conn, in steps) from `seed` through `allowed`, up to n steps; n+1 beyond."""
    dist = np.where(seed, 0, n + 1).astype(np.int16)
    cur = seed.copy()
    for k in range(1, n + 1):
        g = cur.copy()
        g[1:] |= cur[:-1]
        g[:-1] |= cur[1:]
        g2 = g.copy()
        g2[:, 1:] |= g[:, :-1]
        g2[:, :-1] |= g[:, 1:]
        nxt = g2 & allowed
        new = nxt & ~cur
        if not new.any():
            break
        dist[new] = k
        cur = cur | nxt
    return dist


def keep_main_mask(m, min_part=0.03):
    lab, sizes = label(m)
    if sizes.max() == 0:
        return m
    keep = sizes >= sizes.max() * min_part
    keep[0] = False
    return keep[lab]


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


# ----------------------------------------------------------------------------- frame-edge treatment
def frame_fade(a, frac_side=0.06, frac_bottom=0.09, frac_top=0.02):
    """Where the subject runs into the picture frame, fade it out with a curved (half-elliptic) profile
    per contact run: deepest in the middle of the contact, zero at its ends, so the faded boundary is an
    arc that follows the subject instead of a straight soft band. Short contacts (strand tips) get a
    tiny taper, rows/columns that do not touch the frame are untouched."""
    H, W = a.shape
    fade = np.ones((H, W), F32)
    sides = {
        'top': (a[0, :], W, H, frac_top),
        'bottom': (a[-1, :], W, H, frac_bottom),
        'left': (a[:, 0], H, W, frac_side),
        'right': (a[:, -1], H, W, frac_side),
    }
    for side, (edge, n_along, n_across, frac) in sides.items():
        # contact = alpha at the frame line (use a 3px deep max so 1px gaps do not split runs)
        on = edge > 0.35
        if not on.any():
            continue
        # close small gaps
        idx = np.nonzero(on)[0]
        runs = []
        start = prev = idx[0]
        for i in idx[1:]:
            if i - prev > 10:
                runs.append((start, prev + 1))
                start = i
            prev = i
        runs.append((start, prev + 1))
        Lmax = frac * n_across
        t = np.arange(n_along, dtype=F32)
        d = np.arange(n_across, dtype=F32)   # distance from the frame line
        for (r0, r1) in runs:
            Lr = r1 - r0
            depth = float(np.clip(0.45 * Lr, 4, Lmax))
            half = Lr / 2 + 0.35 * depth          # ellipse reaches a little beyond the run ends
            u = (t - (r0 + r1 - 1) / 2) / half
            prof = depth * np.sqrt(np.clip(1 - u * u, 0, 1))      # fade length along the edge
            if side in ('left', 'right'):
                # side cuts fade little near the shoulders and more towards the bottom, so they merge
                # with the bottom dissolve into a rounded vignette instead of a soft rectangle
                prof = prof * (0.35 + 0.65 * t / max(1, n_along - 1))
            sel = prof > 0.5
            if not sel.any():
                continue
            # f = smoothstep(0, prof, d)  -> matrix (n_across x n_along_sel)
            dd = d[:int(np.ceil(depth)) + 2, None]
            z = np.clip((dd + 0.5) / np.maximum(prof[None, sel], 1e-3), 0, 1)
            f = z * z * (3 - 2 * z)
            m = dd.shape[0]
            cols = np.nonzero(sel)[0]
            if side == 'top':
                fade[:m, cols] *= f
            elif side == 'bottom':
                fade[H - m:, cols] *= f[::-1]
            elif side == 'left':
                fade[cols, :m] *= f.T
            else:
                fade[cols, W - m:] *= f.T[:, ::-1]
    return a * fade, fade


# ----------------------------------------------------------------------------- main entry
def cutout(up, prob, sess, debug=None, tiles=True):
    """up: PIL RGB (Real-ESRGAN x4), prob: isnet probability HxW at up size, sess: isnet onnx session.
    Returns PIL RGBA of the same size with final alpha and decontaminated colour."""
    I0 = np.asarray(up.convert('RGB'), F32) / 255
    H, W = I0.shape[:2]
    dbg = debug if debug is not None else {}

    # 1. digital glitch bars: detect + inpaint (model and output both use the cleaned image)
    bars = find_bars(I0)
    I, barmask = inpaint_bars(I0, bars)
    dbg['bars'] = bars

    # 2. test-time augmentation: flips + context scales; scales that change the topology are rejected
    base = predict(sess, I) if bars else np.clip(prob.astype(F32), 0, 1)
    fg0 = base > 0.5
    sem = [base]
    used = ['base']
    for name, kw in (('flip', dict(flip=True)), ('s80', dict(scale=0.8)), ('s60', dict(scale=0.6)),
                     ('s80f', dict(scale=0.8, flip=True))):
        p = predict(sess, I, **kw)
        if iou(p > 0.5, fg0) >= 0.9:
            sem.append(p)
            used.append(name)
    dbg['tta_used'] = used
    P = np.stack(sem)
    p_mean = P.mean(0)
    p_min = P.min(0)
    p_max = P.max(0)
    # high-resolution tiles: refine only near the ensemble's edges, where they agree
    if tiles:
        pt = predict_tiles(sess, I, p_mean)
        nearedge = dilate((p_mean > 0.03) & (p_mean < 0.97), 4)
        agree = np.abs(pt - p_mean) < 0.35
        w_t = (nearedge & agree).astype(F32) * 0.5
        p_fine = p_mean * (1 - w_t) + pt * w_t
    else:
        p_fine = p_mean
    dbg['p_mean'] = p_mean
    dbg['p_fine'] = p_fine

    lab = rgb2lab(I)
    # 3. colour models from what every TTA view agrees on
    sure_fg = erode(p_min > 0.95, 2)
    sure_bg = erode(p_max < 0.05, 2)
    have_bg = sure_bg.sum() > 0.01 * H * W
    # where the TTA views disagree the model is not sure: let colour evidence weigh more
    lp = np.clip(logit(p_mean), -5, 5) * (1 - 0.7 * np.clip(p_max - p_min, 0, 1))
    if have_bg:
        Bp = fill(I, sure_bg)
        Fp = fill(I, sure_fg)
        labB, labF = rgb2lab(Bp), rgb2lab(Fp)
        Cb, wb = kmeans(lab[sure_bg], 8)
        Cb = Cb[wb > 0.01]
        Cf, wf = kmeans(lab[sure_fg], 12, seed=1)
        Cf = Cf[wf > 0.005]
        dBl = np.sqrt(((lab - labB) ** 2).sum(-1))
        dFl = np.sqrt(((lab - labF) ** 2).sum(-1))
        dB = np.minimum(dBl, palette_dist(lab, Cb) + 6)
        dF = np.minimum(dFl, palette_dist(lab, Cf) + 6)
        ce = np.clip(2.2 * np.log((dB + 3) / (dF + 3)), -4, 4)
        dbg['ce'] = ce
        score = lp + ce
    else:
        score = lp
    lock_fg = erode(p_min > 0.97, 6)
    lock_bg = erode(p_max < 0.03, 6)
    score = np.where(lock_fg, 5.0, np.where(lock_bg, -5.0, score)).astype(F32)
    # 4. edge-aware regularisation of the decision (colour guided filter on the score)
    s_sm = guided_filter(I, score / 5, r=5, eps=4e-3, s=2) * 5
    S = s_sm > 0
    # releases must connect to the real background: a 'hole' punched into the model's subject is only
    # accepted when the model itself was unsure there (keeps white-on-white details, clothes, ...)
    S0 = p_mean > 0.5
    rel_reg = S0 & ~S
    if rel_reg.any():
        lab_r, sz = label(rel_reg)
        outside = dilate(~S0, 2)
        rim = rel_reg & dilate(~rel_reg, 1.5)
        n_rim = np.bincount(lab_r[rim], minlength=len(sz))
        n_touch = np.bincount(lab_r[rim & outside], minlength=len(sz))
        contact = n_touch / np.maximum(n_rim, 1)
        pm = np.bincount(lab_r.ravel(), weights=p_mean.ravel(), minlength=len(sz)) / np.maximum(sz, 1)
        cm = (np.bincount(lab_r.ravel(), weights=score.ravel() - lp.ravel(), minlength=len(sz))
              / np.maximum(sz, 1))
        # a sliver along the outline (big contact with the outside) is a normal refinement; a notch
        # carved deep into the subject needs strong colour evidence
        ok = ((contact >= 0.2) & (n_touch > 0)) | ((n_touch > 0) & (cm < -1.5)) | (pm < 0.6)
        ok[0] = True
        S = S | (rel_reg & ~ok[lab_r])
        # deep inside a confident model region colour may not punch holes (white-on-white details)
        S = S | (S0 & (p_mean >= 0.85) & (edt(~S0, cap=8) > 6))
    S = keep_main_mask(S, 0.03)
    dbg['score'] = score
    dbg['S'] = S

    # 5. matting in a thin band around the decision boundary
    rb = 3
    din = edt(~S, cap=64)       # inside S: distance to background
    dout = edt(S, cap=64)       # outside: distance to subject
    band = (S & (din <= rb)) | (~S & (dout <= rb))
    fg_t = S & (din > rb)
    bg_t = ~S & (dout > rb)
    B1 = fill(I, bg_t)
    wrob = np.exp(-((I - B1) ** 2).sum(-1) / (2 * 0.06 ** 2)) * bg_t
    B2 = fill(I, wrob)
    F2 = fill(I, fg_t)
    sig = np.sqrt(fill(((I - B2) ** 2).sum(-1, keepdims=True), wrob)[..., 0])
    FB = F2 - B2
    nFB = np.sqrt((FB ** 2).sum(-1))
    a_proj = np.clip(((I - B2) * FB).sum(-1) / (nFB ** 2 + 1e-4), 0, 1)
    resid = np.sqrt(((I - (a_proj[..., None] * F2 + (1 - a_proj[..., None]) * B2)) ** 2).sum(-1))
    rel = (smoothstep(0.10, 0.25, nFB) * (1 - smoothstep(0.08, 0.22, resid / (nFB + 1e-3)))
           * (1 - smoothstep(0.035, 0.09, sig)))
    a_fb = np.clip(guided_filter(I, S.astype(F32), r=2, eps=1e-3), 0, 1)
    a_band = rel * a_proj + (1 - rel) * a_fb
    alpha = np.where(band, a_band, S.astype(F32))
    dbg['rel'] = rel
    dbg['a_proj'] = a_proj
    dbg['sig'] = sig

    # 6. thin structures the model missed (strands) where the background is clean enough to key
    grow = ~S & ~band & (dout <= 48)
    a_g = np.where(grow, rel * a_proj, 0)
    a_g = np.where(a_g > 0.08, a_g, 0)
    conn = keep_main_mask((alpha > 0.1) | (a_g > 0), 0.03)
    a_g = np.where(conn, a_g, 0)
    alpha = np.maximum(alpha, a_g)

    # 7. soft clean-up: faint pixels far (geodesically) from the solid main body fade out
    solid = keep_main_mask(alpha > 0.5, 0.03)
    core = geodesic_steps(solid, alpha > 0.12, 64) <= 64
    gd = geodesic_steps(core, alpha > 0.02, 10)
    alpha = alpha * (1 - smoothstep(4, 10, gd.astype(F32)))
    alpha = np.clip(alpha, 0, 1)
    dbg['alpha_pre_fade'] = alpha.copy()

    # 8. frame-edge treatment
    alpha, fade = frame_fade(alpha)
    dbg['fade'] = fade

    # 9. decontaminated foreground colour
    Fc = estimate_fg(I, alpha)
    rgb = np.where(alpha[..., None] >= 0.995, I, Fc)
    out = np.dstack([np.clip(rgb, 0, 1) * 255 + 0.5, alpha * 255 + 0.5]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')
