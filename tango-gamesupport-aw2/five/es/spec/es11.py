"""M11 The Treasure Train (Act III): Livia's four APCs run from the harbour along the long road to the Senate's relay camp; the ford, a ruin and two marauder camps stand between."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es11", 26, 12)
    m.header(armies=3, colours=(BH, YC, YC), team=[1, 2, 2], objective=[1],
             comment="M11 The Treasure Train (escort): the four APCs apc1..apc4 start at the harbour (3,4)..(3,7) and must reach the relay camp rectangle (22,5)-(25,7) at the east end; "
                     "the camp's city c (24,6) is neutral on the map and the mission gives it to the player. The road y6 crosses a forest (x7..11), the river x14 at ONE bridge (the ford, (14,6)) "
                     "and a ruin (x15..19). Lash's HQ 2 (23,1) is the NE camp, Flak's HQ 3 (23,10) the SE camp. "
                     "Threat/answer: marauder Tanks and Md Tanks at the ford -> own Md Tanks/Tanks and Artillery hit them from the west bank (the river keeps vehicles off), Missiles are not needed; "
                     "Rockets and Artillery covering the ford and ruin (hold) -> Recon sees them, Tanks rush inside their minimum range, Artillery duels from the forest cover; "
                     "Infantry and Mechs wade the river (foot units cross it) to flank the ford; Anti-Air only for the AA tank the player owns (no enemy aircraft on this map). "
                     "Player start: APC4 RECON3 TANK3 MDT2 ART2 MECH2 INF2 AA1 (19 units), funds 3000, one base. Lash: INF3 TANK3 RECON2 ART1 MECH2 (11); Flak: MDT2 TANK2 INF3 ROCK1 (8). "
                     "Marauders advance; Flak's Md Tanks (15,5),(15,7), Rockets (17,7) and Lash's Artillery (16,5) hold the ford.")
    # the western harbour: sea, a shoal strip, two ports
    m.rect("~", 0, 0, 1, 11)
    m.rect(",", 2, 0, 2, 11)
    m.put("P", 2, 3).put("P", 2, 8)
    m.put("~", 1, 3).put("~", 1, 8)
    # the forest on the road, the bluffs around the ruin and the camps
    m.rect("f", 7, 2, 11, 9)
    m.rect(".", 7, 6, 11, 6)
    m.rect("^", 15, 0, 19, 2).rect("^", 15, 9, 19, 11)
    m.rect("^", 12, 0, 13, 0).rect("^", 12, 11, 13, 11)
    # the river (x14) from the top edge to the bottom edge, one bridge: the ford
    m.river([(14, 0), (14, 11)])
    # the ruin: broken walls of wood on the plain
    m.puts("f", [(16, 4), (17, 4), (18, 5), (16, 8), (17, 8), (18, 7), (19, 4), (19, 8), (17, 3), (17, 9)])
    # the road
    m.road([(3, 6), (23, 6)])
    m.bridge(14, 6)
    # the marauders' camps (HQ and base each) with their branch roads
    m.put("2", 23, 1).put("B", 21, 2).put("C", 22, 3).put("C", 20, 1)
    m.put("3", 23, 10).put("B", 21, 9).put("C", 22, 8).put("C", 20, 10)
    m.road([(21, 3), (21, 5)]).road([(21, 7), (21, 8)])
    # the relay camp (neutral city; the mission hands it to the player) and neutral cities along the road
    m.put("c", 24, 6).put("c", 6, 5).put("c", 10, 4).put("c", 12, 8)
    # the player's town: HQ, base, cities
    m.put("1", 4, 5).put("B", 4, 7).put("C", 5, 3).put("C", 5, 9)

    taken = set()

    def spot(cx, cy, n, lo, hi, kinds=".fR"):
        out = []
        for r in range(0, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and m.inside(x, y) and m.get(x, y) in kinds and (x, y) not in taken and (x, y) not in out:
                        out.append((x, y))
                        if len(out) == n:
                            taken.update(out)
                            return out
        raise RuntimeError("no room")

    def put(army, kind, cx, cy, n=1, lo=(0, 0), hi=(99, 99), kinds=".fR", **kw):
        for x, y in spot(cx, cy, n, lo, hi, kinds):
            m.unit(army, kind, x, y, **kw)

    for i, y in enumerate((4, 5, 6, 7)):
        m.unit(1, APC, 3, y, name=f"apc{i + 1}"); taken.add((3, y))
    P = dict(lo=(3, 1), hi=(7, 10))
    put(1, RECON, 6, 6, 3, **P); put(1, TANK, 6, 4, 3, **P); put(1, MDT, 6, 8, 2, **P)
    put(1, ART, 5, 6, 2, **P); put(1, MECH, 5, 8, 2, **P); put(1, INF, 5, 4, 2, **P); put(1, AA, 4, 6, **P)
    taken.update([(15, 5), (15, 7), (17, 7), (16, 5)])
    # Flak and Lash hold the ford; the rest advance from the camps
    m.unit(3, MDT, 15, 5, hold=True).unit(3, MDT, 15, 7, hold=True).unit(3, ROCK, 17, 7, hold=True).unit(2, ART, 16, 5, hold=True)
    put(2, INF, 21, 3, 3, lo=(19, 1), hi=(25, 4)); put(2, TANK, 20, 3, 3, lo=(18, 1), hi=(25, 5)); put(2, RECON, 22, 5, 2, lo=(19, 3), hi=(25, 5))
    put(2, MECH, 16, 6, 2, lo=(15, 5), hi=(19, 7))
    put(3, INF, 21, 9, 3, lo=(19, 8), hi=(25, 11)); put(3, TANK, 20, 8, 2, lo=(18, 7), hi=(25, 11))

    m.note("apc1", 3, 4, "convoy APC 1 (also apc2 (3,5), apc3 (3,6), apc4 (3,7)); must arrive in `camp`")
    m.note("hq1", 4, 5, "player HQ at the harbour, base (4,7), ports (2,3) and (2,8)")
    m.note("ford", 14, 6, "the only bridge over the river x14 (vehicles cross only here; foot units can wade)")
    m.note("camp_nw", 22, 5, "camp rectangle top-left").note("camp_se", 25, 7, "camp rectangle bottom-right; city c (24,6) neutral, give it to the player at start")
    m.note("ruin", 15, 3, "ruin: plain with wooden rubble x15..19, y3..9, bluffs of mountain north (y0..2) and south (y9..11)")
    m.note("forest", 7, 2, "forest x7..11, y2..9 around the road")
    m.note("hq2", 23, 1, "Lash's HQ (NE camp), branch road (21,3..5)").note("hq3", 23, 10, "Flak's HQ (SE camp), branch road (21,7..8)")
    m.note("road", 3, 6, "road y6 from (3,6) to (23,6): the convoy's path; bridge at (14,6)")
    m.note("ford_holders", 15, 5, "enemy holds: Flak MDT (15,5),(15,7), Flak ROCK (17,7), Lash ART (16,5)")
    return m
