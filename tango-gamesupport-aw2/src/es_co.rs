//! The Emerald Sun Campaign's five COs (`docs/ES_CAMPAIGN.md` section 2, data files `cos/*.toml`, kit `aw2dev co`): **Klaus**, **Aurelia**, **Cassius**, **Livia** and the
//! boss-only **Varro**, tangoAW2's own COs 86..90 (after Crumb and the dialogue's face-only ids), with the Dual Strike pack only. They are built the way Crumb is
//! ([`crate::crumb`]): the numbers are [`bonus`], called by [`crate::co_roster::stat`]; luck, stars, unit cost and the power texts are theirs ([`INFO`]); a power's effect
//! on the units is a function the game calls for each unit of the army ([`each_unit`]); Livia's funds are a trap on the power's payment and on the day's income.
//!
//! Placeholder pictures: each takes a Dual Strike CO's art ([`Info::donor`]) until the portrait work (`aw2dev co portrait`, branch `escampaign`) composes its own.
//!
//! | CO | Day to day | CO Power | Super Power |
//! |---|---|---|---|
//! | **Klaus** 4/8 | Imperium: all units +10% attack and defence, Infantry and Mech +10% more | Testudo: +20% defence on top, Infantry and Mech +1 move, counterattacks against his attacks do 25% less | Legio Aeterna: heal 3 HP, +1 move, +20% attack, Infantry and Mech +40% attack and defence |
//! | **Aurelia** 3/7 | Ballistics: Artillery and Rockets +1 range, indirect units +10% attack, vehicles -10% attack | Ballista: indirect +1 range more, +30% attack | Onager: the same, and each indirect hit costs the enemy units beside the target 1 HP (never below 1 HP) |
//! | **Cassius** 3/7 | Impetus: vehicles +1 move, +10% attack, -10% defence | Charge: vehicles +1 move more, +30% attack | Triumph: +40% attack, a vehicle that has attacked may move once more |
//! | **Livia** 3/6 | Ledger: income +25%, units cost 10% more | Tribute: 200 funds a property | Mare Nostrum: ships +2 move, +30% attack, 100 funds a property |
//! | **Varro** 4/8 | Imperator: all units +15% attack and defence | Edict: +25% attack, +15% defence on top, +1 move | Sol Invictus: +45% attack, +30% defence, +1 move, heal 2 HP |
//!
//! "Vehicles" are the ground vehicles (Md Tank, Megatank, Tank, Recon, APC, Neotank, Piperunner, Anti-Air); "indirect" Artillery, Rockets, Missiles and the Battleship; "naval" every ship.

use mgba::core::Core;

use crate::co_new::FIRST;
use crate::co_roster::{DEFENCE, FIREPOWER, MOVE, RANGE};
use crate::ds_weather::is_on;

pub const KLAUS: u8 = FIRST + 14;
pub const AURELIA: u8 = FIRST + 15;
pub const CASSIUS: u8 = FIRST + 16;
pub const LIVIA: u8 = FIRST + 17;
pub const VARRO: u8 = FIRST + 18;
/// The dialogue's Emerald Sun legionary: the Black Hole trooper's face with its colours turned (a face only, no CO).
pub const LEGIONARY_FACE: u8 = FIRST + 19;
pub const ALL: [u8; 5] = [KLAUS, AURELIA, CASSIUS, LIVIA, VARRO];

pub fn is_es(co: u8) -> bool {
    (KLAUS..=VARRO).contains(&co)
}

/// Whether the five are in Versus' CO lists. Until the campaign is approved they are not (nobody should see placeholder faces in a Versus room): a development aid.
pub fn in_versus() -> bool {
    cfg!(feature = "playtest") || std::env::var_os("TANGOAW2_ES_VERSUS").is_some()
}

