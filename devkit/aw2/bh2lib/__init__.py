"""The BH2 Campaign's map kit (docs/dev/bh2-maps.md): mission table, review pictures (full map with units and labels, fog view, contact sheet), the world-map flag
check and the feature coverage report. Maps come from `five/bh2/spec/bh2_NN.py` (`aw2dev maps gen --campaign bh2`)."""
import re
from pathlib import Path

from .. import cfg

# mission number -> (map name, title). Missions are added as their maps are built.
MISSIONS = {
    1: ("bh2_01", "Black Insight"),
    2: ("bh2_02", "The Quartermaster's Crate"),
    3: ("bh2_03", "Iron Ledger"),
    4: ("bh2_04", "Talons"),
    5: ("bh2_05", "Evergreen in Exile"),
    6: ("bh2_06", "Paper Lanterns"),
    7: ("bh2_07", "Comet Highway"),
    8: ("bh2_08", "Black Lanterns"),
    9: ("bh2_09", "The Table"),
    10: ("bh2_10", "Two Tides"),
}
FRONT2 = {4: "bh2_04b", 10: "bh2_10b"}          # a two-front mission's second map

# game colour id -> RGB (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole)
COLOUR = {1: (240, 130, 30), 2: (60, 110, 240), 3: (50, 170, 70), 4: (240, 210, 40), 5: (140, 60, 190)}
COLOUR_NAME = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}
SRC = cfg.REPO / "tango-gamesupport-aw2" / "src"


def mission_of(name):
    for n, (m, t) in MISSIONS.items():
        if m == name:
            return n
    for n, m in FRONT2.items():
        if m == name:
            return n
    return None


def maps():
    """The BH2 maps as MapData (needs the AW2 ROM, read only)."""
    from ..maplint import load
    return {m.name: m for m in load.bh2_maps()}


# ------------------------------------------------------------------ world-map flags

def flags():
    """(mission, region, x, y) from `world_picture.rs` BH2_FLAGS (the Rust constant is the one source)."""
    text = (SRC / "world_picture.rs").read_text()
    body = re.search(r"BH2_FLAGS: &\[\(u8, u8, i16, i16\)\] = &\[(.*?)\];", text, re.S).group(1)
    return [tuple(int(v) for v in t) for t in re.findall(r"\((\d+),\s*(\d+),\s*(-?\d+),\s*(-?\d+)\)", body)]


def check_flags():
    """Problems (a list of strings): a flag on the sea or outside its nation's mask. The plan: M1, M2 and M26 on Black Hole's island, M3..M5 in Green Earth, M6..M10 in Yellow Comet."""
    from ..worldmaplib import tool
    m, _ = tool.load("bh2")
    out = []
    home = {1: 5, 2: 5, 26: 5, 3: 3, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4, 10: 4}
    seen = set()
    for mission, region, x, y in flags():
        seen.add(mission)
        if not (0 <= x < m.width and 0 <= y < m.height):
            out.append(f"M{mission}: flag ({x}, {y}) is off the map")
            continue
        at = int(m.mask[y, x])
        if at == 0:
            out.append(f"M{mission}: flag ({x}, {y}) is on the sea, not on land")
        elif at != region:
            out.append(f"M{mission}: flag ({x}, {y}) lies in {m.region_names[at]}, not in {m.region_names[region]}")
        if mission in home and region != home[mission]:
            out.append(f"M{mission}: flag is declared for {m.region_names[region]}, the plan puts it in {m.region_names[home[mission]]}")
        # (a flag needs breathing room: not on the rim of its country)
        patch = m.mask[max(0, y - 2): y + 3, max(0, x - 2): x + 3]
        if not (patch == region).all():
            out.append(f"M{mission}: flag ({x}, {y}) is within 2 pixels of another nation or the sea")
    for mission in home:
        if mission not in seen:
            out.append(f"M{mission} has no flag")
    return out


# ------------------------------------------------------------------ feature coverage

FEATURES = [
    ("HQ", "property", "H"), ("base", "property", "B"), ("city", "property", "C"), ("airport", "property", "A"), ("port", "property", "P"),
    ("Com Tower", "property", "T"), ("missile silo", "terrain", "M"),
    ("road", "terrain", "R"), ("river", "terrain", "-"), ("bridge", "terrain", "="), ("shoal", "terrain", ","), ("reef", "terrain", "r"), ("wood", "terrain", "f"),
    ("mountain", "terrain", "^"), ("pipe", "terrain", "I"), ("pipe seam", "terrain", "Z"),
]
INVENTIONS = [("Black Factory", "F"), ("Laser", "L"), ("minicannon", "SNWE"), ("Black Cannon", "vn"), ("Black Crystal", "X"), ("Black Obelisk", "O"), ("Deathray", "D")]


