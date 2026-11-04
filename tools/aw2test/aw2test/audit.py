"""Graphical audit scenes (`aw2dev gfx audit`, docs/dev/graphics.md): the screens of every mode, each reached the way a player gets there and photographed in a look.

A scene is a function `fn(rec)` registered with `@scene(mode, name, ...)`. `rec.snap(e, name, tags=...)` writes the console's picture as a PNG next to a dump of its video
state (VRAM, palette, OAM, I/O: what the detectors in devkit/aw2/gfxlib/audit read). `rec.fact(ok, msg)` records a check the scene can make from the game's own memory
(for example which HQ picture the terrain panel is on); a failed fact is a finding. The scene never judges pictures: devkit/aw2/gfxlib/audit/ does, from the files.

Looks: `aw2` (AW2 graphics, the Dual Strike pack loaded), `ds_tilt` (Dual Strike map graphics with the tilt), `ds_flat` (Dual Strike map graphics, no tilt) and `aw2_nopack`
(AW2 alone, the pack not loaded: only for scenes that exist without it).
Nothing here is game data: pictures and dumps are made from the owner's ROMs into the audit's output folder (git-ignored)."""

import json
import os
import subprocess
import sys
import traceback

from . import paths

LOOKS = {
    "aw2": {"TANGOAW2_DS_GRAPHICS": "0"},
    "ds_tilt": {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SKIP_LOG": "1", "TANGOAW2_TILT_LEAK_LOG": "1"},
    "ds_flat": {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0"},
    "aw2_nopack": {},
}
SCENES = {}          # (mode, name) -> {fn, looks, nopack, doc}
ALL_LOOKS = ("aw2_nopack", "aw2", "ds_tilt", "ds_flat")


def scene(mode, name, looks=("aw2", "ds_tilt", "ds_flat"), nopack=False, pack=True):
    """Register a scene. `looks`: the looks of the pack (with `nopack`, `aw2_nopack` too); `pack=False`: the scene runs only without the pack."""
    def deco(fn):
        use = list(looks if pack else ())
        if nopack or not pack:
            use.insert(0, "aw2_nopack")
        SCENES[(mode, name)] = {"fn": fn, "looks": tuple(use), "doc": (fn.__doc__ or "").strip().split("\n")[0]}
        return fn
    return deco


class Rec:
    """What a scene writes into: pictures, dumps and facts of one (scene, look) run."""

    def __init__(self, mode, name, look, out):
        from .harness import Ctx
        self.mode, self.name, self.look, self.out = mode, name, look, out
        os.makedirs(out, exist_ok=True)
        self.ds = look != "aw2_nopack"
        self.ctx = Ctx(f"audit_{mode}_{name}_{look}", ds=self.ds, out=out)
        self.env = dict(LOOKS[look])
        if look == "ds_tilt":
            self.env["TANGOAW2_TILT_LOG"] = os.path.join(out, "tilt.log")
        self.shots, self.facts, self.notes = [], [], []

    # -- the console -----------------------------------------------------------------
    def emu(self, save=None, env=None, base=True):
        from .emu import Emu
        from .game import Game
        e = Emu(save=save or (paths.base_save() if base else None), ds=self.ds, env={**self.env, **(env or {})})
        g = Game(e, self.ctx.image)
        self.ctx.games.append(g)
        return e, g

    def tilt(self, e):
        """Switch the per-frame tilt logging on (ds_tilt only): its skipped / leaked frames become findings."""
        if self.look == "ds_tilt":
            self.tilt_log = os.path.join(self.out, "tilt.log")
            try:
                os.remove(self.tilt_log)
            except OSError:
                pass
            e.cmd("tiltall 1")

    # -- output ------------------------------------------------------------------------
    def snap(self, e, name, tags=(), dump=True, **meta):
        """One picture + the video state. `tags` say what the screen is (dialogue, battle, map, menu, text, fade, ...) so the detectors know what to expect."""
        p = os.path.join(self.out, name)
        e.shot(p)
        from PIL import Image
        im = Image.open(p + ".bmp").convert("RGB")
        im.save(p + ".png")
        os.remove(p + ".bmp")
        v = None
        if dump:
            v = p + ".vram"
            parts = []
            for i, (addr, n) in enumerate(((0x06000000, 0x18000), (0x05000000, 0x400), (0x07000000, 0x400), (0x04000000, 0x60))):
                f = p + f".part{i}"
                e.cmd(f"dumprange {addr:08x} {n} {f}")
                with open(f, "rb") as fh:
                    parts.append(fh.read())
                os.remove(f)
            with open(v, "wb") as fh:
                fh.write(b"".join(parts))
        self.shots.append({"name": name, "png": os.path.basename(p) + ".png", "vram": os.path.basename(v) if v else None, "tags": list(tags), "size": list(im.size), "frame": e.frame, **meta})
        return p + ".png"

    def fact(self, ok, msg):
        self.facts.append({"ok": bool(ok), "msg": msg})
        return ok

    def note(self, msg):
        self.notes.append(str(msg))

    def manifest(self, error=None):
        m = {"mode": self.mode, "scene": self.name, "look": self.look, "shots": self.shots, "facts": self.facts, "notes": self.notes, "error": error,
             "tilt_log": getattr(self, "tilt_log", None)}
        with open(os.path.join(self.out, "manifest.json"), "w") as f:
            json.dump(m, f, indent=1)
        return m


def run_scene(mode, name, look, out):
    """Run one scene in one look; always writes manifest.json (an exception is recorded as the scene's error)."""
    rec = Rec(mode, name, look, out)
    err = None
    try:
        SCENES[(mode, name)]["fn"](rec)
    except Exception:       # noqa: BLE001 - recorded, the sweep goes on
        err = traceback.format_exc()
    finally:
        for g in rec.ctx.games:
            try:
                g.e.close()
            except Exception:       # noqa: BLE001
                pass
    return rec.manifest(err)


def load_scenes():
    from . import audit_scenes  # noqa: F401  (registers the scenes)
    return SCENES
