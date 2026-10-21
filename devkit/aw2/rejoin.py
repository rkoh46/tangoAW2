"""Crash / rejoin drivers on real app clients (ports of the old rejoin.py and lobby_rejoin.py): a seat is killed -9 in the battle and relaunched,
or not; the match must go on from the same state, or end by the yield.

  aw2dev live rejoin unr-guest      UNRANKED, the match guest (seat 1) killed in the battle and relaunched; A on the rejoin box
  unr-host | unr-guest-gone | unr-host-gone | unr-late | unr-giveup-guest | unr-giveup-host | unr-rejoin-gone | unr-hostrejoin-gone
  lobby-guest | lobby-host | lobby-late | lobby-giveup | lobby-browse     (a lobby room of --players N, default 3)

Meaning (old docs): *-gone: the victim is never relaunched; after the 60 s window the survivor wins by its yield. late: relaunched after the window: the
LOBBY menu says the army yielded. giveup: relaunched, B (Give up) on the box. rejoin: relaunched, A on the box, the match goes on, hashes are compared
after the swap. rejoin-gone: rejoined once, then killed again. browse: relaunched, START (Later) on the box, the JOIN list shows "<room> - In progress".
Env: REL_DELAY (14 s; late: 75), KILL_DELAY (6), DRIVE_HZ, DRIVE_MAX (420), ROOM_NAME (lobby: typed on CREATE's name page).
UNRANKED needs the matchmaking server (--local uses the mock's pairing); browse needs the public lobby relays.
"""
import json, os, re, shutil, time
from . import profiles, scenarios, session, util
from .scenarios import freeze_safe

NAMES = ["unr-guest", "unr-host", "unr-guest-gone", "unr-host-gone", "unr-late", "unr-giveup-guest", "unr-giveup-host", "unr-rejoin-gone", "unr-hostrejoin-gone",
         "lobby-guest", "lobby-host", "lobby-late", "lobby-giveup", "lobby-browse"]

UNR_BASE = ["until level=1 120", "wait 100", "press B 8", "until level=0 20", "seek UP cursor=0 10", "press A 8", "log searching for an opponent", "session",
            "until mypick 300", "wait 20", "press A 8", "until chosen 300", "wait 75", "until teams 120", "wait 90", "press A 8", "wait 120", "press A 8",
            "wait 120", "press A 8", "wait 200", "intro", "log BATTLE READY"]


def turns(rounds, tag):
    s = []
    for r in range(rounds):
        s += ["until banner|acting|over 90", f"jumpif over d{tag}", f"jumpif !banner nb{tag}_{r}", "onbanner", f"label nb{tag}_{r}", "until acting 30", "wait 30", "endturn"]
    return s + [f"label d{tag}"]


def play_on(run, k, tag, rounds=1):
    return ["wait 150", f"shot {run}/resumed_s{k}.png"] + turns(rounds, tag) + ["wait 200", f"shot {run}/resumed_end_s{k}.png", "log SCRIPT END"]


def lobby_prefix(n, k, room):
    pick = scenarios.private_pick(0)
    if k == 0:
        name_steps = ["until level=13 10"] + (["type " + room] if room else []) + ["press A 8"]
        return ["until level=1 30", "seek UP cursor=0 10", "press A 8", *name_steps, "until level=5 10", "press A 8", "until level=2 10", f"until players={n} 40", f"until ready={n-1} 40",
                "press START 8", "session", *pick, "until teams 60", "wait 40", "press RIGHT 8", "wait 10", "press A 8", "until rules 120", "wait 30", "press A 8", "until mapup 120"]
    return ["until level=1 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 10", "wait 30", "press A 8", "until level=5 15", "wait 20", "press A 8",
            "until status=3 40", "wait 30", "press A 8", "wait 30", "session", *pick, "until teams 60", "wait 40", "press LEFT 8", "wait 10", "press A 8", "until mapup 120"]


