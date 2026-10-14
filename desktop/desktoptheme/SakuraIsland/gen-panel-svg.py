#!/usr/bin/env python3
"""Generate panel-background.svg for the Sakura Island Plasma theme.
The panel is drawn as a Dynamic-Island pill: indigo -> plum glass, lilac rim,
white sheen on the outer half, lilac glow as the shadow."""
import sys

R = 19            # corner radius (half the pill thickness)
S = 14            # glow size outside the pill
TOP, MID, BOT = "#231C46", "#2E1F52", "#3F1E4A"
ALPHA = 0.93
RIM, RIM_A = "#C3A6FF", 0.45
GLOW, GLOW_A = "#B48CFF", 0.50

out = []
w = out.append
w(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="400" height="200" viewBox="0 0 400 200">')
w('<defs>')
w(f'<linearGradient id="vg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{TOP}"/><stop offset="0.5" stop-color="{MID}"/><stop offset="1" stop-color="{BOT}"/></linearGradient>')
# sheen across the pill (left -> right), like the island's glassy highlight
w('<linearGradient id="sheenL" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0.16"/><stop offset="1" stop-color="#fff" stop-opacity="0.03"/></linearGradient>')
w('<linearGradient id="sheenR" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0.03"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
for name, (x1, y1, x2, y2) in {"gT": (0, 1, 0, 0), "gB": (0, 0, 0, 1), "gL": (1, 0, 0, 0), "gR": (0, 0, 1, 0)}.items():
    w(f'<linearGradient id="{name}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"><stop offset="0" stop-color="{GLOW}" stop-opacity="{GLOW_A}"/><stop offset="0.45" stop-color="{GLOW}" stop-opacity="{GLOW_A*0.4}"/><stop offset="1" stop-color="{GLOW}" stop-opacity="0"/></linearGradient>')
C = S + R
f = R / C
for name, (cx, cy) in {"cTL": (C, C), "cTR": (0, C), "cBL": (C, 0), "cBR": (0, 0)}.items():
    w(f'<radialGradient id="{name}" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{C}"><stop offset="{f-0.02:.3f}" stop-color="{GLOW}" stop-opacity="0"/><stop offset="{f:.3f}" stop-color="{GLOW}" stop-opacity="{GLOW_A}"/><stop offset="{f+(1-f)*0.45:.3f}" stop-color="{GLOW}" stop-opacity="{GLOW_A*0.4}"/><stop offset="1" stop-color="{GLOW}" stop-opacity="0"/></radialGradient>')
w('</defs>')

def group(id_, x, y, body):
    w(f'<g id="{id_}" transform="translate({x},{y})">{body}</g>')

fillTop = f'fill="{TOP}" fill-opacity="{ALPHA}"'
fillBot = f'fill="{BOT}" fill-opacity="{ALPHA}"'
fillV = f'fill="url(#vg)" fill-opacity="{ALPHA}"'
rim = f'fill="{RIM}" fill-opacity="{RIM_A}"'
H = 20  # height of stretchable pieces in the source file

# ---- frame: corners are quarter discs, edges/centre carry the vertical gradient
ox, oy = 10, 10
r = R - 1
q = {  # quarter disc inside an RxR box, and the 1px rim as a filled ring
    "topleft": (f"M{R},0 A{R},{R} 0 0 0 0,{R} L{R},{R} Z", f"M{R},0 A{R},{R} 0 0 0 0,{R} L1,{R} A{r},{r} 0 0 1 {R},1 Z", fillTop, "sheenL"),
    "topright": (f"M0,0 A{R},{R} 0 0 1 {R},{R} L0,{R} Z", f"M0,0 A{R},{R} 0 0 1 {R},{R} L{r},{R} A{r},{r} 0 0 0 0,1 Z", fillTop, "sheenR"),
    "bottomleft": (f"M0,0 A{R},{R} 0 0 0 {R},{R} L{R},0 Z", f"M0,0 A{R},{R} 0 0 0 {R},{R} L{R},{r} A{r},{r} 0 0 1 1,0 Z", fillBot, "sheenL"),
    "bottomright": (f"M0,0 L{R},0 A{R},{R} 0 0 1 0,{R} Z", f"M{R},0 A{R},{R} 0 0 1 0,{R} L0,{r} A{r},{r} 0 0 0 {r},0 Z", fillBot, "sheenR"),
}
pos = {"topleft": (0, 0), "top": (R, 0), "topright": (R + 2, 0),
       "left": (0, R), "center": (R, R), "right": (R + 2, R),
       "bottomleft": (0, R + H), "bottom": (R, R + H), "bottomright": (R + 2, R + H)}
for k, (d, arc, fill, sheen) in q.items():
    x, y = pos[k]
    group(k, ox + x, oy + y, f'<path d="{d}" {fill}/><path d="{d}" fill="url(#{sheen})"/><path d="{arc}" {rim}/>')
x, y = pos["top"];    group("top", ox + x, oy + y, f'<rect width="2" height="{R}" {fillTop}/><rect width="2" height="{R}" fill="#fff" fill-opacity="0.03"/><rect y="0" width="2" height="1" fill="{RIM}" fill-opacity="{RIM_A}"/>')
x, y = pos["bottom"]; group("bottom", ox + x, oy + y, f'<rect width="2" height="{R}" {fillBot}/><rect width="2" height="{R}" fill="#fff" fill-opacity="0.03"/><rect y="{R-1}" width="2" height="1" fill="{RIM}" fill-opacity="{RIM_A}"/>')
x, y = pos["left"];   group("left", ox + x, oy + y, f'<rect width="{R}" height="{H}" {fillV}/><rect width="{R}" height="{H}" fill="url(#sheenL)"/><rect width="1" height="{H}" fill="{RIM}" fill-opacity="{RIM_A}"/>')
x, y = pos["right"];  group("right", ox + x, oy + y, f'<rect width="{R}" height="{H}" {fillV}/><rect width="{R}" height="{H}" fill="url(#sheenR)"/><rect x="{R-1}" width="1" height="{H}" fill="{RIM}" fill-opacity="{RIM_A}"/>')
x, y = pos["center"]; group("center", ox + x, oy + y, f'<rect width="2" height="{H}" {fillV}/><rect width="2" height="{H}" fill="#fff" fill-opacity="0.03"/>')

# ---- content margins (icons stay clear of the rounded ends)
w(f'<rect id="hint-left-margin" x="100" y="10" width="5" height="4" fill="none"/>')
w(f'<rect id="hint-right-margin" x="110" y="10" width="5" height="4" fill="none"/>')
w(f'<rect id="hint-top-margin" x="120" y="10" width="4" height="13" fill="none"/>')
w(f'<rect id="hint-bottom-margin" x="130" y="10" width="4" height="13" fill="none"/>')
w(f'<rect id="hint-stretch-borders" x="140" y="10" width="2" height="2" fill="none"/>')

# ---- blur/contrast mask (same pill shape, opaque)
mx, my = 160, 10
for k, (d, *_ ) in q.items():
    x, y = pos[k]
    w(f'<path id="mask-{k}" transform="translate({mx + x},{my + y})" d="{d}" fill="#000"/>')
for k, (wd, ht) in {"top": (2, R), "bottom": (2, R), "left": (R, H), "right": (R, H), "center": (2, H)}.items():
    x, y = pos[k]
    w(f'<rect id="mask-{k}" x="{mx + x}" y="{my + y}" width="{wd}" height="{ht}" fill="#000"/>')

# ---- glow (shadow) tiles
sx, sy = 10, 100
w(f'<rect id="shadow-topleft" x="{sx}" y="{sy}" width="{C}" height="{C}" fill="url(#cTL)" transform="translate(0,0)"/>'.replace(f'x="{sx}" y="{sy}" ', '').replace('transform="translate(0,0)"', f'transform="translate({sx},{sy})"'))
w(f'<rect id="shadow-topright" width="{C}" height="{C}" fill="url(#cTR)" transform="translate({sx + C + 4},{sy})"/>')
w(f'<rect id="shadow-bottomleft" width="{C}" height="{C}" fill="url(#cBL)" transform="translate({sx + 2*(C + 4)},{sy})"/>')
w(f'<rect id="shadow-bottomright" width="{C}" height="{C}" fill="url(#cBR)" transform="translate({sx + 3*(C + 4)},{sy})"/>')
bx = sx + 4 * (C + 4)
w(f'<rect id="shadow-top" x="{bx}" y="{sy}" width="2" height="{S}" fill="url(#gT)"/>')
w(f'<rect id="shadow-bottom" x="{bx + 6}" y="{sy}" width="2" height="{S}" fill="url(#gB)"/>')
w(f'<rect id="shadow-left" x="{bx + 12}" y="{sy}" width="{S}" height="2" fill="url(#gL)"/>')
w(f'<rect id="shadow-right" x="{bx + 30}" y="{sy}" width="{S}" height="2" fill="url(#gR)"/>')
w(f'<rect id="shadow-center" x="{bx + 50}" y="{sy}" width="2" height="2" fill="none"/>')
for i, side in enumerate(["top", "bottom", "left", "right"]):
    vert = side in ("top", "bottom")
    w(f'<rect id="shadow-hint-{side}-margin" x="{bx + 60 + i*20}" y="{sy}" width="{2 if vert else S}" height="{S if vert else 2}" fill="none"/>')
w('</svg>')
sys.stdout.write("\n".join(out) + "\n")
