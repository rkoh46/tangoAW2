"""Text integrity: OCR the AW2-font strings in a region against the game's own glyphs. A glyph that matches nothing is garbled (`?`); with `expect`
every expected string must be read; with `in_set` every line read must be one of the listed strings (e.g. the map names of the tab)."""
from PIL import Image
from .. import ocr
from ... import cfg, util

NAME = "text"


def _names(setname):
    import re, subprocess, os
    binary = util.example_bin("aw2_map_audit")
    env = dict(os.environ)
    env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    r = subprocess.run([str(binary), str(cfg.aw2_rom())], capture_output=True, text=True, cwd=cfg.REPO, env=env)
    names = set()
    for l in r.stdout.splitlines():
        m = re.match(r"\dP\s+(?:predeployed\s+)?[0-9a-f]{2}\s+(.+?)\s{2,}", l)
        if m:
            names.add(m.group(1).strip())
    return names


def run(ctx):
    cfgs = ctx.screen.get("text", [])
    out = []
    for t in cfgs:
        region = tuple(t["region"]) if t.get("region") else None
        names = _names(t["in_set"]) if t.get("in_set") == "maps" else None
        for vname, d in ctx.renders.items():
            if t.get("variant") and t["variant"] != vname:
                continue
            for shot in ctx.shots(t.get("shots", ctx.screen.get("shots", []))):
                p = ctx.path(vname, shot)
                if not p:
                    continue
                lines = ocr.read(Image.open(p), region, thresh=t.get("thresh", 140), ink=tuple(t["ink"]) if t.get("ink") else None)
                if region:
                    # (a row cut by the list box's edge while it scrolls is partly hidden by design: only rows that touch neither edge are judged)
                    lines = [l for l in lines if l[0] > region[1] and l[4] < region[1] + region[3]]
                for y, x, text, unk, _y1 in lines:
                    if unk > t.get("max_unknown", 0):
                        out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": f"garbled text at ({x},{y}): {text!r} ({unk} unknown glyphs)"})
                    elif names is not None and text.strip() not in names and not any(text.strip().startswith(n[:len(text.strip())]) and len(text.strip()) < len(n) and t.get("allow_cut") for n in names):
                        out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": f"line {text!r} at ({x},{y}) is not a known name"})
                for want in t.get("expect", []):
                    if not any(want in l[2] for l in lines):
                        out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": f"expected text {want!r} not read (read: {[l[2] for l in lines]})"})
    return out
