//! Crumb ("Pip Hobb", the Black Hole soldier promoted to Commander), tangoAW2's
//! eleventh new CO (id 82, [`crate::co_new::CRUMB`]), with the Dual Strike
//! pack only. **Everything of his is tangoAW2's own**: Dual Strike has no
//! such CO. His pictures are cut from AW2's Black Hole trooper
//! ([`crate::crumb_art`]), his name, texts and quotes are written for the
//! BH Campaign (`docs/BH_CAMPAIGN.md` 3.9 and 4.7c), his numbers are below.
//!
//! | | |
//! |---|---|
//! | Day to day, **Rank and File** | Infantry and Mech +10% attack and +10% defence; his units on his cities and bases are fully resupplied (ammo and fuel) at the start of each of his turns (AW2's own property supply already does it for the units a property repairs; this adds the others: an aircraft on a city, a ship on a base) |
//! | CO Power, **Ration Run** (3 stars) | every unit fully resupplied and healed 1 HP; Infantry and Mech +1 move |
//! | Super Power, **Gerald's Blessing** (6 stars) | every unit healed 2 HP; Infantry and Mech +30% attack (on top of Rank and File); luck 0..19% for every unit (AW2's Nell has up to 99), bad luck none |
//! | Tag with Sturm, **No One Left Behind** | 115%, 2 stars ([`crate::sturm_pairs`]): the Tag Power fires both Super Powers, and then every unit of the army at 3 HP or below is healed to 6 HP and may move 1 space more this turn |
//!
//! **Star costs.** 3 for the CO Power and 6 in all for the Super Power are
//! Dual Strike's most common cost (Andy, Max, Jess, Javier, Kindle and
//! Rachel, 3 and 6; Hachi 3 and 5): a support CO whose powers heal and
//! resupply without hitting anything should not charge faster than
//! Hachi's, nor slower than Max's, who needs the same for a +10% attack.
//!
//! **How.** The numbers (firepower, defence, move) are [`bonus`], called by
//! [`crate::co_roster::stat`]; luck is in his CO table row
//! ([`crate::co_roster`]); the powers' effect on each unit is a function the
//! game calls for every unit of the army ([`each_unit`]: AW2's own
//! resupply and repair routines, written into free ROM as Thumb code);
//! Rank and File's resupply is a trap in the turn's property pass; the Tag
//! Power's rule ([`tick`]) waits for the second Super Power's end.

use mgba::core::Core;

use crate::co_new::CRUMB;
use crate::ds_weather::is_on;

pub const STURM: u8 = 10;
/// AW2's unit ids of Infantry and Mech.
const INFANTRY: u8 = 1;
const MECH: u8 = 2;

pub fn foot(t: u8) -> bool {
    t == INFANTRY || t == MECH
}

/// His luck per power level (day, CO Power, Super Power) and his bad luck:
/// AW2's rows are 10 (0..9%) for most COs; Nell's go 20, 60, 100.
pub const LUCK: [i16; 3] = [10, 10, 20];
pub const BAD_LUCK: [i16; 3] = [0, 0, 0];
/// Stars of the CO Power and of the Super Power in all (the CO table's row).
pub const STARS: (u32, u32) = (3, 6);

/// The CO's own firepower, defence and move for a unit type at a power level
/// (`field` as [`crate::co_roster::stat`]'s; what every power adds to
/// firepower is added by the caller).
pub fn bonus(mode: u8, t: u8, field: usize) -> i32 {
    if !foot(t) {
        return 0;
    }
    match field {
        crate::co_roster::FIREPOWER => 10 + if mode == 2 { 30 } else { 0 },
        crate::co_roster::DEFENCE => 10,
        crate::co_roster::MOVE => (mode == 1) as i32,
        _ => 0,
    }
}

// --- Texts ----------------------------------------------------------------------------

