"""Run the audit: the scenes (tools/aw2test/aw2test/audit_scenes.py, one worker process each per look), the detectors over what they wrote, the report and the sheets."""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ... import cfg, util
from . import detectors, sheets

WORKER = cfg.REPO / "tools" / "aw2test" / "audit_worker.py"
LOOKS = ("aw2_nopack", "aw2", "ds_tilt", "ds_flat")
LOOK_NAMES = {"aw2_nopack": "AW2 graphics, no pack", "aw2": "AW2 graphics (pack)", "ds_tilt": "Dual Strike map graphics, tilt", "ds_flat": "Dual Strike map graphics, flat"}
SHEET_SHAPE = {"online": (4, 6, 1)}      # (cols, rows, scale) where the default 3 x 3 at 2x would need dozens of sheets


def scene_list():
    r = subprocess.run([sys.executable, str(WORKER), "--list"], capture_output=True, text=True, cwd=cfg.REPO)
    if r.returncode:
        util.die("audit_worker --list failed:\n" + r.stderr[-1500:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def plan(modes=None, scenes=None, looks=None):
    """[(mode, scene, look)] of every scene run in every look it has (filtered)."""
    jobs = []
    for s in scene_list():
        if modes and s["mode"] not in modes:
            continue
        if scenes and s["scene"] not in scenes:
            continue
        for look in s["looks"]:
            if looks and look not in looks:
                continue
            jobs.append((s["mode"], s["scene"], look))
    return jobs


def run_job(job, out, binary_dir=None, timeout=1500):
    mode, scene, look = job
    d = Path(out) / mode / scene / look
    env = dict(os.environ)
    env.pop("TANGOAW2_DS_ROM", None)
    if binary_dir:
        env["AW2TEST_RUNNER_DIR"] = str(binary_dir)
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(WORKER), mode, scene, look, str(d)], capture_output=True, text=True, cwd=cfg.REPO, env=env, timeout=timeout)
        (d / "worker.log").write_text(r.stdout + "\n--- stderr ---\n" + "\n".join(l for l in r.stderr.splitlines() if not l.startswith("ds_tilt "))[-20000:])
        rc = r.returncode
    except subprocess.TimeoutExpired:
        (d / "manifest.json").write_text(json.dumps({"mode": mode, "scene": scene, "look": look, "shots": [], "facts": [], "notes": [], "error": f"timed out after {timeout}s"}))
        rc = 124
    return job, rc, time.time() - t0


def sweep(out, jobs, nproc=4, binary_dir=None, timeout=1500, quiet=False):
    done = []
    with ThreadPoolExecutor(nproc) as ex:
        for job, rc, secs in ex.map(lambda j: run_job(j, out, binary_dir, timeout), jobs):
            done.append((job, rc, secs))
            if not quiet:
                util.say(f"{'ok  ' if rc == 0 else 'FAIL'} {'/'.join(job)} ({secs:.0f}s)")
    return done


def load_manifest(out, job):
    p = Path(out) / job[0] / job[1] / job[2] / "manifest.json"
    if not p.exists():
        return {"mode": job[0], "scene": job[1], "look": job[2], "shots": [], "facts": [], "notes": [], "error": "the scene wrote no manifest (the worker crashed: see worker.log)"}
    return json.loads(p.read_text())


def tilt_findings(out, job, man):
    """The tilt's own per-frame logs (`tiltall`): a camera check where more than 2% of the sampled ground pixels differ from the console's BG3 (the tilted picture would be of another map than the
    one the game shows), frames where a blend or window shows the flat map (a leak). Frames the tilt leaves flat on purpose (menus, scenes, dialogue boxes: `skip line`) are only counted in the notes."""
    if not man.get("tilt_log"):
        return []
    p = Path(man["tilt_log"])
    if not p.exists():
        return []
    frames, skip, leak, cam = 0, 0, set(), {}
    fr = -1
    for l in p.read_text(errors="ignore").splitlines():
        m = re.match(r"@frame (\d+)", l)
        if m:
            fr = int(m.group(1))
            frames += 1
        elif l.startswith("ds_tilt skip line"):
            skip += 1
        else:
            m = re.match(r"ds_tilt leak (\d+)", l)
            if m and int(m.group(1)) > 0:
                leak.add(fr)
            m = re.match(r"ds_tilt camcheck bad=(\d+) seen=(\d+)", l)
            if m and int(m.group(2)) and int(m.group(1)) / int(m.group(2)) > 0.02:
                cam[fr] = int(m.group(1)) / int(m.group(2))
    man.setdefault("notes", []).append(f"tilt: {frames} frames, {skip} left flat on purpose")
    out_f = []
    if cam:
        out_f.append({"detector": "tilt", "severity": "fail" if len(cam) * 10 > frames else "warn", "shot": "(tilt log)",
                      "msg": f"{len(cam)} of {frames} tilted frames: the ground drawn from the map differs from the console's BG3 on up to {max(cam.values()):.0%} of the sampled pixels, first at frame {min(cam)}"})
    if leak:
        out_f.append({"detector": "tilt", "severity": "warn", "shot": "(tilt log)", "msg": f"{len(leak)} of {frames} tilted frames: a blend or window shows the flat map, first at frame {min(leak)}"})
    return out_f


