"""aw2dev release <version> --notes FILE: the release checklist, in order. NEVER pushes without --yes (pushing needs the user's approval each time).

Preflight (always run, also with --dry-run): dev branch, clean tree, every target branch is a fast-forward of HEAD, no game files in the
new commits, version is new, notes file present.  Then the steps: bump -> build release-dist -> tests -> install-mac -> IPA -> annotated
tag -> push (--yes only) -> watch the workflow (rerun failed jobs once) -> list the assets.  --dry-run prints the steps and runs nothing.
"""
import fnmatch, json, os, re, shutil, subprocess, time
from pathlib import Path
from . import build as buildmod, cfg, install, util

R = lambda k: cfg.C["release"][k]


def ok(msg):
    print(f"  [ok]   {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")


def scan_game_files(base):
    """Files the new commits add that look like game files: ROMs, saves, PNGs outside the allowed dirs, aw2test output."""
    allow = list(R("allowed_dirs"))
    extra = cfg.DEVKIT / "release_allow.txt"
    patterns = [l.strip() for l in extra.read_text().splitlines() if l.strip() and not l.startswith("#")] if extra.exists() else []
    out = cfg.git("diff", "--name-status", "--no-renames", f"{base}..HEAD", check=False)
    hits = []
    for line in out.splitlines():
        st, _, path = line.partition("\t")
        if st not in ("A", "M"):
            continue
        name = path.rsplit("/", 1)[-1]
        for pat in R("forbidden"):
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(name, pat):
                if pat == "*.png" and (st != "A" or any(path.startswith(a) for a in allow)):
                    break
                if any(fnmatch.fnmatch(path, a) for a in patterns):
                    break
                hits.append(path)
                break
    return hits


def preflight(version, notes):
    fails = 0
    remote = R("remote")
    br = cfg.git("rev-parse", "--abbrev-ref", "HEAD")
    if br == R("dev_branch"):
        ok(f"on dev branch {br}")
    else:
        bad(f"on branch {br}, releases go from {R('dev_branch')}")
        fails += 1
    dirty = cfg.git("status", "--porcelain", "--untracked-files=no")
    if not dirty:
        ok("worktree clean")
    else:
        bad("uncommitted changes:\n    " + dirty.replace("\n", "\n    "))
        fails += 1
    f = subprocess.run(["git", "fetch", "--quiet", remote, "--tags"], cwd=cfg.REPO, capture_output=True, text=True)
    if f.returncode:
        bad(f"git fetch {remote} failed: {f.stderr.strip()}")
        fails += 1
    base = None
    for b in R("push_branches"):
        ref = f"{remote}/{b}"
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=cfg.REPO, capture_output=True).returncode:
            ok(f"{ref} does not exist yet (will be created)")
            continue
        base = base or ref
        if subprocess.run(["git", "merge-base", "--is-ancestor", ref, "HEAD"], cwd=cfg.REPO).returncode == 0:
            ok(f"HEAD:{b} is a fast-forward of {ref}")
        else:
            bad(f"HEAD:{b} would NOT be a fast-forward of {ref}")
            fails += 1
    hits = scan_game_files(base or "HEAD")
    new = cfg.git("rev-list", "--count", f"{base}..HEAD") if base else "?"
    if not hits:
        ok(f"no game files in the {new} new commits")
    else:
        bad("game files in the new commits:\n    " + "\n    ".join(hits))
        fails += 1
    tag = R("tag_prefix") + version
    if cfg.git("tag", "--list", tag):
        bad(f"tag {tag} exists")
        fails += 1
    else:
        ok(f"tag {tag} is free")
    cur = cfg.version()
    key = lambda v: [int(x) for x in re.findall(r"\d+", v)]
    if key(version) > key(cur):
        ok(f"version {cur} -> {version}")
    else:
        bad(f"version {version} is not above {cur}")
        fails += 1
    if notes and Path(notes).is_file() and Path(notes).read_text().strip():
        ok(f"notes {notes} ({len(Path(notes).read_text().splitlines())} lines)")
    else:
        bad(f"notes file {notes} missing or empty (the changelog goes in the tag message / release notes, not the README)")
        fails += 1
    if shutil.which("gh"):
        ok("gh available")
    else:
        bad("gh not installed: cannot watch the workflow")
        fails += 1
    return fails


def bump(version):
    p = cfg.REPO / "tango" / "Cargo.toml"
    t = p.read_text()
    t2 = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', t, count=1)
    p.write_text(t2)
    lock = cfg.REPO / "Cargo.lock"
    lt = lock.read_text()
    lt2 = re.sub(r'(name = "tango"\nversion = )"[^"]+"', rf'\1"{version}"', lt, count=1)
    if lt2 == lt:
        util.die("Cargo.lock has no tango entry to bump")
    lock.write_text(lt2)
    cfg.git("add", "tango/Cargo.toml", "Cargo.lock")
    cfg.git("commit", "-m", f"Version {version}")


