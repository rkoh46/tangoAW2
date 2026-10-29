"""`aw2dev co verify [CO ...]`: every ability of the custom COs in real battles, compared with the specification (docs/dev/co-verify.md).

The scenarios are `tools/aw2test/tests/test_co_verify.py` (library: `tools/aw2test/aw2test/coverify.py`, the specification: `cospec.py`, read from `cos/*.toml` and the design docs, never from the
engine's own tables). Each check is tagged `[<co> <ability>] <detail>: ...` in the test's log; this module runs the tests, collects the tags and prints the pass / fail table.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .. import cfg, util

COS = ["klaus", "aurelia", "cassius", "livia", "crumb", "varro", "cloneandy", "asuka", "aria"]
COLUMNS = ["d2d", "cop", "scop", "meter", "tag", "cpu", "net"]
TITLES = {"d2d": "Day to day", "cop": "CO Power", "scop": "Super Power", "meter": "Meter / stars", "tag": "Tag Powers", "cpu": "CPU use", "net": "Online determinism"}
# Tests of the older suites that are also evidence for a cell of the table (the same CO and ability, played by the same harness).
LEGACY = {
    ("crumb", "d2d"): ["crumb_rank_and_file", "crumb_resupplies_on_cities_and_bases"],
    ("crumb", "cop"): ["crumb_ration_run"],
    ("crumb", "scop"): ["crumb_geralds_blessing"],
    ("crumb", "tag"): ["tag_crumb", "tag_crumb_no_one_left_behind"],
    ("cloneandy", "tag"): ["tag_clone_andy"],
    ("klaus", "cop"): ["es_klaus_testudo_cuts_the_counterattack_by_a_quarter", "es_klaus_testudo_counter_damage_number_is_the_cut_one"],
    ("klaus", "scop"): ["es_klaus_legio_aeterna_heals_three_hp_and_testudo_moves_further"],
    ("aurelia", "scop"): ["es_aurelia_onager_splash_costs_the_units_beside_the_target_one_hp", "es_aurelia_onager_needs_an_indirect_attack"],
    ("cassius", "scop"): ["es_cassius_triumph_a_vehicle_that_attacked_moves_once_more_but_cannot_fire", "es_cassius_triumph_is_for_vehicles_only",
                          "es_cassius_triumph_an_unused_extra_move_ends_with_the_turn"],
    ("livia", "cop"): ["es_livia_collects_funds_when_she_pays_for_a_power"],
    # Asuka (CO 92) has no co_verify_* scenarios: her own suite (tools/aw2test/tests/test_asuka.py) proves every ability with numbers.
    ("asuka", "d2d"): ["asuka_row_is_sonjas_numbers_with_hawkes_powers", "asuka_d2d_vision_is_one_more", "asuka_enemy_terrain_cover_is_cut_one_two_three_stars",
                       "asuka_luck_is_nells_and_there_is_no_bad_luck", "asuka_ground_units_pay_one_movement_point_for_every_terrain", "asuka_hp_is_hidden_from_the_enemy",
                       "asuka_day_to_day_adds_five_percent_attack_and_defence_and_it_stacks_with_the_powers"],
    ("asuka", "cop"): ["asuka_cop_vision_two_more_and_sees_into_woods", "asuka_cop_black_analysis_heals_one_and_costs_the_enemy_one",
                       "asuka_powers_halve_the_enemys_ammo_and_fuel_rounded_down", "asuka_fuel_and_ammo_halving_with_a_unit_in_a_transport_and_none_for_an_ally",
                       "asuka_powers_last_until_her_next_turn_and_hold_through_the_enemys"],
    ("asuka", "scop"): ["asuka_scop_vision_two_more_and_sees_into_woods", "asuka_scop_counter_storm_heals_two_and_costs_the_enemy_two", "asuka_counter_break_her_units_strike_first"],
    ("asuka", "meter"): ["asuka_powers_cost_more_each_use_and_the_meter_charges"],
    ("asuka", "tag"): ["asuka_tag_compatibility_and_names", "asuka_tag_power_with_von_bolt", "asuka_tag_power_with_hawke"],
    ("asuka", "cpu"): ["asuka_cpu_uses_her_powers"],
    # Aria: the generic co_verify_* scenarios play her numbers; her own suite (tests/test_aria.py) proves the rest (Vengeance at 8 and 9 HP, the missing Power entry, the CPU, Build Anew's heal and nothing else)
    ("aria", "d2d"): ["aria_row_has_only_a_super_power_and_the_games_luck", "aria_vengeance_scales_with_hp", "aria_vengeance_defends_too"],
    ("aria", "scop"): ["aria_build_anew_adds_firepower_and_heals_and_nothing_else"],
    ("aria", "meter"): ["aria_has_no_power_entry_and_the_super_power_costs_seven_stars"],
    ("aria", "cpu"): ["aria_cpu_uses_only_her_super_power"],
}
LINE = re.compile(r"^(ok|FAIL)\s+\[(\S+) (\S+)\] (.*)$")


def column(ability, detail):
    if ability == "tag":
        return "cpu" if detail == "cpu" else "tag"
    if detail == "cpu":
        return "cpu"
    if detail.startswith("meter"):
        return "meter"
    return ability


def list_tests(cos, quick=False):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    out = subprocess.run([sys.executable, str(run), "--mode", "ds", "--list", "-k", "co_verify_"], capture_output=True, text=True, cwd=cfg.REPO).stdout
    names = [l.split()[1] for l in out.splitlines() if l.strip()]

    def mine(n):
        parts = n[len("co_verify_"):]
        if re.match(r"hq_(m\d+|tag)$", parts):          # (the missions' and the pairs' HQ checks belong to the Emerald Sun COs)
            return any(c in cos for c in ("klaus", "aurelia", "cassius", "livia", "varro"))
        return any(re.search(rf"(^|_){c}(_|$)", parts) for c in cos)
    names = [n for n in names if mine(n)]
    if quick:
        keep = ("stats_{c}_scop", "move_{c}_scop", "economy_{c}_1000", "meter_{c}", "cpu_{c}_scop", "hooks_{c}", "range_aurelia_scop_edge", "cloneandy_scop")
        want = {k.format(c=c) for k in keep for c in cos}
        names = [n for n in names if n[len("co_verify_"):] in want or n.startswith("co_verify_tag_" + cos[0] + "_with_")]
    return names


def run_tests(names, jobs):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    cmd = [sys.executable, str(run), "--mode", "ds", "-j", str(jobs), "-k", ",".join(names)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cfg.REPO)
    return r, time.time() - t0


def out_dir(name):
    return cfg.REPO / "tools" / "aw2test" / "out" / "ds" / name


LIMITS = []


def collect(names):
    """{(co, column): {"ok": n, "fail": n, "lines": [...], "fails": [...]}} from the tagged lines of the tests' logs. `LIMIT [co ability] ...` lines (what a rule does not cover, measured)
    are kept apart in `LIMITS`."""
    cells = {}
    LIMITS.clear()
    for n in names:
        log = out_dir(n) / "log.txt"
        if not log.exists():
            continue
        for line in log.read_text().splitlines():
            if line.startswith("LIMIT "):
                LIMITS.append(line[6:])
                continue
            m = LINE.match(line)
            if not m:
                continue
            status, co, ability, rest = m.groups()
            detail = rest.split(": ", 1)[0] if ": " in rest else ""
            col = column(ability, detail)
            c = cells.setdefault((co, col), {"ok": 0, "fail": 0, "lines": [], "fails": []})
            c["ok" if status == "ok" else "fail"] += 1
            c["lines"].append(f"[{co} {ability}] {rest}")
            if status != "ok":
                c["fails"].append(f"[{co} {ability}] {rest}")
        # a test that died with an error (not a failed check) fails every cell it belongs to
        text = log.read_text()
        if "\nERROR " in text or text.startswith("ERROR "):
            cells.setdefault(("?", "error"), {"ok": 0, "fail": 0, "lines": [], "fails": []})["fails"].append(f"{n}: " + text[text.index("ERROR "):][:300].replace("\n", " | "))
            cells[("?", "error")]["fail"] += 1
    return cells


def collect_legacy(cos, cells):
    """Count the older suites' tests for the cells they back; they are run by `run_tests` too (names passed in `legacy_names`)."""
    out = {}
    for (co, col), tests in LEGACY.items():
        if co not in cos:
            continue
        for t in tests:
            log = out_dir(t) / "log.txt"
            if not log.exists():
                continue
            lines = log.read_text().splitlines()
            fails = [l for l in lines if l.startswith("FAIL")]
            checks = sum(1 for l in lines if l.startswith(("ok ", "FAIL")))
            c = cells.setdefault((co, col), {"ok": 0, "fail": 0, "lines": [], "fails": []})
            c["ok"] += checks - len(fails)
            c["fail"] += len(fails)
            c["lines"].append(f"[{co} {col}] existing test {t}: {checks} checks, {len(fails)} failed")
            c["fails"] += [f"[{co} {col}] existing test {t}: {l[6:160]}" for l in fails]
    return cells