pub const NAME: &[u8] = b"Crumb";
/// The CO page's bio, with Hit and Miss, in AW2's bio style for a Versus
/// player who has not played the campaign (who he is, what his strength is);
/// the page has six lines of 103 pixels. (The design's longer bio, `docs/
/// BH_CAMPAIGN.md` 4.7c, is the campaign's story and did not read as a CO
/// description.)
pub const BIO: &[u8] = b"A Black Hole soldier promoted by Sturm. Keeps his troops fed and supplied.\rHit: Biscuits\rMiss: Being left behind";
pub const DAY_TO_DAY: &[u8] = b"My foot soldiers are sturdy, and anyone on a city or base gets fed.";
pub const COP_PAGE: &[u8] = b"Restores 1 HP to all units and fully resupplies them. Infantry and Mech move 1 space more.";
pub const SCOP_PAGE: &[u8] = b"Restores 2 HP to all units. Infantry and Mech firepower rises by 30%, and luck improves for all units.";
pub const COP_NAME: &[u8] = b"Ration Run";
pub const SCOP_NAME: &[u8] = b"Gerald's Blessing";
/// The six power quotes the game picks from ([`crate::co_new::T_QUOTES`]):
/// the CO Power's, the Super Power's and the Tag Power's, each twice.
pub const QUOTE_COP: &[u8] = b"Ration run! Everybody\reats! Even you, Gerald!";
pub const QUOTE_SCOP: &[u8] = b"Gerald's Blessing! Hold on,\reverybody, he's glowing!";
pub const QUOTE_TAG: &[u8] = b"No one left behind! Sir,\rthat means YOU too!";
/// The CO page's quote ("I'm not a general...") is the bond-style page text
/// of the BH Campaign ([`SECRET_QUOTE`]'s sibling); the defeat quote is kept
/// for a results box that has room for one (AW2 shows a victory quote only).
pub const PAGE_QUOTE: &[u8] = b"I'm not a general. I'm just\rthe one who stayed.";
pub const VICTORY: &[u8] = b"We won! Sir, may we have cake? For the troops?";
pub const DEFEAT: &[u8] = b"Gerald, don't look. ...Oh, you're already looking.";
/// Earned by winning M14 on day 12 or sooner (flag 0xA9, the BH Campaign's
/// tenth bond-style page quote): the CO page's text.
pub const SECRET_QUOTE: &str = "Nobody left me behind. Not once. I'm keeping count.";

/// A text of his by [`crate::co_new`]'s slot.
pub fn text(which: u16) -> Option<Vec<u8>> {
    use crate::co_new::*;
    let q = |t: &[u8]| t.to_vec();
    Some(match which {
        T_NAME => q(NAME),
        T_BIO => q(BIO),
        T_D2D => q(DAY_TO_DAY),
        T_COP => q(COP_PAGE),
        T_SCOP => q(SCOP_PAGE),
        T_COP_NAME => q(COP_NAME),
        T_SCOP_NAME => q(SCOP_NAME),
        w if (T_QUOTES..T_QUOTES + 6).contains(&w) => match (w - T_QUOTES) % 3 {
            0 => q(QUOTE_COP),
            1 => q(QUOTE_SCOP),
            _ => q(QUOTE_TAG),
        },
        T_VICTORY => q(VICTORY),
        T_DEFEAT => q(DEFEAT),
        _ => return None,
    })
}

// --- Thumb code: his powers' effect on each unit -------------------------------------

/// Free ROM (after crate::heal_effect's, before crate::co_new's pictures).
const ROM: u32 = 0x0874_9C00;
const COP_EACH: u32 = ROM;
const SENTINEL: u32 = ROM + 0x3FC;
const MAGIC: u32 = 0x424D_5243; // "CRMB"

/// AW2's `sub_08029978(unit, pay)` (ammo to full), `sub_08029A48(unit, pay)`
/// (fuel to full) and `RepairUnit(unit, hp, pay)`, Thumb.
const FILL_AMMO: u32 = 0x0802_9979;
const FILL_FUEL: u32 = 0x0802_9A49;
const REPAIR: u32 = 0x0802_9AF9;
/// AW2's Andy's CO Power unit effect: `RepairUnit(unit, 2, 0)`.
const ANDY_HEAL_2: u32 = 0x0804_44ED;

/// The presentation row's unit effect for power 0 (CO Power) or 1: a Thumb
/// function the game calls for each unit of the army.
pub fn each_unit(power: u8) -> u32 {
    if power == 0 {
        COP_EACH | 1
    } else {
        ANDY_HEAL_2
    }
}

