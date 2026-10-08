//! The campaign model: a campaign as tangoAW2's campaign engine
//! ([`crate::ds_campaign`]) plays it, whatever it came from.
//!
//! A **source** loads a campaign into a [`Model`]: its missions compiled
//! for AW2 (map headers, maps, deployments, AW2 event scripts and trigger
//! lists, texts, magic stubs: [`Built`]), its play order, side missions and
//! last mission, its story (prologue, scenes after wins), its staff roll,
//! and its rules (the magic functions its scripts call, [`Source::rules`]).
//! The engine knows nothing of where a campaign came from: it reads the
//! model. [`SOURCES`] lists the sources; the Campaign sub-menu
//! ([`crate::campaign_menu`]) shows AW2's own campaign, then one entry per
//! source whose campaign is there (any number: two are shown at a time).
//!
//! Today's only source is Dual Strike's ([`crate::ds_campaign_data`], with
//! its world map [`crate::ds_worldmap`], story pictures
//! [`crate::ds_story_art`], staff roll [`crate::ds_credits`] and songs
//! [`crate::ds_music`]): it reads the player's own Dual Strike ROM (the
//! pack). Another campaign (a custom one) is a source that fills a
//! [`Model`] the same way: its missions as [`MissionInfo`] and map
//! headers, its scripts in AW2's event format (laid out with [`Built::add`]
//! and [`Built::add_magic`]), its order; its rules are its own (or none).

use std::collections::BTreeMap;

use mgba::core::Core;

/// The most missions a campaign has (the progress keeps one bit each).
pub const MAX_MISSIONS: usize = 32;

/// The AW2 map id a DS mission is played on: its header is written into
/// the map table's entry for it when the mission starts (tangoAW2's map
/// table with room for 0x100 ids, [`crate::survival::TABLE`]; Survival
/// uses 0xC9..0xEF, the Colonel's Vault 0xF1).
pub const MAP_ID: u8 = 0xF0;

/// A campaign as the engine plays it.
pub struct Model {
    /// The Campaign sub-menu's label (the chooser's 5x10 letters).
    pub label: &'static str,
    /// Its missions compiled for AW2.
    pub built: Built,
    /// How many missions (indices 0..missions; at most [`MAX_MISSIONS`]).
    pub missions: usize,
    /// The story missions in play order, the side missions among them, each
    /// with the campaign flag that opens it (played when set, skipped
    /// otherwise), and the last mission (its win is the campaign's end).
    pub order: Vec<u8>,
    pub side_missions: Vec<(u8, u32)>,
    pub final_mission: u8,
    /// The staff roll after the last mission's scenes (crate::ds_credits).
    pub credits: Option<crate::ds_credits::Credits>,
    /// Pictures the story's narration shows (crate::ds_story_art), by the
    /// number its scripts' picture flow carries.
    pub pictures: Vec<Option<crate::ds_story_art::Picture>>,
    /// Its rules.
    pub source: &'static Source,
    /// A data-defined campaign's extras ([`crate::custom_campaign`]); None
    /// for Dual Strike's, which is converted from the pack.
    pub custom: Option<Custom>,
}

/// What a custom (data-defined) campaign adds to the model.
pub struct Custom {
    /// Each mission's flag on AW2's own world map: place, marker style,
    /// difficulty stars (LEVEL), by mission index.
    pub points: Vec<MapPoint>,
    /// Which missions must be won before each opens (by mission index).
    pub requires: Vec<Requires>,
    /// The COs the player can use, in unlock order: (AW2 CO id, open at
    /// the start). Bit k of the record's unlock mask is entry k.
    pub roster: Vec<(u8, bool)>,
    /// Per mission: the roster entries (indexes) a win unlocks.
    pub recruits: Vec<Vec<u8>>,
    /// Per mission: the COs the player may pick from (AW2 ids; the
    /// unlocked ones among them are offered). Empty: the whole roster.
    pub pools: Vec<Vec<u8>>,
    /// The hidden bonds: each names the CO whose page shows its quote once
    /// earned, and the quote's address (the CO page's bio is replaced).
    pub bonds: Vec<(u8, u32)>,
    /// Per mission: the battle's song (an AW2 song id) in place of the COs'
    /// themes.
    pub music: Vec<Option<u16>>,
    /// The recruit missions (mission, bond): the world-map panel shows the
    /// bond badge once the bond is earned ([`crate::bond_ui`]).
    pub marks: Vec<(u8, u8)>,
    /// Per mission: a reversed Black Onyx.
    pub onyx: Vec<Option<OnyxDef>>,
    /// Per mission: a volcano hazard.
    pub volcano: Vec<Option<VolcanoDef>>,
    /// The secret mission (index): its win shows the staff roll's secret
    /// sections.
    pub secret: Option<u8>,
}

