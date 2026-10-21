"""Tile guard: the VRAM tile ranges a screen needs intact (font, UI) must equal the known-good dump's. On a violation it lists the tiles and which
BG / OAM entries show them. Ranges are byte ranges of VRAM in the catalogue (`guard = [{name, range=[start, end]}]`); `aw2dev gfx blame` finds who wrote."""
from ..vram import Dump

NAME = "tiles"


def run(ctx):
    out = []
    for g in ctx.screen.get("guard", []):
        a, b = g["range"]
        for vname, d in ctx.renders.items():
            gd = ctx.golden.get(vname)
            cur, ref = d / f"{g['dump']}.vram", (gd / f"{g['dump']}.vram" if gd else None)
            if not cur.exists():
                cur = d / g["dump"]          # offline_tabs writes a directory of .bin files
            if ref is not None and not ref.exists():
                ref = gd / g["dump"]
            if not cur.exists() or ref is None or not ref.exists():
                if ref is None or not ref.exists():
                    out.append({"detector": NAME, "shot": f"{vname}/{g['dump']}", "severity": "warn", "msg": "no golden VRAM dump to guard against"})
                continue
            X, Y = Dump.load(cur), Dump.load(ref)
            bad = [t for t in range(a // 32, b // 32) if X.vram[32 * t:32 * t + 32] != Y.vram[32 * t:32 * t + 32]]
            if bad:
                used = sorted({s["index"] for s in X.sprites() if any(s["tile"] <= (t - 0x4000 // 32) < s["tile"] + (s["w"] // 8) * (s["h"] // 8) for t in bad)})
                out.append({"detector": NAME, "shot": f"{vname}/{g['dump']}", "severity": "fail",
                            "msg": f"{g.get('name', 'guarded tiles')}: {len(bad)} tiles overwritten ({bad[:8]}{'...' if len(bad) > 8 else ''}), VRAM {a:#x}..{b:#x}" + (f"; OAM entries showing them: {used[:8]}" if used else "")})
    return out
