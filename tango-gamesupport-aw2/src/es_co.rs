//! The Silver Nova Campaign's three COs, **Tabitha**, **Lili** and **Caulder**, tangoAW2's own COs 86..88 (after Crumb and the dialogue's face-only ids), with the Dual Strike pack only.
//! (They replace the Roman COs Klaus, Aurelia, Cassius, Livia and Varro; `docs/dev/silver-nova.md`.) They are built the way Crumb is ([`crate::crumb`]): the numbers are [`bonus`], called by
//! [`crate::co_roster::stat`]; luck, stars and the power texts are theirs ([`INFO`]); a power's effect on the units is a function the game calls for each unit of the army ([`each_unit`]);
//! Firestorm is a strike function ([`crate::co_powers`]) and Enigma a weather function ([`lili`]).
//!
//! Slots: ids 86, 87 and 88 are Tabitha, Lili and Caulder (the Roman Klaus, Aurelia and Cassius slots, so every CO index, War Room record, suspend save and online record stays
//! valid); ids 89 and 90 (Livia and Varro) are **retired**: their rows are still built, as copies of Lili's and Caulder's ([`canon`]), but no list offers them ([`crate::co_new::listed`]).
//!
//! | CO | Day to day | CO Power | Super CO Power |
//! |---|---|---|---|
//! | **Tabitha** 0/9 | Mega Boost: all units +18% attack and defence | none | Firestorm (9 stars): 8 HP to every unit within 2 of the best site (AW2's meteor pick, Von Bolt's animation), no stun |
//! | **Lili** 3/0 | Lullaby: all units +10% attack and defence | Enigma (3 stars): sand, snow or rain at random for two days; her units ignore weather and move 1 more | none |
//! | **Caulder** 0/4 | Hypothesis: all units +18% attack and defence, Sturm's movement (every terrain costs 1) | none | Cataclysm (4 stars): heal 5 HP, +25% attack and defence more |
//!
//! The power's own +10% firepower and +10% defence (every power gets them from the game) are inside the "+25%": Cataclysm's [`bonus`] is 18 + 25 - 10 = 33, so a unit totals +43% in the power.

use mgba::core::Core;

use crate::co_new::FIRST;
use crate::co_roster::{DEFENCE, FIREPOWER, MOVE, RANGE};

pub const TABITHA: u8 = FIRST + 14;
pub const LILI: u8 = FIRST + 15;
pub const CAULDER: u8 = FIRST + 16;
/// Retired slots (Livia 89, Varro 90): rows that copy [`LILI`] and [`CAULDER`], in no list.
pub const RETIRED_A: u8 = FIRST + 17;
pub const RETIRED_B: u8 = FIRST + 18;
/// The dialogue's Silver Nova soldier: the Black Hole trooper's face with its colours turned (a face only, no CO).
pub const LEGIONARY_FACE: u8 = FIRST + 19;
/// The three COs a list may offer.
pub const ALL: [u8; 3] = [TABITHA, LILI, CAULDER];
/// Every row this module owns (the three and the two retired): the CO table builds them all.
pub const ROWS: [u8; 5] = [TABITHA, LILI, CAULDER, RETIRED_A, RETIRED_B];

pub fn is_es(co: u8) -> bool {
    (TABITHA..=RETIRED_B).contains(&co)
}

/// A retired slot's CO is the one it copies; every other id is itself.
pub fn canon(co: u8) -> u8 {
    match co {
        RETIRED_A => LILI,
        RETIRED_B => CAULDER,
        c => c,
    }
}

