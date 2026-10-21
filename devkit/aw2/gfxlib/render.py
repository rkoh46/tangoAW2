"""Render catalogued screens: run the harness (or the offline SELECT MAP example) with a screen's script and env, collect the pictures and dumps.

Works on the current tree's binaries, or on another worktree's (`binary_dir`: its target/release/examples), which is how golden frames are made
from a known-good commit and how a bisect renders old commits."""
import os, subprocess, time
from pathlib import Path
from PIL import Image
from .. import cfg, util
from ..harness import EXAMPLES, resolve_script


def bmp_to_png(p):
    im = Image.open(p).convert("RGB")
    return im


def render_variant(screen, vname, out, binary_dir=None, examples_dir=None):
    """Returns {"rc": int, "log": path, "dir": out}; shots stay as BMP/dump files in `out`."""
    var = screen.get("variants", {}).get(vname, {})
    env = dict(os.environ)
    out = Path(out)
    env.update({k: str(v).replace("{out}", str(out)) for k, v in var.get("env", {}).items()})
    if var.get("ds"):
        env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bd = Path(binary_dir) if binary_dir else cfg.REPO / "target" / "release" / "examples"
    runner = screen.get("runner", "harness")
    log = out / "render.log"
    if runner == "harness":
        binary = bd / "aw2_room_teams"
        ex = Path(examples_dir) if examples_dir else EXAMPLES
        script = ex / (screen["script"] + ".txt")
        if not script.exists():
            script = resolve_script(screen["script"])
        edit = screen.get("script_edit")
        if edit:
            # insert lines before the first script line starting with `match`, and/or append lines (so a catalogue screen needs no script copy)
            lines = script.read_text().splitlines()
            for ins in edit.get("insert_before", []):
                k = next(i for i, l in enumerate(lines) if l.startswith(ins["match"]))
                lines[k:k] = ins["lines"]
            lines += edit.get("append", [])
            script = out / "script_edited.txt"
            script.write_text("\n".join(lines) + "\n")
        if screen.get("vram"):
            # (a `vram NAME` line after every `shotall NAME` / `shot NAME`: the dumps the tile guard and `gfx explain` read)
            lines = []
            for l in script.read_text().splitlines():
                lines.append(l)
                w = l.split()
                if len(w) == 2 and w[0] in ("shotall", "shot"):
                    lines.append(f"vram {w[1]}")
            script = out / "script_with_vram.txt"
            script.write_text("\n".join(lines) + "\n")
        cmd = [str(binary), str(cfg.aw2_rom()), str(out), str(script)]
    elif runner == "example":
        # any example binary that writes pictures (BMP or PPM) into <out>: aw2_armysel_preview <rom> <out> ...
        binary = bd / screen["exe"]
        cmd = [str(binary), str(cfg.aw2_rom()), str(out)] + [str(x) for x in screen.get("args", [])]
    elif runner == "offline_tabs":
        binary = bd / "aw2_offline_tabs"
        cmd = [str(binary), str(cfg.aw2_rom()), str(out), screen["tokens"]]
        if var.get("ds"):
            env["AW2_DS_PACK"] = "1"
    else:
        util.die(f"unknown runner {runner}")
    if not binary.exists():
        util.die(f"{binary} missing: aw2dev build --examples")
    with open(log, "w") as f:
        r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, cwd=cfg.REPO, timeout=int(screen.get("timeout", 600)))
    return {"rc": r.returncode, "log": str(log), "dir": str(out)}


def shot_path(out, name):
    for ext in (".bmp", ".ppm", ".png"):
        p = Path(out) / f"{name}{ext}"
        if p.exists():
            return p
    return None
