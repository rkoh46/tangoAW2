"""aw2dev install-mac: put release-dist into /Applications/TangoAW2.app without closing a running app."""
import os, shutil, subprocess
from . import cfg, util


def install(args):
    app = cfg.path("paths", "app")
    binary = util.release_bin("release-dist")
    util.check_fresh(binary, "release-dist tango (build it: aw2dev build --release)")
    macos = app / "Contents" / "MacOS"
    if not macos.is_dir():
        util.die(f"{app} is not an installed TangoAW2.app (install a release dmg once first)")
    ver = cfg.version()
    new = macos / "tango.new"
    shutil.copy2(binary, new)
    os.chmod(new, 0o755)
    running = util.pids_for(str(macos / "tango"))
    os.replace(new, macos / "tango")   # a running game keeps its old inode; the new binary loads on the next launch
    plist = app / "Contents" / "Info.plist"
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        util.run(["plutil", "-replace", key, "-string", ver, str(plist)])
    util.run(["codesign", "--force", "--deep", "-s", "-", str(app)])
    r = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True, text=True)
    util.say(f"installed {ver} into {app}" + (f"; {len(running)} running copy kept open: reopen the app to load it" if running else ""))
    if r.returncode:
        util.say("codesign verify:", r.stderr.strip())
        return 1
    return 0
