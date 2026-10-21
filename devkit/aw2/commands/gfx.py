"""aw2dev gfx: detect and debug garbled graphics (docs/dev/graphics.md, skill aw2-gfx-debug).

  gfx catalogue                       list the catalogued screens and their checks (devkit/gfx/catalogue.toml)
  gfx check [--screen S ...]          render the screens with the harness, run the detectors, print findings (exit 1 on a failure)
  gfx golden [--from COMMIT]          render reference frames from a known-good build into ~/.aw2dev/golden (never committed)
  gfx explain PATH [--region x,y,w,h] decode a VRAM/OAM/palette dump (and what draws a region of a picture) into images and tables
  gfx bisect --screen S --good C --bad C   run a screen's check across commits for the first bad one
  gfx blame --screen S --dump NAME    the first tick at which a guarded VRAM range stops matching the golden dump, with the procs running then
"""
import json, os, re, shutil, subprocess, time, tomllib
from pathlib import Path
from PIL import Image
from .. import cfg, util
from ..gfxlib import render, vram
from ..gfxlib.detectors import all_detectors

CATALOGUE = cfg.DEVKIT / "gfx" / "catalogue.toml"
GOLDEN = Path.home() / ".aw2dev" / "golden"


def register(sub):
    g = sub.add_parser("gfx", help="graphics integrity: check, golden, explain, bisect, blame (docs/dev/graphics.md)")
    gs = g.add_subparsers(dest="gfxcmd", required=True)
    a = gs.add_parser("catalogue", help="list the screens")
    a.set_defaults(fn=lambda x: catalogue(x))
    a = gs.add_parser("check", help="render screens and run the detectors")
    a.add_argument("--screen", nargs="*")
    a.add_argument("--golden", help="golden set (default: the current one, see `gfx golden`)")
    a.add_argument("--binary-dir", help="another build's target/release/examples (default: this tree)")
    a.add_argument("--examples-dir", help="that build's examples/ (harness scripts)")
    a.add_argument("--revert", nargs="*", metavar="COMMIT", help="check a build of this tree with those fix commits reverted (proves a detector flags the old bug)")
    a.add_argument("--env", action="append", default=[], metavar="K=V", help="extra environment for the renders (e.g. AW2_RESTORE_BANKS=11 reproduces the unit-recolour bug)")
    a.add_argument("--quiet", action="store_true")
    a.set_defaults(fn=lambda x: check(x))
    a = gs.add_parser("regress", help="reintroduce each catalogued past bug (a patch / env switch) and require the detectors to flag it")
    a.add_argument("--bug", nargs="*")
    a.set_defaults(fn=lambda x: regress(x))
    a = gs.add_parser("golden", help="render reference frames from a known-good build")
    a.add_argument("--from", dest="commit", help="a commit (built in a temporary worktree); default: this tree")
    a.add_argument("--tag", help="name of the set (default: the commit or `current`)")
    a.add_argument("--screen", nargs="*")
    a.set_defaults(fn=lambda x: golden(x))
    a = gs.add_parser("explain", help="decode a dump / a region of a picture")
    a.add_argument("path", help="a .vram file, a dir with vram.bin/pal.bin/oam.bin/io.bin, or a .bmp next to a NAME.vram")
    a.add_argument("--region", help="x,y,w,h of the 240x160 picture")
    a.add_argument("--bank", type=int, default=0, help="palette bank for the tile sheets")
    a.set_defaults(fn=lambda x: explain(x))
    a = gs.add_parser("bisect", help="first bad commit for a screen")
    a.add_argument("--screen", required=True)
    a.add_argument("--good", required=True)
    a.add_argument("--bad", default="HEAD")
    a.add_argument("--golden")
    a.set_defaults(fn=lambda x: bisect(x))
    a = gs.add_parser("blame", help="first tick a guarded VRAM range stops matching golden, and the procs then")
    a.add_argument("--screen", required=True)
    a.add_argument("--dump", required=True, help="the guard's dump name (catalogue)")
    a.add_argument("--from-tick", type=int, default=300)
    a.add_argument("--to-tick", type=int, default=6000)
    a.add_argument("--binary-dir", help="another build's target/release/examples (e.g. the build that shows the bug)")
    a.add_argument("--golden")
    a.set_defaults(fn=lambda x: blame(x))


def load_bugs():
    return {b["name"]: b for b in tomllib.loads(CATALOGUE.read_text()).get("bug", [])}