/// Whether the three are in Versus' CO lists.
pub fn in_versus() -> bool {
    true
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
    /// The six power quotes the game picks from (`\r` between lines): the CO Power's, the Super Power's and the Tag Power's, then a second set in the same order
    /// (a CO without a CO Power says a Super Power line in its slots).
    pub quotes: [&'static str; 6],
    pub victory: &'static str,
    pub defeat: &'static str,
    /// The AW2 CO it takes after: its theme, its CPU profile, its place in the lists.
    pub like: u8,
    /// The Dual Strike CO whose pictures it wears if it has none of its own (a Dual Strike id).
    pub donor: u8,
    /// Stars of the CO Power and of the Super Power in all (0: the CO has none).
    pub stars: (u32, u32),
    /// Luck per power level (AW2's rows: 10 is 0..9%) and bad luck.
    pub luck: [i16; 3],
    /// Unit cost per power level as a percentage *change* (the CO table's field is added to 100).
    pub cost: [i16; 3],
}

pub const INFO: [Info; 3] = [
    Info {
        name: "Tabitha",
        bio: "Belongs to Silver Nova. Dr. Caulder's cruel, vindictive daughter. Hit: Breakfast in bed Miss: \"Stupid Weak People\"",
        d2d: "All units fight with 18% more firepower and defense.",
        cop: "Tabitha has no CO Power. She saves all her energy for her Super CO Power.",
        scop: "Deals 8 damage automatically to the most expensive group of enemies in 13 tiles. Cannot kill.",
        cop_name: "",
        scop_name: "Firestorm",
        quotes: [
            "Firestorm! Burn, you\rstupid weak people!",
            "Firestorm! Burn, you\rstupid weak people!",
            "Keep up, or get out\rof my way!",
            "Kneel, or burn. I\rreally do not mind.",
            "Kneel, or burn. I\rreally do not mind.",
            "Stupid weak people!\rWatch how it is done.",
        ],
        victory: "Mission complete. Dismissed.",
        defeat: "I do not accept this result.",
        like: 10,
        donor: 7,
        stars: (0, 9),
        luck: [10, 10, 10],
        cost: [0, 0, 0],
    },
    Info {
        name: "Lili",
        bio: "The youngest child of Dr. Caulder. Her mind is permanently shattered. Hit: Mr. Bear Miss: Broken \"toys\"",
        d2d: "All units fight with 10% more firepower and defense.",
        cop: "For two days the weather turns to sand, snow or rain at random. Her units ignore weather and move 1 more space.",
        scop: "Lili has no Super CO Power. Her one trick is the Enigma.",
        cop_name: "Enigma",
        scop_name: "",
        quotes: ["Tee hee! Let's go,\rMr. Bear!"; 6],
        victory: "Mr. Bear says we won. Yay!",
        defeat: "Oh no. Mr. Bear, they broke all the toys.",
        like: 9,
        donor: 6,
        stars: (3, 0),
        luck: [10, 10, 10],
        cost: [0, 0, 0],
    },
    Info {
        name: "Caulder",
        bio: "The head of Silver Nova. Free to do terrible experiments. Hit: Unrestricted experiments Miss: Ethics",
        d2d: "All units fight with 18% more firepower and defense. Every terrain costs just 1 move.",
        cop: "Caulder has no CO Power. He saves all his energy for his Super CO Power.",
        scop: "Restores 5 HP to all units. Firepower and defense rise by a further 25%.",
        cop_name: "",
        scop_name: "Cataclysm",
        quotes: [
            "Fascinating... Let the\rexperiment begin.",
            "Fascinating... Let the\rexperiment begin.",
            "Observe closely. This is\rwhat progress looks like.",
            "Rise, my subjects. You\rare not finished yet.",
            "Rise, my subjects. You\rare not finished yet.",
            "Fascinating... Two\rvariables, one result.",
        ],
        victory: "As predicted. Log the result.",
        defeat: "An unexpected variable.",
        like: 14,
        donor: 15,
        stars: (0, 4),
        luck: [10, 10, 10],
        cost: [0, 0, 0],
    },
];

pub fn info(co: u8) -> Option<&'static Info> {
    INFO.get(canon(co).checked_sub(TABITHA)? as usize)
}

