"""A mission played to the end by the game's own computer on every side, day by day (`aw2dev campaign playthrough`, docs/dev/playthrough.md). Opt-in: AW2TEST_PLAY_MISSION=<n> (a BH2 mission number),
AW2TEST_PLAY_DAYS=<max days over all stages>, AW2TEST_PLAY_OUT=<report .json>. The computer takes over every army the player commands (a five-army mission's fifth too, and the player's army again after a
stage switch), the dialogue is answered with A. The report: the days taken, the outcome and the reason, the stage switches, each army's units and funds at the start of every day, the HQs that changed hands (a
picture of each, of the switch and of the end), the stalls (days in which nothing changed). `aw2dev campaign playthrough` turns it into Markdown and a contact sheet."""

import json
import os
import importlib.util

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import harness
from aw2test.harness import test

NS = [int(x) for x in os.environ.get("AW2TEST_PLAY_MISSION", "").replace(",", " ").split()]
DAYS = int(os.environ.get("AW2TEST_PLAY_DAYS", "60"))
OUT = os.environ.get("AW2TEST_PLAY_OUT")
GOD = os.environ.get("AW2TEST_PLAY_GOD") == "1"            # the player's units are healed to full every half second (watch every wave land: the player cannot lose)
WAVE_MAPS = os.environ.get("AW2TEST_PLAY_WAVE_MAPS") == "1"  # a whole-map picture at the start and each time an army's units jump (a wave landed), with every army's units by type and funds
ADVANCE = int(os.environ.get("AW2TEST_PLAY_ADVANCE", "0"))   # with the bot: an HQ of the stage still not the player's this many days after the last one fell is captured for it (shows the waves; says nothing about difficulty)
PLAYER = os.environ.get("AW2TEST_PLAY_PLAYER", "cpu")      # cpu: the game's computer plays the player's army too; bot: aw2test.bot.Bot plays it through the pad (goals: the HQs)
STAGE_AT = 0x0203_DCA0
FIVE_ON = 0x0203_0206

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers2", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]

# The HQs whose takeover a picture is taken of, by mission and stage: (name, cell).
# The armies' names on the wave sheet, by mission and stage.
ARMIES = {31: {1: {1: "Nell (Orange Star)", 2: "Olaf (Blue Moon)", 3: "Kanbei (Yellow Comet)", 4: "Eagle (Green Earth)", 5: "Black Hole (player)"}, 2: {1: "Black Hole (player)", 2: "Aria (Orange Star)"}}}
HQS = {31: {0: bp.HQS and [(n, c) for n, c, _, _ in bp.HQS], 1: [("Aria", (33, 5))]}}


def owners(e, cells):
    return {name: bp.owner(e, *cell) for name, cell in cells}


def take_over(g, e):
    """Every human army becomes the computer's (the player's armies change with the stage); returns the armies taken over."""
    p, took = g.players_base, set()
    for a in range(1, 6):
        if e.u8(p + 0x3C * a + 0x1B) == 1:
            e.w8(p + 0x3C * a + 0x1B, 2)
            took.add(a)
    return took


def humans(g, e):
    p = g.players_base
    return {a for a in range(1, 6) if e.u8(p + 0x3C * a + 0x1B) == 1}


def heal(g, armies):
    """--god: every living unit of these armies back to 100 HP."""
    for u in g.units():
        if u["army"] in armies and 0 < u["hp"] < 100:
            a = g.unit_addr(u["id"])
            w = g.e.u16(a + 4)
            g.e.w16(a + 4, (w & ~0x7F) | 100)


def forces(g, e):
    """Every army's units by type and funds: {army: {"funds": f, "units": n, "types": {name: n}}}."""
    from aw2test import rom
    p, out = g.players_base, {}
    for u in g.units():
        r = out.setdefault(u["army"], {"units": 0, "types": {}})
        r["units"] += 1
        name = rom.UNIT_NAMES.get(u["type"], str(u["type"]))
        r["types"][name] = r["types"].get(name, 0) + 1
    for a in range(1, 6):
        if a in out or e.u8(p + 0x3C * a + 0x1B):
            out.setdefault(a, {"units": 0, "types": {}})["funds"] = e.u32(p + 0x3C * a)
    return out