def _bug_build(bug):
    """A worktree at HEAD with the bug's patch applied (devkit/gfx/regressions/<patch>), built with its own target dir."""
    tag = "bug-" + bug["name"]
    wt = cfg.work("gfx_wt", tag)
    if wt.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=cfg.REPO, capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    wt.parent.mkdir(parents=True, exist_ok=True)
    cfg.git("worktree", "add", "--detach", str(wt), "HEAD")
    r = subprocess.run(["git", "apply", "--whitespace=nowarn", str(cfg.DEVKIT / "gfx" / "regressions" / bug["patch"])], cwd=wt, capture_output=True, text=True)
    if r.returncode:
        util.die(f"bug {bug['name']}: patch no longer applies ({r.stderr.strip()[:200]}); regenerate devkit/gfx/regressions/{bug['patch']}")
    return _worktree_build(tag, wt)


def regress(a):
    """Every [[bug]] of the catalogue: build/run with the bug back, the named screens must produce a failing finding; prints DETECTED / MISSED."""
    cat, bugs = load_catalogue(), load_bugs()
    missed = 0
    for name, b in bugs.items():
        if a.bug and name not in a.bug:
            continue
        bd = ed = None
        if b.get("patch"):
            wt, bd = _bug_build(b)
            ed = wt / "tango-gamesupport-aw2" / "examples"
        got = []
        for sn in b["screens"]:
            fs = run_screen(cat[sn], cfg.work("gfx", "regress_" + name), None, bd, ed, env=b.get("env"))
            got += [f for f in fs if f["severity"] == "fail"]
        ok = bool(got)
        missed += not ok
        print(f"[{'DETECTED' if ok else 'MISSED '}] {name}: {b.get('what', '')}" + (f"  e.g. {got[0]['detector']}: {got[0]['msg'][:110]}" if got else ""))
    util.say(f"gfx regress: {missed} bug(s) not detected")
    return 1 if missed else 0


def load_catalogue():
    return {s["name"]: s for s in tomllib.loads(CATALOGUE.read_text())["screen"]}


def expand(names):
    """`f{00..29}` -> f00 .. f29 (zero padded to the first number's width); several ranges in one name make the product."""
    out = []
    for n in names:
        m = re.search(r"\{(\d+)\.\.(\d+)\}", n)
        if not m:
            out.append(n)
            continue
        w = len(m.group(1))
        for i in range(int(m.group(1)), int(m.group(2)) + 1):
            out += expand([n[:m.start()] + f"{i:0{w}d}" + n[m.end():]])
    return out


class Ctx:
    def __init__(self, screen, renders, golden, rcs, out):
        self.screen, self.renders, self.golden, self.rcs, self.out = screen, renders, golden, rcs, out

    def shots(self, names):
        return expand(names)

    def path(self, variant, shot):
        return render.shot_path(self.renders[variant], shot)


def golden_dir(tag=None):
    if tag is None:
        cur = GOLDEN / "LATEST.txt"
        if not cur.exists():
            return None
        tag = cur.read_text().strip()
    return GOLDEN / tag


def catalogue(a):
    for s in load_catalogue().values():
        print(f"{s['name']:20} runner={s.get('runner', 'harness'):12} variants={list(s.get('variants', {'default': {}}))} checks={s.get('checks', 'all')}  {s.get('what', '')}")
    return 0


def run_screen(screen, out_root, gtag=None, binary_dir=None, examples_dir=None, quiet=False, env=None):
    if env:
        screen = dict(screen)
        screen["variants"] = {v: dict(d, env={**d.get("env", {}), **env}) for v, d in screen.get("variants", {"default": {}}).items()}
    out = Path(out_root) / screen["name"]
    out.mkdir(parents=True, exist_ok=True)
    renders, rcs, golden = {}, {}, {}
    gd = golden_dir(gtag)
    for v in screen.get("variants", {"default": {}}):
        r = render.render_variant(screen, v, out / v, binary_dir, examples_dir)
        renders[v], rcs[v] = Path(r["dir"]), r["rc"]
        g = (gd / screen["name"] / v) if gd else None
        golden[v] = g if g and g.exists() else None
    ctx = Ctx(screen, renders, golden, rcs, out)
    want = screen.get("checks")
    findings = []
    if screen.get("rc_is_finding", True):
        for v, rc in rcs.items():
            if rc:
                findings.append({"detector": "harness", "shot": v, "severity": "fail", "msg": f"the script's own checks failed (exit {rc}): {renders[v] / 'render.log'}"})
    for name, mod in all_detectors().items():
        if want is not None and name not in want:
            continue
        findings += mod.run(ctx)
    return findings