/// The AW2 CO a Silver Nova CO takes after.
pub fn like(co: u8) -> u8 {
    info(co).map_or(1, |i| i.like)
}

pub fn name(co: u8) -> Option<&'static [u8]> {
    info(co).map(|i| i.name.as_bytes())
}

/// A text by [`crate::co_new`]'s slot (the six quotes are the CO Power's, the Super Power's and the Tag Power's, twice).
/// A CO's text as the page shows it: names, bio and quotes from the data file, this campaign's numbers in the descriptions of what the CO and the powers do.
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
        w if (T_QUOTES..T_QUOTES + 6).contains(&w) => q(i.quotes[(w - T_QUOTES) as usize]),
        T_VICTORY => q(i.victory),
        T_DEFEAT => q(i.defeat),
        _ => return None,
    })
}

// --- The numbers --------------------------------------------------------------------

/// Tabitha's and Caulder's day to day (percent attack and defence) and Caulder's extra in his Super Power (percent, with the power's own +10 inside it).
pub const TABITHA_DAY: i32 = 18;
pub const CAULDER_DAY: i32 = 18;
pub const CAULDER_SCOP_EXTRA: i32 = 25;
pub const LILI_DAY: i32 = 10;
/// The power's own +10% firepower and defence, which every power gets from the game ([`crate::co_roster::stat`]).
const POWER_OWN: i32 = 10;
/// Cataclysm's HP.
pub const CATACLYSM_HEAL: u8 = 5;

/// The CO's own firepower %, defence %, move and range for unit type `t` at power level `mode` (0 day to day, 1 CO Power, 2 Super Power), in
/// [`crate::co_roster::stat`]'s fields (what every power adds to firepower is added by the caller).
pub fn bonus(co: u8, mode: u8, _t: u8, field: usize) -> i32 {
    let m = mode.min(2);
    match (canon(co), field) {
        (TABITHA, FIREPOWER | DEFENCE) => TABITHA_DAY,
        (LILI, FIREPOWER | DEFENCE) => LILI_DAY,
        (LILI, MOVE) => (m == 1) as i32,
        (CAULDER, FIREPOWER | DEFENCE) => CAULDER_DAY + if m == 2 { CAULDER_SCOP_EXTRA - POWER_OWN } else { 0 },
        _ => {
            let _ = RANGE;
            0
        }
    }
}

/// The Tag Power's compatibility of a pair of a Silver Nova CO with a CO that `cos/tags.toml` does not list ("Every unlisted pair is 95"; Dual Strike's own default).
pub const UNLISTED_PAIR: u8 = 95;

/// Whether `co` is one of the three of the data files (the ones `cos/tags.toml` has pairs for).
pub fn has_pairs(co: u8) -> bool {
    (TABITHA..=CAULDER).contains(&co)
}

// --- Thumb code: a power's effect on each unit -----------------------------------------------

/// Free ROM in `co_new`'s data area (+0x2400, after the body pictures' pairs, before the HUD faces).
const ROM: u32 = 0x0874_2400;
const HEAL3: u32 = ROM;
/// Clone Andy's Hyper Upgrade unit effect: heal 4 HP, for free (`crate::co_new`'s presentation row).
pub const HEAL4: u32 = ROM + 0x100;
/// Cataclysm's: heal 5 HP, for free.
pub const HEAL5: u32 = ROM + 0x180;
/// Enigma's power function (weather, then AW2's usual power procedure).
pub const ENIGMA: u32 = ROM + 0x200;
const SENTINEL: u32 = ROM + 0x3FC;
const MAGIC: u32 = 0x4553_4332; // "2CSE"
/// AW2's `RepairUnit(unit, hp, pay)`, Thumb.
const REPAIR: u32 = 0x0802_9AF9;
/// The default unit effect (none).
const NOTHING: u32 = 0x0804_4531;
/// AW2's usual power procedure (the quote and the cut-in) and its weather setter (`sub_08035144(weather)`), both Thumb.
const DEFAULT_POWER: u32 = 0x0804_43D9;
const SET_WEATHER: u32 = 0x0803_5145;

