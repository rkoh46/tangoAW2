"""Facts read from the player's AW2 ROM at run time (never stored): map ids by name (from the map audit) and a map's HQ cells (from its tiles)."""
import re, struct, subprocess
from . import cfg, util

MAP_HEADERS = 0x085C77A0
TERRAIN_CLASSES = 0x080C1BC4
HQ_KIND = 8


def _lz(rom, ptr):
    off = ptr & 0x1FFFFFF
    n = struct.unpack_from("<I", rom, off)[0] >> 8
    out, i = bytearray(), off + 4
    while len(out) < n:
        f = rom[i]
        i += 1
        for b in range(8):
            if len(out) >= n:
                break
            if f & (0x80 >> b):
                a, c = rom[i], rom[i + 1]
                i += 2
                ln, d = (a >> 4) + 3, ((a & 15) << 8 | c) + 1
                for _ in range(ln):
                    out.append(out[-d])
            else:
                out.append(rom[i])
                i += 1
    return bytes(out)


def hq_cells(map_id, rom=None):
    """{army: (x, y)} of the HQ tiles of the ROM's own map `map_id` (AW2's table; tangoAW2's added maps are not in the ROM)."""
    rom = rom or cfg.aw2_rom().read_bytes()
    tiles = struct.unpack_from("<I", rom, MAP_HEADERS - 0x08000000 + 0x5C * map_id)[0]
    raw = _lz(rom, tiles)
    w, h = raw[0], raw[1]
    cls = rom[TERRAIN_CLASSES - 0x08000000:TERRAIN_CLASSES - 0x08000000 + 0x400]
    out = {}
    for y in range(h):
        for x in range(w):
            c = cls[struct.unpack_from("<H", raw, 2 + 2 * (y * w + x))[0]]
            if c & 0x1F == HQ_KIND and c >> 5:
                out[c >> 5] = (x, y)
    return out


def map_id(name, armies):
    """The id of the map `name` with `armies` armies, from the audit of the console's own list (aw2_map_audit)."""
    binary = util.example_bin("aw2_map_audit")
    r = subprocess.run([str(binary), str(cfg.aw2_rom())], capture_output=True, text=True, cwd=cfg.REPO)
    for l in r.stdout.splitlines():
        m = re.match(r"%dP\s+(?:predeployed\s+)?([0-9a-f]{2})\s+(.+?)\s{2,}" % armies, l)
        if m and m.group(2).strip() == name:
            return int(m.group(1), 16)
    util.die(f"map {name} ({armies}P) not found in the map audit")


def pick_index(name, armies, ds=True):
    """Row of map `name` in a room's plain list for `armies` players (the order of the console's own list, from the audit; with the pack when `ds`)."""
    import os
    binary = util.example_bin("aw2_map_audit")
    env = dict(os.environ)
    if ds:
        env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    r = subprocess.run([str(binary), str(cfg.aw2_rom())], capture_output=True, text=True, cwd=cfg.REPO, env=env)
    rows = []
    for l in r.stdout.splitlines():
        m = re.match(r"%dP\s{2,}([0-9a-f]{2})\s+(.+?)\s{2,}" % armies, l)     # (plain rows have no `predeployed` word)
        if m:
            rows.append(m.group(2).strip())
    if name not in rows:
        util.die(f"map {name} is not in the {armies}P plain list: {rows}")
    return rows.index(name)