/// The Black Onyx turned round: Black Hole's own satellite on a day cycle
/// ([`crate::onyx`], "reversed"): it fires on Black Hole's turn every
/// `period` days from day `first`, at the spot the computer scores best for
/// Black Hole; a silo with a foot soldier of another team on it launches at
/// it once; `hits` hits destroy it, and its fall hurts the fortress.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OnyxDef {
    /// Hits that destroy it.
    pub hits: u8,
    /// The first day it fires, and the days between shots.
    pub first: u8,
    pub period: u8,
    /// The Black Obelisk's top-left cell (3x3): the fortress's centre.
    pub obelisk: (u8, u8),
    /// When it is destroyed: every Black Hole unit within this many cells of
    /// the Obelisk loses `debris_hp` HP (never below 1) ...
    pub radius: u8,
    pub debris_hp: u8,
    /// ... the Obelisk heals nothing for this many Black Hole turns ...
    pub offline_turns: u8,
    /// ... and the player's COs lose this share (%) of their full meters.
    pub meters: u8,
}

/// A volcano's eruptions as a neutral hazard ([`crate::hazard`]): from day
/// `first`, every `interval` days, on the Black Hole turn, every unit of any
/// army on one of `cells` loses `damage` HP (AW2's own eruption: the queued
/// impacts; the Volcano structure of the map runs the turn-start loop), the
/// cells marked from the day before.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VolcanoDef {
    pub first: u8,
    pub interval: u8,
    pub damage: u8,
    pub cells: Vec<(u8, u8)>,
}

impl VolcanoDef {
    pub fn new(first: u8, interval: u8, damage: u8, cells: &[(u8, u8)]) -> VolcanoDef {
        VolcanoDef { first, interval, damage, cells: cells.to_vec() }
    }

    /// Day `day` is an eruption's.
    pub fn erupts(&self, day: u16) -> bool {
        day >= self.first as u16 && self.interval > 0 && (day - self.first as u16) % self.interval as u16 == 0
    }
}

impl OnyxDef {
    /// The design's numbers: 4 hits, day 5 and every 5th day, 4 cells, 3 HP,
    /// 3 turns, 30%.
    pub const fn new(obelisk: (u8, u8)) -> OnyxDef {
        OnyxDef { hits: 4, first: 5, period: 5, obelisk, radius: 4, debris_hp: 3, offline_turns: 3, meters: 30 }
    }
}

/// A mission's flag on AW2's world map (map pixels).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MapPoint {
    pub x: i16,
    pub y: i16,
    /// AW2's marker style (0 plain, 4 a lab's, 8 the last).
    pub style: u8,
    /// The stars beside LEVEL.
    pub stars: u8,
}

/// When a mission opens on the world map.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Requires {
    /// Open from the start.
    Start,
    /// Opens once all of these missions are won.
    All(Vec<u8>),
    /// Opens once any of these missions is won (a branch).
    Any(Vec<u8>),
    /// Opens once all of these are won and every bond is earned (a secret
    /// mission, [`crate::custom_campaign::Bond`]).
    Bonds(Vec<u8>),
}

/// Which art the campaign's world map is drawn on.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorldArt {
    /// Dual Strike's Omega Land (converted from the pack).
    OmegaLand,
    /// AW2's own Wars World map.
    Aw2,
}