def check(a):
    cat = load_catalogue()
    names = a.screen or list(cat)
    out_root = cfg.work("gfx", time.strftime("%H%M%S"))
    if a.revert:
        wt, a.binary_dir = _revert_build(a.revert)
        a.examples_dir = str(wt / "tango-gamesupport-aw2" / "examples")
        util.say("checking a build with reverted:", " ".join(a.revert))
    fails = 0
    report = {}
    for n in names:
        if n not in cat:
            util.die(f"unknown screen {n}; `aw2dev gfx catalogue`")
        fs = run_screen(cat[n], out_root, a.golden, a.binary_dir, a.examples_dir, env=dict(x.split('=', 1) for x in a.env))
        report[n] = fs
        bad = [f for f in fs if f["severity"] == "fail"]
        fails += len(bad)
        print(f"[{'FAIL' if bad else 'PASS'}] {n}")
        for f in fs:
            if not a.quiet or f["severity"] == "fail":
                print(f"    {f['severity']:4} {f['detector']:8} {f['shot']}: {f['msg']}" + (f"  -> {f['artifact']}" if f.get("artifact") else ""))
    (out_root / "report.json").write_text(json.dumps(report, indent=1))
    util.say(f"gfx check: {fails} failing finding(s); report {out_root / 'report.json'}")
    return 1 if fails else 0


# ---- golden ----
def _revert_build(reverts, base="HEAD"):
    """A worktree at `base` with the given commits reverted (their fixes removed: the bug comes back), built with its own target dir. Used by
    `gfx check --revert C` to prove a detector flags the old bug. A revert that conflicts stops with the files named (edit by hand)."""
    tag = "rev-" + "-".join(c[:7] for c in reverts)
    wt = cfg.work("gfx_wt", tag)
    if not wt.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        cfg.git("worktree", "add", "--detach", str(wt), base)
        for c in reverts:
            r = subprocess.run(["git", "revert", "--no-commit", c], cwd=wt, capture_output=True, text=True)
            if r.returncode:
                conflicts = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=wt, capture_output=True, text=True).stdout.split()
                outside = [f for f in conflicts if "/src/" not in f]        # (tools/tests the fix touched: keep this tree's)
                for f in outside:
                    subprocess.run(["git", "checkout", base, "--", f], cwd=wt, capture_output=True)
                    subprocess.run(["git", "reset", "-q", "--", f], cwd=wt, capture_output=True)
                if len(outside) == len(conflicts) and conflicts:
                    continue
                util.die(f"reverting {c} conflicts in {conflicts}: worktree {wt} is left for a hand edit; then run `aw2dev gfx check --binary-dir` on its build")
            # (a revert also undoes tests/examples the fix added: keep this tree's examples and kit files)
            subprocess.run(["git", "checkout", base, "--", "tango-gamesupport-aw2/examples", "devkit"], cwd=wt, capture_output=True)
    return _worktree_build(tag, wt)


def _worktree_build(commit, wt=None):
    """Build the harness examples of `commit` in a worktree with ITS OWN cargo target dir (devkit/work/gfx_target/<commit>): cargo keys workspace crates by
    path, so two worktrees sharing one target dir reuse each other's example binaries (it happened: a "head" build that was another tree's). The target
    dir starts as an APFS clone of this tree's target/ (instant, no extra space) so only the changed crates rebuild. Returns (worktree, examples dir)."""
    wt = Path(wt) if wt else cfg.work("gfx_wt", commit[:9])
    if not wt.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        cfg.git("worktree", "add", "--detach", str(wt), commit)
    tgt = cfg.work("gfx_target", commit[:9])
    if not tgt.exists():
        tgt.parent.mkdir(parents=True, exist_ok=True)
        main = cfg.REPO / "target"
        if main.exists():
            subprocess.run(["cp", "-cR", str(main), str(tgt)], check=False)
    util.run(["cargo", "build", "--release", "-p", "tango-gamesupport-aw2", "--examples"], env=cfg.env_with_cargo({"CARGO_TARGET_DIR": str(tgt)}), cwd=wt)
    return wt, tgt / "release" / "examples"


