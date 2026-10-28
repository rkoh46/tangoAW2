"""aw2dev check <run>: pass/fail checkers over a live run dir (ports of qa/lk2.py, camoff.py, dl.py, hashcmp.py, hudlive.py, moverframes.py
and tools/cam_check.py), plus the harness-output checkers. Writes <run>/check.json; exit 1 when any selected check fails.

  hash    all seats' state hashes agree from the first equal frame on (they differ in the menu phase, agree in battle); a killed seat is left out
  leak    waiting windows show no menu / page / dialog band / range arrows while another seat is the mover (the waiting view's allowlist)
  mover   no waiting frame equals the mover's own frame of the same tick (the mover's UI must never be copied to a waiting window)
  cam     the waiting windows' camera does not reverse direction (phase correlation) and tools/cam_check.py passes on the AW2_CAM_LOG lines
  hud     each window shows its own army's HUD header colour, never the other's (2 seats: red/blue)
  gfx     no frozen window (identical pictures while the game moves on) and no black run; catalogued screens: `aw2dev gfx check`
  black   no black run longer than --black-ms on any window after the battle starts (turn wipes are shorter)
  colours the harness colour scripts and the colour matrix example (not per run)
FALSE-PASS LESSONS: look at the images too; check the build stamp (meta.json `build`) is the same across runs you compare; use the same build for both fog modes.
"""
import os, json, subprocess, sys
import numpy as np
from PIL import Image
from . import cfg, harness, util
from .runlib import Run, game

ALL = ["hash", "leak", "mover", "cam", "hud", "black", "gfx"]


def _arr(run, rec, size=(480, 360)):
    try:
        return np.asarray(game(run.image(rec["file"])).resize(size), dtype=int)
    except Exception:
        return None


# ---- hash ----
def c_hash(run, seats=None, **kw):
    seats = seats or run.seats
    H = {s: {} for s in seats}
    for s in seats:
        for d in run.hashes(s):
            H[s][d["frame"]] = d["h"]
    if not all(H.values()):
        return {"pass": None, "detail": "no hash lines (the app writes them in battle every 60 console frames; this run never reached a battle?)"}
    common = sorted(set.intersection(*[set(h) for h in H.values()]))
    eq = [f for f in common if len({H[s][f] for s in seats}) == 1]
    first_eq = eq[0] if eq else None
    bad = [f for f in common if first_eq is not None and f >= first_eq and len({H[s][f] for s in seats}) > 1]
    ok = bool(eq) and not bad and len(eq) >= 3
    return {"pass": ok, "seats": seats, "common_frames": len(common), "equal": len(eq), "first_equal_frame": first_eq, "differ_after_equal": bad[:10],
            "detail": "hashes agree in battle" if ok else "hashes missing or diverge after agreeing: run `aw2dev check --hash` with TANGOAW2_HASH_PARTS lines to find the chunk"}