/// A far call through r3 with r5 as the return scratch (`bl` does not reach
/// from here): `ldr r3, =f; mov r5, pc; adds r5, #5; mov lr, r5; bx r3`.
struct Asm {
    code: Vec<u16>,
    lits: Vec<u32>,
    fixups: Vec<(usize, usize)>,
}

impl Asm {
    fn new() -> Asm {
        Asm { code: Vec::new(), lits: Vec::new(), fixups: Vec::new() }
    }
    fn op(&mut self, h: u16) {
        self.code.push(h);
    }
    fn call(&mut self, f: u32) {
        let lit = self.lits.len();
        self.lits.push(f);
        self.fixups.push((self.code.len(), lit));
        self.code.extend_from_slice(&[0x4B00, 0x467D, 0x3505, 0x46AE, 0x4718]);
    }
    fn finish(mut self) -> Vec<u8> {
        if self.code.len() % 2 == 1 {
            self.code.push(0x46C0); // nop, to align the literals
        }
        let base = 2 * self.code.len();
        for &(at, lit) in &self.fixups {
            let target = base + 4 * lit;
            let pc = (2 * at + 4) & !3;
            let imm = (target - pc) / 4;
            assert!(imm < 256 && target >= pc);
            self.code[at] |= imm as u16;
        }
        let mut out: Vec<u8> = self.code.iter().flat_map(|h| h.to_le_bytes()).collect();
        for l in &self.lits {
            out.extend_from_slice(&l.to_le_bytes());
        }
        out
    }
}

/// Ration Run's unit effect: `r0` the unit; ammo and fuel to full for free,
/// then one HP.
fn cop_each() -> Vec<u8> {
    let mut a = Asm::new();
    a.op(0xB530); // push {r4, r5, lr}
    a.op(0x1C04); // adds r4, r0, #0
    a.op(0x2100); // movs r1, #0
    a.call(FILL_AMMO);
    a.op(0x1C20); // adds r0, r4, #0
    a.op(0x2100); // movs r1, #0
    a.call(FILL_FUEL);
    a.op(0x1C20); // adds r0, r4, #0
    a.op(0x2101); // movs r1, #1
    a.op(0x2200); // movs r2, #0
    a.call(REPAIR);
    a.op(0xBC30); // pop {r4, r5}
    a.op(0xBC01); // pop {r0}
    a.op(0x4700); // bx r0
    a.finish()
}

/// Writes his code once (the same bytes on every peer).
pub fn install(core: &mut Core) {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return;
    }
    core.raw_write_range(COP_EACH, -1, &cop_each());
    core.raw_write_32(SENTINEL, -1, MAGIC);
}

// --- The map ----------------------------------------------------------------------

const CURRENT_ARMY: u32 = 0x0300_33EC;
const CO_ABILITIES: u32 = 0x0300_3FC8;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const PLAYERS_POINTER: u32 = 0x0849_9598;
const PLAYER: u32 = 0x3C;
const SELECTED_UNIT: u32 = 0x0300_40D8;
/// Unit slots looked at (as crate::co_powers's stun).
const SLOTS: u32 = 320;

/// The army's CO is Crumb (as the game reads it: the active one).
fn is_crumb(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army) && crate::co_roster::army_co(core, army).0 == CRUMB
}

fn abilities_on(core: &Core) -> bool {
    core.raw_read_8(CO_ABILITIES, -1) != 0
}

// --- Rank and File: his units on his cities and bases are resupplied -----------------------

/// The turn's property pass (`0x0802A090`'s test: r0 the "this property
/// repairs this unit" flag as the game read it, r4 the unit, r5 the terrain
/// class byte): for a unit the property does not take care of, on his city
/// or base, ammo and fuel are filled.
const PROPERTY_PASS: u32 = 0x0802_A08E;
const CITY: u8 = 6;
const BASE: u8 = 14;

pub fn resupply(core: &mut Core, unit: u32) {
    let stats = crate::roster::table(core) + 0x5C * core.raw_read_8(unit, -1) as u32;
    let ammo = core.raw_read_8(stats + 0x0B, -1) as u16 & 0xF;
    let fuel = core.raw_read_8(stats + 0x10, -1) & 0x7F;
    let w = core.raw_read_16(unit + 4, -1);
    core.raw_write_16(unit + 4, -1, (w & !0x780) | (ammo << 7));
    let f = core.raw_read_8(unit + 6, -1);
    core.raw_write_8(unit + 6, -1, (f & 0x80) | fuel);
}

