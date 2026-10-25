"""aw2dev ci: run what the GitHub "checks" workflow runs, on this machine (docs/dev/testing.md "CI").

  ci [--job conventions|test] [--list] [--fast]     every `run:` line of `.github/workflows/checks.yaml` (the install steps and the apt line left out), in order, stopping nowhere:
                                                    the summary names each step that failed. `--fast` leaves out the cargo test steps (conventions only).

The workflow is read, not copied: a step added to checks.yaml is run here the next time. `cargo machete` needs `cargo install cargo-machete --version 0.8.0 --locked`
(looked for on PATH and in ~/.cargo/bin; the step is reported as skipped without it, never as passed)."""
import os
import re
import shutil
import subprocess
import sys

from .. import cfg, util


def register(sub):
    p = sub.add_parser("ci", help="run the GitHub checks workflow's commands locally (cargo machete, workspace conventions, rustfmt, the test steps)")
    p.add_argument("--job", choices=("conventions", "test"), help="only this job")
    p.add_argument("--list", action="store_true", help="print the steps and stop")
    p.add_argument("--fast", action="store_true", help="the conventions only (no cargo test)")
    p.set_defaults(fn=run)


def steps(text):
    """[(job, command)] from the workflow's text: every `run:` (single line or `|` block), in order. A tiny reader for this file's shape (no YAML library needed)."""
    out, job, lines, i = [], None, text.splitlines(), 0
    in_jobs = False
    while i < len(lines):
        l = lines[i]
        if l.startswith("jobs:"):
            in_jobs = True
        elif in_jobs and re.match(r"^  [a-z][\w-]*:\s*$", l):
            job = l.strip().rstrip(":")
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", l)
        if m and job:
            indent, rest = len(m.group(1)), m.group(2)
            if rest in ("|", ">"):
                block = []
                i += 1
                while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                    block.append(lines[i].strip())
                    i += 1
                out += [(job, c) for c in block if c]
                continue
            out.append((job, rest))
        i += 1
    return out


SKIP = ("sudo apt-get", "cargo install")


def run(a):
    wf = cfg.REPO / ".github" / "workflows" / "checks.yaml"
    todo = [(j, c) for j, c in steps(wf.read_text()) if not c.startswith(SKIP)]
    if a.job:
        todo = [(j, c) for j, c in todo if j == a.job]
    if a.fast:
        todo = [(j, c) for j, c in todo if not c.startswith("cargo test")]
    if a.list:
        for j, c in todo:
            print(f"{j:12s} {c}")
        return 0
    env = cfg.env_with_cargo()
    env["PATH"] = os.pathsep.join([str(os.path.expanduser("~/.cargo/bin")), env.get("PATH", "")])
    env["CMAKE_POLICY_VERSION_MINIMUM"] = "3.5"
    bad, skipped = [], []
    for job, cmd in todo:
        if cmd == "cargo machete" and not shutil.which("cargo-machete", path=env["PATH"]):
            skipped.append(cmd)
            util.say(f"ci {job}: SKIP {cmd} (cargo install cargo-machete --version 0.8.0 --locked)")
            continue
        util.say(f"ci {job}: {cmd}")
        r = subprocess.run(cmd, shell=True, cwd=cfg.REPO, env=env)
        if r.returncode:
            bad.append(cmd)
    for c in bad:
        print("FAIL", c)
    print(f"ci done steps={len(todo)} bad={len(bad)} skipped={len(skipped)}")
    return 1 if bad else 0