/// A CO's text, numbers and borrowed look.
pub struct Info {
    pub name: &'static str,
    pub bio: &'static str,
    pub d2d: &'static str,
    pub cop: &'static str,
    pub scop: &'static str,
    pub cop_name: &'static str,
    pub scop_name: &'static str,
    /// The CO Power's, the Super Power's and the Tag Power's quote (`\r` between lines), each twice in the six slots.
    pub quotes: [&'static str; 3],
    pub victory: &'static str,
    pub defeat: &'static str,
    /// The AW2 CO it takes after: its theme, its CPU profile, its place in the lists.
    pub like: u8,
    /// The Dual Strike CO whose pictures it wears until its own are composed (a Dual Strike id).
    pub donor: u8,
    /// Stars of the CO Power and of the Super Power in all.
    pub stars: (u32, u32),
    /// Luck per power level (AW2's rows: 10 is 0..9%) and bad luck.
    pub luck: [i16; 3],
    /// Unit cost per power level in percent.
    pub cost: [i16; 3],
}

pub const INFO: [Info; 5] = [
    Info {
        name: "Klaus",
        bio: "Legate of the Emerald Sun, sent across the sea to find who starved his homeland. Stern, fair, tireless. Hit: Discipline Miss: Being doubted",
        d2d: "My legions fight and hold a little better. Infantry and Mech fight best of all.",
        cop: "All units take 20% less damage on top, and my Infantry and Mech move 1 space more. Counterattacks against my attacks are weaker.",
        scop: "All units recover 3 HP, move 1 space more and attack 20% harder. Infantry and Mech gain 40% attack and defence on top.",
        cop_name: "Testudo",
        scop_name: "Legio Aeterna",
        quotes: ["Shields up! Close ranks,\rand not one step back!", "The legion does not fall.\rRise, and march again!", "Hold the line.\rWe march together."],
        victory: "Order restored. March at dawn.",
        defeat: "The legion... will remember.",
        like: 6,
        donor: 7,
        stars: (4, 8),
        luck: [10, 10, 10],
        cost: [100, 100, 100],
    },
    Info {
        name: "Aurelia",
        bio: "Chief engineer of the Emerald Sun. If a wall stands, she knows how it falls. Hit: Range Miss: Walking",
        d2d: "My Artillery and Rockets reach 1 space farther, and indirect units hit 10% harder. Vehicles hit 10% softer.",
        cop: "Indirect units reach 1 more space and attack 30% harder.",
        scop: "Indirect units reach 1 more space and attack 30% harder, and each of their hits also costs enemy units next to the target 1 HP.",
        cop_name: "Ballista",
        scop_name: "Onager",
        quotes: ["Wind the windlass!\rLet the walls hear it!", "Loose the onagers!\rStone for every wall!", "Measure twice.\rFire once."],
        victory: "The wall is down. Fetch the ladders.",
        defeat: "Bad footing. Next time, higher ground.",
        like: 5,
        donor: 6,
        stars: (3, 7),
        luck: [10, 10, 10],
        cost: [100, 100, 100],
    },
    Info {
        name: "Cassius",
        bio: "Commander of the Emerald Sun cavalry and the Senate's favourite, who thinks the legion should be his. Hit: Speed Miss: Patience",
        d2d: "My vehicles move 1 space more and hit 10% harder, but their armour is 10% thinner.",
        cop: "Vehicles move 1 more space and attack 30% harder.",
        scop: "Vehicles move 1 more space and attack 40% harder, and can move again after attacking, once.",
        cop_name: "Charge",
        scop_name: "Triumph",
        quotes: ["With me! Ride them down!\rGlory is a short road!", "Strike, and strike again!\rThey will sing of this!", "Try to keep up, Klaus!\rI am already ahead."],
        victory: "Ha! Write it down, scribe. Write it down!",
        defeat: "Not like this. NOT like this!",
        like: 8,
        donor: 9,
        stars: (3, 7),
        luck: [10, 10, 10],
        cost: [100, 100, 100],
    },
    Info {
        name: "Livia",
        bio: "Senator and quaestor of the Emerald Sun. She keeps the army's purse and the Senate's secrets. Hit: Accounts Miss: Mud",
        d2d: "My properties yield 25% more funds, but my units cost 10% more.",
        cop: "I collect 200 funds for every property I own.",
        scop: "Naval units move 2 spaces more and attack 30% harder. I also collect 100 funds for every property I own.",
        cop_name: "Tribute",
        scop_name: "Mare Nostrum",
        quotes: ["Thank you for your\rgenerous contribution.", "The sea is ours. Again.\rSend the fleet!", "A moment.\rI am counting."],
        victory: "The books balance. So does the war.",
        defeat: "Impossible. I audited this.",
        like: 16,
        donor: 17,
        stars: (3, 6),
        luck: [10, 10, 10],
        cost: [110, 110, 110],
    },
    Info {
        name: "Varro",
        bio: "Consul of Aurea and Klaus's old patron. He found the legions their money and never asked where it came from. Hit: Patronage Miss: Being refused",
        d2d: "My legions are better paid, better armed and better fed than any in the world.",
        cop: "All units attack 25% harder and take 15% less damage on top, and move 1 space more.",
        scop: "All units attack 45% harder and take 30% less damage, move 1 space more and recover 2 HP.",
        cop_name: "Edict",
        scop_name: "Sol Invictus",
        quotes: ["By the Consul's authority,\rthe Senate decrees...", "Sol Invictus! The sun\rdoes not set on Aurea!", "Two banners, one\rpurse. Mine."],
        victory: "The Senate will be told what I tell it.",
        defeat: "My boy... you do not know what you have done.",
        like: 14,
        donor: 15,
        stars: (4, 8),
        luck: [10, 10, 20],
        cost: [100, 100, 100],
    },
];

pub fn info(co: u8) -> Option<&'static Info> {
    INFO.get(co.checked_sub(KLAUS)? as usize)
}

