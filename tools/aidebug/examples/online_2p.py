#!/usr/bin/env python3
"""Two real clients, each with its own channel port: in-game lobby room to a battle, then the hashes of both peers.

    for each peer (profile with a gamertag, the ROM, AUTOSTART=offline, BOOT_LOBBY=1):
      host : TANGOAW2_AI_DEBUG=47811 TANGOAW2_ONLINE_CODE=K7Z2M9 TANGOAW2_BOOT_LOBBY=1 TANGOAW2_AUTOSTART=offline tango
      guest: TANGOAW2_AI_DEBUG=47812 TANGOAW2_TYPE_CODE=K7Z2M9   TANGOAW2_BOOT_LOBBY=1 TANGOAW2_AUTOSTART=offline tango
    python3 online_2p.py 127.0.0.1:47811 127.0.0.1:47812
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from client import AiDebug  # noqa: E402

H, G = AiDebug.connect(sys.argv[1]), AiDebug.connect(sys.argv[2])
HE, GE = AiDebug.connect(sys.argv[1]), AiDebug.connect(sys.argv[2])
for c in (HE, GE):
    c.subscribe(["hash", "rollback", "link"])

def press_through(c, done, timeout=60):
    """A on every page of the lobby (one press per page, waiting for the page to change) until `done` holds."""
    end = time.time() + timeout
    while time.time() < end:
        s = c.state(["online"])["online"]
        if done(s):
            return
        c.press("A")
        try:
            c.wait_until({"any": [{"online.level": {"ne": s["level"]}}, {"online.lobby.status": {"ne": s["lobby"]["status"]}}]}, 5)
        except Exception:
            pass
    raise SystemExit("the lobby did not get there")


# the room: the host makes it (the env gives the code), the guest joins
H.wait_until({"online.level": 1}, 60)                    # the LOBBY menu
H.press_until("UP", {"online.lobby.menu_cursor": 0}, 20)
press_through(H, lambda s: s["level"] == 2 and s["lobby"]["status"] == 1)   # CREATE: name page, password page, the room
G.press_until("DOWN", {"online.lobby.menu_cursor": 1}, 20)
# JOIN, the typed code accepted, the password page: A until the room is joined (status 3: connected)
press_through(G, lambda s: s["lobby"]["status"] == 3, 90)
H.wait_until({"online.lobby.players.1": {"exists": True}}, 30)
G.press_until("A", {"online.lobby.players.1.ready": True}, 20)
H.wait_until({"online.lobby.players.1.ready": True}, 20)
time.sleep(6)                                             # (the peers still set their direct link up behind the room page)
H.press("START")

# the maps are picked in turn, one seat at a time
for c in (H, G):
    c.wait_until({"phase": "select_map"}, 60)
for seat, c in enumerate((H, G)):
    c.wait_until({"cues.picks_made": seat}, 120)
    c.press("DOWN")
    c.press("A")
for c in (H, G):
    c.wait_until({"phase": "army_select"}, 120)
H.press("RIGHT"); H.press("A")                            # armies
G.press("LEFT"); G.press("A")
H.press_until("A", {"phase": "battle"}, 40)               # the host sets the rules
for c in (H, G):
    c.wait_until({"phase": "battle"}, 60)
    c.press_until("A", {"screen": "map", "cues.mapup": True}, 40, gap=1.5)

hs = H.state(["active_army", "mine", "map", "link"])
gs = G.state(["active_army", "mine"])
print("battle on", hs["map"]["name"], "| host mine:", hs["mine"], "guest mine:", gs["mine"])
l = hs["link"]["links"][0]
print("link:", l["path"], "rtt", l["rtt_ms"], "jitter", l["jitter_ms"], "| delay", hs["link"]["input_delay"], "rollbacks", hs["link"]["rollback"])

time.sleep(15)
hh = {e["frame"]: e["h"] for e in HE.events(timeout=1) if e["event"] == "hash"}
gg = {e["frame"]: e["h"] for e in GE.events(timeout=1) if e["event"] == "hash"}
common = sorted(set(hh) & set(gg))
equal = sum(hh[f] == gg[f] for f in common)
print(f"hash lines: host {len(hh)} guest {len(gg)} common {len(common)} equal {equal}")
sys.exit(0 if common and equal == len(common) else 1)