/// A power's unit effect: `RepairUnit(unit, hp, 0)`, for free.
fn heal(hp: u8) -> Vec<u8> {
    let mut a = crate::crumb::Asm::new();
    a.op(0xB530); // push {r4, r5, lr}
    a.op(0x2100 | hp as u16); // movs r1, #hp
    a.op(0x2200); // movs r2, #0
    a.call(REPAIR);
    a.op(0xBC30); // pop {r4, r5}
    a.op(0xBC01); // pop {r0}
    a.op(0x4700); // bx r0
    a.finish()
}

/// Enigma: `sub_08035144(2)` (the weather the trap [`weather_pick`] replaces by the roll), then AW2's usual power procedure with the argument it was given.
fn enigma() -> Vec<u8> {
    let mut a = crate::crumb::Asm::new();
    a.op(0xB530); // push {r4, r5, lr}
    a.op(0x1C04); // adds r4, r0, #0
    a.op(0x2002); // movs r0, #2  (the weather: the trap on SET_WEATHER's entry rolls it)
    a.call(SET_WEATHER);
    a.op(0x1C20); // adds r0, r4, #0
    a.call(DEFAULT_POWER);
    a.op(0xBC30); // pop {r4, r5}
    a.op(0xBC01); // pop {r0}
    a.op(0x4700); // bx r0
    a.finish()
}

pub fn install(core: &mut Core) {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return;
    }
    core.raw_write_range(HEAL3, -1, &heal(3));
    core.raw_write_range(HEAL4, -1, &heal(4));
    core.raw_write_range(HEAL5, -1, &heal(CATACLYSM_HEAL));
    core.raw_write_range(ENIGMA, -1, &enigma());
    core.raw_write_32(SENTINEL, -1, MAGIC);
}

/// The presentation row's unit effect (a Thumb function the game calls for each unit of the army) for power 0 (CO Power) or 1 (Super Power).
pub fn each_unit(co: u8, power: u8) -> u32 {
    match (canon(co), power) {
        (CAULDER, 1) => HEAL5 | 1,
        (crate::co_new::ARIA, 1) => HEAL3 | 1,
        _ => NOTHING,
    }
}

// --- Lili's Enigma -----------------------------------------------------------------------------
//
// Enigma sets the weather to snow, rain or (with the Dual Strike features on, which every Silver Nova CO needs) a sandstorm, drawn from the game's own random number
// generator (`sandstorm::next_random`: the same on every peer and every rollback), for two days:
// - snow and rain are AW2's own power weather (`sub_08035144`), made two days long by the flag Olaf's snow uses ([`crate::ds_weather`]'s `POWER_SNOW`);
// - the sandstorm is [`crate::sandstorm`]'s one-day state, switched on by the roll and switched off again here after two of Lili's turn starts (the engine's own
//   day count only runs in Random weather, so a Rules screen with fixed weather would keep the sand for ever);
// - a map whose weather is permanent keeps it: Enigma only gives her units the immunity and the move there.
// Her units are immune while Enigma runs, both days ([`enigma_on`], [`weather_immune`]): no sandstorm range cut, no snow fuel doubling, +1 move ([`second_day_move`] on day 2) and +1 vision offsets rain's -1 ([`rain_vision`]).
// The state rides in a suspended game's tag tail ([`lili_state`]): +0 turn starts left, +1 her army, +2 the weather rolled (1 snow, 2 rain, 3 sand), +40 the army of the last tick.

/// RAM (`ram_map::REGIONS`): the state above.
pub const LILI_STATE: u32 = 0x0203_C980;
pub const LILI_BYTES: u32 = 40;
pub const LILI_LEN: u32 = LILI_BYTES + 1;
const LILI_TURN: u32 = LILI_STATE + LILI_BYTES;
const CURRENT_ARMY: u32 = 0x0300_33EC;
/// gPlaySt's weather mode: 2 is permanent weather.
const WEATHER_MODE: u32 = 0x0300_3FED;
pub const SNOW: u8 = 1;
pub const RAIN: u8 = 2;
pub const SAND: u8 = 3;

