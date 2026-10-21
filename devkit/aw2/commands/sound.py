"""aw2dev sound: song and sound-effect ids with names (docs/dev/campaign-scenes.md, skill aw2-add-music).

  sound list [--source aw2|ds|roles]   aw2: AW2's own song ids with what the ROM does with them (CO themes, event-script uses, scene roles);
                                       ds: Dual Strike's sequences by name (BGM_* / SE_*) from the .nds' sound archive, with the ones the pack converts;
                                       roles: the names a scene's `@SONG` may use (src/campaign_music.rs)
"""
import re, struct
from .. import cfg


def register(sub):
    s = sub.add_parser("sound", help="song and sound-effect ids with names (docs/dev/campaign-scenes.md)")
    ss = s.add_subparsers(dest="soundcmd", required=True)
    a = ss.add_parser("list", help="list songs")
    a.add_argument("--source", default="roles", choices=["aw2", "ds", "roles"])
    a.set_defaults(fn=lst)


CO = ["Nell", "Andy", "Max", "Olaf", "Sami", "Grit", "Kanbei", "Sonja", "Eagle", "Drake", "Sturm", "Flak", "Lash", "Adder", "Hawke", "Hachi", "Colin", "Jess", "Sensei"]
KNOWN = {400: "title", 404: "mission card (AW2)", 405: "mission card", 406: "mission card (BH, Dual Strike look)", 411: "Black Hole officers' scene", 413: "allies' scene",
         416: "staff roll setup", 417: "results", 205: "results rank", 220: "Sturm's citadel", 409: "Sturm's last words", 420: "final push", 421: "Green Earth scenes",
         422: "Yellow Comet scenes", 423: "Blue Moon scenes", 424: "world map", 425: "prologue", 25: "Orange Star in crisis", 0x1A3: "CO Power (Black Hole)", 0x1A4: "CO Power",
         0x199: "Super CO Power", 0x19A: "Super CO Power"}


def aw2_uses(rom):
    uses = {}
    for a in range(0, len(rom) - 16, 4):
        w0, w1, h8, ha, wc = struct.unpack_from("<IIHHI", rom, a)
        if w0 == 0x41 and w1 == 0 and ha == 0 and wc == 0 and 0 < h8 < 600:
            uses[h8] = uses.get(h8, 0) + 1
    return uses


def roles():
    src = (cfg.REPO / "tango-gamesupport-aw2" / "src" / "campaign_music.rs").read_text()
    return re.findall(r'\("(\w+)",\s*(Track::[^\n]*?),\s*"([^"]*)"\),', src)


def ds_names(path):
    nds = path.read_bytes()
    i = nds.find(b"SDAT")
    while i >= 0 and nds[i + 4:i + 6] != b"\xff\xfe":
        i = nds.find(b"SDAT", i + 1)
    if i < 0:
        return []
    sym = i + struct.unpack_from("<I", nds, i + 0x10)[0]
    base = sym
    rec = struct.unpack_from("<I", nds, sym + 8)[0]           # the seq record
    n = struct.unpack_from("<I", nds, base + rec)[0]
    out = []
    for k in range(n):
        off = struct.unpack_from("<I", nds, base + rec + 4 + 4 * k)[0]
        e = nds.index(b"\0", base + off)
        out.append(nds[base + off:e].decode("latin-1") if off else "")
    return out


def lst(a):
    if a.source == "roles":
        for n, t, d in roles():
            print(f"{n:12} {t:34} {d}")
        return 0
    if a.source == "aw2":
        rom = cfg.aw2_rom().read_bytes()
        uses = aw2_uses(rom)
        cos = {}
        for i, n in enumerate(CO):
            cos.setdefault(struct.unpack_from("<H", rom, 0x5D3DD0 + 0x104 * i + 4)[0], []).append(n + "'s theme")
        for sid in sorted(set(uses) | set(cos) | set(KNOWN)):
            what = ", ".join(cos.get(sid, []) + ([KNOWN[sid]] if sid in KNOWN else []))
            print(f"{sid:4}  {uses.get(sid, 0):3} event-script uses  {what}")
        return 0
    p = cfg.ds_rom()
    if not p.exists():
        print("no Dual Strike ROM")
        return 1
    for k, n in enumerate(ds_names(p)):
        print(f"{k:3}  {n}")
    return 0