def golden(a):
    cat = load_catalogue()
    names = a.screen or list(cat)
    binary_dir = examples_dir = None
    tag = a.tag or (a.commit[:9] if a.commit else "tree-" + cfg.git("rev-parse", "--short=9", "HEAD"))
    if a.screen and not a.tag and (GOLDEN / "LATEST.txt").exists() and not a.commit:
        tag = (GOLDEN / "LATEST.txt").read_text().strip()     # (a partial run adds to the current set)
    if a.commit:
        wt, binary_dir = _worktree_build(a.commit)
        examples_dir = wt / "tango-gamesupport-aw2" / "examples"
    else:
        util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
    out_root = cfg.work("gfx", "golden_" + time.strftime("%H%M%S"))
    for n in names:
        s = cat[n]
        for v in s.get("variants", {"default": {}}):
            r = render.render_variant(s, v, out_root / n / v, binary_dir, examples_dir)
            dst = GOLDEN / tag / n / v
            shutil.rmtree(dst, ignore_errors=True)
            dst.mkdir(parents=True)
            for f in Path(r["dir"]).iterdir():
                if f.suffix in (".bmp", ".ppm"):
                    Image.open(f).convert("RGB").save(dst / (f.stem + ".png"))
                elif f.suffix == ".vram":
                    shutil.copy2(f, dst / f.name)
                elif f.is_dir() or f.suffix == ".bin":
                    pass
            for d in Path(r["dir"]).glob("*.bin"):
                pass
            # offline_tabs writes vram.bin/pal.bin/oam.bin/io.bin into the render dir: keep them as a dump dir named `vram`
            if (Path(r["dir"]) / "vram.bin").exists():
                (dst / "vram").mkdir(exist_ok=True)
                for b in ("vram", "pal", "oam", "io"):
                    if (Path(r["dir"]) / f"{b}.bin").exists():
                        shutil.copy2(Path(r["dir"]) / f"{b}.bin", dst / "vram" / f"{b}.bin")
            util.say(f"golden {tag}/{n}/{v}: rc={r['rc']}")
    (GOLDEN / "LATEST.txt").write_text(tag)
    util.say(f"golden set {tag} is current ({GOLDEN / tag}); it holds frames rendered from your ROM: keep it out of git")
    return 0