fn property_pass(core: &mut Core) {
    if !is_on(core) || !abilities_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    if cpu.gpr(0) != 0 {
        return;
    }
    let (unit, class) = (cpu.gpr(4) as u32, cpu.gpr(5) as u8 & 0x1F);
    if class != CITY && class != BASE {
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if is_crumb(core, army) {
        resupply(core, unit);
    }
}

// --- The Tag Power: No One Left Behind -----------------------------------------------------

/// RAM: tag pairs' state (crate::tag, `STATE + 0xD0..0xFB` is free): the
/// army whose Tag Power was Sturm's and Crumb's (0 none), and its state (1
/// waiting for the second Super Power's end, 2 done); the units healed that
/// get one more move (a bit a unit slot, 40 bytes after crate::tag_extras's
/// state).
const ARMY: u32 = crate::tag::STATE + 0xD0;
const PHASE: u32 = crate::tag::STATE + 0xD1;
const MOVE_BITS: u32 = 0x0203_F5D8;
const MOVE_BYTES: u32 = 40;
/// At or under this (HP x 10) a unit is healed, to [`HEAL_TO`].
const HEAL_AT: u8 = 30;
const HEAL_TO: u8 = 60;

fn bit(core: &Core, i: u32) -> bool {
    core.raw_read_8(MOVE_BITS + i / 8, -1) & (1 << (i % 8)) != 0
}

fn set_bit(core: &mut Core, i: u32) {
    let b = core.raw_read_8(MOVE_BITS + i / 8, -1);
    core.raw_write_8(MOVE_BITS + i / 8, -1, b | 1 << (i % 8));
}

fn clear(core: &mut Core) {
    for k in 0..MOVE_BYTES {
        if core.raw_read_8(MOVE_BITS + k, -1) != 0 {
            core.raw_write_8(MOVE_BITS + k, -1, 0);
        }
    }
    for at in [ARMY, PHASE] {
        if core.raw_read_8(at, -1) != 0 {
            core.raw_write_8(at, -1, 0);
        }
    }
}

/// The Tag Power's second half has begun for `army` (crate::tag): if the
/// pair is Sturm and Crumb, the rule waits for the second Super Power.
pub fn tag_second_half(core: &mut Core, army: u32) {
    if !is_on(core) || !(1..=5).contains(&army) {
        return;
    }
    clear(core);
    let a = crate::tag::army_co_of(core, army);
    let Some(b) = crate::tag::partner(core, army) else { return };
    if (a == STURM && b == CRUMB) || (a == CRUMB && b == STURM) {
        core.raw_write_8(ARMY, -1, army as u8);
        core.raw_write_8(PHASE, -1, 1);
    }
}

fn unit_alive(core: &Core, u: u32) -> bool {
    core.raw_read_8(u, -1) != 0 && core.raw_read_8(u + 1, -1) & 0x08 == 0
}

/// Every frame: the second Super Power is over, so every unit of the army
/// at 3 HP or below heals to 6 and gets one move more; when the turn ends
/// the extra moves go.
pub fn tick(core: &mut Core, on: bool) {
    if !on {
        return;
    }
    install(core);
    let army = core.raw_read_8(ARMY, -1) as u32;
    let phase = core.raw_read_8(PHASE, -1);
    if army == 0 || phase == 0 {
        return;
    }
    if core.raw_read_16(CURRENT_ARMY, -1) as u32 != army {
        clear(core);
        return;
    }
    let p = core.raw_read_32(PLAYERS_POINTER, -1) + PLAYER * army;
    if phase == 1 && crate::tag::phase(core, army) == 2 && core.raw_read_8(p + 0x1E, -1) == 2 {
        let units = core.raw_read_32(UNITS_POINTER, -1);
        for i in 1..SLOTS {
            let u = units + UNIT * i;
            if crate::five::army_of_index(core, i) != army || !unit_alive(core, u) {
                continue;
            }
            let hp = core.raw_read_8(u + 4, -1);
            if hp & 0x7F <= HEAL_AT {
                core.raw_write_8(u + 4, -1, (hp & 0x80) | HEAL_TO);
                set_bit(core, i);
            }
        }
        core.raw_write_8(PHASE, -1, 2);
    }
}

/// `GetUnitMovementWithCoBonus(army r5, type r6)` at its return (r4 the move;
/// called from crate::co_skills's trap there: one trap an address): the unit
/// being selected, if it was healed by the Tag Power, gets one more.
pub fn move_bonus(core: &mut Core) {
    if !is_on(core) || core.raw_read_8(PHASE, -1) == 0 {
        return;
    }
    let cpu = core.gba().cpu();
    let (army, t) = (cpu.gpr(5) as u32, cpu.gpr(6) as u8);
    if army != core.raw_read_8(ARMY, -1) as u32 {
        return;
    }
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let sel = core.raw_read_32(SELECTED_UNIT, -1);
    let i = sel.wrapping_sub(units) / UNIT;
    if sel < units || i == 0 || i >= SLOTS || !bit(core, i) || core.raw_read_8(sel, -1) != t {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    let r4 = cpu.gpr(4);
    cpu.set_gpr(4, r4 + 1);
}

/// RAM: the power being paid for (1 CO Power, 2 Super Power), for the quote
/// the power's script shows next.
const POWER_MODE: u32 = crate::tag::STATE + 0xD2;

/// `PayForPower(army, mode)`'s entry (the map menu's Power and Super, the
/// computer's choice): its script starts the quote (`sub_08039634`).
const PAY_FOR_POWER: u32 = 0x0804_438C;
fn power_paid(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let mode = core.gba().cpu().gpr(1) as u8;
    core.raw_write_8(POWER_MODE, -1, mode);
}

/// `sub_080398D0`'s pick of one of the six power quotes (r0 = rand % 6, just
/// before it is doubled into a halfword offset): his are in the order Ration
/// Run's, Gerald's Blessing's, the Tag Power's (twice over), so the quote
/// is the power's own.
const QUOTE_PICK: u32 = 0x0803_98E0;
fn quote_pick(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !is_crumb(core, army) {
        return;
    }
    let power = core.raw_read_8(POWER_MODE, -1);
    let tag = crate::tag::phase(core, army) != 0;
    let k = match power {
        1 => 0,
        2 if tag => 2,
        2 => 1,
        _ => return,
    };
    core.gba_mut().cpu_mut().set_gpr(0, k);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(PROPERTY_PASS, Box::new(property_pass)), (QUOTE_PICK, Box::new(quote_pick)), (PAY_FOR_POWER, Box::new(power_paid))]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers() {
        use crate::co_roster::{DEFENCE, FIREPOWER, MOVE, RANGE};
        // Rank and File: Infantry and Mech +10% / +10%, nothing else.
        for t in [INFANTRY, MECH] {
            assert_eq!((bonus(0, t, FIREPOWER), bonus(0, t, DEFENCE), bonus(0, t, MOVE)), (10, 10, 0));
            assert_eq!(bonus(1, t, MOVE), 1, "Ration Run: +1 move");
            assert_eq!(bonus(2, t, FIREPOWER), 40, "Gerald's Blessing: +30% on top of Rank and File");
            assert_eq!(bonus(2, t, MOVE), 0);
            assert_eq!(bonus(0, t, RANGE), 0);
        }
        for t in [3, 5, 12, 20] {
            assert_eq!((bonus(2, t, FIREPOWER), bonus(0, t, DEFENCE), bonus(1, t, MOVE)), (0, 0, 0));
        }
        assert_eq!(LUCK, [10, 10, 20]);
    }

    #[test]
    fn code() {
        let c = cop_each();
        assert!(c.len() <= 0x100, "{}", c.len());
        assert!(COP_EACH + c.len() as u32 <= SENTINEL);
        // Every `ldr r3, =` reaches its literal.
        assert_eq!(c.len() % 4, 0);
    }

    #[test]
    fn texts_exist() {
        use crate::co_new::*;
        for w in [T_NAME, T_BIO, T_D2D, T_COP, T_SCOP, T_COP_NAME, T_SCOP_NAME, T_VICTORY, T_DEFEAT] {
            assert!(text(w).is_some(), "{w}");
        }
        for q in 0..6 {
            assert!(text(T_QUOTES + q).is_some());
        }
        assert!(text(15).is_none());
    }
}
