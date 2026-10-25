//! What Dual Strike's COs do beyond numbers, with the Dual Strike pack.
//!
//! Powers built from AW2's own pieces, as small functions and a proc
//! script tangoAW2 writes into free ROM (ordinary code the game calls, as
//! a CO's `powerAssembly`):
//! - Von Bolt's Ex Machina: AW2's meteor strike (`0x084A0858`: radius 2,
//!   every unit there; the spot Dual Strike's, [`strike_pick`]) at 3 HP,
//!   and the enemy units hit skip their army's next turn ([`stun`]; his
//!   own are done for the turn).
//! - Rachel's Covering Fire: the same strike three times, 3 HP each.
//! - Kindle's Urban Blight: AW2's mass damage (Black Wave's,
//!   `sub_08044D70`) at 3 HP, only to enemy units on properties.
//!
//! Abilities, by trap:
//! - Kindle's High Society: +3% firepower per property she owns when it
//!   starts ([`extra_firepower`], with the Com Towers').
//! - Sasha: +100 funds a day per property; Market Crash lowers each
//!   enemy's power meters (its tag partner's too) by 1% of the full meter
//!   per 500 funds she has
//!   (Dual Strike's 0x020E1D2C); War Bonds pays her half the value of the
//!   HP her units take off enemies (at the enemy CO's prices).
//! - Rachel: property repairs give one HP more (her blocks' `repairBonus`).
//! - Javier: defence against indirect attacks, +20/+40/+80%.
//! - Eagle: Dual Strike's Lightning Drive lets units move again, as
//!   Lightning Strike does (his COP takes his SCOP's unit effect).

use mgba::core::Core;
use std::sync::OnceLock;

use crate::co_roster::army_co;
use crate::ds_weather::is_on;

pub const JUGGER: u8 = 72;
pub const KOAL: u8 = 73;
pub const KINDLE: u8 = 74;
pub const VON_BOLT: u8 = 75;
pub const GRIMM: u8 = 76;
pub const JAVIER: u8 = 77;
pub const SASHA: u8 = 78;
pub const JAKE: u8 = 79;
pub const RACHEL: u8 = 80;
const EAGLE: u8 = 8;

pub(crate) const COP: u8 = 1;
pub(crate) const SCOP: u8 = 2;

// --- ROM ------------------------------------------------------------------------

const DATA: u32 = 0x0874_9600;
const COVERING_FIRE_SCRIPT: u32 = DATA; // 29 commands of 8 bytes
const EX_MACHINA_FN: u32 = DATA + 0x200;
const COVERING_FIRE_FN: u32 = DATA + 0x240;
const URBAN_BLIGHT_FN: u32 = DATA + 0x280;
const SENTINEL: u32 = DATA + 0x3FC;
const MAGIC: u32 = 0x3843_5344; // "DSC8"

pub(crate) const METEOR_SCRIPT: u32 = 0x084A_0858;
/// The meteor script's commands: 3 to start, 7 for one strike (pick the
/// target, move there, draw, animate, hit, redraw), 5 to end.
const METEOR_START: u32 = 3;
const METEOR_STRIKE: u32 = 7;
const METEOR_END: u32 = 5;
const PROC_START_BLOCKING: u32 = 0x0801_C95D;
const MASS_DAMAGE: u32 = 0x0804_4D71;
const MASS_DAMAGE_SCRIPT: u32 = 0x084A_0994;
/// Black Wave's picture and palette (Hawke's COP), for Urban Blight.
const BLACK_WAVE_GFX: u32 = 0x0811_33D0;
const BLACK_WAVE_PAL: u32 = 0x0811_3BA0;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const CO_ABILITIES: u32 = 0x0300_3FC8;

/// Hit points of damage a strike or Urban Blight does, in the game's
/// tenths.
const THREE_HP: u16 = 30;

fn halfwords(h: &[u16]) -> Vec<u8> {
    h.iter().flat_map(|v| v.to_le_bytes()).collect()
}

/// `proc = Proc_StartBlocking(script, parent); proc->damage = dmg`, as
/// AW2's `sub_08044A88` but for a far call (a `bl` does not reach from
/// here).
pub(crate) fn strike_fn(script: u32, damage: u16) -> Vec<u8> {
    let mut b = halfwords(&[
        0xB500, // push {lr}
        0x1C01, // adds r1, r0, #0
        0x4805, // ldr r0, =script
        0x4A06, // ldr r2, =Proc_StartBlocking
        0x467B, // mov r3, pc
        0x3307, // adds r3, #7 (return below, Thumb)
        0x469E, // mov lr, r3
        0x4710, // bx r2
        0x46C0, // nop
        0x3064, // adds r0, #0x64
        0x2100 | (damage & 0xFF), // movs r1, #damage
        0x8001, // strh r1, [r0]
        0xBC01, // pop {r0}
        0x4700, // bx r0
    ]);
    b.extend_from_slice(&script.to_le_bytes());
    b.extend_from_slice(&PROC_START_BLOCKING.to_le_bytes());
    b
}