# ---- explain ----
def explain(a):
    p = Path(a.path)
    pic = None
    if p.suffix == ".bmp":
        pic = p
        cand = p.with_suffix(".vram")
        if not cand.exists():
            cand = p.with_name(re.sub(r"_s\d+$", "", p.stem) + ".vram")      # (shotall NAME writes NAME_s<k>.bmp; `vram NAME` writes NAME.vram)
        if not cand.exists():
            cand = p.parent / "vram"
        p = cand if cand.exists() else None
        if p is None:
            util.die("no NAME.vram next to the picture: add `vram NAME` to the harness script (or token V in aw2_offline_tabs)")
    d = vram.Dump.load(p)
    out = cfg.work("gfx", "explain_" + time.strftime("%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    d.palette_image().save(out / "palette.png")
    for cb in range(4):
        d.tile_sheet(cb * 0x4000, 512, a.bank).save(out / f"bg_charblock{cb}.png")
    d.tile_sheet(0x10000, 512, a.bank, obj=True).save(out / "obj_tiles.png")
    dc = d.dispcnt()
    print(f"DISPCNT mode {dc['mode']} BGs on {dc['bg_on']} OBJ {dc['obj_on']} (1D mapping {dc['obj_1d']})")
    for i in range(4):
        print(f"BG{i}: {d.bgcnt(i)}")
    sp = d.sprites()
    print(f"{len(sp)} OAM entries")
    reg = tuple(int(x) for x in a.region.split(",")) if a.region else None
    for s in sp:
        if reg is None or (s["x"] < reg[0] + reg[2] and s["x"] + s["w"] > reg[0] and s["y"] < reg[1] + reg[3] and s["y"] + s["h"] > reg[1]):
            print(f"  OAM {s['index']:3}: ({s['x']},{s['y']}) {s['w']}x{s['h']} tile {s['tile']} (VRAM {0x10000 + 32 * s['tile']:#x}) pal {s['pal']} prio {s['prio']}")
    if reg:
        x, y, w, h = reg
        for i in range(4):
            if not dc["bg_on"][i]:
                continue
            tiles = set()
            for py in range(y, y + h, 8):
                for px in range(x, x + w, 8):
                    (t, hf, vf, pb), cell = d.bg_cell_at(i, px, py)
                    tiles.add((t, pb))
            print(f"  BG{i} tiles under the region (tile, palbank): {sorted(tiles)[:30]}{' ...' if len(tiles) > 30 else ''}  charblock base {d.bgcnt(i)['char_base']:#x}")
        if pic:
            Image.open(pic).convert("RGB").crop((x, y, x + w, y + h)).resize((w * 4, h * 4), Image.NEAREST).save(out / "region.png")
    util.say("images in", out)
    return 0


# ---- bisect / blame ----
def bisect(a):
    cat = load_catalogue()
    s = cat[a.screen]
    commits = cfg.git("rev-list", "--first-parent", "--reverse", f"{a.good}..{a.bad}").split()
    if not commits:
        util.die("no commits between good and bad")
    lo, hi = -1, len(commits) - 1     # commits[lo] good (virtually), commits[hi] bad
    util.say(f"{len(commits)} commits to search; ~{len(commits).bit_length()} builds")

    def bad(c):
        wt, bd = _worktree_build(c)
        fs = run_screen(s, cfg.work("gfx", "bisect_" + c[:9]), a.golden, bd, wt / "tango-gamesupport-aw2" / "examples", quiet=True)
        fl = [f for f in fs if f["severity"] == "fail"]
        util.say(f"{c[:9]}: {'BAD' if fl else 'good'} {fl[0]['msg'] if fl else ''}")
        return bool(fl)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if bad(commits[mid]):
            hi = mid
        else:
            lo = mid
    print("first bad commit:", cfg.git("log", "-1", "--format=%h %s", commits[hi]))
    return 0


def blame(a):
    cat = load_catalogue()
    s = cat[a.screen]
    g = next((x for x in s.get("guard", []) if x["dump"] == a.dump), None)
    if not g:
        util.die(f"screen {a.screen} has no guard with dump {a.dump}")
    gd = golden_dir(a.golden)
    if gd is None:
        util.die("no golden set: `aw2dev gfx golden`")
    ref_path = gd / a.screen / list(s.get("variants", {"default": {}}))[-1] / f"{a.dump}.vram"
    ref = vram.Dump.load(ref_path if ref_path.exists() else ref_path.with_suffix(""))
    lo_a, hi_a = g["range"]
    variant = list(s.get("variants", {"default": {}}))[-1]
    tmp = cfg.work("gfx", "blame_" + time.strftime("%H%M%S"))

    def probe(t):
        d = tmp / f"t{t}"
        d.mkdir(parents=True, exist_ok=True)
        s2 = dict(s)
        s2["variants"] = {variant: dict(s.get("variants", {}).get(variant, {}), env={**s.get("variants", {}).get(variant, {}).get("env", {}), "AW2_RAM_DUMP": str(t), "AW2_RAM_DIR": str(d)})}
        render.render_variant(s2, variant, d / "o", a.binary_dir)
        f = d / f"vram_{t}.bin"
        if not f.exists():
            return None
        v = f.read_bytes()
        return v[lo_a:hi_a] != ref.vram[lo_a:hi_a]
    lo, hi = a.from_tick, a.to_tick
    if probe(lo):
        util.say(f"already differs at tick {lo}")
        hi = lo
    elif not probe(hi):
        util.say(f"the range still equals the golden at tick {hi}: the damage is transient (or later); widen --to-tick")
        return 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if probe(mid):
            hi = mid
        else:
            lo = mid
    util.say(f"first differing tick: {hi}")
    s3 = dict(s)
    env = dict(s.get("variants", {}).get(variant, {}).get("env", {}), AW2_PROC_LOG="1")
    s3["variants"] = {variant: dict(s.get("variants", {}).get(variant, {}), env=env)}
    r = render.render_variant(s3, variant, tmp / "procs", a.binary_dir)
    lines = Path(r["log"]).read_text(errors="ignore").splitlines()
    near = [l for l in lines if re.search(r"\b(tick|t)[ =:]*(%d)\b" % hi, l)] or [l for l in lines if "proc" in l.lower()][-20:]
    print(f"first differing tick {hi}. The proc log is not tick-stamped: these are the last proc lines of the run (AW2_PROC_LOG); match them to the screen's script:")
    for l in near[-12:]:
        print("  ", l[:200])
    return 0
