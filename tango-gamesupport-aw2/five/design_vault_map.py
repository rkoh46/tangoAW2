"""The Colonel's Vault (2P, 30x20; with the Dual Strike pack only): the BH
Campaign's secret mission map as a Versus map. Two halls mirrored left to
right round a harbour pool that opens to the north sea by a two-wide
channel; each hall has a vault of five cities, two bases, an airport, two
ports and two beaches on the pool, a Black Crystal, and a land road to the
other hall on each side of the pool, so every rule of the sea holds and both
armies start alike. Legend in map.py."""

ROWS = [
    "..............~~..............",
    "......C..^^^^^~~^^^^^..C......",
    "..f......^^^^^~~^^^^^......f..",
    "......f..^^^f^~~^f^^^..f......",
    "..C.......R...~~...R.......C..",
    ".f......f.R...~~...R.f......f.",
    "....C..C..R.~~~~~~.R..C..C....",
    "...CCC....R,~~~~~~,R....CCC...",
    "....C...C.RP~~~~~~PR.C...C....",
    ".C........R.~~~~~~.R........C.",
    "...1RRBRXRR.~~~~~~.RRXRBRR2...",
    "..........RP~~~~~~PR..........",
    "..C..f.A..R,~~~~~~,R..A.f..C..",
    "..fB...fC.R.~~~~~~.R.Cf...Bf..",
    ".....C..f.R........R.f..C.....",
    "...RRRRRRRRRRRRRRRRRRRRRRRR...",
    ".f........R........R........f.",
    "......RRRRRRRRRRRRRRRRRR......",
    ".C..f....................f..C.",
    ".......C..............C.......",
]


def draw(emit):
    ARMY = [1, 1, 2, 5, 6, 10, 23]
    emit("The Colonel's Vault", {1: ARMY, 2: ARMY}, [list(r) for r in ROWS], armies=2, tab=3, colours=(5, 4), look="pack")
