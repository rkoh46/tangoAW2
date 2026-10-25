"""The Emerald Sun Campaign's world map (docs/dev/es-campaign.md "The world map"): its sixteen flags on Dual Strike's Omega Land (480 x 240 map pixels, `es_campaign::region`), in story order,
each on land, apart from the others, inside the cursor's limits, and every mission opened by the one before. Read from the Rust sources; the land test needs the player's Dual Strike .nds."""
import re
from .. import cfg

SRC = lambda: cfg.REPO / "tango-gamesupport-aw2" / "src"
LIMIT = (463, 223)          # ds_worldmap: the cursor's last map position on Omega Land
MARGIN = 8
MIN_APART = 16              # a flag is 16 px wide


def nodes():
    """[(x, y)] of the sixteen missions in order: es_campaign::region ACT1..ACT4."""
    text = (SRC() / "es_campaign.rs").read_text()
    body = text[text.index("pub mod region"):]
    body = body[:body.index("\n}\n")]
    out = []
    for act in range(1, 5):
        m = re.search(rf"ACT{act}: \[\(i16, i16\); 4\] = \[(.*?)\];", body, re.S)
        out += [(int(x), int(y)) for x, y in re.findall(r"\((\d+),\s*(\d+)\)", m.group(1))]
    return out


def needs():
    """{mission key: what its `m.needs` says} from the acts: ['Start'] or the keys it needs."""
    out = {}
    for n in range(1, 5):
        text = (SRC() / f"es_act{n}.rs").read_text()
        for fn in re.finditer(r'fn (es\d\d)\(\) -> MissionDef \{(.*?)\n\}\n', text, re.S):
            m = re.search(r"m\.needs = Needs::(Start|All\(vec!\[(.*?)\]\))", fn.group(2))
            out[fn.group(1)] = ["Start"] if m.group(1) == "Start" else re.findall(r'"(es\d\d)"', m.group(2))
    return out


def water(rgb5):
    """A sea pixel of Omega Land's picture (5-bit channels): blue clearly above red. Land is yellow, green, grey or white."""
    r, g, b = rgb5
    return b - r > 4