/// The AW2 CO a Emerald Sun CO takes after.
pub fn like(co: u8) -> u8 {
    info(co).map_or(1, |i| i.like)
}

pub fn name(co: u8) -> Option<&'static [u8]> {
    info(co).map(|i| i.name.as_bytes())
}

/// A text by [`crate::co_new`]'s slot (the six quotes are the CO Power's, the Super Power's and the Tag Power's, twice).
/// A CO's text as the page shows it: the project owner's words (names, bio, power names, quotes, lines) where she has them, this campaign's own numbers in the
/// descriptions of what the CO and the powers do.
pub fn text_of(co: u8, which: u16) -> Option<Vec<u8>> {
    use crate::co_new::*;
    match which {
        T_D2D | T_COP | T_SCOP => text(co, which),
        _ => crate::es_cos::text(co, which).or_else(|| text(co, which)),
    }
}

pub fn text(co: u8, which: u16) -> Option<Vec<u8>> {
    use crate::co_new::*;
    let i = info(co)?;
    let q = |s: &str| s.as_bytes().to_vec();
    Some(match which {
        T_NAME => q(i.name),
        T_BIO => q(i.bio),
        T_D2D => q(i.d2d),
        T_COP => q(i.cop),
        T_SCOP => q(i.scop),
        T_COP_NAME => q(i.cop_name),
        T_SCOP_NAME => q(i.scop_name),
        w if (T_QUOTES..T_QUOTES + 6).contains(&w) => q(i.quotes[((w - T_QUOTES) % 3) as usize]),
        T_VICTORY => q(i.victory),
        T_DEFEAT => q(i.defeat),
        _ => return None,
    })
}

// --- The numbers --------------------------------------------------------------------

fn foot(t: u8) -> bool {
    matches!(t, 1 | 2)
}

/// Ground vehicles (not the indirect ones).
fn vehicle(t: u8) -> bool {
    matches!(t, 3 | 4 | 5 | 6 | 7 | 8 | 9 | 14)
}

/// Artillery, Rockets, Missiles, the Battleship.
fn indirect(t: u8) -> bool {
    matches!(t, 10 | 11 | 15 | 21)
}

fn naval(t: u8) -> bool {
    matches!(t, 18 | 21 | 22 | 23 | 24 | 26)
}

