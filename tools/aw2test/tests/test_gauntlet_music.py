"""The Gauntlet's dialogue has music (`-k gauntlet_music`; crate::gauntlet_mode::OPENING, add_music; `aw2dev campaign scenes --campaign gauntlet` lists the songs).
Per map: the song the game has started while the opening speech's box is up is the map's chosen one, and the song while the first fall's arrival scene is up is the arriving CO's; the battle's own
theme (the player's CO's own) is back after the next turn."""

import os
import subprocess

from aw2test import gauntlet as ga
from aw2test import gauntlet_maps as gm
from aw2test import bhact4, paths, story
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

# the first fall of each map: (HQ cell, the player's army); Cinder Sea and Iron Crown are not in gauntlet_maps
ANDY_THEME = 209
FIRST = {0: (ga.CINDER["drake"], 1), 1: (ga.IRON["grit"], 5)}


def expected():
    """{mission key: {"intro": song id, "arrival": song id of the first trigger scene}} from the Rust definition (the example `aw2_campaign_scenes ... gauntlet`)."""
    exe = paths.runner("aw2_campaign_scenes")
    env = dict(os.environ, TANGOAW2_DS_ROM=paths.ds_rom())
    out = subprocess.run([exe, paths.aw2_rom(), "gauntlet"], capture_output=True, text=True, env=env, check=True).stdout
    res = {}
    for line in out.splitlines():
        key, kind, _boxes, _label, sid = line.split("\t")
        if kind in ("intro", "trigger") and sid != "-":
            res.setdefault(key, {}).setdefault("intro" if kind == "intro" else "arrival", int(sid))
    return res


class Heard:
    """Records the song the game last started each time a dialogue box is up (sampled on every press of A through the scenes)."""

    def __init__(self, e, d):
        self.e, self.d, self.seen = e, d, []
        self.press = e.press
        e.press = self._press

    def _press(self, *a, **k):
        try:
            if bhact4.text_shown(self.d):
                self.seen.append(self.e.u16(story.SONG))
        except Exception:
            pass
        return self.press(*a, **k)

    def take(self):
        s, self.seen = self.seen, []
        return s


def one(mission):
    def fn(ctx):
        key = f"gauntlet_{mission + 1:02d}"
        want = expected()[key]
        e = Emu(save=paths.base_save(), ds=ctx.ds)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = ga.Gauntlet(g)
        heard = Heard(e, d)
        hq, army = FIRST.get(mission) or ((gm.MAPS[mission].lines[0].hq, gm.MAPS[mission].player))
        d.start(ga.ANDY, map=mission)
        if army == 5:        # (a five-army map: the other armies' turns go by before the player's)
            from tests.test_gauntlet_map2 import to_player_turn
            to_player_turn(e, g, d, army=5)
        got = heard.take()
        ctx.check(len(got) >= 2, f"{key}: the opening's boxes were sampled ({len(got)})")
        ctx.eq(sorted(set(got)), [want["intro"]], f"{key}: the opening speech plays song {want['intro']}")
        d.capture(ctx, hq, army=army)
        d.settle()
        got = heard.take()
        ctx.check(len(got) >= 2, f"{key}: the arrival's boxes were sampled ({len(got)})")
        ctx.eq(sorted(set(got)), [want["arrival"]], f"{key}: the arrival scene plays song {want['arrival']}")
        # the battle's music comes back: after the next turn change the song is the player's CO's own theme again (Andy's, AW2 209)
        g._units_base = g._players_base = None
        d.end_turn()
        for _ in range(600):
            if d.scripts_running():
                e.press("A", 4)
            e.wait(30)
            if g.current_army() == army and not d.scripts_running() and g.idle():
                break
        e.wait(120)
        ctx.eq(e.u16(story.SONG), ANDY_THEME, f"{key}: after the next turn the CO's theme is back")
        e.close()
    fn.__name__ = f"gauntlet_music_{mission + 1:02d}_opening_and_first_arrival_have_their_song"
    test(modes=("ds",))(fn)


for _m in range(12):
    one(_m)