/// Whether Lili's Enigma is running for the army: from the activation through her second turn start after it, as long as the weather it drew
/// (the state [`LILI_STATE`]: turn starts left, her army). Her CO Power itself ends at her next turn start; the immunity, the +1 move and the vision
/// last the two days.
pub fn enigma_on(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army)
        && core.raw_read_8(LILI_STATE, -1) != 0
        && core.raw_read_8(LILI_STATE + 1, -1) as u32 == army
        && canon(crate::co_roster::army_co(core, army).0) == LILI
}

/// Whether the army's units ignore weather: Lili in Enigma's two days, or in her CO Power on a map where the weather is permanent (no state starts there).
pub fn weather_immune(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army)
        && crate::co_roster::abilities_enabled(core)
        && (enigma_on(core, army) || crate::co_roster::army_co(core, army) == (LILI, 1))
}

/// Her units' extra move while Enigma runs on its second day, when the CO Power (mode 1) is over and the CO table gives day-to-day numbers: +1 for
/// every unit (the table's own +1 covers the first day). (the table call names no army: Enigma's own army is taken).
pub fn second_day_move(core: &Core) -> i32 {
    let army = core.raw_read_8(LILI_STATE + 1, -1) as u32;
    (enigma_on(core, army) && crate::co_roster::army_co(core, army) == (LILI, 0)) as i32
}

/// The vision Lili's units regain in rain while Enigma runs (rain takes 1 off): +1.
pub fn rain_vision(core: &Core, army: u32) -> i32 {
    (enigma_on(core, army) && core.raw_read_8(crate::ds_weather::WEATHER, -1) == RAIN) as i32
}

/// The weather Enigma draws: snow, rain or sand (without the sandstorm, only snow or rain).
pub fn roll(r: u32, sand: bool) -> u8 {
    let n = if sand { 3 } else { 2 };
    1 + (r % n) as u8
}

/// The trap on `sub_08035144`'s entry (r0 the weather): while Lili's CO Power is being paid, the weather is the roll. Returns the weather it chose.
pub fn weather_pick(core: &mut Core) -> Option<u8> {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !(1..=5).contains(&army) || crate::co_powers::activating(core, army) != (LILI, 1) {
        return None;
    }
    if core.raw_read_8(WEATHER_MODE, -1) == 2 {
        // permanent weather: nothing changes (r0 stays what the game has)
        let w = core.raw_read_8(crate::ds_weather::WEATHER, -1);
        core.gba_mut().cpu_mut().set_gpr(0, w as i32);
        return None;
    }
    let weather = roll(crate::sandstorm::next_random(core), true);
    core.raw_write_8(LILI_STATE, -1, 2);
    core.raw_write_8(LILI_STATE + 1, -1, army as u8);
    core.raw_write_8(LILI_STATE + 2, -1, weather);
    if weather == SAND {
        crate::sandstorm::start_power_sand(core);
    }
    // (sand is clear weather to the game: the sandstorm is [`crate::sandstorm`]'s own state)
    let arg = if weather == SAND { 0 } else { weather as i32 };
    core.gba_mut().cpu_mut().set_gpr(0, arg);
    Some(weather)
}

/// The weather Enigma rolled and has running (0 none).
pub fn rolled(core: &Core) -> u8 {
    if core.raw_read_8(LILI_STATE, -1) != 0 {
        core.raw_read_8(LILI_STATE + 2, -1)
    } else {
        0
    }
}