def snapshot(g, e):
    p = g.players_base
    units, funds = {}, {}
    for u in g.units():
        units[u["army"]] = units.get(u["army"], 0) + 1
    for a in range(1, 6):
        if e.u8(p + 0x3C * a + 0x1B) or units.get(a):
            funds[a] = e.u32(p + 0x3C * a)
    return {"units": units, "funds": funds}


def run(ctx, n):
    prog = open(os.path.join(ctx.out, "progress.log"), "w", buffering=1)   # the log as it happens (a long run can be followed: tail -f)
    log0 = ctx.log

    def log(msg):
        log0(msg)
        prog.write(f"{msg}\n")
    ctx.log = log
    e, g, d = b2.enter(ctx, n)
    d.leave_setup()
    a2.intro(ctx, e, d, f"m{n}", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    e.w8(dc.LAST_RESULT, 0)
    days, events, shots, stalls = [], [], [], []
    stage, day0 = e.u8(STAGE_AT), e.u16(dc.DAY)
    last_day, same, prev_sig = day0, 0, None
    cells = {k: v for k, v in HQS.get(n, {}).items()}
    held = owners(e, cells.get(stage, []))
    frames, max_frames = 0, 3_000_000
    gods = humans(g, e)
    progress_day = e.u16(dc.DAY)
    waves, want_map, last_counts = [], ["the start"], {}

    def wave_map(why):
        from aw2test import cpuprobe
        name = f"wave_{len(waves):02d}"
        g._units_base = g._players_base = None
        path = cpuprobe.whole_map(ctx, e, g, d, n, name)
        waves.append({"file": name, "path": path, "why": why, "day": e.u16(dc.DAY), "stage": e.u8(STAGE_AT) + 1, "forces": forces(g, e)})
        ctx.log(f"wave map {name} day {e.u16(dc.DAY)}: {why}")

    def shot(name, why):
        ctx.shot(g, name)
        shots.append({"file": name, "why": why, "day": e.u16(dc.DAY), "stage": e.u8(STAGE_AT)})

    shot("start", "after the opening")
    bot = None
    if PLAYER == "bot":
        from aw2test.bot import Bot
        bot = Bot(d, log=ctx.log, goals=[c for _, c in cells.get(stage, [])], cap=42, own_structures=True, garrison=os.environ.get("AW2TEST_PLAY_GARRISON") == "1")
    while frames < max_frames:
        e.wait(30)
        frames += 30
        if e.u8(dc.LAST_RESULT):
            break
        g._units_base = g._players_base = None
        if d.in_battle():
            if GOD:
                gods |= humans(g, e)
                heal(g, gods)
            if WAVE_MAPS and not d.scripts_running():
                counts = {}
                for u in g.units():
                    counts[u["army"]] = counts.get(u["army"], 0) + 1
                for a, c in counts.items():
                    if c - last_counts.get(a, 0) >= 5 and last_counts:
                        want_map.append(f"army {a} landed: {last_counts.get(a, 0)} -> {c} units")
                last_counts = counts
        if bot is None and d.in_battle() and e.u32(0x0849_9598) != 0:
            gods |= take_over(g, e)
        elif bot is not None and d.in_battle() and not d.scripts_running():
            army = g.current_army()
            if army != getattr(run, "_last_army", None):
                run._last_army = army
                ctx.log(f"turn: army {army} (control {e.u8(g.players_base + 0x3C * army + 0x1B) if 1 <= army <= 5 else '-'}) day {e.u16(dc.DAY)}")
            if 1 <= army <= 5 and e.u8(g.players_base + 0x3C * army + 0x1B) == 1:
                if ADVANCE and e.u16(dc.DAY) - progress_day >= ADVANCE:
                    left = [(nm, c) for nm, c in cells.get(stage, []) if bp.owner(e, *c) != army]
                    if left:
                        nm, c = left[0]
                        try:
                            d.wait_control()
                            bp.capture(ctx, e, g, d, c, army)
                            bp.settle(e, g, d)
                            events.append({"event": "forced", "hq": nm, "day": e.u16(dc.DAY), "stage": stage + 1})
                            ctx.log(f"forced: {nm}'s HQ {c} captured for the player on day {e.u16(dc.DAY)}")
                        except Exception as ex:
                            ctx.log(f"forced capture of {nm}: {ex}")
                        progress_day = e.u16(dc.DAY)
                        g._units_base = g._players_base = None
                        continue
                if want_map:
                    why = "; ".join(want_map)
                    want_map.clear()
                    for k in range(6):     # the day's banner and the turn's start: the cursor is free a moment later
                        e.wait(90)
                        try:
                            d.wait_control()
                            wave_map(why)
                            break
                        except Exception as ex:
                            ctx.log(f"wave map (try {k + 1}): {ex}")
                    last_counts = {}
                try:
                    bot.play_turn(army)
                    e.wait(40)
                except Exception as ex:
                    if e.u8(dc.LAST_RESULT):
                        break
                    ctx.log(f"turn of army {army}: {ex}")
                    bot.cancel()
                continue
        if d.scripts_running() or not d.in_battle() or d.on_co_select():
            e.press("A", 4)
        st = e.u8(STAGE_AT)
        if st != stage:
            events.append({"event": "stage switch", "from": stage + 1, "to": st + 1, "day": e.u16(dc.DAY), "frame": frames})
            stage = st
            progress_day = e.u16(dc.DAY)
            want_map.append(f"stage {st + 1} begins")
            if bot is not None:
                bot.goals = [c for _, c in cells.get(stage, [])]
            e.wait(120)
            g._units_base = g._players_base = None
            held = owners(e, cells.get(stage, []))
            shot("switch", f"stage {stage + 1} begins")
        if d.in_battle() and not d.scripts_running():
            now = owners(e, cells.get(stage, []))
            for name, o in now.items():
                if held.get(name) != o:
                    events.append({"event": "takeover", "hq": name, "owner": o, "day": e.u16(dc.DAY), "stage": stage + 1})
                    if o == 5:
                        progress_day = e.u16(dc.DAY)
                    shot(f"takeover_{name}", f"{name}'s HQ taken (owner {o})")
            held = now
        day = e.u16(dc.DAY)
        if day != last_day and d.in_battle():
            last_day = day
            s = snapshot(g, e)
            s.update(day=day, stage=stage + 1, army=g.current_army(), frame=frames)
            days.append(s)
            ctx.log(f"day {day} (stage {stage + 1}): units {s['units']} funds {s['funds']}")
            sig = (json.dumps(s["units"], sort_keys=True), json.dumps(s["funds"], sort_keys=True), tuple(sorted(held.items())), stage)
            same = same + 1 if sig == prev_sig else 0
            prev_sig = sig
            if same >= 3:
                stalls.append({"day": day, "stage": stage + 1, "why": "nothing changed for 3 days"})
                shot("stall", "stalled")
                break
            if day - day0 >= DAYS:
                stalls.append({"day": day, "stage": stage + 1, "why": f"day limit {DAYS}"})
                break
    r = d.last_result()
    shot("end", "the end")
    row = {"mission": n, "title": b2.TITLES[n], "player": PLAYER, "result": {1: "won", 2: "lost"}.get(r["result"], "none"), "days": e.u16(dc.DAY) - day0 + 1, "frames": frames,
           "reason": d.end_reason() if r["result"] else None, "stages_reached": stage + 1, "events": events, "daily": days, "stalls": stalls, "shots": shots, "god": GOD, "waves": waves, "armies": ARMIES.get(n, {}),
           "dir": ctx.out}
    ctx.log(json.dumps({k: v for k, v in row.items() if k not in ("daily", "shots")}))
    if OUT:
        with open(OUT, "w") as f:
            json.dump(row, f, indent=1)
    e.close()


def _play(n):
    def fn(ctx):
        run(ctx, n)
    fn.__name__ = f"playthrough_m{n}"
    test(modes=("ds",))(fn)


for _n in NS:
    _play(_n)
