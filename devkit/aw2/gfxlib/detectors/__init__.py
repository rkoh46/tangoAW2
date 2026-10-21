"""Detectors: each module defines NAME and `run(ctx) -> [finding]`. ctx has .screen (catalogue entry), .renders {variant: dir}, .golden {variant: dir or None},
.out (artifact dir). A finding: {"detector", "shot", "severity": "fail"|"warn", "msg", "artifact": optional PNG path}. Add a module here to add a detector
(it is picked up automatically; list it in the screen's `checks` in devkit/gfx/catalogue.toml)."""
import importlib, pkgutil


def all_detectors():
    out = {}
    for m in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f"{__name__}.{m.name}")
        if hasattr(mod, "NAME") and hasattr(mod, "run"):
            out[mod.NAME] = mod
    return out