def net_cells(cos, cells):
    """The online-determinism column from `co verify --net` (devkit/work/co_verify/net.json: {"<co> <power>": {"runs": n, "equal": n}})."""
    f = cfg.work("co_verify", "net.json")
    if not f.exists():
        return cells
    data = json.loads(f.read_text())
    for key, v in data.items():
        co = key.split()[0]
        if co in cos:
            c = cells.setdefault((co, "net"), {"ok": 0, "fail": 0, "lines": [], "fails": []})
            c["ok"] += v["equal"]
            c["fail"] += v["runs"] - v["equal"]
            c["lines"].append(f"[{co} net] {key}: {v['equal']} of {v['runs']} runs with equal hashes")
            if v["equal"] != v["runs"]:
                c["fails"].append(f"[{co} net] {key}: {v['equal']} of {v['runs']} runs with equal hashes")
    return cells


def table(cos, cells):
    rows = ["| CO | " + " | ".join(TITLES[c] for c in COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]
    for co in cos:
        cs = []
        for col in COLUMNS:
            c = cells.get((co, col))
            if not c or not (c["ok"] + c["fail"]):
                cs.append("-")
            elif c["fail"]:
                cs.append(f"**FAIL** {c['fail']} of {c['ok'] + c['fail']}")
            else:
                cs.append(f"PASS {c['ok']}")
        rows.append(f"| {co} | " + " | ".join(cs) + " |")
    return "\n".join(rows)


def report(cos, cells):
    """Markdown: the table, the failures, and per cell the first line of each detail (the numbers)."""
    out = ["# Custom CO verification", "", table(cos, cells), ""]
    fails = [f for c in cells.values() for f in c["fails"]]
    out += [f"## Failures ({len(fails)})", ""] + [f"- {f}" for f in fails[:200]] + [""]
    out += [f"## Known limits ({len(LIMITS)}): measured, not failures", ""] + [f"- {l}" for l in LIMITS] + [""]
    for co in cos:
        out.append(f"## {co}")
        for col in COLUMNS:
            c = cells.get((co, col))
            if not c:
                continue
            seen, shown = set(), []
            for l in c["lines"]:
                key = re.sub(r"\d+", "#", l.split(": ", 1)[0])
                if key not in seen:
                    seen.add(key)
                    shown.append(l)
            out.append(f"### {TITLES[col]}: {c['ok']} ok, {c['fail']} failed")
            out += [f"- {l[:230]}" for l in shown[:40]]
            out.append("")
    return "\n".join(out)


def verify(a):
    cos = a.co or COS
    unknown = [c for c in cos if c not in COS]
    if unknown:
        util.die(f"unknown CO {unknown}: {', '.join(COS)}")
    if not cfg.aw2_rom().exists() or not cfg.ds_rom().exists():
        util.die("co verify needs the AW2 ROM and the Dual Strike ROM (devkit/config.toml)")
    util.check_fresh(util.example_bin("aw2_script"), "aw2_script")
    names = list_tests(cos, a.quick)
    legacy = sorted({t for (co, _), ts in LEGACY.items() if co in cos for t in ts}) if not a.quick else []
    if a.list:
        print("\n".join(names + legacy))
        return 0
    util.say(f"co verify: {len(names)} scenarios + {len(legacy)} existing tests for {', '.join(cos)}")
    r, secs = run_tests(names + legacy, a.jobs)
    fails_run = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    cells = collect(names)
    cells = collect_legacy(cos, cells)
    cells = net_cells(cos, cells)
    out = cfg.work("co_verify")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report(cos, cells))
    (out / "cells.json").write_text(json.dumps({f"{k[0]} {k[1]}": {"ok": v["ok"], "fail": v["fail"], "fails": v["fails"]} for k, v in cells.items()}, indent=1))
    print(table(cos, cells))
    bad = sum(c["fail"] for c in cells.values())
    for l in [f for c in cells.values() for f in c["fails"]][:40]:
        print("  FAIL", l[:230])
    for l in fails_run:
        print("  ", l[:200])
    for l in LIMITS:
        print("  LIMIT", l[:230])
    util.say(f"co verify done in {secs:.0f}s: {'bad=' + str(bad)}; report {out / 'report.md'}")
    print(f"co verify done bad={bad}")
    return 1 if (bad or r.returncode) else 0