def feature_counts(m):
    """{feature name: count} of one MapData: properties and terrain by tile, inventions by their anchor character in the text rows, second HQ (Q)."""
    from ..maplint.terrain import terrain
    T = terrain()
    out = {}
    for row in m.tiles:
        for t in row:
            c = T.ch(t)
            for name, _, ch in FEATURES:
                if c == ch:
                    out[name] = out.get(name, 0) + 1
    for row in (m.text or []):
        for ch in row:
            for name, chars in INVENTIONS:
                if ch in chars:
                    out[name] = out.get(name, 0) + 1
            if ch == "Q":
                out["second HQ"] = out.get("second HQ", 0) + 1
    # a footprint's `#` and the neutral city 'c' are not features; unit kinds are listed apart
    return out


def features_table(ms):
    """Markdown: one row per map and column per feature, then a coverage line (which features no map uses yet)."""
    names = [f[0] for f in FEATURES] + [i[0] for i in INVENTIONS] + ["second HQ"]
    counts = {m.name: feature_counts(m) for m in ms}
    used = [n for n in names if any(counts[m.name].get(n) for m in ms)]
    lines = ["| map | size | " + " | ".join(used) + " |", "|---|---|" + "---|" * len(used)]
    for m in ms:
        lines.append(f"| {m.name} | {len(m.tiles[0])}x{len(m.tiles)} | " + " | ".join(str(counts[m.name].get(n, "")) for n in used) + " |")
    missing = [n for n in names if n not in used]
    lines.append("")
    lines.append("Every feature on at least one map: " + ("yes" if not missing else "no; unused so far: " + ", ".join(missing)))
    return "\n".join(lines), counts, missing


# ------------------------------------------------------------------ looks and weather (the owner's rule: vary them, neighbouring missions never look alike)

LOOK_NAMES = {0: "normal", 1: "snow", 2: "desert", 3: "wasteland"}


def looks():
    """[(mission number, key, look name, weather name, fog)] read from `bh2_campaign.rs` (`m.look`, `m.weather`, `m.fog`), in mission order."""
    text = (SRC / "bh2_campaign.rs").read_text()
    fns = list(re.finditer(r"^fn (bh2_\d\d)\(\) -> MissionDef \{", text, re.M))
    out = []
    for i, f in enumerate(fns):
        body = text[f.start(): fns[i + 1].start() if i + 1 < len(fns) else len(text)]
        lk = re.search(r"m\.look = (\d)", body)
        wt = re.search(r"m\.weather = Weather::(\w+)", body)
        n = int(f.group(1)[4:])
        out.append((n, f.group(1), LOOK_NAMES[int(lk.group(1))] if lk else "normal", wt.group(1).lower() if wt else "clear", bool(re.search(r"m\.fog = true", body))))
    return out


def check_looks():
    """Warnings (strings): two consecutive missions with the same look, weather and fog."""
    rows = looks()
    out = []
    for a, b in zip(rows, rows[1:]):
        if a[2:] == b[2:]:
            out.append(f"M{a[0]} and M{b[0]} look alike: both {a[2]}, {a[3]}{', fog' if a[4] else ''}")
    return out


def ground_colour(png):
    """The dominant colour of a game picture's ground (units and buildings are small: the most common colour after quantising to 8 levels a channel, averaged over its bin)."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGB")).reshape(-1, 3).astype(int)
    q = a // 32
    key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    top = np.bincount(key).argmax()
    return tuple(int(v) for v in a[key == top].mean(axis=0))


def check_pictures(raw, near=40, near2=22):
    """Warnings comparing the ground colours of the game's own pictures (`aw2dev maps boot --campaign bh2`): two consecutive missions whose ground colours are within `near` (RGB distance) and
    whose weather and fog match, or two missions with one between them within `near2` (their grounds are the same sand). Returns (table lines, warnings)."""
    raw = Path(raw)
    cols, lines, warns = {}, [], []
    for n, key, look, weather, fog in looks():
        f = next((raw / f"m{n}_{v}.png" for v in ("full", "fogoff") if (raw / f"m{n}_{v}.png").exists()), None)
        if f:
            cols[n] = (ground_colour(f), look, weather, fog)
            lines.append(f"M{n} {look:<9} {weather:<9}{' fog' if fog else '    '} ground {cols[n][0]}")
    ns = sorted(cols)
    dist = lambda a, b: sum((x - y) ** 2 for x, y in zip(cols[a][0], cols[b][0])) ** 0.5
    for a, b in zip(ns, ns[1:]):
        d = dist(a, b)
        if d < near and cols[a][2:] == cols[b][2:]:
            warns.append(f"M{a} and M{b} look alike in the game: ground colours {d:.0f} apart (under {near}) with the same weather and fog")
    for a, b in zip(ns, ns[2:]):
        d = dist(a, b)
        if d < near2 and cols[a][2:] == cols[b][2:]:
            warns.append(f"M{a} and M{b} (one mission between) have the same ground: {d:.0f} apart (under {near2}) with the same weather and fog")
    return lines, warns