/// Where campaigns come from.
pub struct Source {
    /// The Campaign sub-menu's label.
    pub label: &'static str,
    /// Its campaign is there (Dual Strike's: the pack).
    pub available: fn(&Core) -> bool,
    /// Loads it (once: the engine keeps it).
    pub load: fn(&Core) -> Option<Model>,
    /// Runs a magic function of its own (a predicate's answer, a call's
    /// result); [`TAIL_CALLED`] when it has jumped to game code itself.
    pub rules: fn(&mut Core, &Magic) -> u32,
    /// The Flash slot of its record, and of a mission saved halfway (the
    /// layout is in docs/AW2.md "Saves").
    pub save_slot: u8,
    pub mid_slot: u8,
    /// The record's first word ("AWDC" is the DS Campaign's).
    pub progress_magic: u32,
    pub art: WorldArt,
    /// It has a Hard Campaign (Normal / Hard on New).
    pub has_hard: bool,
}

/// A rule that jumped to game code itself (the caller returns nothing).
pub const TAIL_CALLED: u32 = u32::MAX;

/// The sources, in the sub-menu's order (after AW2's own campaign).
pub static SOURCES: [Source; 2] = [
    Source {
        label: "DS CAMPAIGN",
        available: crate::ds_weather::is_on,
        load: crate::ds_campaign_data::load,
        rules: crate::ds_campaign_rules::run,
        save_slot: 15,
        mid_slot: 14,
        progress_magic: 0x4344_5741, // "AWDC"
        art: WorldArt::OmegaLand,
        has_hard: true,
    },
    Source {
        label: "BH CAMPAIGN",
        available: crate::ds_weather::is_on,
        load: crate::bh_campaign::load,
        rules: crate::custom_campaign::rules,
        save_slot: 13,
        mid_slot: 12,
        progress_magic: 0x4342_5741, // "AWBC"
        art: WorldArt::Aw2,
        has_hard: false,
    },
];

/// What a magic function stands for: Rust runs it ([`crate::ds_campaign`]'s
/// own flow, else the campaign's source's rules, [`Source::rules`]). The
/// source's variants carry the source's own keys (Dual Strike's: the
/// addresses of its predicates and functions).
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Magic {
    /// A Dual Strike predicate (`u8 f(void)`), by its address.
    Predicate(u32),
    /// Script op 0x4E: army's (CO, tag CO) is (a, b) (AW2 ids; 0xFF any).
    CoPair { army: u8, a: u8, b: u8 },
    /// A Dual Strike function called by a script (op 0x00/0x52/0x55/0x57).
    Call(u32, u32),
    /// Op 0x5A: a real-time countdown (frames); 0x5B clears it.
    Countdown(u32),
    /// Op 0x41/0x43/0x44: an army's units shown or hidden (Dual Strike's
    /// flag 0x80 on every unit of the army).
    ArmyFlag { op: u8, army: u8 },
    /// A Dual Strike op AW2 has nothing for (kept for the documentation).
    Unhandled(u8),
    /// The DS Campaign's own flow (crate::ds_campaign): its id.
    Flow(u8),
}

/// A campaign's story outside its battles, as AW2 event scripts (their
/// addresses): the prologue before the first mission, and scenes played on
/// the world map after a mission's win.
#[derive(Clone, Debug, Default)]
pub struct Story {
    pub prologue: u32,
    /// (mission index, script) to play on the world map after its win.
    pub after_win: Vec<(usize, u32)>,
}

#[derive(Clone, Debug)]
pub struct Built {
    pub story: Story,
    /// The ROM blob, to be written at [`Built::base`].
    pub blob: Vec<u8>,
    pub base: u32,
    /// AW2 text ids and their strings' addresses (in the blob).
    pub texts: Vec<(u16, u32)>,
    /// Map headers (0x5C bytes) by record index (missions, then fronts).
    pub headers: Vec<(u8, [u8; 0x5C])>,
    /// Magic functions by id (the stub's r3).
    pub magic: Vec<Magic>,
    /// Stubs: id -> address of its Thumb stub.
    pub stubs: Vec<u32>,
    pub missions: Vec<MissionInfo>,
    /// Dual Strike script ops seen and not converted, with counts.
    pub unhandled: BTreeMap<u8, u32>,
}

