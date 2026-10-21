"""Test profiles (TANGOAW2_PROFILE dirs) and the stamped test app bundle. Everything lands under devkit/work/."""
import json, os, plistlib, shutil, subprocess
from pathlib import Path
from . import cfg, util

NAMES = ["host", "guest", "guest2", "guest3", "guest4"]
GAMERTAGS = ["Host", "Guest", "Guest3", "Guest4", "Guest5"]


def profile_dir(name):
    return cfg.work("profiles", name)


def _clone(src, dst):
    """APFS clone copy (instant, no extra space); plain copy elsewhere. The source is only read."""
    if dst.exists():
        return
    r = subprocess.run(["cp", "-c", str(src), str(dst)], capture_output=True)
    if r.returncode:
        shutil.copy2(src, dst)


def ensure(name, pack=True, reset=False):
    """Create (or reuse) a profile. The ROM (and the Dual Strike pack when `pack`) are copied in; the ROM folder is never written."""
    d = profile_dir(name)
    if reset and d.exists():
        shutil.rmtree(d)
    data = d / "data"
    for sub in ("roms", "saves", "patches", "replays", "logs"):
        (data / sub).mkdir(parents=True, exist_ok=True)
    (d / "config").mkdir(parents=True, exist_ok=True)
    rom = cfg.aw2_rom()
    if not rom.exists():
        util.die(f"AW2 ROM not found at {rom} (set paths.roms in devkit/config.local.toml or AW2DEV_PATHS_ROMS)")
    _clone(rom, data / "roms" / rom.name)
    if pack:
        for p in cfg.C["paths"]["packs"]:
            src = cfg.path("paths", "roms") / p
            if src.exists():
                _clone(src, data / "roms" / src.name)
    cj = d / "config" / "config.json"
    if not cj.exists():
        idx = NAMES.index(name) if name in NAMES else 0
        cj.write_text(json.dumps({
            "data_path": str(data),
            "gamertag": GAMERTAGS[idx] if name in NAMES else name.title(),
            "last_game": ["aw2", 0], "last_family": "aw2",
            "last_save_per_family": {"aw2": "saves/Advance Wars 2.sav"},
            "language": "en-US", "theme": "AdvanceWars", "advance_wars_skin": True, "ds_graphics": True,
            "enable_updater": False, "allow_prerelease_upgrades": False,
            "volume": float(cfg.C["live"].get("volume", 0.0)),
            "last_window_position": [40.0 + 480 * (idx % 3), 80.0 + 380 * (idx // 3)], "last_window_size": [480.0, 360.0],
        }, indent=2))
    return d


def reset_live_state(name):
    """Drop the per-profile leftovers that change a run (an unranked match to rejoin) and empty the app log."""
    data = profile_dir(name) / "data"
    for f in ("unranked_live.json", "unranked_live.part"):
        (data / f).unlink(missing_ok=True)
    shutil.rmtree(data / "suspended", ignore_errors=True)
    lg = data / "logs" / "tango.log"
    lg.parent.mkdir(parents=True, exist_ok=True)
    lg.write_text("")
    return lg


def test_app(binary):
    """work/testapp/tangoAW2.app with `binary` as its executable. A bundle of our own: its path is unique to this worktree's
    runs, so pgrep/kill never touches the player's /Applications/TangoAW2.app or another worktree's windows."""
    app = cfg.work("testapp", "tangoAW2.app")
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    plist = app / "Contents" / "Info.plist"
    if not plist.exists():
        plist.write_bytes(plistlib.dumps({
            "CFBundleExecutable": "tango", "CFBundleIdentifier": "net.n1gp.TangoAW2.devkit", "CFBundleName": "TangoAW2 devkit",
            "CFBundlePackageType": "APPL", "CFBundleVersion": cfg.version() or "0", "CFBundleShortVersionString": cfg.version() or "0",
            "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "10.15.7",
        }))
    dst = macos / "tango"
    shutil.copy2(binary, dst)
    return dst