/// The CO's own firepower %, defence %, move and range for unit type `t` at power level `mode` (0 day to day, 1 CO Power, 2 Super Power), in
/// [`crate::co_roster::stat`]'s fields (what every power adds to firepower is added by the caller).
pub fn bonus(co: u8, mode: u8, t: u8, field: usize) -> i32 {
    let m = mode.min(2) as i32;
    let on = |b: bool, v: i32| if b { v } else { 0 };
    match (co, field) {
        (KLAUS, FIREPOWER) => 10 + on(foot(t), 10) + on(m == 2, 20 + on(foot(t), 40)),
        (KLAUS, DEFENCE) => 10 + on(foot(t), 10) + on(m == 1, 20) + on(m == 2, on(foot(t), 40)),
        (KLAUS, MOVE) => on(m == 1, on(foot(t), 1)) + on(m == 2, 1),
        (AURELIA, FIREPOWER) => on(indirect(t), 10 + on(m > 0, 30)) - on(vehicle(t), 10),
        (AURELIA, RANGE) => on(matches!(t, 10 | 11), 1) + on(m > 0, on(indirect(t), 1)),
        (CASSIUS, FIREPOWER) => on(vehicle(t), 10 + on(m == 1, 30) + on(m == 2, 40)),
        (CASSIUS, DEFENCE) => -on(vehicle(t), 10),
        (CASSIUS, MOVE) => on(vehicle(t), 1 + on(m > 0, 1)),
        (LIVIA, FIREPOWER) => on(m == 2, on(naval(t), 30)),
        (LIVIA, MOVE) => on(m == 2, on(naval(t), 2)),
        (VARRO, FIREPOWER) => 15 + on(m == 1, 25) + on(m == 2, 45),
        (VARRO, DEFENCE) => 15 + on(m == 1, 15) + on(m == 2, 30),
        (VARRO, MOVE) => on(m > 0, 1),
        _ => 0,
    }
}

/// Funds a day on top of the income: Livia's Ledger, 25% (250 a property that earns).
pub fn income_bonus(co: u8, earners: i32) -> i32 {
    if co == LIVIA {
        250 * earners
    } else {
        0
    }
}

/// Funds her powers collect for each property that earns: Tribute 200, Mare Nostrum 100.
pub fn tribute(co: u8, power: u8) -> i32 {
    match (co, power) {
        (LIVIA, 1) => 200,
        (LIVIA, 2) => 100,
        _ => 0,
    }
}

// --- Thumb code: a power's effect on each unit -----------------------------------------------

/// Free ROM in `co_new`'s data area (+0x2400, after the body pictures' pairs, before the HUD faces).
const ROM: u32 = 0x0874_2400;
const HEAL3: u32 = ROM;
const SENTINEL: u32 = ROM + 0x3FC;
const MAGIC: u32 = 0x4553_434F; // "ESCO"
/// AW2's `RepairUnit(unit, hp, pay)`, Thumb.
const REPAIR: u32 = 0x0802_9AF9;
/// Andy's CO Power unit effect: `RepairUnit(unit, 2, 0)`.
const HEAL2: u32 = 0x0804_44ED;
/// The default unit effect (none).
const NOTHING: u32 = 0x0804_4531;

/// Legio Aeterna's unit effect: heal 3 HP, for free.
fn heal3() -> Vec<u8> {
    let mut a = crate::crumb::Asm::new();
    a.op(0xB530); // push {r4, r5, lr}
    a.op(0x2103); // movs r1, #3
    a.op(0x2200); // movs r2, #0
    a.call(REPAIR);
    a.op(0xBC30); // pop {r4, r5}
    a.op(0xBC01); // pop {r0}
    a.op(0x4700); // bx r0
    a.finish()
}

pub fn install(core: &mut Core) {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return;
    }
    core.raw_write_range(HEAL3, -1, &heal3());
    core.raw_write_32(SENTINEL, -1, MAGIC);
}

/// The presentation row's unit effect (a Thumb function the game calls for each unit of the army) for power 0 (CO Power) or 1 (Super Power).
pub fn each_unit(co: u8, power: u8) -> u32 {
    match (co, power) {
        (KLAUS, 1) => HEAL3 | 1,
        (VARRO, 1) => HEAL2,
        _ => NOTHING,
    }
}

// --- Livia's funds -----------------------------------------------------------------------------

const CURRENT_ARMY: u32 = 0x0300_33EC;
const PLAYER: u32 = 0x3C;
/// `PayForPower(army, mode)`'s entry (the map menu's Power and Super, the computer's choice).
const PAY_FOR_POWER: u32 = 0x0804_438C;

