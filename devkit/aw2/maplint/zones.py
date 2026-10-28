"""Where Black Hole's inventions fire (docs/AW2.md "Firing zones": `cpu_inv_firing_zones_are_the_games`, measured by `bh_act5_m29_laser_probe` / `..._cannon_reach_probe`):
a Laser its whole row and column, a minicannon four cells in its facing (S down, N up, W left, E right), a Black Cannon a cone of ten rows widening by one cell a side from the middle
of its facing edge (v down, n up), the Deathray the three columns below it (the footprint's, to the bottom edge). Every unit of any army in a zone is hit on Black Hole's turn:
a mission must start with nobody in one (rule IV02, `Canvas.clear_fire_lines`)."""

MINI = {"S": (0, 1), "N": (0, -1), "W": (-1, 0), "E": (1, 0)}


def zone(ch, x, y, w, h):
    """The set of cells (x, y) the invention `ch` anchored at (x, y) fires on, on a w x h map."""
    cells = set()
    if ch == "L":
        cells |= {(i, y) for i in range(w)} | {(x, j) for j in range(h)}
    elif ch in MINI:
        dx, dy = MINI[ch]
        cells |= {(x + dx * k, y + dy * k) for k in range(1, 5)}
    elif ch in "vn":
        sgn = 1 if ch == "v" else -1
        for i in range(10):
            yy = y + sgn * (2 + i)
            cells |= {(xx, yy) for xx in range(x - 1 - i, x + 2 + i)}
    elif ch == "D":
        cells |= {(xx, yy) for xx in range(x - 1, x + 2) for yy in range(y + 2, h)}
    return {(a, b) for a, b in cells if 0 <= a < w and 0 <= b < h}


def zones_of(text):
    """{cell: [(invention char, x, y)]} for every cell some invention of the map's text rows fires on."""
    h, w = len(text), len(text[0])
    out = {}
    for y, row in enumerate(text):
        for x, ch in enumerate(row):
            if ch in "LSNWEvnD":
                for c in zone(ch, x, y, w, h):
                    out.setdefault(c, []).append((ch, x, y))
    return out
