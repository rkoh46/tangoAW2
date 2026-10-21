"""External checks: commands whose exit code is a finding (existing checkers and tests that already know a screen's bug: tools/hud_check.py, aw2test).
`external = [{cmd = ["python3", "tools/hud_check.py", "{dump}", "1", "red", "945"], what = "..."}]`; `{dump}` is the AW2_DUMP dir, `{out}` the render dir (variant `variant`
or the first), `{repo}` the repo root."""
import subprocess
from ... import cfg

NAME = "external"


def run(ctx):
    out = []
    for e in ctx.screen.get("external", []):
        v = e.get("variant") or next(iter(ctx.renders))
        d = ctx.renders[v]
        cmd = [str(c).format(dump=d / "dump", out=d, repo=cfg.REPO) for c in e["cmd"]]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cfg.REPO)
        if r.returncode:
            out.append({"detector": NAME, "shot": v, "severity": "fail", "msg": f"{e.get('what', ' '.join(cmd[:3]))}: exit {r.returncode}: " + " ".join((r.stdout + r.stderr).split())[:200]})
    return out
