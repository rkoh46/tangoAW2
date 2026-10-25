"""`aw2dev co verify --net`: each custom CO's CO Power and Super Power played on two real app clients through `net repeat` (devkit/aw2/scenarios.py `co_<co>_cop`,
`co_<co>_scop`, `co_tag_<co>_<partner id>`): the two peers' hashes must agree on every run and the scripts must run to the end. The result goes to `devkit/work/co_verify/net.json`, which the
table's last column reads. (The leak check of `net repeat` is not part of this verdict: it flags the same episodes for Andy and Kanbei with these scripts, which attack from the map menu.)"""
import json
import re
import subprocess
import sys

from .. import cfg, scenarios, util

TAGS = {}      # (a Tag Power through net repeat: the first half plays, the Change to the second did not complete in the pad script; both peers' hashes were equal. The Tag Powers are played by `co_verify_tag_*` on the harness.)


def scenarios_for(cos):
    out = []
    for co in cos:
        out += [(f"{co} cop", f"co_{co}_cop"), (f"{co} scop", f"co_{co}_scop")]
        out += [(f"{co} tag {p}", f"co_tag_{co}_{p}") for p in TAGS.get(co, [])]
    return [(k, s) for k, s in out if s in scenarios.SCEN]


def run(a):
    cos = a.co or ["klaus", "aurelia", "cassius", "livia", "crumb", "varro", "cloneandy"]
    f = cfg.work("co_verify", "net.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(f.read_text()) if f.exists() else {}
    for key, scen in scenarios_for(cos):
        util.say(f"net repeat {scen} x{a.net_runs}")
        for attempt in range(6):        # (another worktree's live run may hold the lock past the wait: try again)
            r = subprocess.run([sys.executable, str(cfg.DEVKIT / "aw2dev"), "net", "repeat", scen, "--runs", str(a.net_runs), "--no-skin", "--fog", "off"], capture_output=True, text=True, cwd=cfg.REPO)
            rows = re.findall(r"^\s+(PASS|FAIL)\s+\S+\s+hash=(equal|DIVERGED)\s+scripts=(ran to the end|stalled)", r.stdout, re.M)
            if rows or "lock wait timed out" not in r.stderr + r.stdout:
                break
        good = sum(1 for _, h, s in rows if h == "equal" and s == "ran to the end")
        data[key] = {"runs": len(rows), "equal": good, "scenario": scen}
        f.write_text(json.dumps(data, indent=1))
        util.say(f"  {key}: {good} of {len(rows)} runs with equal hashes")
    return 0 if all(v["runs"] == v["equal"] for k, v in data.items() if k.split()[0] in cos) else 1