pub fn power_paid(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let mode = core.gba().cpu().gpr(1) as u8;
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !(1..=5).contains(&army) {
        return;
    }
    let co = crate::co_roster::army_co(core, army).0;
    let per = tribute(co, mode);
    if per == 0 {
        return;
    }
    let n = crate::co_powers::earners(core, army);
    let p = crate::five::players(core) + PLAYER * army;
    let funds = core.raw_read_32(p, -1) as i64 + (per * n) as i64;
    core.raw_write_32(p, -1, funds.clamp(0, 999_999) as u32);
}

/// `PayForPower(army, mode)`'s entry is trapped once, by [`crate::crumb::traps`] (one trap an address): it calls this.
pub const POWER_PAID_AT: u32 = PAY_FOR_POWER;


// --- The powers' rules: Testudo, Onager, Triumph ------------------------------------------------
//
// Three effects the numbers cannot say, each a trap at a game routine and each a pure function of emulated memory (the units, the player blocks, the
// battle records), so every peer and every rollback works them out alike:
//
// - **Testudo** (Klaus's CO Power): the enemy's counterattack against one of his attacks does 25% less damage. `sub_08024DDC(target, attacker)` applies a
//   strike's damage (`+0xC` is the attacker's damage before the target's defence, `+0x14` the forecast's); the trap sits at its first instruction after the
//   push. A counterattack is the strike of the battle's defender record (`0x030013B0`) at the attacker's (`0x030013D0`); when the attacker's army is Klaus
//   in his CO Power both numbers are cut to 75% (whole numbers, rounded down), so the forecast and the hit agree.
// - **Onager** (Aurelia's Super Power): `sub_08041978` has worked a battle out and is about to charge the power meters (the trap `co_powers::attacker_charged`
//   at `0x08041CB8` calls [`onager`]): when the attacker is an indirect unit of Aurelia's army in her Super Power and struck from range, every unit of another team
//   on a cell next to the target (the four cells beside it, hidden units too, never an Oozium) loses 1 HP, and a unit on 1 HP stays on 1. The attacker's cell is the
//   move's destination (`0x03003100`), because the work-out puts the unit back on its old cell.
// - **Triumph** (Cassius's Super Power): `sub_080424FC` ends the selected unit's action (`+1` bit 0 = done). Called from a battle's end (the four return
//   addresses in [`BATTLE_ENDS`], the calls at `0x080419FC`, `0x08041E00`, `0x08041E50`, `0x08040972`) for a vehicle of a human-played Cassius army in his Super Power that has not yet had its extra move, the trap at `0x08042532` (the
//   `orrs` that sets done) leaves the unit not done and sets its bit in [`MOVED_AFTER_ATTACK`]. The unit can be picked up again; while its bit is set Fire is
//   hidden (the two Fire rows' show tests are trapped), so it can move and do anything but attack, and any ordinary end of its action (Wait, ...) clears the bit
//   and finishes it as always. The bits are cleared when the turn changes hands ([`tick`]). The computer's Cassius does not get the extra move (its unit loop would
//   fire the unit again).

const BATTLE_ATTACKER: u32 = 0x0300_13D0;
const BATTLE_DEFENDER: u32 = 0x0300_13B0;
const CO_ABILITIES: u32 = 0x0300_3FC8;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const SELECTED_UNIT: u32 = 0x0300_40D8;
const DESTINATION: u32 = 0x0300_3100;
const MAP: u32 = 0x0201_E450;
const PLAYER_TEAM: u32 = 0x2A;
const SLOTS: u32 = 320;

fn abilities_on(core: &Core) -> bool {
    core.raw_read_8(CO_ABILITIES, -1) != 0
}

/// Testudo keeps this share (percent) of a counterattack's damage.
pub const TESTUDO_KEEPS: i32 = 75;

/// `sub_08024DDC(target r0, attacker r1)` after its push: the counterattack's damage numbers.
const STRIKE_APPLIED: u32 = 0x0802_4DDE;
fn strike_applied(core: &mut Core) {
    if !is_on(core) || !abilities_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (target, attacker) = (cpu.gpr(0) as u32, cpu.gpr(1) as u32);
    if attacker != BATTLE_DEFENDER || target != BATTLE_ATTACKER {
        return;
    }
    let army = crate::co_roster::battle_army(core, target);
    if !(1..=5).contains(&army) || crate::co_roster::army_co(core, army) != (KLAUS, 1) {
        return;
    }
    for at in [0x0C, 0x14] {
        let v = core.raw_read_16(attacker + at, -1) as i16 as i32;
        core.raw_write_16(attacker + at, -1, (v * TESTUDO_KEEPS / 100) as u16);
    }
}