/// Hawke's Black Wave (`sub_08044CF8`) at 3 HP and no healing:
/// `sub_08044D70(script, gfx, pal, army, 3, 0, -1, 0, proc)`, with the
/// overlay's map and palette `gfx`, `pal`.
fn urban_blight_fn(gfx: u32, pal: u32) -> Vec<u8> {
    let mut b = halfwords(&[
        0xB530, // push {r4, r5, lr}
        0xB085, // sub sp, #0x14
        0x4D0B, // ldr r5, =script
        0x490C, // ldr r1, =gfx
        0x4A0C, // ldr r2, =pal
        0x4B0D, // ldr r3, =current army
        0x881B, // ldrh r3, [r3]
        0x2403, // movs r4, #3 (HP)
        0x9400, // str r4, [sp]
        0x2400, // movs r4, #0 (no healing)
        0x9401, // str r4, [sp, #4]
        0x3C01, // subs r4, #1 (weather unchanged)
        0x9402, // str r4, [sp, #8]
        0x2400, // movs r4, #0 (fuel kept)
        0x9403, // str r4, [sp, #0xc]
        0x9004, // str r0, [sp, #0x10]
        0x1C28, // adds r0, r5, #0
        0x4C08, // ldr r4, =sub_08044D70
        0x467D, // mov r5, pc
        0x3505, // adds r5, #5 (return below, Thumb)
        0x46AE, // mov lr, r5
        0x4720, // bx r4
        0xB005, // add sp, #0x14
        0xBC30, // pop {r4, r5}
        0xBC01, // pop {r0}
        0x4700, // bx r0
    ]);
    for w in [MASS_DAMAGE_SCRIPT, gfx, pal, CURRENT_ARMY, MASS_DAMAGE] {
        b.extend_from_slice(&w.to_le_bytes());
    }
    b
}

fn covering_fire_script(core: &Core) -> Vec<u8> {
    let command = |k: u32| {
        let mut c = [0u8; 8];
        core.raw_read_range(METEOR_SCRIPT + 8 * k, -1, &mut c);
        c
    };
    let mut s = Vec::new();
    for k in 0..METEOR_START {
        s.extend_from_slice(&command(k));
    }
    for _ in 0..3 {
        for k in METEOR_START..METEOR_START + METEOR_STRIKE {
            s.extend_from_slice(&command(k));
        }
    }
    for k in METEOR_START + METEOR_STRIKE..METEOR_START + METEOR_STRIKE + METEOR_END {
        s.extend_from_slice(&command(k));
    }
    s
}

/// A new CO's power function for a power level, if not AW2's default.
pub fn power_assembly(co: u8, mode: u8) -> Option<u32> {
    match (co, mode) {
        (VON_BOLT, SCOP) => Some(EX_MACHINA_FN | 1),
        (RACHEL, SCOP) => Some(COVERING_FIRE_FN | 1),
        (KINDLE, COP) => Some(URBAN_BLIGHT_FN | 1),
        _ => None,
    }
}

static SCRIPT: OnceLock<Vec<u8>> = OnceLock::new();

/// Writes the functions and the script once (the same bytes on every
/// peer). With Dual Strike's pictures ([`crate::power_anim`]) the powers
/// run its copies of the meteor script and its overlay map.
pub fn install(core: &mut Core) {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return;
    }
    let script = SCRIPT.get_or_init(|| covering_fire_script(core)).clone();
    core.raw_write_range(COVERING_FIRE_SCRIPT, -1, &script);
    let (exm, cf, gfx, pal) = if crate::power_anim::install(core) {
        use crate::power_anim as anim;
        (anim::EXM_SCRIPT, anim::CF_SCRIPT, anim::URBAN_MAP, anim::URBAN_PALETTE)
    } else {
        (METEOR_SCRIPT, COVERING_FIRE_SCRIPT, BLACK_WAVE_GFX, BLACK_WAVE_PAL)
    };
    core.raw_write_range(EX_MACHINA_FN, -1, &strike_fn(exm, THREE_HP));
    core.raw_write_range(COVERING_FIRE_FN, -1, &strike_fn(cf, THREE_HP));
    core.raw_write_range(URBAN_BLIGHT_FN, -1, &urban_blight_fn(gfx, pal));
    core.raw_write_32(SENTINEL, -1, MAGIC);
}

/// With the pack, the presentation row of Eagle's COP takes his SCOP's
/// unit effect (move again), as in Dual Strike. (row, bytes)
pub fn presentation_changes(pres: &mut [u8]) {
    let row = 0x44 * EAGLE as usize;
    let (cop, scop) = (row + 0x1C, row + 0x1C + 0x14);
    let effect = pres[scop + 4..scop + 12].to_vec();
    pres[cop + 4..cop + 12].copy_from_slice(&effect);
}

// --- The map -------------------------------------------------------------------

const MAP_POINTER: u32 = 0x0849_9590;
const UNITS_POINTER: u32 = 0x0849_9594;
const PLAYERS_POINTER: u32 = 0x0849_9598;
const PLAYER: u32 = 0x3C;
const UNIT: u32 = 12;
const ROWS: u32 = 0x417A;
const CLASSES: u32 = 0x1432;
const UNIT_PLANE: u32 = 0x51A;
/// Properties: city, HQ, airport, port, base, and the Lab / Com Tower
/// (Dual Strike's list, 0x020E3F30).
const PROPERTIES: [u8; 6] = [6, 8, 10, 11, 14, 20];
/// Properties that earn funds (a Com Tower does not).
const EARNERS: [u8; 5] = [6, 8, 10, 11, 14];

fn map(core: &Core) -> u32 {
    core.raw_read_32(MAP_POINTER, -1)
}

fn class_at(core: &Core, x: u32, y: u32) -> u8 {
    let m = map(core);
    let row = core.raw_read_16(m + ROWS + 2 * y, -1) as u32;
    core.raw_read_8(m + CLASSES + row + x, -1)
}

/// Properties of an army that earn funds.
pub fn earners(core: &Core, army: u32) -> i32 {
    owned(core, army, &EARNERS)
}

/// Properties of `kinds` an army owns.
fn owned(core: &Core, army: u32, kinds: &[u8]) -> i32 {
    let m = map(core);
    let (w, h) = (core.raw_read_16(m, -1) as u32, core.raw_read_16(m + 2, -1) as u32);
    let mut n = 0;
    for y in 0..h.min(64) {
        for x in 0..w.min(64) {
            let c = class_at(core, x, y);
            if (c >> 5) as u32 == army && kinds.contains(&(c & 0x1F)) {
                n += 1;
            }
        }
    }
    n
}

