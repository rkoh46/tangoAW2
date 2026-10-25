"""Recolour-based COs (`[portrait] base` + `[portrait.recolour]`, docs/dev/co-kit.md "Recolour-based COs"): they have no picture to import and no committed art, so
`aw2dev co portrait import` checks their recolour instead: the table is valid, and on the donor's palette (Dual Strike's, read from the player's .nds) every listed entry becomes
the given colour in every colour scheme, every other entry stays the donor's, and every listed entry is drawn on the donor's large figure (a recolour that shows). The 555
conversion is `ds_co_art::Recolour::parse`'s (each channel `>> 3`)."""
from . import data

DONORS = {"andy": 1}         # portrait.base -> Dual Strike CO id (roms.DS_NAMES)


def is_recolour(d):
    return bool(d.get("portrait", {}).get("base"))


def table(d):
    """-> {index: BGR555} as the engine parses it."""
    out = {}
    for k, v in d["portrait"].get("recolour", {}).items():
        n = int(str(v), 16)
        r, g, b = (n >> 16) & 255, (n >> 8) & 255, n & 255
        out[int(k)] = r >> 3 | (g >> 3) << 5 | (b >> 3) << 10
    return out


def apply(palettes, tab):
    """palettes: the donor's colour schemes (lists of 16 BGR555). -> recoloured copies."""
    return [[tab.get(i, c) for i, c in enumerate(p)] for p in palettes]


def check(co, d, donor=None):
    """-> (problems, summary). `donor`: a roms.Portrait (default: read from the .nds when it is there; without it only the data is checked)."""
    bad = data.problems({co: d}, {})
    if bad:
        return bad, "the recolour table is invalid"
    base = d["portrait"]["base"]
    tab = table(d)
    if donor is None:
        from .. import cfg
        if base not in DONORS or not cfg.ds_rom().exists():
            return [], f"recolour of {base}: {len(tab)} entries valid (no Dual Strike ROM: the output is not checked)"
        from . import roms
        donor = roms.ds_portrait(DONORS[base])
    out = apply(donor.palettes, tab)
    used = {v for row in donor.body for v in row}
    for s, (old, new) in enumerate(zip(donor.palettes, out)):
        for i in range(16):
            want = tab.get(i, old[i])
            if new[i] != want:
                bad.append(f"{co}: scheme {s} entry {i} is {new[i]:#06x}, want {want:#06x}")
    for i in sorted(tab):
        if i not in used:
            bad.append(f"{co}: recolour entry {i} is not drawn on {base}'s large figure (the recolour would not show)")
        elif all(p[i] == tab[i] for p in donor.palettes):
            bad.append(f"{co}: recolour entry {i} is {base}'s own colour in every scheme (no change)")
    return bad, f"recolour of {base}: {len(tab)} of 16 entries replaced in {len(out)} colour schemes, all drawn on the figure"
