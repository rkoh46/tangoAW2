"""Where an army's colours come from: renders the catalogue's screens with two different armies, finds the palette banks that differ, searches
AW2's ROM for each bank's colours and says which of those ROM palettes the skin does not patch yet (docs/dev/army-packs.md "Finding sources")."""
import struct
from pathlib import Path
from . import Rom, dump
from .. import cfg, harness


def banks(vram_path):
    v = Path(vram_path).read_bytes()
    pal = struct.unpack_from("<512H", v, 0x18000)
    return [pal[i * 16:(i + 1) * 16] for i in range(32)]


def search(rom_bytes, vals):
    pat = struct.pack(f"<{len(vals)}H", *vals)
    out, i = [], 0
    while True:
        i = rom_bytes.find(pat, i)
        if i < 0:
            return out
        out.append(0x08000000 + i)
        i += 2


def covered(addr, spans):
    return any(a <= addr < a + n for a, n in spans)


def run(scenarios_, ids_a=(1, 2), ids_b=(3, 4), out=None, ds=False, say=print):
    from . import scenarios
    out = Path(out or cfg.work("armyskin", "sources"))
    out.mkdir(parents=True, exist_ok=True)
    rom = cfg.aw2_rom().read_bytes()
    spans = set()
    for h in range(1, 6):
        for p in dump(h)["patches"]:
            if p["what"] not in ("text", "army name"):
                spans.add((p["addr"], len(p["hex"]) // 2))
    unknown, report = {}, []
    for n in scenarios_:
        sc = scenarios.SCENARIOS[n]
        if sc["five"] or len(sc["ids"]) != 2:
            continue
        dirs = {}
        for tag, ids in (("a", list(ids_a)), ("b", list(ids_b))):
            d = out / f"{n}_{tag}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "script.txt").write_text(scenarios.script(n, ids, vram=True))
            harness.run_script(d / "script.txt", d, ds=ds)
            dirs[tag] = d
        for shot in sc["shots"]:
            try:
                ba, bb = banks(dirs["a"] / f"{shot}.vram"), banks(dirs["b"] / f"{shot}.vram")
            except FileNotFoundError:
                continue
            for k, (ra, rb) in enumerate(zip(ba, bb)):
                if ra != rb:
                    # the ROM palettes holding bank colours of army A (idx 2..5 as a signature; 4 in a row)
                    for name, row in (("a", ra), ("b", rb)):
                        for sig_at in range(1, 13):
                            sig = list(row[sig_at:sig_at + 4])
                            if len(set(sig)) < 3:
                                continue
                            hits = search(rom, sig)
                            full = []
                            for h in hits:
                                base = h - 2 * sig_at
                                have = struct.unpack_from("<16H", rom, base - 0x08000000) if base >= 0x08000000 else None
                                # (the whole palette, bar a colour the game changes itself: the outline, the pulse)
                                if have and sum(1 for x, y in zip(have, row) if x == y) >= 14:
                                    full.append(base)
                            if full:
                                for base in full:
                                    if not covered(base, spans):
                                        unknown.setdefault(base, set()).add(f"{n}/{shot} bank {'BG' if k < 16 else 'OBJ'}{k % 16}")
                                break
    for base in sorted(unknown):
        report.append(f"  unpatched ROM palette {base:#010x}: {', '.join(sorted(unknown[base])[:4])}")
    return report