impl Built {
    /// Appends a magic function's stub to the blob; its Thumb address.
    pub fn add_magic(&mut self, m: Magic) -> u32 {
        while self.blob.len() % 4 != 0 {
            self.blob.push(0);
        }
        let id = self.magic.len() as u32;
        self.magic.push(m);
        let at = self.base + self.blob.len() as u32;
        self.blob.extend_from_slice(&stub(id));
        self.stubs.push(at);
        at | 1
    }

    /// Appends bytes (word-aligned); their address.
    pub fn add(&mut self, b: &[u8]) -> u32 {
        while self.blob.len() % 4 != 0 {
            self.blob.push(0);
        }
        let at = self.base + self.blob.len() as u32;
        self.blob.extend_from_slice(b);
        at
    }
}

/// A battle on two fronts: the description [`crate::two_front`] plays (Dual
/// Strike's dual-screen battles; docs/AW2.md "Two fronts"). The battle's
/// own [`MissionInfo`] and map header are its main front's; this names the
/// second front's and its rules. Nothing here is Dual Strike's: a custom
/// campaign's mission (or, later, a Versus map) describes its fronts the
/// same way.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TwoFront {
    /// The second front: its map header (an index of [`Built::headers`]:
    /// its map, deployment, structure picture, event lists, COs, colours,
    /// teams; no day limit) and its [`MissionInfo`] (an index of
    /// [`Built::missions`]: look, weather, fog, armies).
    pub second: u8,
    /// Each army's CO on the second front (AW2 CO ids; [`PICK`]: the player
    /// picks it on the CO screen, after the main front's picks).
    pub cos: [u8; 4],
    /// Who gives each army's orders on the second front (army slots 1..4):
    /// [`FrontControl`]. The engine decides a second-front turn by the
    /// army's own controller (AW2's per-army controller byte), never by
    /// "the player": any number of armies may be human, local or a netplay
    /// peer's.
    pub control: [FrontControl; 4],
    /// What the main front may send to the second ([`SendRule`]).
    pub send: SendRule,
    /// Whether CO powers may be used on the second front.
    pub powers: bool,
    /// The second front is in the sky (drawn as clouds with its structure
    /// in the sky, crate::sky_front; clear weather).
    pub sky: bool,
    /// Intel > General (Dual Strike's ally posture, crate::ally_posture):
    /// an army's owner sets, on its main-front turns, how the computer
    /// directs the army on the second front (Strike, Assault, General,
    /// Defense), shown while the computer directs it there (or with Auto
    /// CO's item, on or off).
    pub posture: bool,
}

/// The second front's CO is the player's pick ([`TwoFront::cos`]).
pub const PICK: u8 = 0xFE;

/// Who directs an army on the second front. The army's **owner** is
/// whoever controls it on the main front (its controller byte there: 1 a
/// human, local or a netplay peer by its seat; 2 the computer).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FrontControl {
    /// The computer, always (Dual Strike's campaign before Lightning
    /// Strikes: "In Campaign mode, the second front is controlled
    /// automatically").
    Cpu,
    /// Its owner, always: a human owner plays its second-front turns (a
    /// Versus map's armies, where each seat commands its army on both
    /// fronts).
    Owner,
    /// Its owner chooses: Intel > Auto CO on, the computer plays the
    /// army's second-front turns; off, its owner does (Dual Strike's
    /// Lightning Strikes and Ring of Fire: "open Intel on the menu, and
    /// find Auto CO. Touch Auto CO to turn it on or off"). `on`: Auto CO at
    /// the battle's start (Dual Strike's: on). The owner may change it on
    /// its own main-front turns; it takes effect at the next second-front
    /// round. A computer owner's army is the computer's either way.
    AutoCo { on: bool },
}

/// Which units the main front may send to the second (the unit's Send
/// command), and where they arrive.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SendRule {
    /// No sending.
    None,
    /// A front in the sky: Fighters, Bombers, Stealths and Black Bombs from
    /// anywhere ("You won't be able to send helicopters, because they can't
    /// fly high enough"); they arrive by the army's own units there.
    Air,
    /// Both fronts on the ground: any unit standing on its army's HQ or a
    /// base, airport or port ("units can be sent to the second front from
    /// bases that build units. Oh, and from the HQ, too"); they arrive
    /// around the army's HQ there, naval units in the waters near it.
    Ground,
}