def release(args):
    version = args.version.lstrip("v")
    tag = R("tag_prefix") + version
    dry = args.dry_run
    print(f"release {version} ({'DRY RUN' if dry else 'for real'}; push {'ALLOWED (--yes)' if args.yes else 'refused without --yes'})")
    print("preflight:")
    fails = preflight(version, args.notes)
    if fails and not (dry or args.force):
        util.die(f"{fails} preflight check(s) failed; fix them (or --dry-run to see the steps)")
    dd = cfg.path("paths", "developer_dir")
    ipa = R("ipa_name").format(version=version)
    push_branches = " ".join(f"HEAD:{b}" for b in R("push_branches"))
    steps = [
        ("bump", f"set version = \"{version}\" in tango/Cargo.toml and the tango entry of Cargo.lock; commit 'Version {version}'", lambda: bump(version)),
        ("build", "cargo build --profile release-dist --bin tango", lambda: buildmod.build(_A(release=True))),
        ("tests", "cargo test --lib: tango-gamesupport-aw2, tango-session, tango-match", lambda: _chk(buildmod.test(_A(package=None)), "tests")),
        ("install-mac", f"copy release-dist into {cfg.path('paths', 'app')}, plutil version {version}, ad-hoc codesign (a running app is left open)", lambda: _chk(install.install(_A()), "install-mac")),
        ("ipa", f"DEVELOPER_DIR={dd} ./ios/build.sh -> dist/{ipa}, copied to {cfg.path('paths', 'downloads')}", lambda: _ipa(ipa)),
        ("tag", f"git tag -a {tag} -F {args.notes}", lambda: cfg.git("tag", "-a", tag, "-F", str(args.notes))),
        ("push", f"git push {R('remote')} {R('dev_branch')} {push_branches} {tag}   [needs --yes]", lambda: _push(args, tag, push_branches)),
        ("watch", f"gh run list/watch --workflow {R('workflow')} for {tag}; rerun failed jobs once", lambda: _watch(tag)),
        ("assets", f"gh release view {tag}: list the assets", lambda: _assets(tag)),
    ]
    skip = set(args.skip or [])
    print("steps:")
    for i, (name, desc, fn) in enumerate(steps, 1):
        flag = " (skipped)" if name in skip else ""
        print(f"  {i}. {name}: {desc}{flag}")
    if dry:
        print("dry run: nothing was changed, nothing pushed.")
        return 1 if fails else 0
    for name, desc, fn in steps:
        if name in skip:
            continue
        util.say(f"== {name}")
        fn()
    return 0


class _A:
    def __init__(self, **kw):
        self.ios = self.sim = self.examples = self.all = self.release = False
        self.package = None
        self.__dict__.update(kw)


def _chk(rc, what):
    if rc:
        util.die(f"{what} failed; stopping before anything is pushed")


def _ipa(name):
    env = dict(os.environ, DEVELOPER_DIR=str(cfg.path("paths", "developer_dir")))
    env["PATH"] = str(cfg.path("paths", "cargo_bin")) + os.pathsep + env["PATH"]
    util.run(["./ios/build.sh"], env=env, cwd=cfg.REPO)
    src = cfg.REPO / "dist" / name
    if not src.exists():
        util.die(f"{src} was not produced")
    dst = cfg.path("paths", "downloads") / name
    shutil.copy2(src, dst)
    util.say("IPA copied to", dst)


def _push(args, tag, push_branches):
    if not args.yes:
        util.die("REFUSING to push: pass --yes after the user approved this release. Everything local is done (commit, tag " + tag + ").", 3)
    util.run(f"git push {R('remote')} {R('dev_branch')} {push_branches}", cwd=cfg.REPO)
    util.run(["git", "push", R("remote"), tag], cwd=cfg.REPO)


def _gh(*a):
    r = subprocess.run(["gh", *a], cwd=cfg.REPO, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def _watch(tag):
    run_id = None
    for _ in range(40):
        rc, out = _gh("run", "list", "--workflow", R("workflow"), "--branch", tag, "--limit", "1", "--json", "databaseId,status,conclusion")
        if rc == 0 and out and json.loads(out):
            run_id = json.loads(out)[0]["databaseId"]
            break
        time.sleep(5)
    if not run_id:
        util.die("no release workflow run appeared for " + tag)
    for attempt in (1, 2):
        r = subprocess.run(["gh", "run", "watch", str(run_id), "--exit-status", "--interval", "30"], cwd=cfg.REPO)
        if r.returncode == 0:
            util.say("release workflow succeeded")
            return
        if attempt == 1:
            util.say("workflow failed: rerunning the failed jobs once")
            subprocess.run(["gh", "run", "rerun", str(run_id), "--failed"], cwd=cfg.REPO)
            time.sleep(15)
    util.die("release workflow failed twice; look at `gh run view " + str(run_id) + " --log-failed`")


def _assets(tag):
    rc, out = _gh("release", "view", tag, "--json", "assets", "-q", ".assets[] | \"\\(.name)  \\(.size)\"")
    print(out)