fn army_at(core: &Core, unit: u32) -> u32 {
    crate::five::army_of_index(core, unit.wrapping_sub(core.raw_read_32(UNITS_POINTER, -1)) / UNIT)
}

fn team_of(core: &Core, army: u32) -> u8 {
    core.raw_read_8(crate::five::players(core) + 0x3C * army + PLAYER_TEAM, -1)
}

/// The HP (tenths) a unit with `hp` is left with after Onager's splash: 1 shown HP less, a unit on its last stays.
pub fn splash_hp(hp: u16) -> u16 {
    if hp > 10 {
        hp - 10
    } else {
        hp
    }
}

/// The battle `sub_08041978` has worked out (attacker: the selected unit, defender index in `defender`) is about to charge the meters.
pub fn onager(core: &mut Core, defender: u32) {
    if !abilities_on(core) || defender == 0 || defender >= SLOTS {
        return;
    }
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let att = core.raw_read_32(SELECTED_UNIT, -1);
    if att < units || att >= units + UNIT * SLOTS {
        return;
    }
    let army = army_at(core, att);
    if !(1..=5).contains(&army) || crate::co_roster::army_co(core, army) != (AURELIA, 2) || !indirect(core.raw_read_8(att, -1)) {
        return;
    }
    let dfd = units + UNIT * defender;
    if core.raw_read_8(dfd, -1) == 0 {
        return;
    }
    let (tx, ty) = (core.raw_read_8(dfd + 2, -1) as i32, core.raw_read_8(dfd + 3, -1) as i32);
    let (ax, ay) = (core.raw_read_16(DESTINATION, -1) as i16 as i32, core.raw_read_16(DESTINATION + 2, -1) as i16 as i32);
    if (ax - tx).abs() + (ay - ty).abs() < 2 {
        return;
    }
    let mine = team_of(core, army);
    for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
        let Some(u) = crate::unit_actions::unit_at(core, tx + dx, ty + dy) else { continue };
        if u == dfd || team_of(core, army_at(core, u)) == mine || crate::oozium::immune(core, u) {
            continue;
        }
        let w = core.raw_read_16(u + 4, -1);
        let hp = w & 0x7F;
        let left = splash_hp(hp);
        if left != hp {
            core.raw_write_16(u + 4, -1, (w & !0x7F) | left);
        }
    }
}

/// One bit per unit slot (320): the unit attacked under Triumph and has its extra move left. EWRAM `ram_map::REGIONS`; +0x28 the army whose turn it was last tick.
pub const MOVED_AFTER_ATTACK: u32 = 0x0203_C980;
pub const MOVED_BYTES: u32 = 40;
pub const MOVED_LEN: u32 = MOVED_BYTES + 1;
const MOVED_TURN: u32 = MOVED_AFTER_ATTACK + MOVED_BYTES;

fn moved_bit(core: &Core, i: u32) -> bool {
    core.raw_read_8(MOVED_AFTER_ATTACK + i / 8, -1) & (1 << (i % 8)) != 0
}

fn set_moved_bit(core: &mut Core, i: u32, on: bool) {
    let b = core.raw_read_8(MOVED_AFTER_ATTACK + i / 8, -1);
    let v = if on { b | 1 << (i % 8) } else { b & !(1 << (i % 8)) };
    if v != b {
        core.raw_write_8(MOVED_AFTER_ATTACK + i / 8, -1, v);
    }
}

/// The unit slot of a unit record (None for a pointer outside gUnits).
fn slot_of(core: &Core, unit: u32) -> Option<u32> {
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let i = unit.wrapping_sub(units) / UNIT;
    (unit >= units && i != 0 && i < SLOTS).then_some(i)
}

