"""Original portraits as the kit builds them (docs/dev/co-kit.md): a design drawn, fitted to the game's 15 colours, with its four expression faces, small face and HUD face; the checks
(`co portrait lint`: palette, outline, light, and the donor-similarity check) and the review sheets with the real COs beside."""
import numpy as np
from PIL import Image, ImageDraw
from .. import cfg, util
from . import designs as D, compose as cp, render as rd, roms
from .draw import hexrgb


class RPic:
    """An Art rendered to RGB (None transparent): the shape compose.fit_palette works on."""

    def __init__(self, art, colours):
        self.h, self.w = art.h, art.w
        self.px = [[hexrgb(colours[art.g[y, x]]) if art.g[y, x] else None for x in range(art.w)] for y in range(art.h)]


def all_designs():
    out = {}
    for co in ("klaus", "aurelia", "cassius", "livia"):
        for L, d in getattr(D, co.upper()).items():
            out[(co, L)] = d
    return out


def make(design):
    """-> dict(body, face [4 expressions], mini, hud as RPic fitted to 15 colours), palette, merged count, raw arts."""
    fig, mug = D.build(design, "normal")
    faces = []
    for e in D.EXPRS:
        f, m = D.build(design, e)
        faces.append(m)
    mini, hud = D.small_faces(faces[0])
    c = design.colours
    pics = {"body": RPic(fig, c), "face": [RPic(f, c) for f in faces], "mini": RPic(mini, c), "hud": RPic(hud, c)}
    mapping, pal, merged = cp.fit_palette(pics)
    cp.apply_fit(pics, mapping)
    return pics, pal, merged, (fig, faces)


# --- checks ---------------------------------------------------------------------------------------------------------------------------------------------------------

def _lum(pic):
    a = np.zeros((pic.h, pic.w))
    m = np.zeros((pic.h, pic.w), bool)
    for y, r in enumerate(pic.px):
        for x, c in enumerate(r):
            if c is not None:
                a[y, x] = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
                m[y, x] = True
    return a, m


def _edges(a, m):
    gx = np.abs(np.diff(a, axis=1, prepend=0))
    gy = np.abs(np.diff(a, axis=0, prepend=0))
    e = (gx + gy) > 40
    return e & m | (m ^ np.roll(m, 1, 1)) | (m ^ np.roll(m, 1, 0))


def _best_overlap(e1, e2, shift=4):
    """Best Dice overlap of two edge maps over small shifts."""
    best = 0.0
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            s = np.roll(np.roll(e2, dy, 0), dx, 1)
            den = e1.sum() + s.sum()
            if den:
                best = max(best, 2 * (e1 & s).sum() / den)
    return best


def _contour(m):
    """The silhouette's contour (a mask minus its erosion), without the canvas' cut edges."""
    e = m.copy()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        e &= np.roll(m, (dy, dx), (0, 1))
    c = m & ~e
    c[-1, :] = False
    c[:, 0] = False
    c[:, -1] = False
    return c


def _iou(m1, m2, shift=3):
    """Dice overlap of the two silhouettes' contours over small shifts (1.0: the same outline)."""
    c1, c2 = _contour(m1), _contour(m2)
    best = 0.0
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            s = np.roll(np.roll(c2, dy, 0), dx, 1)
            den = c1.sum() + s.sum()
            if den:
                best = max(best, 2 * (c1 & s).sum() / den)
    return best


def donor_pics(source):
    ids = range(19) if source == "aw2" else range(2, 28)
    for i in ids:
        d = roms.aw2_portrait(i) if source == "aw2" else roms.ds_portrait(i)
        yield f"{source}:{d.name}", d