/// An army's CO and the power it is setting off (player +0x1F): the
/// power level (+0x1E) is only set once the power's effects are over.
pub(crate) fn activating(core: &Core, army: u32) -> (u8, u8) {
    let p = player(core, army);
    (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x1F, -1))
}

fn player(core: &Core, army: u32) -> u32 {
    core.raw_read_32(PLAYERS_POINTER, -1) + PLAYER * army
}

fn unit_index_at(core: &Core, x: u32, y: u32) -> u32 {
    let m = map(core);
    let row = core.raw_read_16(m + ROWS + 2 * y, -1) as u32;
    core.raw_read_8(m + UNIT_PLANE + row + x, -1) as u32
}

fn army_of_index(core: &Core, i: u32) -> u32 {
    crate::five::army_of_index(core, i)
}

/// Firepower % an army's units get on top of their CO's: its Com Towers'
/// and Kindle's High Society. Nothing with CO abilities off (Dual Strike's
/// `Player_GetFirepowerBonus` returns 0 then, towers and all).
pub fn extra_firepower(core: &Core, army: u32) -> i32 {
    let mut add = 0;
    if core.raw_read_8(CO_ABILITIES, -1) == 0 {
        return 0;
    }
    if crate::com_tower::active(core) {
        let per = crate::co_roster::tower_attack(core, army) + crate::co_skills::tower_bonus(core, army);
        add += per * crate::com_tower::towers(core, army) as i32;
    }
    if is_on(core) && army_co(core, army) == (KINDLE, SCOP) {
        add += high_society(core, army);
    }
    add
}

/// Kindle's High Society as Dual Strike has it (`UrbanMultiplier`, her
/// Super Power's bonus, worked out once as it starts): +3% per property
/// she owns then, kept until it ends. [`activate`] counts it; a game
/// continued during the power without the count counts now.
const HIGH_SOCIETY: u32 = crate::ram_map::HIGH_SOCIETY.0;
fn high_society(core: &Core, army: u32) -> i32 {
    match core.raw_read_16(HIGH_SOCIETY + 2 * (army - 1), -1) {
        0 => 3 * owned(core, army, &PROPERTIES),
        v => v as i32 - 1,
    }
}
fn count_high_society(core: &mut Core, army: u32, mode: u8) {
    let v = if army_co(core, army).0 == KINDLE && mode == SCOP { 1 + 3 * owned(core, army, &PROPERTIES) as u16 } else { 0 };
    core.raw_write_16(HIGH_SOCIETY + 2 * (army - 1), -1, v);
}

/// Defence % for Javier's units against an indirect attack: +20 day to
/// day, +40 in Tower Shield, +80 in Tower of Power.
///
/// Dual Strike's numbers, from its code: his power blocks set one skill bit
/// each (block +0x09 = 0x08 / 0x10 / 0x20, skills 0x0C / 0x0D / 0x0E, which
/// 0x020E70xx copies into the player's skill words at +0x74), and
/// 0x020E61D8 adds 0x14 / 0x28 / 0x50 to the defender's defence when the
/// attacker's unit class is indirect (0x020DF7AC = 8). It goes on top of
/// the power's standard +10% and the Com Towers', straight into the
/// defence value (100 + bonuses), which Dual Strike caps at 200 with the
/// terrain (0x020C34C8; see `co_roster`'s `defence_total`).
pub fn indirect_defence(core: &Core, army: u32) -> i32 {
    let (co, mode) = army_co(core, army);
    if !is_on(core) || co != JAVIER {
        return 0;
    }
    [20, 40, 80][mode.min(2) as usize]
}

// --- Stun (Ex Machina) --------------------------------------------------------------

/// Unit bits (index = army * 64 + slot, 5 armies): hit and waiting for
/// their army's turn, and held through that turn. RAM tangoAW2 keeps.
const STUN_PENDING: u32 = 0x0203_FE00;
const STUN_ACTIVE: u32 = 0x0203_FE28;
const STUN_BYTES: u32 = 40;
const STUN_PREV_ARMY: u32 = 0x0203_FE50;
const MOVED: u8 = 0x01;

fn bit(core: &Core, base: u32, i: u32) -> bool {
    core.raw_read_8(base + i / 8, -1) & (1 << (i % 8)) != 0
}

fn set_bit(core: &mut Core, base: u32, i: u32, on: bool) {
    let b = core.raw_read_8(base + i / 8, -1);
    let v = if on { b | 1 << (i % 8) } else { b & !(1 << (i % 8)) };
    if v != b {
        core.raw_write_8(base + i / 8, -1, v);
    }
}

fn clear_stuns(core: &mut Core) {
    for k in 0..STUN_BYTES {
        for base in [STUN_PENDING, STUN_ACTIVE] {
            if core.raw_read_8(base + k, -1) != 0 {
                core.raw_write_8(base + k, -1, 0);
            }
        }
    }
}