/// The return addresses (Thumb) with which a battle ends a unit's action by `sub_080424FC`: no defender, the map-only battle, the scene's
/// end, an attack on a structure.
const BATTLE_ENDS: [u32; 4] = [0x0804_1A01, 0x0804_1E05, 0x0804_1E55, 0x0804_0977];
/// `sub_080424FC` at its `orrs r0, r1` (r0 the unit's flags, r1 = 1) that sets the unit's done bit.
const ACTION_DONE: u32 = 0x0804_2532;
fn action_done(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let unit = core.raw_read_32(SELECTED_UNIT, -1);
    let Some(i) = slot_of(core, unit) else { return };
    let sp = core.gba().cpu().gpr(13) as u32;
    let lr = core.raw_read_32(sp + 4, -1);
    if !BATTLE_ENDS.contains(&lr) {
        // Any other end of the action (Wait, ...) finishes the unit for good.
        set_moved_bit(core, i, false);
        return;
    }
    let army = army_at(core, unit);
    let (flags, hp) = (core.raw_read_8(unit + 1, -1), core.raw_read_8(unit + 4, -1) & 0x7F);
    if !abilities_on(core)
        || !(1..=5).contains(&army)
        || crate::co_roster::army_co(core, army) != (CASSIUS, 2)
        || crate::ds_ai::is_cpu(core, army)
        || !vehicle(core.raw_read_8(unit, -1))
        || flags & 0x08 != 0
        || hp == 0
        || moved_bit(core, i)
    {
        return;
    }
    set_moved_bit(core, i, true);
    core.gba_mut().cpu_mut().set_gpr(1, 0);
}

/// The two Fire rows' show tests (`0x0802CA78` direct, `0x0802CB20` ranged; r0 = 1 hides): the selected unit has had its extra move, it may not fire again.
const FIRE_SHOWN: [u32; 2] = [0x0802_CA78, 0x0802_CB20];
fn fire_shown(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let Some(i) = slot_of(core, core.raw_read_32(SELECTED_UNIT, -1)) else { return };
    if !moved_bit(core, i) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, 1);
    let lr = cpu.gpr(14) as u32;
    cpu.set_thumb_pc(lr & !1);
}

/// Every frame: when the turn passes to another army the extra moves are forgotten.
fn forget_moves(core: &mut Core) {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u8;
    if core.raw_read_8(MOVED_TURN, -1) == army {
        return;
    }
    for k in 0..MOVED_BYTES {
        if core.raw_read_8(MOVED_AFTER_ATTACK + k, -1) != 0 {
            core.raw_write_8(MOVED_AFTER_ATTACK + k, -1, 0);
        }
    }
    core.raw_write_8(MOVED_TURN, -1, army);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![(STRIKE_APPLIED, Box::new(strike_applied)), (ACTION_DONE, Box::new(action_done))];
    for at in FIRE_SHOWN {
        t.push((at, Box::new(fire_shown)));
    }
    t
}