def similarity(pics):
    """The closest donor per part: figure silhouette IoU and face edge overlap against every AW2 and Dual Strike CO (first palette; shifts of +-4 px). -> list of (name, iou, face_overlap)."""
    fm = _lum(pics["body"])[1]
    fe, fmask = _lum(pics["face"][0])
    fedge = _edges(fe, fmask)
    out = []
    for src in ("aw2", "ds"):
        for name, d in donor_pics(src):
            pal = d.palettes[0]
            body = np.array([[bool(v) for v in r] for r in d.body])
            face = np.array([[roms.bgr(pal[v]) if v else None for v in r] for r in d.faces[0]], dtype=object)
            fl = np.zeros((48, 48))
            fmk = np.zeros((48, 48), bool)
            for y in range(48):
                for x in range(48):
                    c = face[y, x]
                    if c is not None:
                        fl[y, x] = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
                        fmk[y, x] = True
            out.append((name, _iou(fm, body), _best_overlap(fedge, _edges(fl, fmk))))
    return out


# Calibration: unrelated AW2 faces score 0.44 on average and 0.54 at most on the face edge overlap, a recoloured copy scores 1.0; unrelated silhouettes' contours score 0.0 to 0.1.
MAX_IOU, MAX_FACE = 0.40, 0.70


def lint(design):
    """-> list of problems. Palette: at most 15 colours; the figure's silhouette is outlined all round; each material (slot family) uses at most three tones; no donor is too like it."""
    pics, pal, merged, (fig, faces) = make(design)
    bad = []
    if len(pal) > 15:
        bad.append(f"{len(pal)} colours")
    if merged > 8:
        bad.append(f"{merged} colours had to be merged to fit 15 (a design should plan its palette; the sheet shows the merged result)")
    # outline: every transparent pixel next to a filled one is already outline (outline_pass); check the figure has no filled pixel on the canvas edge except the cut at the bottom/sides
    filled = fig.g != ""
    if filled[0].any():
        bad.append("the figure touches the top edge")
    # tones per material family
    fam = {}
    for slot in set(fig.g.flatten()) | {s for f in faces for s in set(f.g.flatten())}:
        if slot and "_" in slot:
            fam.setdefault(slot.split("_")[0], set()).add(slot)
    for f, slots in fam.items():
        if f in ("sk", "ha", "st", "rd", "gd", "cr", "lt", "pu", "lf") and len(slots) > 3:
            bad.append(f"material {f}: {len(slots)} tones (max 3)")
    sim = similarity(pics)
    for name, iou, fo in sorted(sim, key=lambda t: -max(t[1] / MAX_IOU, t[2] / MAX_FACE))[:1]:
        if iou > MAX_IOU or fo > MAX_FACE:
            bad.append(f"too like {name}: silhouette {iou:.2f} (max {MAX_IOU}), face {fo:.2f} (max {MAX_FACE})")
    return bad, sim


# --- sheets ---------------------------------------------------------------------------------------------------------------------------------------------------------

def _img(pic, scale=1, bg=None):
    return rd.to_image(pic.px, scale, bg)


def real_faces(names, which=0):
    out = []
    for n in names:
        src, who = n.split(":")
        d = cp.donor(n)
        pal = d.palettes[0]
        out.append((who, cp.Pic(d.faces[which], pal), cp.Pic(d.hud, pal), cp.Pic(d.body, pal)))
    return out


CONTEXT = ["aw2:andy", "aw2:max", "aw2:sami", "aw2:hawke", "aw2:kanbei", "aw2:sonja", "aw2:eagle", "aw2:nell", "aw2:colin", "aw2:jess"]


