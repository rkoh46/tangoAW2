# The Anti-Air fires back at a hidden Stealth

**The rule (the owner's, differs from Dual Strike).** Dual Strike lets only Fighters and Stealths hit a hidden Stealth, so a hidden
Stealth that attacks an Anti-Air takes no counterattack. In tangoAW2 an Anti-Air always counterattacks a Stealth that attacked it,
hidden or not: the damage is the chart's Anti-Air against a (visible) Stealth, and the usual counter rules hold (the Anti-Air must
survive the hit, have ammo and be in range; the counter is worked out from its HP after the hit).

**Narrow on purpose.** Only the counterattack changes:
- an Anti-Air still cannot *start* an attack on a hidden Stealth (no Fire in its menu; the hidden column of the chart is still 0 for it);
- no other unit gains anything (a Tank cannot hit air; a Fighter and a Stealth already counter a hidden Stealth; Missiles are indirect and
  never counter at range 1).

**Where.** `roster.rs` `dived_column`: `CalcDamage(attacker, defender, distance, is_attacker)` (`0x08024ABC`) picks the dived-Sub column
(`movs r3, #0x19`, two sites) where the defender is dived or hidden; for a Stealth we put the hidden column `0x1C` there. The game calls
CalcDamage twice up front, `is_attacker` 1 for the attacker and 0 for the counter (`0x08024FAA` / `0x08024FB6`, read at sp + 4). When
`is_attacker` is 0 and the unit hitting the Stealth is an Anti-Air (`roster::counters_hidden`), the Stealth's ordinary column is used.
Everything that follows is AW2's normal counter flow (the Stealth's HP loss, the power meters, the battle scene).

**Forecast and CPU.** The forecast box ("Damage xx%") shows the attacker's damage only (it is the attacker's CalcDamage; AW2 and Dual
Strike never show the counter in it), so the box is unchanged; the counter is in the battle records (`BattleUnit` at `0x030013B0`,
`+0x10` base damage, `+0x18` weapon). The CPU's decisions (the ROM's AI, `ds_ai*`, `bh_smart`, `cpu_tactics`) read the same chart
functions and the Stealth's visible column for what a target does back, so they already count the Anti-Air's counter against a
Stealth; they need no change. A CPU Stealth still hides only when no Fighter or Stealth is near (`cpu_tactics::end_of_turn_plan`),
which is about being *attacked*, which this rule does not change.

**Tests.** `python3 tools/aw2test/run.py -k stealth_counter` (`tests/test_stealth_counter.py`, `ds` mode): hidden Stealth attacks an
Anti-Air (the Stealth loses HP), hidden and visible give the same counter, a Tank does not counter, a Fighter still counters, an Anti-Air
cannot start an attack on a hidden Stealth. `sim_version` 45.