def problems(points, picture=None, needed=None):
    """[str]: what is wrong with the flags. `picture`: rows of (r, g, b) 5-bit (the land test is skipped without it); `needed`: `needs()`."""
    bad = []
    if len(points) != 16:
        bad.append(f"{len(points)} flags (16 wanted)")
    for k, (x, y) in enumerate(points):
        if not (MARGIN <= x <= LIMIT[0] - MARGIN and MARGIN <= y <= LIMIT[1] - MARGIN):
            bad.append(f"M{k + 1} at ({x}, {y}) is outside the map's {LIMIT[0]} x {LIMIT[1]} (with {MARGIN} px of margin)")
        for j in range(k):
            ox, oy = points[j]
            if max(abs(x - ox), abs(y - oy)) < MIN_APART:
                bad.append(f"M{k + 1} and M{j + 1} are {max(abs(x - ox), abs(y - oy))} px apart (flags are 16 px wide: at least {MIN_APART})")
        if picture is not None:
            cells = [picture[min(239, max(0, y + dy))][min(479, max(0, x + dx))] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
            avg = tuple(sum(c[i] for c in cells) / 9 for i in range(3))
            if water(avg):
                bad.append(f"M{k + 1} at ({x}, {y}) is in the sea (Omega Land's picture there: {tuple(round(v) for v in avg)})")
    if needed is not None:
        for k in range(1, 17):
            key = f"es{k:02d}"
            want = ["Start"] if k == 1 else [f"es{k - 1:02d}"]
            if needed.get(key) != want:
                bad.append(f"{key} needs {needed.get(key)} (the story order wants {want})")
    return bad


def picture():
    """Omega Land's picture from the player's Dual Strike .nds, or None."""
    import sys
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    try:
        from aw2test import worldmap, rom
        return worldmap.ds_picture(rom.DualStrike())
    except Exception:
        return None


# --- the review sheet (`aw2dev campaign worldmap`) -------------------------------------------------------------------------------------------------------------

STAGES = (("start", "start: M1 open"), ("mid", "mid-campaign: M1..M8 won, M9 open"), ("before_m16", "before M16: M1..M15 won"))
STATES = (("locked", "locked: no flag"), ("open", "open"), ("current", "current: cursor on the open flag"), ("cleared", "cleared (starred flag)"), ("last", "the last mission's marker"))
UNLOCKS = (4, 8, 12, 15)


def _bmp(path):
    from PIL import Image
    return Image.open(path).convert("RGB")


def sheet(review, runs, out):
    """es_world_map.png: the map at three stages with every node numbered and labelled, a close-up of each flag state, and unlock moments before and after a win.
    `review`: AW2TEST_REVIEW_DIR of the tests (es_world_map_<stage>.png, es_unlock_<n>_*.bmp); `runs`: tools/aw2test/out/ds (cursor shots)."""
    from PIL import Image, ImageDraw
    from ..colib import render as rd
    pts = nodes()
    S = 3
    cw = 480 * S + 40
    imgs = {k: _bmp(review / f"es_world_map_{k}.png") for k, _ in STAGES}
    names = ["Landfall", "Testudo", "The Wall", "Second Legion", "Dust and Wheels", "Tribute", "Mare Nostrum", "Hammer and Anvil", "Grain Ships", "Quiet Pass", "Treasure Train", "Siege of Iron", "Free Port",
             "Varro's Gambit", "Pax Romana", "Sol Invictus"]
    H = 70 + len(STAGES) * (240 * S + 50) + 330 + 60 + 2 * 230 + 40
    sh = Image.new("RGB", (cw, H), rd.BG)
    rd.text(sh, (14, 10), "Emerald Sun Campaign: the world map is Dual Strike's Omega Land. 16 flags in story order (Aurea's home island is the south-west island, off the nodes).", size=17)
    rd.text(sh, (14, 36), "States: AW2's white pennant = open, starred flag = cleared, blue pennant = the last mission's marker; a locked mission has no flag (Dual Strike's map has no route lines and no region colours).", size=13)
    y = 70
    for k, label in STAGES:
        rd.text(sh, (14, y), label, size=15)
        big = imgs[k].resize((480 * S, 240 * S), Image.NEAREST)
        d = ImageDraw.Draw(big)
        for i, (x, yy) in enumerate(pts):
            label = f"M{i + 1} {names[i]}"
            w = d.textlength(label, font=rd.font(15))
            lx = x * S + 12 if x * S + 12 + w < 480 * S - 6 else x * S - 8 - w
            d.text((lx, yy * S - 24), label, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0), font=rd.font(15))
        d.text((15 * S, 198 * S), "Aurea (home island)", fill=(255, 240, 120), stroke_width=2, stroke_fill=(0, 0, 0), font=rd.font(15))
        sh.paste(big, (20, y + 22))
        y += 240 * S + 50
    rd.text(sh, (14, y), "Close-ups of each flag state (the map's own pixels, 6x)", size=15)
    crops = {
        "locked": (imgs["start"], pts[11]), "open": (imgs["mid"], pts[8]), "cleared": (imgs["mid"], pts[0]), "last": (imgs["before_m16"], pts[15]),
        "current": (None, None),
    }
    x = 16
    for key, label in STATES:
        im, p = crops[key]
        if key == "current":
            cur = _bmp(runs / "es_world_map_stages" / "cursor_start.bmp")
            tile = cur.resize((360, 240), Image.NEAREST)
        else:
            tile = im.crop((p[0] - 20, p[1] - 20, p[0] + 20, p[1] + 20)).resize((240, 240), Image.NEAREST)
        sh.paste(tile, (x, y + 26))
        rd.text(sh, (x, y + 26 + tile.height + 4), label, size=12)
        x += tile.width + 16
    y += 300
    rd.text(sh, (14, y), "Unlock moments: before the win, right after it (the map returns), and settled (the next flag open, the cursor on it)", size=15)
    for row, group in enumerate((UNLOCKS[:2], UNLOCKS[2:])):
        x = 20
        for n in group:
            for tag in ("before", "after", "after2"):
                p = review / f"es_unlock_{n:02d}_{tag}.bmp"
                if p.exists():
                    t = _bmp(p).resize((228, 152), Image.NEAREST)
                    sh.paste(t, (x, y + 26))
                    rd.text(sh, (x, y + 26 + 156), f"M{n}: before the win" if tag == "before" else f"M{n} won: {'the map returns' if tag == 'after' else 'settled'}", size=11)
                x += 238
            x += 12
        y += 195
    y -= 195
    sh = sh.crop((0, 0, cw, y + 200))
    out.parent.mkdir(parents=True, exist_ok=True)
    sh.save(out)
    return out
