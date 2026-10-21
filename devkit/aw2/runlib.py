"""Reading a live run dir: shots (sidecar), state/act/hash lines, the mover timeline, frames."""
import glob, json, os
from pathlib import Path
from . import cfg, util


class Run:
    def __init__(self, path):
        p = Path(path)
        if not p.is_dir():
            cand = cfg.work("runs", str(path))
            p = cand if cand.is_dir() else p
        if not p.is_dir():
            runs = sorted(cfg.work("runs").glob(f"*{path}*")) if cfg.work("runs").is_dir() else []
            if runs:
                p = runs[-1]
        if not p.is_dir():
            util.die(f"run dir {path} not found (runs live in {cfg.work('runs')}; `latest` picks the newest)")
        self.dir = p
        self.meta = {}
        if (p / "meta.json").exists():
            self.meta = json.loads((p / "meta.json").read_text())
        self.seats = sorted(int(f.split("_s")[1].split(".")[0]) for f in glob.glob(str(p / "shots_s*.jsonl")))
        self._shots, self._state = {}, {}

    @staticmethod
    def latest(prefix=""):
        d = cfg.work("runs")
        runs = sorted((x for x in d.glob(f"{prefix}*") if (x / "meta.json").exists()), key=lambda x: x.stat().st_mtime) if d.is_dir() else []
        return runs[-1] if runs else None

    @property
    def n(self):
        return len(self.seats) or self.meta.get("n", 0)

    def shots(self, s):
        if s not in self._shots:
            self._shots[s] = [x for x in util.jsonl(self.dir / f"shots_s{s}.jsonl") if (self.dir / x["file"]).exists()]
        return self._shots[s]

    def state_lines(self, s=0):
        if s not in self._state:
            self._state[s] = util.jsonl(self.dir / f"state_s{s}.jsonl")
        return self._state[s]

    def states(self, s=0):
        return [r for r in self.state_lines(s) if r.get("k") == "state"]

    def acts(self, what=None, s=0):
        return [r for r in self.state_lines(s) if r.get("k") == "act" and (what is None or r.get("what") == what)]

    def hashes(self, s):
        return [r for r in self.state_lines(s) if r.get("k") == "hash"]

    def mover(self, ms, s=0):
        b = None
        for r in self.states(s):
            if r["ms"] <= ms:
                b = r.get("mover")
            else:
                break
        return b

    def t0(self):
        """The first moment anything happened in the battle (first non-build act, else the first state line)."""
        st = self.states()
        acts = [a["ms"] for a in self.acts() if a["what"] != "build"]
        return min(acts + ([st[0]["ms"]] if st else [])) if (acts or st) else 0

    def image(self, f):
        from PIL import Image
        im = Image.open(self.dir / f)
        im.load()
        return im.convert("RGB")


def game(im):
    """Crop to the GBA picture: the app's screenshot is the window (title bar 38 px on top, a netplay status bar below);
    the picture is 3:2 (240x160 scaled by an integer)."""
    w, h = im.size
    sc = max(1, w // 240)
    gh = 160 * sc
    top = 38 if h >= 38 + gh else max(0, h - gh)
    return im.crop((0, top, w, min(h, top + gh)))
