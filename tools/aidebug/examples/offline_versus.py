#!/usr/bin/env python3
"""Title screen to an offline Versus battle, state-driven (no fixed waits), then: read the state, build a Tank, move it,
take a screenshot, save a checkpoint.

    TANGOAW2_AUTOSTART=offline TANGOAW2_AI_DEBUG=47811 tango &
    python3 offline_versus.py 127.0.0.1:47811 [checkpoint-name]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from client import AiDebug  # noqa: E402

d = AiDebug.connect(sys.argv[1] if len(sys.argv) > 1 else None)
name = sys.argv[2] if len(sys.argv) > 2 else "versus_day1"

d.wait_until({"phase": "title"}, 90)
d.press_until("START", {"phase": "select_mode"}, 30)
# the wheel: DOWN until Versus (item 1) is under the cursor and the wheel is still
for _ in range(10):
    s = d.state(["screen_info"])["screen_info"]
    if s.get("wheel_item") == 1 and s.get("box_open") is False:
        break
    d.press("DOWN")
    time.sleep(0.7)
d.press_until("A", {"phase": "select_map"}, 20)           # Versus -> SELECT MAP
d.press_until("A", {"phase": "army_select"}, 20)          # first map
d.press_until("A", {"phase": "battle"}, 40)               # armies and rules pages
d.press_until("A", {"screen": "map", "cues.mapup": True}, 40, gap=1.5)   # the opening pages
s = d.state()
print("battle:", s["map"]["name"], "army", s["active_army"], "day", s["day"], "funds", [a["funds"] for a in s["armies"]])

base = next(p for p in s["properties"] if p["owner"] == s["active_army"] and p["name"] == "base")
d.goto(base["x"], base["y"])
d.press("A")                                              # the production menu
d.wait_until({"screen": "build_menu"}, 5)
m = d.state(["menu"])["menu"]
print("production menu:", [(r["text"], r["cost"], "ok" if r["enabled"] else "greyed") for r in m["rows"]][:6], "...")
d.press("DOWN")                                           # (the menu remembers its row: whatever is below it)
d.press("A")
d.wait_until({"unit_at": [base["x"], base["y"]]}, 10)
tank = next(u for u in d.state(["units"])["units"] if (u["x"], u["y"]) == (base["x"], base["y"]))
print("built:", tank["name"], "hp", tank["hp"], "fuel", tank["fuel"], "ammo", tank["ammo"])
d.press_until("B", {"screen": "map"}, 10, frames=6)
d.checkpoint_save(name)                                   # resume here later: TANGOAW2_BOOT_CHECKPOINT=<name>

# end the turn through the map menu, let the computer play, and move the new unit on day 2
d.press("A", 3)                                           # (a short press: a long one would also pick the menu's first item)
d.wait_until({"screen": "map_menu"}, 5)
for _ in range(8):
    if d.state(["menu"])["menu"]["item"] == "End":
        break
    d.press("DOWN")
d.press("A")
d.wait_until({"active_army": 1, "day": 2, "screen": "map"}, 180)
# (try neighbouring cells until the game accepts one: the unit's command menu opens)
dest = None
for dx, dy in [(0, -1), (1, -1), (-1, -1), (0, -2), (1, 0), (0, 1), (2, 0)]:
    d.press_until("B", {"screen": "map"}, 10, frames=6)
    d.goto(tank["x"], tank["y"])
    d.press("A")                                          # pick the unit up
    d.wait_until({"flags.plain_map": False}, 3)          # (the movement range is up)
    cell = (tank["x"] + dx, tank["y"] + dy)
    d.goto(*cell)
    d.press("A")                                          # the command menu, if the cell can be reached (its rows: state.menu.rows)
    try:
        d.wait_until({"screen": "unit_menu"}, 2)
    except Exception:
        continue
    d.press("A")                                          # Wait
    d.wait_until({"unit_at": list(cell)}, 10)
    dest = cell
    break
assert dest, "no neighbouring cell accepted the move"
u = next(u for u in d.state(["units"])["units"] if (u["x"], u["y"]) == dest)
print("moved:", u["name"], "to", dest, "moved flag", u["moved"])
d.screenshot("offline_versus.png")
print("screenshot offline_versus.png; hash", d.hash()["h"])
