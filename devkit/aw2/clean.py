"""aw2dev clean: free disk. Dry run unless --yes. Keeps only the configured worktrees (~/tangoAW2, ~/tangoAW2-hires) checked out."""
import os, shutil, subprocess, time
from pathlib import Path
from . import cfg, util


def worktrees():
    out = cfg.git("worktree", "list", "--porcelain")
    wts, cur = [], {}
    for l in out.splitlines() + [""]:
        if not l:
            if cur:
                wts.append(cur)
            cur = {}
        elif " " in l:
            k, v = l.split(" ", 1)
            cur[k] = v
        else:
            cur[l] = True
    return wts


def clean(args):
    keep = {str(Path(os.path.expanduser(p)).resolve()) for p in cfg.C["clean"]["keep_worktrees"]}
    here = str(cfg.REPO.resolve())
    apply = args.yes
    freed = 0
    util.say("plan" if not apply else "cleaning", "(dry run: add --yes to delete)" if not apply else "")
    want_all = not (args.runs or args.targets or args.worktrees or args.harness)
    # 1. old run PNGs
    if args.runs or want_all:
        runs = cfg.work("runs")
        cutoff = time.time() - args.days * 86400 if args.days is not None else time.time() - cfg.C["clean"]["run_days"] * 86400
        if runs.is_dir():
            for d in sorted(runs.iterdir()):
                if d.is_dir() and d.stat().st_mtime < cutoff:
                    size = sum(f.stat().st_size for f in d.rglob("*.png"))
                    if size:
                        print(f"  run PNGs {d.name}: {util.human(size)}")
                        freed += size
                        if apply:
                            for f in d.rglob("*.png"):
                                f.unlink()
    # 2. harness/suite outputs
    if args.harness or want_all:
        for sub in ("harness", "suite", "audit"):
            d = cfg.work(sub)
            if d.is_dir():
                size = util.du(d)
                print(f"  {d}: {util.human(size)}")
                freed += size
                if apply:
                    shutil.rmtree(d, ignore_errors=True)
    # 3. targets and worktrees
    for wt in worktrees():
        p = str(Path(wt["worktree"]).resolve())
        is_keep, is_here = p in keep, p == here
        tgt = Path(p) / "target"
        if (args.targets or want_all) and tgt.is_dir() and (not is_keep or args.keep_targets_too):
            if is_keep and not args.keep_targets_too:
                continue
            size = util.du(tgt)
            print(f"  target/ of {p}: {util.human(size)}")
            freed += size
            if apply and (is_here or args.other_targets):
                shutil.rmtree(tgt, ignore_errors=True)
            elif apply:
                print("    (another worktree's target: pass --other-targets to delete it; it may be building)")
        if (args.worktrees or want_all) and not is_keep and not is_here and not wt.get("bare"):
            dirty = cfg.git("status", "--porcelain", "--untracked-files=no", cwd=p, check=False)
            size = util.du(p)
            print(f"  stale worktree {p} ({wt.get('branch', 'detached')}): {util.human(size)}{'  DIRTY: skipped' if dirty else ''}")
            if dirty:
                continue
            freed += size
            if apply and args.remove_worktrees:
                cfg.git("worktree", "remove", "--force", p, check=False)
            elif apply:
                print("    (pass --remove-worktrees to remove it; the branch is kept; another agent may be using it)")
    util.say(f"{'freed' if apply else 'would free'} about {util.human(freed)}")
    print(util.df())
    return 0
