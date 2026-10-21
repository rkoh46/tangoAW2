"""Configuration: devkit/config.toml, then devkit/config.local.toml, then AW2DEV_<SECTION>_<KEY> environment variables."""
import os, subprocess, tomllib
from pathlib import Path

DEVKIT = Path(__file__).resolve().parent.parent
REPO = DEVKIT.parent


def _load():
    c = tomllib.loads((DEVKIT / "config.toml").read_text())
    local = DEVKIT / "config.local.toml"
    if local.exists():
        for sec, vals in tomllib.loads(local.read_text()).items():
            c.setdefault(sec, {}).update(vals)
    for sec, vals in c.items():
        for k, v in list(vals.items()):
            e = os.environ.get(f"AW2DEV_{sec}_{k}".upper())
            if e is not None:
                vals[k] = e.split(os.pathsep) if isinstance(v, list) else (type(v)(e) if not isinstance(v, str) else e)
    return c


C = _load()


def path(sec, key):
    p = Path(os.path.expanduser(str(C[sec][key])))
    return p if p.is_absolute() else REPO / p


def work(*parts):
    p = path("paths", "work").joinpath(*parts)
    return p


def env_with_cargo(extra=None):
    e = dict(os.environ)
    e["PATH"] = str(path("paths", "cargo_bin")) + os.pathsep + e.get("PATH", "")
    e.pop("DEVELOPER_DIR", None) if e.get("DEVELOPER_DIR", "").startswith("/Library/Developer/CommandLineTools") else None
    if extra:
        e.update(extra)
    return e


def aw2_rom():
    return path("paths", "roms") / C["paths"]["aw2_rom"]


def ds_rom():
    return path("paths", "roms") / C["paths"]["ds_rom"]


def version():
    for line in (REPO / "tango" / "Cargo.toml").read_text().splitlines():
        if line.startswith("version"):
            return line.split('"')[1]


def git(*args, check=True, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd or REPO, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()