/// `sub_08044854(x, y, damage)`, a strike's hit on one square: in Von
/// Bolt's Ex Machina the unit there is paralysed (not an Oozium), as Dual
/// Strike's `Unit_ParalyseAtTile`: another army's is marked to lose its
/// next turn; one of his own is done for this turn (it moved), and free
/// again on his next.
const STRIKE_SQUARE: u32 = 0x0804_4854;
fn strike_square(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if activating(core, army) != (VON_BOLT, SCOP) {
        return;
    }
    let cpu = core.gba().cpu();
    let (x, y) = (cpu.gpr(0), cpu.gpr(1));
    let m = map(core);
    let (w, h) = (core.raw_read_16(m, -1) as i32, core.raw_read_16(m + 2, -1) as i32);
    if !(0..w).contains(&x) || !(0..h).contains(&y) {
        return;
    }
    let i = unit_index_at(core, x as u32, y as u32);
    if i == 0 {
        return;
    }
    let u = core.raw_read_32(UNITS_POINTER, -1) + UNIT * i;
    let f = core.raw_read_8(u + 1, -1);
    if core.raw_read_8(u, -1) == 0 || f & 0x08 != 0 || crate::oozium::immune(core, u) {
        return;
    }
    if army_of_index(core, i) == army {
        core.raw_write_8(u + 1, -1, f | MOVED);
    } else {
        set_bit(core, STUN_PENDING, i, true);
    }
}

