"""aw2dev playtest-app: build `dist/TangoAW2-Playtest.app`, a macOS bundle of this checkout with the Emerald Sun Campaign and its COs on by default (cargo feature `playtest`, no environment
variables) and everything of its own: bundle id `net.n1gp.TangoAW2Playtest`, name "TangoAW2 Playtest", settings under `net.n1gp.tangoaw2-playtest`, data under `~/Documents/TangoAW2-Playtest`
(a fresh install: point it at your ROMs once). It installs beside the real TangoAW2.app and never touches it, its settings, ROMs or saves; this command installs nothing and does not
touch /Applications. The self-updater is off in this build. Needs the Command Line Tools toolchain only."""
import os, plistlib, shutil, subprocess
from . import cfg, util

BUNDLE_ID = "net.n1gp.TangoAW2Playtest"
NAME = "TangoAW2 Playtest"


def build(args):
    root = cfg.REPO
    target = root / "target" / "playtest"
    cmd = ["cargo", "build", "--bin", "tango", "--profile", "release-dist", "--features", "playtest", "--target-dir", str(target)]
    util.say("building the playtest binary (release-dist, feature playtest): " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=root)
    if r.returncode:
        util.die("cargo build failed")
    binary = target / "release-dist" / "tango"
    app = root / "dist" / "TangoAW2-Playtest.app"
    if app.exists():
        shutil.rmtree(app)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir(parents=True)
    shutil.copy2(binary, app / "Contents" / "MacOS" / "tango")
    os.chmod(app / "Contents" / "MacOS" / "tango", 0o755)
    # (the icon, as macos/build.sh makes it)
    iconset = root / "dist" / "TangoAW2Playtest.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    src = root / "tango" / "src" / "icon.png"
    for size, name in ((16, "icon_16x16"), (32, "icon_16x16@2x"), (32, "icon_32x32"), (64, "icon_32x32@2x"), (128, "icon_128x128"), (256, "icon_128x128@2x"),
                       (256, "icon_256x256"), (512, "icon_256x256@2x"), (512, "icon_512x512"), (1024, "icon_512x512@2x")):
        subprocess.run(["sips", "-z", str(size), str(size), str(src), "--out", str(iconset / f"{name}.png")], check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "--output", str(app / "Contents" / "Resources" / "TangoAW2.icns")], check=True)
    shutil.rmtree(iconset)
    # (ffmpeg, for replay videos: copied from the installed app if there is one; read only, the installed app is not touched)
    ff = cfg.path("paths", "app") / "Contents" / "MacOS" / "ffmpeg"
    if ff.exists():
        shutil.copy2(ff, app / "Contents" / "MacOS" / "ffmpeg")
    ver = cfg.version()
    plist = {
        "CFBundleDevelopmentRegion": "en", "CFBundleExecutable": "tango", "CFBundleIconFile": "TangoAW2.icns", "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleInfoDictionaryVersion": "6.0", "CFBundleName": NAME, "CFBundleDisplayName": NAME, "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": f"{ver}-playtest", "CFBundleVersion": f"{ver}-playtest", "CFBundleSupportedPlatforms": ["MacOSX"],
        "LSMinimumSystemVersion": "10.15.7", "NSHumanReadableCopyright": "",
    }
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(plist, f)
    util.run(["codesign", "--force", "--deep", "-s", "-", str(app)])
    r = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True, text=True)
    util.say(f"built {app} (bundle id {BUNDLE_ID}, version {ver}-playtest)")
    if r.returncode:
        util.say("codesign verify:", r.stderr.strip())
        return 1
    return 0