def relaunch_pad(run, k, what, lobby):
    """What the relaunched victim does: take the rejoin box (level 12) the way `what` says."""
    box = ["until level=12 240", "wait 90", f"shot {run}/box_s{k}.png"]
    if what == "late":
        return ["until level=1 240", "wait 150", f"shot {run}/late_note_s{k}.png", "wait 150", "log SCRIPT END"]
    if what == "giveup":
        return box + ["press B 8", "log GAVE UP", "wait 240", f"shot {run}/gaveup_s{k}.png", "log SCRIPT END"]
    if what == "browse":
        return box + ["press START 8", "until level=1 20", "wait 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 20", "wait 60", f"shot {run}/browser_s{k}.png",
                      "press UP 8", "wait 30", f"shot {run}/browser_own_s{k}.png", "press A 8", "wait 30", f"shot {run}/rejoining_s{k}.png", "session"] + play_on(run, k, f"rj{k}")
    if what in ("rejoin-gone", "hostrejoin-gone"):
        return box + ["press A 8", "wait 30", f"shot {run}/rejoining_s{k}.png", "session", "wait 36000"]
    return box + ["press A 8", "wait 30", f"shot {run}/rejoining_s{k}.png", "session"] + play_on(run, k, f"rj{k}")


def run(name, n=None, local=False, hz=None, max_s=None, tag=None, rel_delay=None, kill_delay=None):
    if name not in NAMES:
        util.die(f"unknown rejoin scenario {name}; choose from {' '.join(NAMES)}")
    lobby = name.startswith("lobby-")
    what = name.split("-", 1)[1]                       # guest, host, guest-gone, late, giveup(-guest|-host), rejoin-gone, hostrejoin-gone, browse
    n = n or (3 if lobby else 2)
    victim_host = what.startswith("host") or what.endswith("-host") or what.startswith("hostrejoin")
    victim = 0 if victim_host else 1
    kind = {"guest": "rejoin", "host": "rejoin", "browse": "browse", "late": "late", "giveup": "giveup", "giveup-guest": "giveup", "giveup-host": "giveup",
            "rejoin-gone": "rejoin-gone", "hostrejoin-gone": "hostrejoin-gone", "guest-gone": "gone", "host-gone": "gone"}[what]
    relaunch = kind not in ("gone",)
    rel_delay = float(rel_delay if rel_delay is not None else os.environ.get("REL_DELAY", "75" if kind == "late" else "14"))
    kill_delay = float(kill_delay if kill_delay is not None else os.environ.get("KILL_DELAY", "6"))
    hz = hz or int(os.environ.get("DRIVE_HZ", "2"))
    max_s = int(max_s or os.environ.get("DRIVE_MAX", "420"))
    room = os.environ.get("ROOM_NAME", "")
    with session.Session(tag or f"rj_{name}", n, "on", hz, local, flow="unranked" if not lobby else "lobby", scenario=name, no_code=not lobby) as ses:
        rd = str(ses.dir)

        def first(k):
            base = UNR_BASE if not lobby else lobby_prefix(n, k, room) + ["log BATTLE READY"]
            if kind in ("rejoin-gone", "hostrejoin-gone") and not lobby:
                return base + ["wait 36000", "session", "wait 200", f"shot {rd}/resumed_s{k}.png"] + turns(1, f"z{k}") + \
                    ["until over 600", "log VICTORY SEEN", "wait 240", f"shot {rd}/victory_s{k}.png", "wait 300", "log SCRIPT END"]
            if kind == "gone":
                return base + turns(1, f"g{k}") + ["until over 400", "log VICTORY SEEN", "wait 240", f"shot {rd}/victory_s{k}.png", "wait 400", "press A 8", "wait 200", "press A 8", "wait 300", "log SCRIPT END"]
            if kind in ("late", "giveup"):
                return base + ["wait 36000"]
            return base + ["wait 36000", "session"] + play_on(rd, k, f"sv{k}")
        ses.launch_all({k: first(k) for k in range(n)})
        res = {"scenario": name, "n": n, "victim": victim, "kind": kind}
        deadline = time.time() + max_s
        state, t_kill, t_rel, relaunched, second_kill, t_swap = "start", None, None, False, False, None
        survivors = [k for k in range(n) if k != victim]
        while time.time() < deadline:
            time.sleep(1)
            if state == "start":
                if all("BATTLE READY" in ses.log_text(k) for k in range(n)):
                    util.say("battle ready; killing seat", victim, "in", kill_delay, "s")
                    time.sleep(kill_delay)
                    ses.kill(victim)
                    t_kill = time.time()
                    res["killed_at"] = round(t_kill - ses.t0, 1)
                    state = "killed"
            else:
                if relaunch and not relaunched and time.time() - t_kill >= rel_delay:
                    shutil.copy2(ses.logs[victim], ses.dir / f"tango_s{victim}_before.log")
                    ses.launch(victim, relaunch_pad(rd, victim, kind, lobby), "_b")
                    t_rel, relaunched = time.time(), True
                    res["relaunched_epoch_ms"] = int(t_rel * 1000)
                    res["relaunched_at"] = round(t_rel - ses.t0, 1)
                    util.say("relaunched seat", victim)
                sv = [ses.log_text(k) for k in survivors]
                vt = ses.log_text(victim) if relaunched else ""
                done_surv = all("SCRIPT END" in t for t in sv)
                done_vic = relaunched and "SCRIPT END" in vt
                if kind in ("rejoin-gone", "hostrejoin-gone") and relaunched and not second_kill:
                    if any("is being let back in" in t for t in sv):
                        t_swap = t_swap or time.time()
                        if time.time() - t_swap >= 12:
                            ses.kill(victim)
                            second_kill = True
                            util.say("killed again")
                    continue
                if kind in ("rejoin-gone", "hostrejoin-gone") and second_kill and (any("unranked: the match ended" in t for t in sv) or done_surv):
                    break
                if kind in ("rejoin", "browse") and done_surv and done_vic:
                    break
                if kind == "late" and relaunched and done_vic and time.time() - t_rel > 10:
                    break
                if kind == "giveup" and relaunched and done_vic and (time.time() - t_rel > 20 or any("unranked: the match ended" in t for t in sv)):
                    break
                if kind == "gone" and (done_surv or any("unranked: the match ended" in t for t in sv)):
                    break
        res["elapsed_s"] = round(time.time() - ses.t0, 1)
        res["events"] = [{"action": "kill", "seat": victim, "at_s": res.get("killed_at", 0)}] + ([{"action": "relaunch", "seat": victim, "at_s": res["relaunched_at"]}] if relaunched else [])
        res["live_file_left"] = [(profiles.profile_dir(ses.names[k]) / "data" / "unranked_live.json").exists() for k in range(n)]
        # per-event evidence
        sv_text = ses.log_text(survivors[0])
        res["survivor_saw_swap"] = "is being let back in" in sv_text
        res["ok"] = (relaunched or kind == "gone") and (not relaunch or "SCRIPT END" in ses.log_text(victim) or kind in ("rejoin-gone", "hostrejoin-gone", "gone"))
    ses.copy_logs()
    # the hashes after the rejoin: the victim's second life (hash lines written after its relaunch) against the survivor's, frame by frame
    if kind in ("rejoin", "browse") and relaunched:
        from .runlib import Run
        run = Run(ses.dir)
        rel = res["relaunched_epoch_ms"]
        f0 = max([h["frame"] for h in run.hashes(victim) if h["ms"] < rel] or [0])    # the victim's first life reached this frame; its menu frames after the relaunch restart at 0
        vic = {h["frame"]: h["h"] for h in run.hashes(victim) if h["ms"] >= rel and h["frame"] >= f0}
        sur = {h["frame"]: h["h"] for h in run.hashes(survivors[0])}
        common = sorted(set(vic) & set(sur))
        bad = [f for f in common if vic[f] != sur[f]]
        res["hash_after_rejoin"] = {"common_frames": len(common), "differ": bad[:10]}
        res["ok"] = res["ok"] and len(common) >= 3 and not bad
    return ses.finish(res)