def design_sheet(co, letters=None):
    ds = {k[1]: v for k, v in all_designs().items() if k[0] == co}
    letters = letters or sorted(ds)
    cw, ch = 520, 780
    sheet = Image.new("RGB", (len(letters) * cw if len(letters) <= 2 else 2 * cw, ((len(letters) + 1) // 2 if len(letters) > 2 else 1) * ch + 70), rd.BG)
    cols = 2 if len(letters) > 2 else len(letters)
    rd.text(sheet, (14, 10), f"{ds[letters[0]].co.title()}: original designs (v2)", size=24)
    rd.text(sheet, (14, 40), "large figure 2x and 1x | four expression faces 2x (normal, happy, sad, angry) and 1x | small face and HUD face | all drawn by us, no donor pixels", fill=(170, 176, 190), size=12)
    for n, L in enumerate(letters):
        d = ds[L]
        pics, pal, merged, _ = make(d)
        x0, y0 = (n % cols) * cw + 4, 66 + (n // cols) * ch
        ImageDraw.Draw(sheet).rounded_rectangle((x0, y0, x0 + cw - 12, y0 + ch - 10), 8, fill=rd.PANEL)
        rd.text(sheet, (x0 + 12, y0 + 8), f"{d.co.title()} {L}: {d.title}", size=22)
        big = _img(pics["body"], 2)
        sheet.paste(big, (x0 + 12, y0 + 40), big)
        one = _img(pics["body"], 1)
        sheet.paste(one, (x0 + 12 + 262, y0 + 40), one)
        for k in range(4):
            f = _img(pics["face"][k], 2 if k == 0 else 1)
            if k == 0:
                sheet.paste(f, (x0 + 12 + 262 + 134, y0 + 40), f)
            else:
                sheet.paste(f, (x0 + 12 + 262 + 134 + (k - 1) * 49, y0 + 40 + 100), f)
        m = _img(pics["mini"], 2)
        sheet.paste(m, (x0 + 12 + 262, y0 + 40 + 170), m)
        h = _img(pics["hud"], 2)
        sheet.paste(h, (x0 + 12 + 262 + 70, y0 + 40 + 170), h)
        for k, line in enumerate(rd.wrap(d.desc, 62)[:5]):
            rd.text(sheet, (x0 + 12, y0 + 40 + 330 + 17 * k), line, fill=(225, 228, 235), size=13)
        # in context: the CO select grid with real faces around it, and the HUD strip
        ctx = Image.new("RGB", (cw - 36, 120), (36, 40, 52))
        reals = real_faces(CONTEXT[:7])
        xs = 0
        for i, (who, face, hud, body) in enumerate(reals):
            if i == 3:
                f = _img(pics["face"][0], 1)
                ctx.paste(f, (6 + i * 50, 4), f)
                xs = 1
            fi = _img(face, 1)
            ctx.paste(fi, (6 + (i + xs) * 50, 4), fi)
        for i, (who, face, hud, body) in enumerate(reals[:6]):
            hi = _img(hud, 1)
            ctx.paste(hi, (6 + (i + (1 if i >= 2 else 0)) * 40, 62), hi)
            if i == 1:
                hh = _img(pics["hud"], 1)
                ctx.paste(hh, (6 + 2 * 40, 62), hh)
        rd.text(ctx, (6, 98), "CO select faces and HUD faces next to AW2's own (1x)", fill=(170, 176, 190), size=11)
        sheet.paste(ctx, (x0 + 12, y0 + 40 + 330 + 17 * 5 + 6))
        # the CO page: real figures beside ours, at the game's size
        page = Image.new("RGB", (cw - 36, 164), (36, 40, 52))
        reals = real_faces(["aw2:hawke", "aw2:sonja", "aw2:kanbei"])
        order = [reals[0], reals[1], None, reals[2]]
        for i, r in enumerate(order):
            im = _img(pics["body"], 1) if r is None else _img(r[3], 1)
            page.paste(im, (4 + i * 124, 2), im)
        rd.text(page, (4, 148), "CO page figures (128 x 160, 1x): ours third", fill=(170, 176, 190), size=11)
        sheet.paste(page, (x0 + 12, y0 + 40 + 330 + 17 * 5 + 6 + 126))
    return sheet


def layers_sheet(design, scale=3):
    """The figure as it is built: the back layer (cloak, hair), the torso and arms, the head, the front pieces, and the result."""
    stages = ("back", "torso", "head", "front")
    out = []
    for k in range(len(stages)):
        fig, mug = D.build(design, "normal", upto=stages[k])
        out.append(rd.to_image(RPic(fig, design.colours).px, scale, rd.BG))
    full = rd.to_image(make(design)[0]["body"].px, scale, rd.BG)
    out.append(full)
    sheet = Image.new("RGB", (sum(i.width for i in out) + 12 * len(out), out[0].height + 28), rd.BG)
    x = 6
    for name, im in zip(stages + ("result (15 colours)",), out):
        sheet.paste(im, (x, 24))
        rd.text(sheet, (x, 4), name, size=13)
        x += im.width + 12
    return sheet
