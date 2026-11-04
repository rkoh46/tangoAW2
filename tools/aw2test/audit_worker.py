#!/usr/bin/env python3
"""One audit scene in one look (`aw2dev gfx audit` starts these in parallel): audit_worker.py MODE SCENE LOOK OUTDIR  |  audit_worker.py --list."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aw2test import audit  # noqa: E402


def main():
    scenes = audit.load_scenes()
    if sys.argv[1] == "--list":
        print(json.dumps([{"mode": m, "scene": n, "looks": s["looks"], "doc": s["doc"]} for (m, n), s in scenes.items()]))
        return 0
    mode, name, look, out = sys.argv[1:5]
    m = audit.run_scene(mode, name, look, out)
    print(json.dumps({"shots": len(m["shots"]), "facts": len(m["facts"]), "error": (m["error"] or "").strip().splitlines()[-1:] or None}))
    return 1 if m["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