/// Every frame: a marked unit is held (as if it had moved) through its
/// army's next turn.
fn stun(core: &mut Core) {
    let in_battle = (1..=5).any(|a| army_co(core, a).0 == VON_BOLT);
    if !in_battle {
        clear_stuns(core);
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    let prev = core.raw_read_8(STUN_PREV_ARMY, -1) as u32;
    if army != prev {
        for i in 0..STUN_BYTES * 8 {
            if army_of_index(core, i) == army && bit(core, STUN_PENDING, i) {
                set_bit(core, STUN_PENDING, i, false);
                set_bit(core, STUN_ACTIVE, i, true);
            } else if army_of_index(core, i) == prev && bit(core, STUN_ACTIVE, i) {
                // Released: the game cleared its moved flag as its turn
                // ended, which this tick then set again.
                set_bit(core, STUN_ACTIVE, i, false);
                let u = core.raw_read_32(UNITS_POINTER, -1) + UNIT * i;
                let f = core.raw_read_8(u + 1, -1);
                core.raw_write_8(u + 1, -1, f & !MOVED);
            }
        }
        core.raw_write_8(STUN_PREV_ARMY, -1, army as u8);
    }
    let units = core.raw_read_32(UNITS_POINTER, -1);
    for i in 0..STUN_BYTES * 8 {
        if bit(core, STUN_ACTIVE, i) {
            let u = units + UNIT * i;
            let f = core.raw_read_8(u + 1, -1);
            if core.raw_read_8(u, -1) == 0 {
                set_bit(core, STUN_ACTIVE, i, false);
            } else if f & MOVED == 0 {
                core.raw_write_8(u + 1, -1, f | MOVED);
            }
        }
    }
}

pub fn tick(core: &mut Core, on: bool) {
    if on {
        install(core);
        stun(core);
    }
}

/// The stun's bits (pending, then held), for a suspended game
/// ([`crate::suspend`]).
pub const STUN_STATE_LEN: usize = 2 * STUN_BYTES as usize;

pub fn stun_state(core: &Core) -> Vec<u8> {
    let mut b = vec![0u8; STUN_STATE_LEN];
    core.raw_read_range(STUN_PENDING, -1, &mut b[..STUN_BYTES as usize]);
    core.raw_read_range(STUN_ACTIVE, -1, &mut b[STUN_BYTES as usize..]);
    b
}

/// A suspended game continued: its stun bits (none from a game saved
/// without them), the army whose turn it is taken as the tick's last.
pub fn set_stun_state(core: &mut Core, state: Option<&[u8]>, army: u8) {
    clear_stuns(core);
    if let Some(b) = state.filter(|b| b.len() == STUN_STATE_LEN) {
        core.raw_write_range(STUN_PENDING, -1, &b[..STUN_BYTES as usize]);
        core.raw_write_range(STUN_ACTIVE, -1, &b[STUN_BYTES as usize..]);
    }
    core.raw_write_8(STUN_PREV_ARMY, -1, army);
}

// --- Strike sites (Covering Fire, Ex Machina) ------------------------------------

/// Where Covering Fire's missiles and Ex Machina's bolt land, as Dual
/// Strike picks them (`Strike_FindBestSite` / `Strike_ScoreSite`): every
/// cell is a candidate centre (rows from the top, cells from the left; a
/// later one only on a higher score); each unit within 2 (a 13-cell
/// diamond) scores for 3 HP of damage, enemy and own team apart, and an
/// enemy on the centre adds 1. Ex Machina scores by HP or by funds (the
/// game's RNG, `Rng_Range(0, 1)`) and takes enemy - 2 x own; Covering
/// Fire's three missiles by HP, then funds, then infantry, each enemy - 4 x
/// own, each seeing the last one's damage. No enemy score: no site, and
/// that missile or bolt falls nowhere (Dual Strike skips the infantry
/// missile and the bolt then; tangoAW2 the other two missiles too, whose
/// site Dual Strike leaves unset).
///
/// AW2's meteor script picks an enemy unit (`sub_0805C290`) into the
/// proc's +0x66 and reads that unit's square where it moves the cursor,
/// draws and hits: with a site from here +0x66 holds 1 and the square is
/// put in at those three places ([`strike_pick`], [`strike_draw`],
/// [`strike_hit`]).
const STRIKE: u32 = crate::ram_map::STRIKE_SITE.0;
/// [`STRIKE`]: +0 the power whose sites are picked (1 Ex Machina, 2
/// Covering Fire, 0 none), +1 its army, +2 missiles picked, +3 a site is
/// set, +4 its x, +5 its y.
const STRIKE_EX_MACHINA: u8 = 1;
const STRIKE_COVERING_FIRE: u8 = 2;
const STRIKE_DAMAGE: i32 = 30;
const STRIKE_RADIUS: i32 = 2;
const NO_SITE: i32 = i32::MIN + 1;
/// Units with no weapon (`UnitType_GetAttackKind` 2): APC, Black Boat, T
/// Copter, Lander.
const NO_WEAPON: [u8; 4] = [7, 18, 20, 23];
const INFANTRY: u8 = 1;
const MECH: u8 = 2;
const RNG: u32 = 0x0300_1FD4;

#[derive(Clone, Copy)]
enum StrikeScore {
    Hp,
    Funds,
    Infantry,
}

fn strike_unit_score(core: &Core, u: u32, kind: StrikeScore, enemy: bool) -> i32 {
    let t = core.raw_read_8(u, -1);
    if t == crate::roster::OOZIUM {
        return 0;
    }
    let hp = (core.raw_read_8(u + 4, -1) & 0x7F) as i32;
    let small = if matches!(kind, StrikeScore::Funds) { 2 } else { 1 };
    let no_weapon = NO_WEAPON.contains(&t);
    if hp <= 10 || (no_weapon && enemy) {
        return small;
    }
    let lost = if hp > STRIKE_DAMAGE { STRIKE_DAMAGE } else { hp - 1 };
    let mut v = match kind {
        StrikeScore::Hp => lost,
        StrikeScore::Funds => core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as i32 * lost,
        StrikeScore::Infantry => {
            let mut v = lost;
            if enemy && (t == INFANTRY || t == MECH) {
                v *= 4;
            }
            if enemy && core.raw_read_8(u + 5, -1) >> 3 != 0 {
                v *= 2;
            }
            v
        }
    };
    if no_weapon && !enemy {
        v /= 2;
    }
    v
}

fn strike_site_score(core: &Core, army: u32, x: i32, y: i32, kind: StrikeScore, own_weight: i32) -> i32 {
    let m = map(core);
    let (w, h) = (core.raw_read_16(m, -1) as i32, core.raw_read_16(m + 2, -1) as i32);
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let team = |a: u32| core.raw_read_8(player(core, a) + 0x2A, -1);
    let mine = team(army);
    let (mut enemy, mut own) = (0i32, 0i32);
    for ty in (y - STRIKE_RADIUS).max(0)..=(y + STRIKE_RADIUS).min(h - 1) {
        for tx in (x - STRIKE_RADIUS).max(0)..=(x + STRIKE_RADIUS).min(w - 1) {
            if (x - tx).abs() + (y - ty).abs() > STRIKE_RADIUS {
                continue;
            }
            let i = unit_index_at(core, tx as u32, ty as u32);
            let u = units + UNIT * i;
            if i == 0 || core.raw_read_8(u, -1) == 0 {
                continue;
            }
            if team(army_of_index(core, i)) == mine {
                own += strike_unit_score(core, u, kind, false);
            } else {
                enemy += strike_unit_score(core, u, kind, true);
            }
        }
    }
    let c = unit_index_at(core, x as u32, y as u32);
    if c != 0 && team(army_of_index(core, c)) != mine {
        enemy += 1;
    }
    if enemy == 0 { NO_SITE } else { enemy - own_weight * own }
}

/// `Strike_FindBestSite` for `army`.
fn strike_best_site(core: &Core, army: u32, kind: StrikeScore, own_weight: i32) -> Option<(u8, u8)> {
    let m = map(core);
    let (w, h) = (core.raw_read_16(m, -1) as i32, core.raw_read_16(m + 2, -1) as i32);
    let mut best = (NO_SITE, None);
    for y in 0..h.min(64) {
        for x in 0..w.min(64) {
            let v = strike_site_score(core, army, x, y, kind, own_weight);
            if v > best.0 {
                best = (v, Some((x as u8, y as u8)));
            }
        }
    }
    best.1
}

/// The pick step (`sub_080448E4(proc)`, just past its `push`: r4 the
/// proc): with a site from here, +0x66 = 1 and on to its cursor move
/// (0x08044912, r0/r1 the square); with none, +0x66 = 0 and out.
const STRIKE_PICK: u32 = 0x0804_48E8;
const STRIKE_PICK_CURSOR: u32 = 0x0804_4912;
const STRIKE_PICK_OUT: u32 = 0x0804_4916;
fn strike_pick(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let power = core.raw_read_8(STRIKE, -1);
    let army = core.raw_read_8(STRIKE + 1, -1) as u32;
    if power == 0 || army != core.raw_read_16(CURRENT_ARMY, -1) as u32 {
        return;
    }
    let site = if power == STRIKE_EX_MACHINA {
        core.raw_write_8(STRIKE, -1, 0);
        let s = core.raw_read_32(RNG, -1).wrapping_mul(4);
        let r = s.wrapping_add(2).wrapping_mul(s.wrapping_add(3)) >> 2;
        core.raw_write_32(RNG, -1, r);
        let kind = if r % 2 == 0 { StrikeScore::Funds } else { StrikeScore::Hp };
        strike_best_site(core, army, kind, 2)
    } else {
        let k = core.raw_read_8(STRIKE + 2, -1);
        core.raw_write_8(STRIKE + 2, -1, k + 1);
        if k >= 2 {
            core.raw_write_8(STRIKE, -1, 0);
        }
        let kind = [StrikeScore::Hp, StrikeScore::Funds, StrikeScore::Infantry][k.min(2) as usize];
        strike_best_site(core, army, kind, 4)
    };
    let p = core.gba().cpu().gpr(4) as u32;
    match site {
        Some((x, y)) => {
            core.raw_write_8(STRIKE + 3, -1, 1);
            core.raw_write_8(STRIKE + 4, -1, x);
            core.raw_write_8(STRIKE + 5, -1, y);
            core.raw_write_16(p + 0x66, -1, 1);
            let cpu = core.gba_mut().cpu_mut();
            cpu.set_gpr(0, x as i32);
            cpu.set_gpr(1, y as i32);
            cpu.set_gpr(4, (p + 0x66) as i32);
            cpu.set_thumb_pc(STRIKE_PICK_CURSOR);
        }
        None => {
            core.raw_write_8(STRIKE + 3, -1, 0);
            core.raw_write_16(p + 0x66, -1, 0);
            core.gba_mut().cpu_mut().set_thumb_pc(STRIKE_PICK_OUT);
        }
    }
}

fn strike_square_set(core: &Core) -> Option<(i32, i32)> {
    (is_on(core) && core.raw_read_8(STRIKE + 3, -1) != 0)
        .then(|| (core.raw_read_8(STRIKE + 4, -1) as i32, core.raw_read_8(STRIKE + 5, -1) as i32))
}

/// A strike's target square: the site from here, else the square of the
/// unit at its proc's +0x66 (AW2's pick; none for 0). For the drawing
/// (crate::power_anim).
pub(crate) fn strike_target(core: &Core, proc: u32) -> Option<(u8, u8)> {
    if let Some((x, y)) = strike_square_set(core) {
        return Some((x as u8, y as u8));
    }
    let i = core.raw_read_16(proc + 0x66, -1) as i16;
    (i > 0).then(|| {
        let u = core.raw_read_32(UNITS_POINTER, -1) + UNIT * i as u32;
        (core.raw_read_8(u + 2, -1), core.raw_read_8(u + 3, -1))
    })
}

/// The draw step (`sub_08044968`), about to draw at the unit's square
/// (r0, r1).
const STRIKE_DRAW: u32 = 0x0804_4988;
fn strike_draw(core: &mut Core) {
    if let Some((x, y)) = strike_square_set(core) {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(0, x);
        cpu.set_gpr(1, y);
    }
}

/// The hit step (`sub_08044994`), the unit's square just loaded (r8, r6):
/// the site's, used once.
const STRIKE_HIT: u32 = 0x0804_49BE;
fn strike_hit(core: &mut Core) {
    if let Some((x, y)) = strike_square_set(core) {
        core.raw_write_8(STRIKE + 3, -1, 0);
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(8, x);
        cpu.set_gpr(6, y);
    }
}

// --- Traps -----------------------------------------------------------------------

/// `sub_08044F24`'s per-unit step of a mass damage (r4 the unit, just
/// found to be on the map): an Oozium is skipped (0x0804505E is the next
/// unit), and in Urban Blight a unit off a property.
const MASS_UNIT: u32 = 0x0804_4FFC;
const MASS_NEXT: u32 = 0x0804_505E;
fn mass_unit(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    // Powers pass the Oozium by ([`crate::oozium`]).
    if crate::oozium::immune(core, core.gba().cpu().gpr(4) as u32) {
        core.gba_mut().cpu_mut().set_thumb_pc(MASS_NEXT);
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if activating(core, army) != (KINDLE, COP) {
        return;
    }
    let u = core.gba().cpu().gpr(4) as u32;
    let (x, y) = (core.raw_read_8(u + 2, -1) as u32, core.raw_read_8(u + 3, -1) as u32);
    if !PROPERTIES.contains(&(class_at(core, x, y) & 0x1F)) {
        core.gba_mut().cpu_mut().set_thumb_pc(MASS_NEXT);
    }
}

/// `ActivateCoPower(army, mode, proc)`: Kindle's High Society is counted
/// ([`high_society`]); Sasha's Market Crash (and the History's count).
const ACTIVATE: u32 = 0x0804_4B28;
const SCOP_COST: u32 = 0x0804_4208;
fn activate(core: &mut Core) {
    // (a room's battle counts the powers used for the online record, with the pack or not)
    {
        let cpu = core.gba().cpu();
        let (army, mode) = (cpu.gpr(0) as u32, cpu.gpr(1) as u8);
        crate::online_stats::power_used(core, army, mode);
    }
    if !is_on(core) {
        return;
    }

    let cpu = core.gba().cpu();
    let (army, mode) = (cpu.gpr(0) as u32, cpu.gpr(1) as u8);
    // (the History's powers used, crate::history)
    crate::history::power(core, army, mode);
    if (1..=5).contains(&army) {
        count_high_society(core, army, mode);
        // The strikes' sites are Dual Strike's ([`strike_pick`]).
        let power = match (army_co(core, army).0, mode) {
            (VON_BOLT, SCOP) => STRIKE_EX_MACHINA,
            (RACHEL, SCOP) => STRIKE_COVERING_FIRE,
            _ => 0,
        };
        core.raw_write_range(STRIKE, -1, &[power, army as u8, 0, 0]);
    }
    let (co, _) = army_co(core, army);
    if co != SASHA || mode != COP {
        return;
    }
    // Dual Strike's `MarketCrash`: every enemy in the game, its active CO
    // and its tag partner, each loses its Super Power's cost x the % (worked
    // in Dual Strike's meter units, AW2's / 180, as it rounds).
    let funds = core.raw_read_32(player(core, army), -1);
    let pct = (funds / 500).min(100);
    let cut = |full: u32| full / METER_SCALE * pct / 100 * METER_SCALE;
    let team: Vec<u8> = (0..=5u32).map(|a| core.raw_read_8(player(core, a) + 0x2A, -1)).collect();
    for enemy in 1..=5u32 {
        if enemy == army || team[enemy as usize] == team[army as usize] || !crate::co_roster::in_game(core, enemy) {
            continue;
        }
        let full = super_cost(core, enemy);
        let p = player(core, enemy) + 0x20;
        let charge = core.raw_read_32(p, -1);
        core.raw_write_32(p, -1, charge.saturating_sub(cut(full)));
        if let Some(co) = crate::tag::partner(core, enemy) {
            let full = crate::tag::scop_cost(core, co, crate::tag::partner_uses(core, enemy));
            let charge = crate::tag::partner_charge(core, enemy);
            crate::tag::set_partner_charge(core, enemy, charge.saturating_sub(cut(full)));
        }
    }
    let _ = SCOP_COST;
}

/// An army's full meter (its SCOP's cost): 9000 per star, +20% per power
/// used (at most +100%), `GetCoPowerStarCost`.
fn super_cost(core: &Core, army: u32) -> u32 {
    let p = player(core, army);
    let uses = core.raw_read_8(p + 0x25, -1) as u32;
    let pct = if uses > 9 { 200 } else { 100 + 20 * uses };
    let (co, _) = army_co(core, army);
    let table = core.raw_read_32(0x0804_2DDC, -1);
    let stars = core.raw_read_32(table + 0x104 * co as u32 + 0x10, -1);
    9000 * pct / 100 * stars
}

/// `AddPlayerIncomeToFunds`: the day's income in r1 just before it is
/// added. Sasha gets 100 more per property that earns.
const INCOME: u32 = 0x0802_6F18;
/// gPlaySt's funds per property (the Rules screen's Funds, 1000 by default; 0 when a mode pays no income).
const FUNDS_PER_PROPERTY: u32 = 0x0300_3FE8;
fn income(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    let earners = owned(core, army, &EARNERS);
    let mut add = crate::co_skills::income_bonus(core, army, earners);
    if army_co(core, army).0 == SASHA {
        add += 100 * earners;
    }
    add += crate::es_co::income_bonus(army_co(core, army).0, earners, core.raw_read_32(FUNDS_PER_PROPERTY, -1) as i32);
    if add == 0 {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    let r1 = cpu.gpr(1);
    cpu.set_gpr(1, r1 + add);
}

/// `RepairUnit(unit, hp, pay)`: a property's daily repair (its two calls,
/// by their return addresses) gives Dual Strike's `Player_GetDailyRepairHp`:
/// 2 + the CO's `repairBonus` (its power block +0x1A, Rachel's 1; with CO
/// abilities on) + Mechanic's 1 / Gear Head's 2. A power's heal (Andy's 2
/// and 5 HP) or Ration Run's 1 HP is a fixed number of steps, no bonus.
const REPAIR: u32 = 0x0802_9AF8;
const DAILY_REPAIR_CALLS: [u32; 2] = [0x0802_A0C5, 0x0802_A137];
fn repair(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (u, hp, lr) = (cpu.gpr(0) as u32, cpu.gpr(1), cpu.gpr(14) as u32);
    if hp <= 0 || !DAILY_REPAIR_CALLS.contains(&lr) {
        return;
    }
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let army = army_of_index(core, u.wrapping_sub(units) / UNIT);
    if !(1..=5).contains(&army) {
        return;
    }
    let add = crate::co_roster::repair_bonus(core, army) + crate::co_skills::repair_bonus(core, army);
    if add != 0 {
        core.gba_mut().cpu_mut().set_gpr(1, hp + add);
    }
}

/// Dual Strike's `Unit_GetValuePerHp(army, type)`: the unit's cost / 10 x
/// (100 + its CO's cost % at its power level, with CO abilities on, + Sale
/// Price's / Fire Sale's cut) / 100, as AW2's `sub_08042C9C` with
/// tangoAW2's price trap ([`crate::co_skills`]) works it out. For repairs
/// and War Bonds.
pub(crate) fn value_per_hp(core: &Core, army: u32, t: u8) -> u32 {
    let cost10 = core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as i32;
    let mut pct = 0;
    if core.raw_read_8(CO_ABILITIES, -1) != 0 {
        let (co, mode) = army_co(core, army);
        let table = core.raw_read_32(COST_TABLE_POOL, -1);
        pct += core.raw_read_16(table + 0x104 * co as u32 + 0x4C + 0x44 * mode.min(2) as u32, -1) as i16 as i32;
    }
    pct -= crate::co_skills::price_cut(core, army);
    (cost10 * (100 + pct) / 100).max(0) as u32
}
/// `GetCoPriceModifier`'s literal pool word: the CO table it reads.
const COST_TABLE_POOL: u32 = 0x0804_329C;

/// `sub_08041978(defender index, ...)`, after a battle is chosen: it
/// works the battle out (`sub_080251BC`), then charges both power meters
/// (the first at 0x08041CB8), with the units' HP not yet updated and the
/// battle records holding what is left. There War Bonds pays Sasha half
/// the value of the HP her side took off the other, and with the pack
/// both charges are Dual Strike's ([`battle_charges`]). (The defender is
/// kept from its entry.)
const AFTER_BATTLE: u32 = 0x0804_1978;
const METERS_CHARGED: u32 = 0x0804_1CB8;
const BATTLE_DEFENDER_INDEX: u32 = 0x0203_FE54;
const SELECTED_UNIT: u32 = 0x0300_40D8;
const BATTLE_ATTACKER: u32 = 0x0300_13D0;
const BATTLE_DEFENDER: u32 = 0x0300_13B0;
const MAX_FUNDS: u32 = 999_999;
fn bars(hp: i32) -> i32 {
    if hp > 0 { (hp - 1) / 10 + 1 } else { 0 }
}
fn after_battle(core: &mut Core) {
    if is_on(core) {
        let d = core.gba().cpu().gpr(0) as u8;
        core.raw_write_8(BATTLE_DEFENDER_INDEX, -1, d);
    }
}

/// AW2's meter is Dual Strike's x 180: a star costs 9000 to its 50, and
/// both add 20% a power used ([`super_cost`]).
pub(crate) const METER_SCALE: u32 = 180;

/// Dual Strike's meter charge per shown HP a unit type loses (its unit
/// record +0x13, `chargePerHp`: Infantry 2, Tank 5, Megatank 11), in its
/// own units; 0 without the pack.
pub(crate) fn charge_per_hp(t: u8) -> u32 {
    crate::roster::ds_record(t).map_or(0, |r| r[0x13] as u32)
}

/// The battle's charge for each side in Dual Strike's units
/// (`ActingUnit_StartAttack`): its shown HP lost x its unit's
/// `chargePerHp`, plus half the other side's. AW2 values the HP at the
/// unit's price instead.
fn battle_charges(core: &Core) -> Option<(u32, u32)> {
    let d = core.raw_read_8(BATTLE_DEFENDER_INDEX, -1) as u32;
    if d == 0 {
        return None;
    }
    let att = core.raw_read_32(SELECTED_UNIT, -1);
    let dfd = core.raw_read_32(UNITS_POINTER, -1) + UNIT * d;
    let loss = |u: u32, record: u32| {
        let before = bars(core.raw_read_8(u + 4, -1) as i32 & 0x7F);
        let after = bars(core.raw_read_16(record + 8, -1) as i16 as i32);
        (before - after).max(0) as u32 * charge_per_hp(core.raw_read_8(u, -1))
    };
    let (a, b) = (loss(att, BATTLE_ATTACKER), loss(dfd, BATTLE_DEFENDER));
    Some((a + (b >> 1), b + (a >> 1)))
}

/// The attacker's `AddCoPowerCharge` (r1 the amount), after War Bonds:
/// with the pack, Dual Strike's charge.
fn attacker_charged(core: &mut Core) {
    war_bonds(core);
    if !is_on(core) {
        return;
    }
    // (Aurelia's Onager: the units beside the target lose 1 HP, crate::es_co)
    crate::es_co::onager(core, core.raw_read_8(BATTLE_DEFENDER_INDEX, -1) as u32);
    if let Some((a, _)) = battle_charges(core) {
        core.gba_mut().cpu_mut().set_gpr(1, (a * METER_SCALE) as i32);
    }
}

/// The defender's `AddCoPowerCharge` (0x08041CCA, r1 the amount).
const DEFENDER_CHARGED: u32 = 0x0804_1CCA;
fn defender_charged(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    if let Some((_, d)) = battle_charges(core) {
        core.gba_mut().cpu_mut().set_gpr(1, (d * METER_SCALE) as i32);
    }
}

fn war_bonds(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let d = core.raw_read_8(BATTLE_DEFENDER_INDEX, -1) as u32;
    if d == 0 {
        return;
    }
    // (an Oozium destroyed: Dual Strike's bonus points, crate::battle_points; the History's counters)
    crate::battle_points::battle_fought(core, core.raw_read_32(SELECTED_UNIT, -1), d);
    crate::history::battle_fought(core, core.raw_read_32(SELECTED_UNIT, -1), d);
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let att = core.raw_read_32(SELECTED_UNIT, -1);
    let dfd = units + UNIT * d;
    let sides = [(att, BATTLE_ATTACKER, dfd, BATTLE_DEFENDER), (dfd, BATTLE_DEFENDER, att, BATTLE_ATTACKER)];
    for (own, _, foe, foe_record) in sides {
        let army = army_of_index(core, own.wrapping_sub(units) / UNIT);
        let bonds = army_co(core, army) == (SASHA, SCOP);
        if !(1..=5).contains(&army) || !(bonds || crate::co_skills::has(core, army, crate::co_skills::COMBAT_PAY)) {
            continue;
        }
        let before = bars(core.raw_read_8(foe + 4, -1) as i32 & 0x7F);
        let after = bars(core.raw_read_16(foe_record + 8, -1) as i16 as i32);
        let lost = (before - after).max(0) as u32;
        // The HP's value as its owner's (Dual Strike's `DamageToFunds`:
        // `Unit_GetValuePerHp(targetOwner, type)`, the CO's cost % in it).
        let foe_army = army_of_index(core, foe.wrapping_sub(units) / UNIT);
        let cost = value_per_hp(core, foe_army, core.raw_read_8(foe, -1)) * 10;
        let pay = if bonds { lost * cost / 10 / 2 } else { 0 } + crate::co_skills::combat_pay(core, army, lost, cost);
        if pay == 0 {
            continue;
        }
        let p = player(core, army);
        let funds = core.raw_read_32(p, -1);
        core.raw_write_32(p, -1, (funds + pay).min(MAX_FUNDS));
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (STRIKE_SQUARE, Box::new(strike_square)),
        (MASS_UNIT, Box::new(mass_unit)),
        (ACTIVATE, Box::new(activate)),
        (INCOME, Box::new(income)),
        (REPAIR, Box::new(repair)),
        (AFTER_BATTLE, Box::new(after_battle)),
        (METERS_CHARGED, Box::new(attacker_charged)),
        (DEFENDER_CHARGED, Box::new(defender_charged)),
        (STRIKE_PICK, Box::new(strike_pick)),
        (STRIKE_DRAW, Box::new(strike_draw)),
        (STRIKE_HIT, Box::new(strike_hit)),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn code_sizes() {
        assert_eq!(strike_fn(0, 30).len(), 36);
        assert_eq!(urban_blight_fn(0, 0).len(), 72);
        assert!(COVERING_FIRE_SCRIPT + 8 * 29 <= EX_MACHINA_FN);
        assert!(URBAN_BLIGHT_FN + 72 <= SENTINEL);
    }
}