def judge(out, jobs, only=None):
    """Run the detectors over every shot of every job. Returns {"findings": [...], "shots": n, "jobs": {...}}."""
    findings, stats = [], {}
    for job in jobs:
        man = load_manifest(out, job)
        d = Path(out) / job[0] / job[1] / job[2]
        prev = None
        n = 0
        for sh in man["shots"]:
            shot = detectors.Shot(job[0], job[1], job[2], sh["name"], d / sh["png"], d / sh["vram"] if sh.get("vram") else None, sh.get("tags", []), sh, prev=prev)
            for f in detectors.judge(shot, only):
                f.update({"mode": job[0], "scene": job[1], "look": job[2], "shot": sh["name"], "png": str(d / sh["png"])})
                findings.append(f)
            prev = shot
            n += 1
        for f in man.get("facts", []):
            if not f["ok"]:
                findings.append({"detector": "facts", "severity": "fail", "mode": job[0], "scene": job[1], "look": job[2], "shot": "(fact)", "msg": f["msg"]})
        if man.get("error"):
            findings.append({"detector": "scene", "severity": "fail", "mode": job[0], "scene": job[1], "look": job[2], "shot": "(scene)", "msg": "the scene stopped: " + man["error"].strip().splitlines()[-1]})
        for f in tilt_findings(out, job, man):
            f.update({"mode": job[0], "scene": job[1], "look": job[2]})
            findings.append(f)
        stats["/".join(job)] = {"shots": n, "facts": len(man.get("facts", [])), "error": bool(man.get("error"))}
    return {"findings": findings, "stats": stats}


def make_sheets(out, jobs, findings):
    """Contact sheets per (mode, look) into <out>/sheets. Returns {(mode, look): [paths]}."""
    bad = {(f["mode"], f["scene"], f["look"], f["shot"]) for f in findings if f.get("shot") and f["severity"] == "fail"}
    sheets_out = {}
    groups = {}
    for job in jobs:
        groups.setdefault((job[0], job[2]), []).append(job)
    for (mode, look), js in sorted(groups.items()):
        items = []
        for job in js:
            man = load_manifest(out, job)
            for sh in man["shots"]:
                p = Path(out) / job[0] / job[1] / job[2] / sh["png"]
                if p.exists():
                    items.append((str(p), f"{job[1]}/{sh['name']}", (job[0], job[1], job[2], sh["name"]) in bad))
        if items:
            cols, rows, scale = SHEET_SHAPE.get(mode, (3, 3, 2))
            sheets_out[(mode, look)] = sheets.make([(a, b, c) for a, b, c in items], Path(out) / "sheets", f"{mode}__{look}", cols=cols, rows=rows, scale=scale)
    return sheets_out


def write_report(out, jobs, result, sheets_out, args_line=""):
    f = result["findings"]
    fails = [x for x in f if x["severity"] == "fail"]
    warns = [x for x in f if x["severity"] != "fail"]
    out = Path(out)
    (out / "report.json").write_text(json.dumps({"command": args_line, "jobs": ["/".join(j) for j in jobs], "stats": result["stats"], "findings": f,
                                                  "sheets": {f"{m}/{l}": p for (m, l), p in sheets_out.items()}}, indent=1))
    L = [f"# Graphics audit {time.strftime('%Y-%m-%d %H:%M')}", "", f"`{args_line}`", "",
         f"{len(jobs)} scene runs, {sum(s['shots'] for s in result['stats'].values())} pictures: **{len(fails)} failing findings**, {len(warns)} warnings.", "",
         "## Coverage (pictures per mode and look)", ""]
    modes = sorted({j[0] for j in jobs})
    looks = [l for l in LOOKS if any(j[2] == l for j in jobs)]
    L.append("| mode | scenes | " + " | ".join(looks) + " |")
    L.append("|---|---|" + "---|" * len(looks))
    for m in modes:
        scs = sorted({j[1] for j in jobs if j[0] == m})
        cells = []
        for l in looks:
            n = sum(result["stats"].get(f"{m}/{s}/{l}", {}).get("shots", 0) for s in scs)
            runs = sum(1 for s in scs if f"{m}/{s}/{l}" in result["stats"])
            cells.append(f"{n} ({runs})" if runs else "-")
        L.append(f"| {m} | {', '.join(scs)} | " + " | ".join(cells) + " |")
    L += ["", "(each cell: pictures taken, and the scene runs in brackets)", "", "## Findings", ""]
    if not f:
        L.append("None.")
    by = {}
    for x in f:
        by.setdefault((x["detector"], x["severity"]), []).append(x)
    for (det, sev), xs in sorted(by.items()):
        L.append(f"### {det} ({sev}): {len(xs)}")
        L.append("")
        for x in xs[:60]:
            L.append(f"- `{x['mode']}/{x['scene']}/{x['look']}` {x.get('shot', '')}: {x['msg']}" + (f"  ![]({os.path.relpath(x['png'], out)})" if x.get("png") else ""))
        if len(xs) > 60:
            L.append(f"- ... {len(xs) - 60} more in report.json")
        L.append("")
    L += ["## Contact sheets", ""]
    for (m, l), ps in sorted(sheets_out.items()):
        L.append(f"- {m} / {LOOK_NAMES.get(l, l)}: " + ", ".join(os.path.relpath(p, out) for p in ps))
    (out / "report.md").write_text("\n".join(L) + "\n")
    return fails, warns