fn end_enigma(core: &mut Core) {
    if core.raw_read_8(LILI_STATE + 2, -1) == SAND {
        crate::sandstorm::end_power_sand(core);
    }
    for k in 0..LILI_BYTES {
        if core.raw_read_8(LILI_STATE + k, -1) != 0 {
            core.raw_write_8(LILI_STATE + k, -1, 0);
        }
    }
}

/// A map starts: no Enigma carries over.
pub fn map_start(core: &mut Core) {
    for k in 0..=LILI_BYTES {
        if core.raw_read_8(LILI_STATE + k, -1) != 0 {
            core.raw_write_8(LILI_STATE + k, -1, 0);
        }
    }
}

/// Every frame: when the turn passes to Lili's army, one of the two days is over; after the second the sandstorm stops.
fn lili_tick(core: &mut Core) {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u8;
    if core.raw_read_8(LILI_TURN, -1) == army {
        return;
    }
    core.raw_write_8(LILI_TURN, -1, army);
    let left = core.raw_read_8(LILI_STATE, -1);
    if left == 0 || army != core.raw_read_8(LILI_STATE + 1, -1) {
        return;
    }
    if left <= 1 {
        end_enigma(core);
    } else {
        core.raw_write_8(LILI_STATE, -1, left - 1);
    }
}

/// The state and the army whose turn it was, for a suspended game ([`crate::suspend`]): [`LILI_LEN`] bytes.
pub fn lili_state(core: &Core) -> Vec<u8> {
    let mut b = vec![0u8; LILI_LEN as usize];
    core.raw_read_range(LILI_STATE, -1, &mut b);
    b
}

/// Whether an Enigma is running (a suspended game then carries the state).
pub fn lili_any(core: &Core) -> bool {
    core.raw_read_8(LILI_STATE, -1) != 0
}

/// The state of a suspended game, put back after Continue.
pub fn set_lili_state(core: &mut Core, b: &[u8]) {
    if b.len() == LILI_LEN as usize {
        core.raw_write_range(LILI_STATE, -1, b);
        // Snow and rain run on the game's own weather days, whose second-day flag ([`crate::ds_weather`]'s power snow) is not in the save: it follows from the turn starts left
        // (2: the first day is not over yet, 1: it is and the second runs). Without it a continued game lost the weather a day early.
        if b[0] != 0 && (b[2] == SNOW || b[2] == RAIN) {
            core.raw_write_8(crate::ram_map::POWER_SNOW.0, -1, (b[0] >= 2) as u8);
        }
    }
}

/// gPlaySt's default weather: what a fixed-weather game (the Rules screen's, mode 3) has when no power weather is on.
const DEFAULT_WEATHER: u32 = 0x0300_3FEF;
/// `sub_08035170`'s return (the weather of the next turn in r4, drawn at each turn's end), as [`crate::sandstorm`] knows it.
const NEXT_WEATHER_DONE: u32 = 0x0803_51E8;

/// The army whose turn follows `army`'s (the next one in the game).
fn next_army(core: &Core, army: u32) -> u32 {
    (1..=5u32).map(|k| (army + k - 1) % 5 + 1).find(|&a| a != army && crate::co_roster::in_game(core, a)).unwrap_or(army)
}

/// The turn end that comes just before her last turn start of Enigma, in a game whose Rules weather is fixed to snow or rain: a sandstorm is clear weather to the game, and AW2 brings the
/// Rules' weather back only from snow or rain (its draw of a clear day in a fixed game is clear again), so the end of Enigma's sand puts it back here: the next turn's weather is the
/// Rules' own, which AW2 then starts as any weather change (the fade, the colours).
fn next_weather(core: &mut Core) {
    if !crate::ds_weather::is_on(core) {
        return;
    }
    if core.raw_read_8(LILI_STATE, -1) != 1 || core.raw_read_8(LILI_STATE + 2, -1) != SAND || core.raw_read_8(WEATHER_MODE, -1) != 3 {
        return;
    }
    let default = core.raw_read_8(DEFAULT_WEATHER, -1);
    if default == 0 || core.gba().cpu().gpr(4) != 0 {
        return;
    }
    let (now, hers) = (core.raw_read_16(CURRENT_ARMY, -1) as u32, core.raw_read_8(LILI_STATE + 1, -1) as u32);
    if now != hers && next_army(core, now) == hers {
        core.gba_mut().cpu_mut().set_gpr(4, default as i32);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(NEXT_WEATHER_DONE, Box::new(next_weather))]
}