/// Every frame with the pack: the code is in ROM.
pub fn tick(core: &mut Core, on: bool) {
    if on {
        install(core);
        forget_moves(core);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn all_types() -> impl Iterator<Item = u8> {
        1..=27u8
    }

    #[test]
    fn klaus_is_the_strongest_on_foot() {
        for t in [1u8, 2] {
            assert_eq!((bonus(KLAUS, 0, t, FIREPOWER), bonus(KLAUS, 0, t, DEFENCE)), (20, 20));
            assert_eq!(bonus(KLAUS, 1, t, DEFENCE), 40);
            assert_eq!(bonus(KLAUS, 1, t, MOVE), 1);
            assert_eq!((bonus(KLAUS, 2, t, FIREPOWER), bonus(KLAUS, 2, t, DEFENCE), bonus(KLAUS, 2, t, MOVE)), (80, 60, 1));
        }
        assert_eq!((bonus(KLAUS, 0, 5, FIREPOWER), bonus(KLAUS, 0, 5, DEFENCE)), (10, 10));
        assert_eq!(bonus(KLAUS, 1, 5, MOVE), 0);
        assert_eq!(bonus(KLAUS, 2, 5, MOVE), 1);
    }

    #[test]
    fn aurelia_reaches_further_and_cassius_runs_faster() {
        assert_eq!(bonus(AURELIA, 0, 10, RANGE), 1);
        assert_eq!(bonus(AURELIA, 1, 10, RANGE), 2);
        assert_eq!(bonus(AURELIA, 1, 15, RANGE), 1, "Missiles gain the power's range only");
        assert_eq!(bonus(AURELIA, 0, 5, FIREPOWER), -10);
        assert_eq!(bonus(AURELIA, 2, 10, FIREPOWER), 40);
        assert_eq!((bonus(CASSIUS, 0, 5, MOVE), bonus(CASSIUS, 1, 5, MOVE), bonus(CASSIUS, 0, 5, DEFENCE)), (1, 2, -10));
        assert_eq!(bonus(CASSIUS, 2, 5, FIREPOWER), 50);
        assert_eq!(bonus(CASSIUS, 2, 1, FIREPOWER), 0, "foot soldiers are not vehicles");
        assert_eq!(bonus(CASSIUS, 2, 10, MOVE), 0, "nor is Artillery");
    }

    #[test]
    fn livia_is_a_treasurer_and_an_admiral() {
        for t in all_types() {
            assert_eq!(bonus(LIVIA, 0, t, FIREPOWER), 0);
            assert_eq!(bonus(LIVIA, 1, t, MOVE), 0);
        }
        assert_eq!((bonus(LIVIA, 2, 22, MOVE), bonus(LIVIA, 2, 22, FIREPOWER), bonus(LIVIA, 2, 5, MOVE)), (2, 30, 0));
        assert_eq!(income_bonus(LIVIA, 12), 3000);
        assert_eq!(income_bonus(KLAUS, 12), 0);
        assert_eq!((tribute(LIVIA, 1), tribute(LIVIA, 2), tribute(LIVIA, 0)), (200, 100, 0));
    }

    #[test]
    fn varro_stays_under_kanbei() {
        // aw2dev co check: day to day <= 40, CO Power <= 90, Super Power <= 120 points of firepower plus defence (the power's own 10 included).
        for (mode, cap) in [(0u8, 40), (1, 90), (2, 120)] {
            let fp = bonus(VARRO, mode, 5, FIREPOWER) + if mode > 0 { 10 } else { 0 };
            assert!(fp + bonus(VARRO, mode, 5, DEFENCE) <= cap, "mode {mode}");
        }
    }

    #[test]
    fn onager_takes_one_hp_and_never_the_last() {
        assert_eq!((splash_hp(100), splash_hp(55), splash_hp(11)), (90, 45, 1));
        assert_eq!((splash_hp(10), splash_hp(7), splash_hp(1)), (10, 7, 1), "a unit on its last HP keeps it");
    }

    #[test]
    fn triumph_keeps_a_bit_for_every_unit_slot() {
        assert!(MOVED_BYTES * 8 >= SLOTS);
        assert_eq!(MOVED_LEN, MOVED_BYTES + 1);
        // The traps sit at distinct game addresses (the factory's test checks them against every module's).
        let at: Vec<u32> = traps().iter().map(|t| t.0).collect();
        let mut sorted = at.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), at.len());
        assert!(BATTLE_ENDS.iter().all(|a| a & 1 == 1), "return addresses are Thumb");
    }

    #[test]
    fn texts_exist_and_the_code_fits() {
        use crate::co_new::*;
        for co in ALL {
            for w in [T_NAME, T_BIO, T_D2D, T_COP, T_SCOP, T_COP_NAME, T_SCOP_NAME, T_VICTORY, T_DEFEAT] {
                assert!(text(co, w).is_some(), "{co} {w}");
            }
            for q in 0..6 {
                assert!(text(co, T_QUOTES + q).is_some());
            }
            let i = info(co).unwrap();
            assert!(i.name.len() <= 7);
            for q in i.quotes {
                assert!(q.split('\r').count() <= 2 && q.split('\r').all(|l| l.len() <= 28), "{q:?}");
            }
        }
        assert!(text(KLAUS, 15).is_none());
        let c = heal3();
        assert!(c.len() <= 0x100 && c.len() % 4 == 0);
        assert!(!is_es(crate::co_new::CRUMB) && is_es(KLAUS) && is_es(VARRO) && !is_es(LEGIONARY_FACE));
    }
}