#[derive(Clone, Debug)]
pub struct MissionInfo {
    pub index: usize,
    pub name: String,
    /// The world map's mission panel text: the mission's objective (the
    /// first text of its objective script), two lines.
    pub info_text: u16,
    /// A battle on two fronts ([`TwoFront`], crate::two_front): its second
    /// front's description. None for an ordinary one-front battle.
    pub two_front: Option<TwoFront>,
    pub number: u8,
    pub cos: [(u8, u8); 4],
    pub colours: [u8; 4],
    pub teams: [u8; 4],
    pub armies: u8,
    pub pool: Vec<u8>,
    pub day_limit: u16,
    pub width: u8,
    pub height: u8,
    pub look: u8,
    pub weather: u8,
    pub fog: bool,
    /// Dual Strike's research labs on the map (its Lab tiles, 0x1D9..0x1DD;
    /// its Com Towers 0x1B9..0x1BD become the same AW2 tiles).
    pub labs: Vec<(u8, u8)>,
    /// A trigger list the mission's rules run every frame the battle's
    /// clock runs (AW2's format, its address; 0: none): Dual Strike's
    /// real-time list, Crystal Calamity's Black Onyx (crate::onyx).
    pub realtime: u32,
    /// The header's fifth list (AW2's format, its address; 0: none), which
    /// Dual Strike runs with an argument from the game's own code: Crystal
    /// Calamity's CPU Launch (crate::onyx).
    pub unit_event_list: u32,
    /// A custom campaign's mission ([`crate::custom_campaign`]): its COs
    /// as AW2 ids. None for Dual Strike's, whose `cos` are its own ids.
    pub native: Option<Native>,
}

/// A custom mission's COs in AW2 ids (`MissionInfo::cos` keeps 0x1C for an
/// army the player picks, so the engine's tests of it still hold).
#[derive(Clone, Debug, Default)]
pub struct Native {
    /// (CO, tag CO) per army slot: AW2 ids, [`NO_CO`] none. An army the
    /// player picks for reads [`NO_CO`] here and 0x1C in `cos`.
    pub cos: [(u8, u8); 4],
    /// The mission's own pool for the player's pick (AW2 ids; empty: the
    /// campaign's roster).
    pub pool: Vec<u8>,
    /// Starting funds per army (None: as the map).
    pub funds: [Option<u32>; 4],
    /// A five-army mission ([`crate::five`]): the player is army 5, Black
    /// Hole, the fifth army the patched game has (armies 1..4 are the header's
    /// four); its CO, its partner (NO_CO none) and its team (0xFF: its own).
    pub five: Option<(u8, u8, u8)>,
    /// The Setup phase (scout the map, then Deploy) before day 1 when the
    /// player picks a CO ([`crate::setup_phase`]).
    pub setup: bool,
}

/// "No CO" in [`Native::cos`].
pub const NO_CO: u8 = 0xFF;

/// The landing every magic stub jumps to: dead code in `sub_0803CC3C`
/// (no callers; [`crate::five_map`] made its start a helper), trapped by
/// [`crate::ds_campaign`]. r3 = the magic id, lr = the caller's return.
pub const LANDING: u32 = 0x0803_CC5E;

pub fn stub(id: u32) -> [u8; 16] {
    let mut s = [0u8; 16];
    let h: [u16; 4] = [
        0x4B01, // ldr r3, [pc, #4] (id)
        0x4A02, // ldr r2, [pc, #8] (landing)
        0x4710, // bx r2
        0x46C0, // nop
    ];
    for (k, v) in h.iter().enumerate() {
        s[2 * k..2 * k + 2].copy_from_slice(&v.to_le_bytes());
    }
    s[8..12].copy_from_slice(&id.to_le_bytes());
    s[12..16].copy_from_slice(&(LANDING | 1).to_le_bytes());
    s
}

/// AW2 text ids for the campaign's strings: read from the text table's
/// free tail (`0x08610A38 + 4 * id`, free ROM from 0x0862DA38; ids are
/// read signed, so at most 0x7FFF).
pub const TEXT_FIRST: u16 = 0x7400;
pub const TEXT_LAST: u16 = 0x7FFF;
pub const TEXT_TABLE: u32 = 0x0861_0A38;