# ---- leak ----
def _feats(a):
    m = a[40:340]
    white = int(((m[:, :, 0] > 238) & (m[:, :, 1] > 238) & (m[:, :, 2] > 238)).sum())
    dark = int((m.sum(axis=2) < 150).sum())
    b = a[285:345, 40:440]
    band = int(((b[:, :, 0] > 225) & (b[:, :, 1] > 220) & (b[:, :, 2] > 215)).sum())
    # (a move/attack range tints whole map cells cyan: count 16x16 blocks that are almost entirely cyan. Blue Moon's own units and sea sparkle are cyan too, but never fill a block)
    cyan = (m[:, :, 0] < 190) & (m[:, :, 1] > 215) & (m[:, :, 2] > 225) & (m[:, :, 2] - m[:, :, 0] > 45)
    h, w = cyan.shape
    blocks = cyan[:h // 16 * 16, :w // 16 * 16].reshape(h // 16, 16, w // 16, 16).mean(axis=(1, 3))
    cy = int((blocks > 0.85).sum()) * 300      # (scaled so the old threshold of 1800 means 6 full blocks)
    return white, dark, band, cy


def _cream_box(a):
    """A big filled near-white rectangle (a menu, page or dialog): the white pixels' bounding box is large and mostly white. White buildings scattered
    over the map (neutral cities at fog off) have a large box but a low fill ratio."""
    m = a[40:340]
    mask = (m[:, :, 0] > 238) & (m[:, :, 1] > 238) & (m[:, :, 2] > 238)
    rows = np.where(mask.sum(axis=1) > 25)[0]
    cols = np.where(mask.sum(axis=0) > 12)[0]
    if len(rows) < 25 or len(cols) < 60:
        return False
    sub = mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return sub.size > 60 * 40 and sub.mean() > 0.5


POWER_QUOTE_MS = 12_000      # a power's quote box is typed out letter by letter on every window BEFORE the power's act is logged (about 5 to 10 s earlier with the menu and the box's slide): allowed too


def quiet_windows(acts, allow_ms=2500):
    """[(from_ms, to_ms)] around the acts every window may legitimately show: a battle scene, narration, a capture (+-allow_ms) and a CO power (its quote box and cut-in: POWER_QUOTE_MS before the act, allow_ms after).
    `net repeat asuka` / `net repeat super` once reported FAIL with equal hashes because the quote box of a power, on the waiting window 5 to 10 s before the logged act, was taken for a leaked dialog."""
    out = []
    for a in acts:
        if a["what"] == "power":
            out.append((a["ms"] - POWER_QUOTE_MS, a["ms"] + allow_ms))
        elif a["what"] in ("attack", "eliminated", "kill", "capture"):
            out.append((a["ms"] - allow_ms, a["ms"] + allow_ms))
    return out


def c_leak(run, allow_ms=2500, **kw):
    acts = run.acts()
    t0 = run.t0()
    # allowed on every window: battle scene, CO power cut-in, narration boxes (elimination), captures seen: stay quiet around those acts
    quiet = quiet_windows(acts, allow_ms)
    # AW2's own reconnect box shows on every other window while a peer is frozen, dropped or rejoining (scripted events): not a leak
    try:
        sm = json.loads((run.dir / "summary.json").read_text())
        for e in sm.get("events", []):
            ms = sm["t0_epoch_ms"] + int(e["at_s"] * 1000)
            quiet.append((ms, ms + 150_000 if e["action"] in ("kill", "relaunch") else ms + int(1000 * (e.get("arg") or 10)) + 20_000))
    except Exception:
        pass
    eps = []
    for s in run.seats:
        cur = None
        for x in run.shots(s):
            if x["ms"] < t0 - 3000 or any(a <= x["ms"] <= b for a, b in quiet):
                continue
            m = run.mover(x["ms"])
            if m is None or m == s:
                continue
            a = _arr(run, x)
            if a is None:
                continue
            w, dk, band, cy = _feats(a)
            kinds = []
            if 2600 < w < 9000 and dk < 9000 and _cream_box(a):
                kinds.append("menu/page")
            if w >= 9000 and dk < 30000:
                kinds.append("bigmenu")
            if band > 3000 and dk < 30000:
                kinds.append("dialog-band")
            if cy > 1800:
                kinds.append("range/arrow")
            if not kinds:
                continue
            t = (x["ms"] - t0) / 1000
            key = tuple(kinds)
            if cur and cur["seat"] == s and t - cur["t1"] <= 0.7 and cur["kinds"] == key:
                cur["t1"] = t
                cur["n"] += 1
                cur["last"] = x["file"]
            else:
                cur = {"seat": s, "t0": round(t, 1), "t1": t, "n": 1, "kinds": key, "mover": m, "first": x["file"], "last": x["file"]}
                eps.append(cur)
    for e in eps:
        e["t1"] = round(e["t1"], 1)
        e["kinds"] = list(e["kinds"])
    real = [e for e in eps if e["n"] >= 2]   # a single frame is a transition artefact
    return {"pass": not real, "episodes": real, "single_frame_flags": len(eps) - len(real),
            "detail": "no leaked UI on waiting windows" if not real else f"{len(real)} episode(s) of mover UI on a waiting window: look at the frames named first/last"}


# ---- mover ----
def c_mover(run, **kw):
    if run.n < 2:
        return {"pass": None, "detail": "needs 2+ windows"}
    s0 = run.shots(0)[:-1]
    res = []
    n = 0
    for s in run.seats[1:]:
        for x in run.shots(s)[:-1]:
            if (x.get("tick") or 0) < 1500:
                continue
            i = min(range(len(s0)), key=lambda k: abs(s0[k].get("tick", 0) - x.get("tick", 0)))
            if abs(s0[i].get("tick", 0) - x.get("tick", 0)) > 3:
                continue
            m = run.mover(x["ms"])
            if m != 0:
                continue   # only when seat 0 is the mover
            a, b = _arr(run, x, (120, 80)), _arr(run, s0[i], (120, 80))
            if a is None or b is None:
                continue
            n += 1
            if np.abs(a - b).mean() < 1.5:
                res.append({"seat": s, "file": x["file"], "tick": x.get("tick")})
    return {"pass": not res, "compared": n, "mover_like": res[:20], "detail": "no waiting frame equals the mover's" if not res else "waiting frames equal the mover's frame"}


# ---- cam ----
def _shift(prev, a):
    F = np.fft.fft2(prev) * np.conj(np.fft.fft2(a))
    F /= np.abs(F) + 1e-9
    c = np.fft.ifft2(F).real
    iy, ix = np.unravel_index(c.argmax(), c.shape)
    h, w = c.shape
    return (ix if ix < w // 2 else ix - w), (iy if iy < h // 2 else iy - h), float(c.max())


def c_cam(run, max_gap_ms=250, **kw):
    """Camera steadiness of the waiting windows: phase-correlate consecutive shots (gap <= max_gap_ms, so run with --hz 4 or more) while
    another seat is the mover; a shift that reverses the previous shift is a camera jerk. Banners and wipes decorrelate (low peak) and are skipped."""
    out = {"seats": {}, "cam_check": {}}
    ok = True
    judged = 0
    for s in run.seats:
        prev, prev_ms, last, revs, nmoves = None, None, (0, 0), [], 0
        for x in run.shots(s):
            try:
                im = run.image(x["file"]).convert("L")
            except Exception:
                continue
            W, H = im.size
            top = 38
            a = np.asarray(im.crop((0, top, W, top + 160 * (W // 240))).resize((480, 288)), dtype=float)
            a = a - a.mean()
            mover = run.mover(x["ms"])
            if prev is not None and x["ms"] - prev_ms <= max_gap_ms and mover is not None and mover != s:
                judged += 1
                dx, dy, pk = _shift(prev, a)
                dx, dy = dx * 4, dy * 4
                if pk > 0.25 and (abs(dx) >= 16 or abs(dy) >= 16):
                    nmoves += 1
                    if last != (0, 0) and (dx * last[0] < 0 or dy * last[1] < 0):
                        revs.append({"file": x["file"], "shift": (dx, dy), "prev": last})
                    last = (dx, dy)
            else:
                last = (0, 0)
            prev, prev_ms = a, x["ms"]
        out["seats"][s] = {"camera_moves": nmoves, "reversals": revs[:10], "n_reversals": len(revs)}
        ok = ok and not revs
    for s in run.seats:
        log = run.dir / f"tango_s{s}.log"
        if log.exists() and "cam seat" in log.read_text(errors="ignore"):
            r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "cam_check.py"), str(log)], capture_output=True, text=True)
            out["cam_check"][s] = {"rc": r.returncode, "head": "\n".join((r.stdout + r.stderr).splitlines()[:3])}
            ok = ok and r.returncode == 0
    if judged < 20 and not out["cam_check"]:
        return {"pass": None, "detail": f"only {judged} frame pairs close enough in time: run with --hz 5 or more", **out}
    out["pass"] = ok
    out["detail"] = "camera steady (no reversals)" if ok else "camera reversed direction or cam_check failed"
    return out


# ---- hud ----
def _runlen(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def c_hud(run, **kw):
    if run.n != 2:
        return {"pass": None, "detail": "HUD colour check is for 2 seats (red vs blue header)"}
    res = {}
    ok = True
    for seat, never in ((0, "blue"), (1, "red")):
        # (a run with the army skin picked spends longer on the army page: its Rules page is still up at tick 2000)
        first = 2600 if os.environ.get("AW2DEV_SKIN") == "1" else 2000
        # (the battle's first state record: before it a window may still be on the Rules page, whose red-bordered boxes are no HUD; a
        # window that got there later than the other, as a relaunched seat does, would be judged on them)
        st = run.states(seat)
        began = st[0]["ms"] if st else 0
        recs = [x for x in run.shots(seat)[:-1] if (x.get("tick") or 0) >= first and x.get("ms", 0) >= began]
        wrong = []
        for x in recs:
            im = run.image(x["file"])
            w, h = im.size
            sc = w // 240
            a = np.asarray(im, dtype=int)[38 + 3 * sc: 38 + 11 * sc: sc, ::sc]
            if never == "red":
                hit = (a[:, :, 0] > 200) & (a[:, :, 1] < 110) & (a[:, :, 2] < 110)
            else:
                hit = (abs(a[:, :, 0] - 115) < 6) & (abs(a[:, :, 1] - 90) < 6) & (a[:, :, 2] > 240)
            r = max(_runlen(row) for row in hit)
            if r >= 28 and not (never == "blue" and r >= 100):
                wrong.append(x["file"])
        res[f"seat{seat}_never_{never}"] = {"frames": len(recs), "wrong": len(wrong), "files": wrong[:6]}
        ok = ok and len(wrong) <= max(2, len(recs) // 20)   # a few frames at hand-off (NEXT TURN banner) are tolerated: 5 %
    return {"pass": ok, "detail": "own HUD colour on both windows" if ok else "a window drew the other army's HUD", **res}


# ---- black ----
def c_black(run, black_ms=4000, **kw):
    t0 = run.t0()
    out = {}
    ok = True
    for s in run.seats:
        runs, cur = [], None
        for x in run.shots(s):
            if x["ms"] < t0 - 2000:
                continue
            a = np.asarray(game(run.image(x["file"])).convert("L").resize((96, 64)), dtype=int)
            blk = (a < 20).mean()
            bright = (a > 200).sum()
            black = blk >= 0.85 and bright <= 6
            if black:
                if cur and x["ms"] - cur[1] <= 1500:
                    cur[1] = x["ms"]
                else:
                    cur = [x["ms"], x["ms"]]
                    runs.append(cur)
        long_ = [{"t": round((a - t0) / 1000, 1), "ms": b - a} for a, b in runs if b - a >= black_ms]
        out[s] = {"black_runs": len(runs), "long": long_}
        ok = ok and not long_
    return {"pass": ok, "detail": "no long black runs" if ok else f"black for {black_ms} ms or more", "seats": out}


def c_gfx(run, frozen_ms=20000, **kw):
    """Graphics sanity of a live run: black runs (c_black) and FROZEN windows: identical consecutive pictures for longer than `frozen_ms` while the game
    state still changes (the mover's acts / state lines advance). For tile, text and palette integrity of catalogued screens use `aw2dev gfx check`."""
    res = {}
    ok = True
    st = run.states()
    for s in run.seats:
        prev, run_start, worst, spans = None, None, 0, []
        for x in run.shots(s):
            a = np.asarray(game(run.image(x["file"])).convert("L").resize((60, 40)), dtype=int)
            if prev is not None and np.abs(a - prev).max() == 0:
                run_start = run_start if run_start is not None else x["ms"]
                length = x["ms"] - run_start
                if length > frozen_ms:
                    moving = any(run_start <= r["ms"] <= x["ms"] and (r.get("army"), r.get("mover")) != (st[0].get("army"), st[0].get("mover")) for r in st) if st else False
                    if moving and (not spans or spans[-1][0] != run_start):
                        spans.append((run_start, x["ms"]))
                worst = max(worst, length)
            else:
                run_start = None
            prev = a
        res[s] = {"longest_identical_ms": worst, "frozen_spans": len(spans)}
        ok = ok and not spans
    b = c_black(run, **kw)
    return {"pass": ok and b["pass"], "detail": "no frozen or black windows" if ok and b["pass"] else "a window froze (identical pictures while the game moved on) or stayed black", "seats": res, "black": b["detail"]}


def c_colours(**kw):
    ok = True
    for sc, n in (("aw2_waiting_colours_2p", None), ("aw2_waiting_colours_2p_nofog", None), ("aw2_waiting_colours_ship_5p", None)):
        rc, _ = harness.run_script(sc, cfg.work("check", sc), sample=10)
        ok = ok and rc == 0
    b = util.example_bin("aw2_colour_matrix")
    if b.exists():
        r = subprocess.run([str(b), str(cfg.aw2_rom())], capture_output=True, text=True, cwd=cfg.REPO)
        ok = ok and r.returncode == 0
    return {"pass": ok, "detail": "colour scripts and the colour matrix pass" if ok else "a colour script failed"}


CHECKS = {"gfx": c_gfx, "hash": c_hash, "leak": c_leak, "mover": c_mover, "cam": c_cam, "hud": c_hud, "black": c_black}


def cmd(args):
    if args.colours and not args.run:
        r = c_colours()
        print(json.dumps(r))
        return 0 if r["pass"] else 1
    run = Run(args.run if args.run != "latest" else Run.latest())
    chosen = [n for n in ALL if getattr(args, n)] or ALL
    seats = [int(x) for x in args.seats.split(",")] if args.seats else None
    kw = {"seats": seats, "black_ms": args.black_ms}
    report = {"run": str(run.dir), "build": run.meta.get("build"), "scenario": run.meta.get("scenario"), "fog": run.meta.get("fog"), "checks": {}}
    summ = None
    try:
        summ = json.loads((run.dir / "summary.json").read_text())
    except Exception:
        pass
    if summ is not None and not summ.get("ok", True):
        report["run_summary"] = {"ok": False, "gave_up": summ.get("gave_up")}
    for name in chosen:
        try:
            r = CHECKS[name](run, **kw)
        except Exception as e:
            r = {"pass": False, "detail": f"checker crashed: {e!r}"}
        report["checks"][name] = r
        mark = {True: "PASS", False: "FAIL", None: "n/a "}[r["pass"]]
        print(f"  [{mark}] {name}: {r['detail']}")
    if args.colours:
        r = c_colours()
        report["checks"]["colours"] = r
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] colours: {r['detail']}")
    report["pass"] = all(v["pass"] is not False for v in report["checks"].values()) and (summ is None or summ.get("ok", True))
    (run.dir / "check.json").write_text(json.dumps(report, indent=1, default=str))
    util.say(f"{'PASS' if report['pass'] else 'FAIL'} {run.dir.name} (report: {run.dir / 'check.json'})")
    return 0 if report["pass"] else 1