/// Every frame with the pack: the code is in ROM.
pub fn tick(core: &mut Core, on: bool) {
    if on {
        install(core);
        lili_tick(core);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn all_types() -> impl Iterator<Item = u8> {
        1..=27u8
    }

    #[test]
    fn tabitha_and_caulder_are_flat_and_stay_under_kanbei() {
        for t in all_types() {
            for m in 0..3u8 {
                assert_eq!(bonus(TABITHA, m, t, FIREPOWER), 18);
                assert_eq!(bonus(TABITHA, m, t, DEFENCE), 18);
                assert_eq!(bonus(TABITHA, m, t, MOVE), 0);
            }
            assert_eq!([0u8, 2].map(|m| bonus(CAULDER, m, t, FIREPOWER)), [18, 33]);
            assert_eq!([0u8, 2].map(|m| bonus(CAULDER, m, t, DEFENCE)), [18, 33]);
            assert_eq!(bonus(CAULDER, 2, t, MOVE), 0);
        }
        // aw2dev co check: day to day <= 40, Super Power <= 120 points of firepower plus defence (the power's own 10 + 10 included)
        assert!(2 * 18 <= 40 && 2 * (33 + 10) <= 120);
    }

    #[test]
    fn lili_is_a_small_edge_and_one_more_move_in_enigma() {
        for t in all_types() {
            assert_eq!([0u8, 1, 2].map(|m| bonus(LILI, m, t, FIREPOWER)), [10; 3]);
            assert_eq!([0u8, 1].map(|m| bonus(LILI, m, t, MOVE)), [0, 1]);
        }
    }

    #[test]
    fn the_retired_slots_copy_lili_and_caulder() {
        assert_eq!((canon(89), canon(90), canon(86)), (LILI, CAULDER, TABITHA));
        assert_eq!(bonus(RETIRED_B, 2, 5, FIREPOWER), bonus(CAULDER, 2, 5, FIREPOWER));
        assert!(info(RETIRED_A).unwrap().name == "Lili" && !ALL.contains(&RETIRED_A));
        assert!(is_es(RETIRED_B) && !is_es(LEGIONARY_FACE) && !has_pairs(RETIRED_A));
    }

    #[test]
    fn enigma_draws_three_weathers_or_two_without_sand() {
        let w: Vec<u8> = (0..6).map(|r| roll(r, true)).collect();
        assert_eq!(w, [1, 2, 3, 1, 2, 3]);
        assert!((0..12).all(|r| roll(r, false) <= 2));
    }

    #[test]
    fn pairs_belong_to_the_three() {
        assert!(has_pairs(TABITHA) && has_pairs(CAULDER) && !has_pairs(crate::co_new::CRUMB));
        assert_eq!(UNLISTED_PAIR, 95);
    }

    #[test]
    fn stars_match_the_design() {
        assert_eq!(INFO[0].stars, (0, 9));
        assert_eq!(INFO[1].stars, (3, 0));
        assert_eq!(INFO[2].stars, (0, 4));
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
        assert!(text(TABITHA, 15).is_none());
        let c = heal(3);
        assert!(c.len() <= 0x100 && c.len() % 4 == 0);
        assert_eq!(heal(5)[2], 5, "movs r1, #5");
        assert!(enigma().len() <= 0x100);
        assert!(!is_es(crate::co_new::CRUMB) && is_es(TABITHA) && is_es(RETIRED_B) && !is_es(LEGIONARY_FACE));
    }
}
