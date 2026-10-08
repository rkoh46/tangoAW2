//! Custom campaigns: a campaign described as data, played by the DS
//! Campaign's engine ([`crate::ds_campaign`]) through the campaign model
//! ([`crate::campaign_model`]). The BH Campaign ([`crate::bh_campaign`]) is
//! the first; a sequel is another [`CampaignDef`] and another entry of
//! [`crate::campaign_model::SOURCES`].
//!
//! A [`CampaignDef`] holds the campaign's roster (the COs the player can
//! use and when each is unlocked), its prologue and staff roll, and its
//! [`MissionDef`]s. [`compile`] turns it into a `Model`: per mission a map
//! header, the map, the deployment, AW2 event scripts and trigger lists,
//! texts and the world map point. Nothing here is Dual Strike's or AW2's
//! art or text: a mission may *name* a map of AW2's or of the player's
//! Dual Strike ROM (read at run time), or give its own tiles.
//!
//! How to add a mission is in docs/AW2.md "BH Campaign".

use std::collections::HashMap;
use std::sync::OnceLock;

use mgba::core::Core;

use crate::campaign_model::*;
use crate::ds_campaign_data::{cmd, wrap_dialogue, Ds};

// --- Ids -----------------------------------------------------------------------

/// AW2 CO ids (tangoAW2's: AW2's 0..18, Dual Strike's new ones from 72).
pub mod co {
    pub const NELL: u8 = 0;
    pub const ANDY: u8 = 1;
    pub const MAX: u8 = 2;
    pub const OLAF: u8 = 3;
    pub const SAMI: u8 = 4;
    pub const GRIT: u8 = 5;
    pub const KANBEI: u8 = 6;
    pub const SONJA: u8 = 7;
    pub const EAGLE: u8 = 8;
    pub const DRAKE: u8 = 9;
    pub const STURM: u8 = 10;
    pub const FLAK: u8 = 11;
    pub const LASH: u8 = 12;
    pub const ADDER: u8 = 13;
    pub const HAWKE: u8 = 14;
    pub const HACHI: u8 = 15;
    pub const COLIN: u8 = 16;
    pub const JESS: u8 = 17;
    pub const SENSEI: u8 = 18;
    pub const JUGGER: u8 = 72;
    pub const KOAL: u8 = 73;
    pub const KINDLE: u8 = 74;
    pub const VON_BOLT: u8 = 75;
    pub const GRIMM: u8 = 76;
    pub const JAVIER: u8 = 77;
    pub const SASHA: u8 = 78;
    pub const JAKE: u8 = 79;
    pub const RACHEL: u8 = 80;
    pub const CLONE_ANDY: u8 = crate::co_new::CLONE_ANDY;
}

/// Army colours (the header's colour bytes).
pub mod colour {
    pub const ORANGE_STAR: u8 = 1;
    pub const BLUE_MOON: u8 = 2;
    pub const GREEN_EARTH: u8 = 3;
    pub const YELLOW_COMET: u8 = 4;
    pub const BLACK_HOLE: u8 = 5;
}

/// AW2 unit types.
pub mod unit {
    pub const INFANTRY: u8 = 1;
    pub const MECH: u8 = 2;
    pub const MD_TANK: u8 = 3;
    pub const MEGATANK: u8 = 4;
    pub const TANK: u8 = 5;
    pub const RECON: u8 = 6;
    pub const APC: u8 = 7;
    pub const NEOTANK: u8 = 8;
    pub const PIPERUNNER: u8 = 9;
    pub const ARTILLERY: u8 = 10;
    pub const ROCKETS: u8 = 11;
    pub const STEALTH: u8 = 12;
    pub const BLACK_BOMB: u8 = 13;
    pub const ANTI_AIR: u8 = 14;
    pub const MISSILES: u8 = 15;
    pub const FIGHTER: u8 = 16;
    pub const BOMBER: u8 = 17;
    pub const BLACK_BOAT: u8 = 18;
    pub const B_COPTER: u8 = 19;
    pub const T_COPTER: u8 = 20;
    pub const BATTLESHIP: u8 = 21;
    pub const CRUISER: u8 = 22;
    pub const LANDER: u8 = 23;
    pub const SUB: u8 = 24;
    pub const CARRIER: u8 = 26;
    pub const OOZIUM: u8 = 27;
}

// --- The format ------------------------------------------------------------------

/// A campaign.
#[derive(Clone, Debug, Default)]
pub struct CampaignDef {
    /// The campaign's index in [`SOURCES`] (its save slots, its texts).
    pub source: usize,
    /// The COs the player can use, in unlock order: (AW2 CO id, open at the
    /// start). A mission's `recruits` open the later ones.
    pub roster: Vec<(u8, bool)>,
    /// Pages shown on the world map before the first mission.
    pub prologue: Vec<Page>,
    /// The staff roll after the last mission's scenes.
    pub credits: Vec<CreditSection>,
    pub missions: Vec<MissionDef>,
    /// The mission whose win ends the campaign (an index of `missions`).
    /// The key of the mission whose win ends the campaign.
    pub final_mission: &'static str,
    /// The hidden bonds (at most 12): earned by `Action::EarnBond(k)` in a
    /// recruit mission; each puts its quote on its CO's page; the secret
    /// mission's `Needs::Bonds` opens when all are earned.
    pub bonds: Vec<Bond>,
    /// The key of the secret mission ("" none): the staff roll's `secret`
    /// sections are shown once it is won.
    pub secret_mission: &'static str,
}

/// A hidden bond: the CO whose CO page shows the secret quote once the bond
/// is earned (it replaces that CO's bio page while the BH Campaign's session
/// is on).
#[derive(Clone, Copy, Debug)]
pub struct Bond {
    pub co: u8,
    pub quote: &'static str,
}

/// When a mission opens, by mission key (the order of `CampaignDef::missions`
/// is only the world map's: a mission names what it needs by key, so acts
/// can be written apart).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Needs {
    Start,
    /// All of these missions won.
    All(Vec<&'static str>),
    /// Any of these (a branch).
    Any(Vec<&'static str>),
    /// All of these won and every bond earned.
    Bonds(Vec<&'static str>),
}

/// A narration page: text in a box with no speaker, over an optional
/// Dual Strike story picture (an index of
/// [`crate::ds_story_art::NARRATION`], read from the player's ROM).
#[derive(Clone, Copy, Debug, Default)]
pub struct Page {
    pub text: &'static str,
    /// A Dual Strike story picture (Omega Land's map only).
    pub picture: Option<u8>,
    /// The speaker when the page is a dialogue box (AW2's map): default a
    /// Black Hole soldier.
    pub who: Option<Speaker>,
}

/// One section of the staff roll: a heading and names.
#[derive(Clone, Debug, Default)]
pub struct CreditSection {
    pub heading: &'static str,
    pub names: Vec<&'static str>,
    /// Shown only after the campaign's secret mission is won (a credits
    /// line, or the secret epilogue's pages: names of at most 21 letters).
    pub secret: bool,
}

/// Who a scene line is spoken by: a CO (AW2 id) in a mood, or an army's
/// soldier (AW2's trooper faces, by colour).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Speaker {
    Co(u8, Mood),
    Trooper(u8),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mood {
    Normal = 0,
    Happy = 1,
    Sad = 2,
}

/// A line of a scene. Text is plain; it is wrapped to AW2's box (two
/// lines of 176 pixels; `\x0f` forces a new box).
#[derive(Clone, Copy, Debug)]
pub struct Line {
    pub who: Speaker,
    pub text: &'static str,
    /// Shown only when the player's (main) CO is this one (a conditional jump over
    /// the line's two commands on [`Cond::PlayerCo`]; AW2's own op 0x43 compares the
    /// CO id modulo 24, which cannot tell the Dual Strike COs apart): the design's
    /// `@IF CO` rows.
    pub only: Option<u8>,
    /// Shown only when the player's tag partner (the second front's CO once it has joined) is this CO.
    pub partner: Option<u8>,
    /// Shown only when this CO is in the player's pair (the main CO or the partner).
    pub with: Option<u8>,
}

/// `Line::say(co::STURM, "...")`.
impl Line {
    pub const fn say(co: u8, text: &'static str) -> Line {
        Line { who: Speaker::Co(co, Mood::Normal), text, only: None, partner: None, with: None }
    }
    pub const fn feel(co: u8, mood: Mood, text: &'static str) -> Line {
        Line { who: Speaker::Co(co, mood), text, only: None, partner: None, with: None }
    }
    pub const fn soldier(colour: u8, text: &'static str) -> Line {
        Line { who: Speaker::Trooper(colour), text, only: None, partner: None, with: None }
    }
    /// The line is shown only when the player's CO is `co`.
    pub const fn only(mut self, co: u8) -> Line {
        self.only = Some(co);
        self
    }
    /// The line is shown only when `co` is in the player's pair (leading it or as its partner).
    pub const fn with(mut self, co: u8) -> Line {
        self.with = Some(co);
        self
    }
    /// The line is shown only when the player's partner is `co`.
    pub const fn only_partner(mut self, co: u8) -> Line {
        self.partner = Some(co);
        self
    }
}

/// A scene: lines, optionally with a song (AW2 song id) for its length.
#[derive(Clone, Debug, Default)]
pub struct Scene {
    pub lines: Vec<Line>,
    pub song: Option<u16>,
}

impl Scene {
    pub fn new(lines: Vec<Line>) -> Scene {
        Scene { lines, song: None }
    }
    pub fn is_empty(&self) -> bool {
        self.lines.is_empty()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Weather {
    #[default]
    Clear = 0,
    Snow = 1,
    Rain = 2,
    Sandstorm = 3,
}

/// Where a mission's map comes from.
#[derive(Clone, Debug)]
pub enum MapSrc {
    /// One of AW2's maps by its map id (its terrain and, unless the
    /// mission lists units, its deployment).
    Aw2 { id: u8 },
    /// One of Dual Strike's campaign maps (record index 0..32), from the
    /// player's ROM.
    Ds { record: u8 },
    /// Tile ids row by row (AW2's tile ids; see `docs/AW2.md`).
    Tiles { width: u8, height: u8, tiles: Vec<u16> },
    /// A text picture of terrain (see [`ascii_tiles`]).
    Ascii(&'static [&'static str]),
    /// A map built by `five/bhmap.py` from `five/bh/*.txt` (every road, river,
    /// pipe, coast and shoal joined as AW2 draws them, checked for
    /// reachability), by its name; its units are the mission's unless it
    /// lists its own.
    Built(&'static str),
}

/// A map built by `five/bhmap.py` (`bh_map_data.rs`).
pub struct BuiltMap {
    pub name: &'static str,
    pub width: u8,
    pub height: u8,
    pub armies: u8,
    pub tiles: &'static [u16],
    pub units: &'static [BuiltUnit],
}

/// A unit of a built map (`name` empty: none).
pub struct BuiltUnit {
    pub army: u8,
    pub kind: u8,
    pub x: u8,
    pub y: u8,
    pub hp: u8,
    pub hold: bool,
    pub name: &'static str,
}

fn built_map(name: &str) -> Option<&'static BuiltMap> {
    crate::bh_map_data::MAPS.iter().find(|m| m.name == name)
}

/// A built map's units as the mission's.
fn built_units(src: &MapSrc) -> Vec<UnitDef> {
    let MapSrc::Built(n) = src else { return Vec::new() };
    built_map(n)
        .map(|m| {
            m.units
                .iter()
                .map(|u| {
                    let mut d = UnitDef::new(u.army, u.kind, u.x, u.y).hp(u.hp);
                    if u.hold {
                        d = d.hold();
                    }
                    if !u.name.is_empty() {
                        d = d.named(u.name);
                    }
                    d
                })
                .collect()
        })
        .unwrap_or_default()
}

/// A property on the map: kind and owner (0 neutral, 1..4 an army).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Prop {
    pub kind: PropKind,
    pub owner: u8,
    pub x: u8,
    pub y: u8,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PropKind {
    Hq = 0,
    Base = 1,
    City = 2,
    Airport = 3,
    Port = 4,
}

/// Black Hole's structures and inventions, stamped at an anchor cell.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Structure {
    MiniCannonDown,
    MiniCannonUp,
    MiniCannonLeft,
    MiniCannonRight,
    Laser,
    BlackCannonDown,
    BlackCannonUp,
    BlackFactory,
    Volcano,
    Deathray,
    BlackCrystal,
    BlackObelisk,
}

/// A unit deployed at the mission's start.
#[derive(Clone, Copy, Debug)]
pub struct UnitDef {
    pub army: u8,
    pub kind: u8,
    pub x: u8,
    pub y: u8,
    /// Hit points 1..100 (internal; the display is HP / 10).
    pub hp: u8,
    /// The computer's order for it: 0 attack, 1 hold, 5 (as Dual Strike's).
    pub ai: u8,
    /// A name the mission's rules can refer to ([`Cond::UnitAt`], ...).
    pub name: Option<&'static str>,
}

impl UnitDef {
    pub const fn new(army: u8, kind: u8, x: u8, y: u8) -> UnitDef {
        UnitDef { army, kind, x, y, hp: 100, ai: 0, name: None }
    }
    pub const fn hp(mut self, hp: u8) -> UnitDef {
        self.hp = hp;
        self
    }
    pub const fn hold(mut self) -> UnitDef {
        self.ai = 1;
        self
    }
    pub const fn named(mut self, name: &'static str) -> UnitDef {
        self.name = Some(name);
        self
    }
}

/// An army's CO (or pair), or the player's pick.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CoSpec {
    None,
    /// A CO, in any army colour.
    Fixed(u8),
    /// A tag pair: the lead and the partner.
    Pair(u8, u8),
    /// The player picks one CO from the unlocked ones.
    Pick,
    /// The player picks two, a tag pair.
    PickPair,
}

/// An army in a mission: colour and CO are independent (Von Bolt can lead
/// a Green Earth army).
#[derive(Clone, Copy, Debug)]
pub struct ArmyDef {
    pub colour: u8,
    pub team: u8,
    pub co: CoSpec,
    /// Starting funds (None: as the map).
    pub funds: Option<u32>,
}

impl ArmyDef {
    pub const fn new(colour: u8, co: CoSpec) -> ArmyDef {
        ArmyDef { colour, team: 0, co, funds: None }
    }
    pub const fn team(mut self, team: u8) -> ArmyDef {
        self.team = team;
        self
    }
    pub const fn funds(mut self, funds: u32) -> ArmyDef {
        self.funds = Some(funds);
        self
    }
}

/// A battle's second front ([`crate::two_front`]).
#[derive(Clone, Debug)]
pub struct FrontDef {
    pub map: MapSrc,
    pub props: Vec<Prop>,
    pub structures: Vec<(Structure, u8, u8)>,
    pub units: Vec<UnitDef>,
    /// Each army's CO there; `CoSpec::Pick` is the player's pick for that
    /// front (after the main front's picks).
    pub cos: [CoSpec; 4],
    pub send: SendRule,
    pub sky: bool,
    pub weather: Weather,
    pub fog: bool,
}

/// A condition of a trigger. All are evaluated on AW2's live battle state.
#[derive(Clone, Debug)]
pub enum Cond {
    /// The day is this or later.
    DayAtLeast(u16),
    /// The named unit stands on (x, y).
    UnitAt { name: &'static str, x: u8, y: u8 },
    /// The named unit is still alive / is gone.
    UnitAlive(&'static str),
    UnitGone(&'static str),
    /// An army has at most this many units.
    ArmyUnitsAtMost { army: u8, n: u8 },
    /// An army owns at least this many properties.
    PropertiesAtLeast { army: u8, n: u8 },
    Not(Box<Cond>),
    /// All of these.
    All(Vec<Cond>),
    /// Any of these.
    Any(Vec<Cond>),
    /// Every `n` days from day `from` (that day included): `Trigger::repeating`.
    EveryDays { n: u16, from: u16 },
    /// The player's tag pair (army 1's CO and partner) is this pair, in either order.
    PlayerPair { a: u8, b: u8 },
    /// The player's (main) CO is this one.
    PlayerCo(u8),
    /// The player's tag partner is this CO.
    PartnerCo(u8),
    /// This CO is the player's main CO or its tag partner.
    PlayerHas(u8),
    /// The cell (x, y) belongs to this army (0 neutral).
    OwnerAt { x: u8, y: u8, army: u8 },
    /// An army is defeated (its HQ taken or its units gone).
    ArmyDefeated(u8),
    /// At least `n` of an army's units stand in the rectangle (the escort and
    /// evacuation missions' "everyone is out").
    UnitsIn { army: u8, area: Rect, at_least: u8 },
    /// The named unit stands in the rectangle.
    NamedIn { name: &'static str, area: Rect },
    /// The mission's reversed Black Onyx ([`MissionDef::onyx`]) has at most
    /// this many hits left / is destroyed.
    OnyxHitsAtMost(u8),
    OnyxDestroyed,
    /// A mission-local flag ([`FLAG_FIRST`]..) is set (a trigger's own once-latch).
    Flag(u8),
    /// A predicate written in Rust for a mission with a rule of its own (an
    /// escort, an evacuation): it gets the live battle; see the helpers
    /// ([`unit_by_name`], [`units_of`], [`day`]).
    Custom(fn(&mut Core) -> bool),
}

/// A rectangle of cells, corners included.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x0: u8,
    pub y0: u8,
    pub x1: u8,
    pub y1: u8,
}

impl Rect {
    pub const fn new(x0: u8, y0: u8, x1: u8, y1: u8) -> Rect {
        Rect { x0, y0, x1, y1 }
    }
    pub fn has(&self, x: u8, y: u8) -> bool {
        (self.x0..=self.x1).contains(&x) && (self.y0..=self.y1).contains(&y)
    }
}

/// What a trigger does.
#[derive(Clone, Debug)]
pub enum Action {
    /// A scene plays.
    Scene(Scene),
    /// The player's side wins / loses the mission (after the scene).
    Win,
    Lose,
    /// An army's funds are set to this.
    SetFunds { army: u8, funds: u32 },
    /// Funds are added (negative: taken).
    AddFunds { army: u8, funds: i32 },
    /// Hidden bond `k` is earned ([`CampaignDef::bonds`]).
    EarnBond(u8),
    /// Reinforcements: these units appear (full HP, ammo and fuel) on their
    /// cells for their armies, if the cells are free.
    Spawn(Vec<UnitDef>),
    /// An army's CO becomes this one (the second stage of a mission: Nell,
    /// then Andy; keep the power meter as it is).
    SetCo { army: u8, co: u8 },
    /// AW2's meteor strike (Von Bolt's Ex Machina) of `hp` on the spot the
    /// CPU's scorer picks best for the army whose turn it is now (the
    /// player's, at a turn-start trigger: the Black Onyx turned on the
    /// enemy), every unit within two cells, never below 1 HP.
    Strike { hp: u8 },
    /// A function of the mission's own.
    Custom(fn(&mut Core)),
}

/// When a trigger is looked at.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum When {
    /// At the start of each of army 1's turns.
    TurnStart,
    /// After each action.
    AfterAction,
}

/// A rule of a mission: when its condition holds, its actions run once.
#[derive(Clone, Debug)]
pub struct Trigger {
    pub when: When,
    pub cond: Cond,
    pub then: Vec<Action>,
    /// Fires once (the default: a latch flag of its own); `repeating()` fires
    /// at every look while the condition holds.
    pub once: bool,
}

impl Trigger {
    pub fn new(when: When, cond: Cond, then: Vec<Action>) -> Trigger {
        Trigger { when, cond, then, once: true }
    }
    pub fn repeating(mut self) -> Trigger {
        self.once = false;
        self
    }
}

/// A mission.
#[derive(Clone, Debug)]
pub struct MissionDef {
    /// A stable key (for saves of the future and for tests).
    pub key: &'static str,
    pub title: &'static str,
    /// The objective, as the world map's panel shows it (about two lines).
    pub objective: &'static str,
    pub map: MapSrc,
    /// 2..=4 armies, in army order (army 1 is the player's).
    pub armies: Vec<ArmyDef>,
    pub props: Vec<Prop>,
    pub structures: Vec<(Structure, u8, u8)>,
    /// The deployment; empty keeps an AW2 / Dual Strike map's own.
    pub units: Vec<UnitDef>,
    /// 0 normal, 1 snow, 2 desert, 3 wasteland (Dual Strike's looks).
    pub look: u8,
    pub weather: Weather,
    pub fog: bool,
    /// The days the player has (0: no limit); exceeding it loses.
    pub day_limit: u16,
    /// The days for the S rank (0: AW2's default).
    pub rank_days: u16,
    pub triggers: Vec<Trigger>,
    /// A battle on two fronts.
    pub front2: Option<FrontDef>,
    /// Before the first turn / after the win, in the battle.
    pub intro: Scene,
    pub victory: Scene,
    /// On the world map after the win, before the next mission.
    pub after: Scene,
    /// The battle's song (an AW2 song id); None keeps the CO's theme.
    pub music: Option<u16>,
    /// The COs this mission's win unlocks (indexes of the roster).
    pub recruits: Vec<u8>,
    /// When the mission opens (by mission key).
    pub needs: Needs,
    /// Its flag on AW2's world map (map pixels), marker style, stars.
    pub flag: (i16, i16),
    pub style: u8,
    pub stars: u8,
    /// The COs the player may pick from, if not the whole roster.
    pub pool: Vec<u8>,
    /// The Setup phase before day 1 when the player picks a CO (scout the
    /// map, open the menu, Deploy). A mission with no pick has none.
    pub setup: bool,
    /// A reversed Black Onyx on the mission ([`OnyxDef`]).
    pub onyx: Option<OnyxDef>,
    /// The Black Factory's unit table: (day 0..=31, the three door slots' unit types, 0 none),
    /// else Factory Blues' schedule (the factory spawns on Black Hole's turns: the player's).
    pub factory: Vec<(u8, [u8; 3])>,
}

impl MissionDef {
    pub fn new(key: &'static str, title: &'static str) -> MissionDef {
        MissionDef {
            key,
            title,
            objective: "Rout the enemy.",
            map: MapSrc::Ascii(&[]),
            armies: Vec::new(),
            props: Vec::new(),
            structures: Vec::new(),
            units: Vec::new(),
            look: 0,
            weather: Weather::Clear,
            fog: false,
            day_limit: 0,
            rank_days: 0,
            triggers: Vec::new(),
            front2: None,
            intro: Scene::default(),
            victory: Scene::default(),
            after: Scene::default(),
            music: None,
            recruits: Vec::new(),
            needs: Needs::Start,
            flag: (0, 0),
            style: 0,
            stars: 1,
            pool: Vec::new(),
            setup: true,
            onyx: None,
            factory: Vec::new(),
        }
    }
}

// --- Maps ------------------------------------------------------------------------

const PLAIN: u16 = 0x001;
const MOUNTAIN: u16 = 0x022;
const SEA: u16 = 0x008;
const UNDERLAY: u16 = 0x1A4;
const VOLCANO_RIM: u16 = 0x1A5;
const TILE_CLASS: u32 = 0x080C_1BC4;
const CLASS_WOOD: u8 = 4;
const CLASS_ROAD: u8 = 5;
const CLASS_RIVER: u8 = 2;
const CLASS_SHOAL: u8 = 13;
const CLASS_REEF: u8 = 19;

/// The first tile whose class is `class` (AW2's tile table).
fn tile_of_class(core: &Core, class: u8) -> u16 {
    (0..0x180u32).find(|&t| core.raw_read_8(TILE_CLASS + t, -1) & 0x1F == class).map_or(PLAIN, |t| t as u16)
}

/// A text picture of terrain as tiles: `.` plain, `f` forest, `m`
/// mountain, `=` road, `r` river, `~` sea, `s` shoal, `:` reef, `c` a
/// neutral city, `A`..`D` army n's city, `b` base, `a` airport, `p` port, `1`..`4` army n's HQ.
/// Roads, rivers and the sea are the first tile of their class (they do
/// not join up): use `MapSrc::Tiles` or an AW2 / Dual Strike map for
/// finished terrain.
pub fn ascii_tiles(core: &Core, rows: &[&str]) -> (u8, u8, Vec<u16>) {
    let h = rows.len();
    let w = rows.iter().map(|r| r.chars().count()).max().unwrap_or(0);
    let mut tiles = Vec::with_capacity(w * h);
    for r in rows {
        let mut cs = r.chars();
        for _ in 0..w {
            let t = match cs.next().unwrap_or('.') {
                'f' => tile_of_class(core, CLASS_WOOD),
                'm' => MOUNTAIN,
                '=' => tile_of_class(core, CLASS_ROAD),
                'r' => tile_of_class(core, CLASS_RIVER),
                '~' => SEA,
                's' => tile_of_class(core, CLASS_SHOAL),
                ':' => tile_of_class(core, CLASS_REEF),
                'c' => property_tile(PropKind::City, 0),
                'b' => property_tile(PropKind::Base, 0),
                'a' => property_tile(PropKind::Airport, 0),
                'p' => property_tile(PropKind::Port, 0),
                d @ '1'..='4' => property_tile(PropKind::Hq, d as u8 - b'0'),
                d @ 'A'..='D' => property_tile(PropKind::City, d as u8 - b'A' + 1),
                _ => PLAIN,
            };
            tiles.push(t);
        }
    }
    (w as u8, h as u8, tiles)
}

/// A property's tile: 0x1C0 + kind + 5 * owner.
pub fn property_tile(kind: PropKind, owner: u8) -> u16 {
    0x1C0 + kind as u16 + 5 * owner.min(4) as u16
}

/// A structure's footprint: rows of tiles from (anchor + dx, anchor + dy),
/// as the Design Room places them (crate::design).
fn footprint(s: Structure) -> (i32, i32, Vec<Vec<u16>>) {
    let u = UNDERLAY;
    match s {
        Structure::MiniCannonDown => (0, 0, vec![vec![0x182]]),
        Structure::MiniCannonUp => (0, 0, vec![vec![0x183]]),
        Structure::MiniCannonLeft => (0, 0, vec![vec![0x184]]),
        Structure::MiniCannonRight => (0, 0, vec![vec![0x185]]),
        Structure::Laser => (0, 0, vec![vec![0x181]]),
        Structure::BlackCannonDown => (-1, -1, vec![vec![u; 3], vec![0x186, 0x187, 0x188], vec![u; 3]]),
        Structure::BlackCannonUp => (-1, -1, vec![vec![u; 3], vec![0x189, 0x18A, 0x18B], vec![u; 3]]),
        Structure::BlackFactory => (-1, -2, vec![vec![u, 0x143, u], vec![u; 3], vec![0x18C, 0x18D, 0x18E], vec![u; 3]]),
        Structure::Volcano => {
            let r = VOLCANO_RIM;
            (-1, -2, vec![vec![r; 4], vec![r, u, u, r], vec![0x1A6, 0x1A7, 0x1A8, 0x1A9], vec![u; 4]])
        }
        Structure::Deathray => (-1, -1, vec![vec![u; 3], vec![0x18F, 0x190, 0x191], vec![u; 3]]),
        Structure::BlackCrystal => (0, 0, vec![vec![0x192]]),
        Structure::BlackObelisk => (-1, -1, vec![vec![u; 3], vec![u, 0x193, u], vec![u; 3]]),
    }
}

/// Props and structures put on a map's tiles.
fn decorate(w: u8, h: u8, tiles: &mut [u16], props: &[Prop], structures: &[(Structure, u8, u8)]) -> Result<(), String> {
    let at = |x: i32, y: i32| (x >= 0 && y >= 0 && x < w as i32 && y < h as i32).then(|| (y * w as i32 + x) as usize);
    for p in props {
        let i = at(p.x as i32, p.y as i32).ok_or(format!("property at ({}, {}) is off the map", p.x, p.y))?;
        tiles[i] = property_tile(p.kind, p.owner);
    }
    for &(s, x, y) in structures {
        let (dx, dy, rows) = footprint(s);
        for (ry, row) in rows.iter().enumerate() {
            for (rx, &t) in row.iter().enumerate() {
                let (cx, cy) = (x as i32 + dx + rx as i32, y as i32 + dy + ry as i32);
                let i = at(cx, cy).ok_or(format!("{s:?} at ({x}, {y}) leaves the map"))?;
                tiles[i] = t;
            }
        }
    }
    Ok(())
}

// --- Compiling -------------------------------------------------------------------

/// The pieces a compiled campaign needs at run time.
#[derive(Debug)]
pub struct Rules {
    /// Conditions by predicate code ([`PRED`] | mission << 16 | index).
    pub conds: Vec<(u32, Cond)>,
    /// The named units: (mission, name) -> (army, slot 1.., bit): the unit's
    /// persistent id is its bit in the death latch ([`LATCH`]).
    pub units: HashMap<(usize, &'static str), (u8, u8, u8)>,
    /// The mission's own functions (`Action::Custom`).
    pub fns: Vec<fn(&mut Core)>,
}

/// Predicate codes of custom campaigns' conditions.
pub const PRED: u32 = 0xBC00_0000;
/// Function codes of actions: [`FUNDS`] | army sets that army's funds.
pub const FUNDS: u32 = 0xBC10_0000;
/// [`FUNDS_ADD`] | army adds funds; [`BOND`] | k earns bond k.
pub const FUNDS_ADD: u32 = 0xBC20_0000;
pub const BOND: u32 = 0xBC30_0000;
/// Reinforcements: [`SET_ARMY`] | army makes the army the one moving, each
/// [`SPAWN`] (x | y << 8 | type << 16) creates a unit for it, [`RESTORE_ARMY`]
/// puts the army moving back; [`STRIKE`] (a function's address) is a meteor
/// strike; [`SET_CO`] | army (the CO); [`CUSTOM_FN`] | index.
pub const SET_ARMY: u32 = 0xBC40_0000;
pub const SPAWN: u32 = 0xBC50_0000;
pub const RESTORE_ARMY: u32 = 0xBC60_0000;
pub const STRIKE: u32 = 0xBC70_0000;
pub const SET_CO: u32 = 0xBC80_0000;
pub const CUSTOM_FN: u32 = 0xBC90_0000;
/// A jump's relative marker (script op 0x1E whose target word is `REL_JUMP | n`: n commands on).
const REL_JUMP: u32 = 0xFFFE_0000;
/// A trigger's once-latch flags: campaign flags [`FLAG_FIRST`]..=[`FLAG_LAST`]
/// (but AW2's Hard flag, [`FLAG_HARD`]).
pub const FLAG_FIRST: u8 = 0x20;
pub const FLAG_LAST: u8 = 0x8F;
pub const FLAG_HARD: u8 = 0x60;

static RULES: [OnceLock<Rules>; 4] = [OnceLock::new(), OnceLock::new(), OnceLock::new(), OnceLock::new()];

/// An error found while compiling.
pub type Error = String;

struct Compiler<'a> {
    art: WorldArt,
    built: Built,
    next_text: u16,
    /// (text id, plain text, text with the earned-bond mark, bond) of the recruit missions' panels.
    marks: Vec<(u16, u32, u32, u8)>,
    magic: HashMap<Magic, u32>,
    widths: &'a [u8],
    conds: Vec<(u32, Cond)>,
    units: HashMap<(usize, &'static str), (u8, u8, u8)>,
    fns: Vec<fn(&mut Core)>,
    /// The next once-latch flag.
    next_flag: u8,
    /// The player's army and the index of the mission being compiled (for `Line::only`).
    player: u8,
    mission: usize,
}

fn face(who: Speaker) -> u16 {
    match who {
        Speaker::Co(c, m) => c as u16 + 24 * m as u16,
        // AW2's troopers: faces 19..23 by colour.
        Speaker::Trooper(col) => 19 + (col.clamp(1, 5) as u16 - 1),
    }
}

impl<'a> Compiler<'a> {
    fn text(&mut self, bytes: Vec<u8>) -> Result<u16, Error> {
        let id = self.next_text;
        if id > TEXT_LAST {
            return Err("out of text ids".into());
        }
        self.next_text += 1;
        let mut z = bytes;
        z.push(0);
        let at = self.built.add(&z);
        self.built.texts.push((id, at));
        Ok(id)
    }

    fn dialogue(&mut self, s: &str) -> Result<u16, Error> {
        let t = wrap_dialogue(s.replace("\\x0f", "\x0f").as_bytes(), self.widths);
        self.text(t)
    }

    fn stub(&mut self, m: Magic) -> u32 {
        if let Some(&a) = self.magic.get(&m) {
            return a;
        }
        let a = self.built.add_magic(m.clone());
        self.magic.insert(m, a);
        a
    }

    /// A scene as AW2 script commands (no end).
    fn scene_cmds(&mut self, scene: &Scene) -> Result<Vec<[u8; 16]>, Error> {
        let mut out = Vec::new();
        if scene.lines.is_empty() {
            return Ok(out);
        }
        if let Some(s) = scene.song {
            out.push(cmd(0x41, 0, s, 0, 0));
        }
        out.push(cmd(0x17, 0, face(scene.lines[0].who), 0, 0));
        for l in &scene.lines {
            if let Some(co) = l.only {
                // (jumps over the two commands below unless the player's CO is `co`: a relative
                // jump, made absolute by `script`)
                let stub = self.cond(self.mission, &Cond::Not(Box::new(Cond::PlayerCo(co))));
                out.push(cmd(0x1E, REL_JUMP | 2, 0, 0, stub));
            }
            if let Some(co) = l.with {
                let stub = self.cond(self.mission, &Cond::Not(Box::new(Cond::PlayerHas(co))));
                out.push(cmd(0x1E, REL_JUMP | 2, 0, 0, stub));
            }
            if let Some(co) = l.partner {
                let stub = self.cond(self.mission, &Cond::Not(Box::new(Cond::PartnerCo(co))));
                out.push(cmd(0x1E, REL_JUMP | 2, 0, 0, stub));
            }
            out.push(cmd(0x38, 0, face(l.who), 0, 0));
            let id = self.dialogue(l.text)?;
            out.push(cmd(0x19, 0, id, 0, 0));
        }
        if scene.song.is_some() {
            out.push(cmd(0x42, 0, 0, 0, 0));
        }
        out.push(cmd(0x18, 0, 0, 0, 0));
        Ok(out)
    }

    fn script(&mut self, mut cmds: Vec<[u8; 16]>) -> u32 {
        // Relative jumps (a scene's conditional lines) become the address of the command n on.
        let at = self.built.base + ((self.built.blob.len() + 3) & !3) as u32;
        for i in 0..cmds.len() {
            let w1 = u32::from_le_bytes(cmds[i][4..8].try_into().unwrap());
            if cmds[i][0] == 0x1E && w1 & 0xFFFF_0000 == REL_JUMP {
                let target = at + 16 * (i as u32 + 1 + (w1 & 0xFFFF));
                cmds[i][4..8].copy_from_slice(&target.to_le_bytes());
            }
        }
        let mut b: Vec<u8> = cmds.iter().flatten().copied().collect();
        b.extend_from_slice(&cmd(0x04, 0, 0, 0, 0));
        self.built.add(&b)
    }

    /// The pseudo-predicate for a condition of `mission`.
    fn cond(&mut self, mission: usize, c: &Cond) -> u32 {
        let idx = self.conds.iter().filter(|(k, _)| (k >> 16) & 0xFF == mission as u32).count() as u32;
        let code = PRED | (mission as u32) << 16 | idx;
        self.conds.push((code, c.clone()));
        self.stub(Magic::Predicate(code))
    }
}

/// The units blob (AW2's 12-byte records) of a deployment; named units get
/// their slot.
fn deployment(
    mut names: Option<&mut HashMap<(usize, &'static str), (u8, u8, u8)>>,
    mission: usize,
    armies: usize,
    units: &[UnitDef],
) -> Result<Vec<u8>, Error> {
    let mut out = Vec::new();
    for army in 1..=armies as u8 {
        out.extend_from_slice(&[0xFE, army, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        let mut slot = 0u8;
        for u in units.iter().filter(|u| u.army == army) {
            slot += 1;
            if let (Some(n), Some(names)) = (u.name, names.as_deref_mut()) {
                let bit = names.keys().filter(|k| k.0 == mission).count() as u8;
                if bit >= 24 {
                    return Err("at most 24 named units in a mission".into());
                }
                if names.insert((mission, n), (army, slot, bit)).is_some() {
                    return Err(format!("unit name {n} used twice in mission {mission}"));
                }
            }
            if u.hp == 0 || u.hp > 100 {
                return Err(format!("unit hp {} out of 1..=100", u.hp));
            }
            let fuel = 99;
            out.extend_from_slice(&[u.x, u.y, u.kind, 0, u.hp, 0, fuel, 0, 0, u.ai, 0, 0]);
        }
    }
    out.extend_from_slice(&[0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    Ok(out)
}

/// A map's tiles, size and own deployment.
fn load_map(core: &Core, src: &MapSrc) -> Result<(u8, u8, Vec<u16>, Option<Vec<u8>>), Error> {
    match src {
        MapSrc::Tiles { width, height, tiles } => {
            if tiles.len() != *width as usize * *height as usize {
                return Err("tiles do not fill the map".into());
            }
            Ok((*width, *height, tiles.clone(), None))
        }
        MapSrc::Built(n) => {
            let m = built_map(n).ok_or(format!("no built map {n:?} (five/bhmap.py)"))?;
            Ok((m.width, m.height, m.tiles.to_vec(), None))
        }
        MapSrc::Ascii(rows) => {
            if rows.is_empty() {
                return Err("an empty map".into());
            }
            let (w, h, t) = ascii_tiles(core, rows);
            Ok((w, h, t, None))
        }
        MapSrc::Aw2 { id } => {
            let at = crate::five_map::MAP_TABLE + crate::five_map::ENTRY * *id as u32;
            let (map, units) = (core.raw_read_32(at, -1), core.raw_read_32(at + 0x34, -1));
            let size = read_map(core, map).ok_or(format!("AW2 map {id:#x} unreadable"))?;
            let mut u = Vec::new();
            let mut p = units;
            for _ in 0..400 {
                let mut r = [0u8; 12];
                core.raw_read_range(p, -1, &mut r);
                u.extend_from_slice(&r);
                if r[0] == 0xFF {
                    break;
                }
                p += 12;
            }
            Ok((size.0, size.1, size.2, Some(u)))
        }
        MapSrc::Ds { record } => {
            let pack = crate::ds_pack::pack().ok_or("no Dual Strike pack")?;
            let ds = Ds::from_pack(pack).ok_or("no Dual Strike data")?;
            let rec = crate::ds_campaign_data::record(&ds, *record as usize).ok_or("no such Dual Strike record")?;
            let (w, h, t) = crate::ds_campaign_data::convert_map(&ds, rec.maps.0).ok_or("Dual Strike map unreadable")?;
            Ok((w, h, t, Some(crate::ds_campaign_data::convert_units(&ds, rec.units.0))))
        }
    }
}

/// An AW2 map blob in ROM (LZ77 of width, height, u16 tiles).
fn read_map(core: &Core, at: u32) -> Option<(u8, u8, Vec<u16>)> {
    let size = (core.raw_read_32(at, -1) >> 8) as usize;
    if size < 2 || size > 0x2000 {
        return None;
    }
    let mut b = vec![0u8; size + size / 4 + 64];
    core.raw_read_range(at, -1, &mut b);
    let raw = crate::ds_art::lz10(&b)?;
    let (w, h) = (*raw.first()?, *raw.get(1)?);
    let tiles: Vec<u16> = raw[2..].chunks_exact(2).map(|c| u16::from_le_bytes([c[0], c[1]])).collect();
    (tiles.len() == w as usize * h as usize).then_some((w, h, tiles))
}

fn co_ids(spec: CoSpec) -> ((u8, u8), (u8, u8)) {
    // (native, record ids for the engine's tests: 0x1C a pick)
    match spec {
        CoSpec::None => ((NO_CO, NO_CO), (0, 0)),
        CoSpec::Fixed(c) => ((c, NO_CO), (1, 0)),
        CoSpec::Pair(a, b) => ((a, b), (1, 1)),
        CoSpec::Pick => ((NO_CO, NO_CO), (0x1C, 0)),
        CoSpec::PickPair => ((NO_CO, NO_CO), (0x1C, 0x1C)),
    }
}

/// Compiles a campaign definition into the engine's model.
pub fn compile(core: &Core, def: &CampaignDef) -> Result<Model, Error> {
    let source = &SOURCES[def.source];
    let mut widths = vec![0u8; 256];
    core.raw_read_range(0x084C_36E4, -1, &mut widths);
    let built = Built {
        story: Story::default(),
        blob: b"CUSTCAMP".to_vec(),
        base: crate::ds_campaign::DATA + 0x100,
        texts: Vec::new(),
        headers: Vec::new(),
        magic: Vec::new(),
        stubs: Vec::new(),
        missions: Vec::new(),
        unhandled: Default::default(),
    };
    let mut cx = Compiler {
        art: source.art,
        built,
        next_text: TEXT_FIRST,
        marks: Vec::new(),
        magic: HashMap::new(),
        widths: &widths,
        conds: Vec::new(),
        units: HashMap::new(),
        fns: Vec::new(),
        next_flag: FLAG_FIRST,
        player: 1,
        mission: 0,
    };
    let n = def.missions.len();
    if n == 0 || n > MAX_MISSIONS {
        return Err(format!("{n} missions (1..={MAX_MISSIONS})"));
    }
    if def.roster.is_empty() || def.roster.len() > 24 {
        return Err("the roster needs 1..=24 COs".into());
    }
    // Missions first, then the second fronts after them (as Dual Strike's).
    let mut fronts: Vec<(usize, &FrontDef)> = Vec::new();
    let mut records: Vec<MissionRecord> = Vec::new();
    for (i, m) in def.missions.iter().enumerate() {
        records.push(MissionRecord::Main(i, m));
        if let Some(f) = &m.front2 {
            fronts.push((i, f));
        }
    }
    for &(i, f) in &fronts {
        records.push(MissionRecord::Second(i, f));
    }
    let mut second_index: HashMap<usize, u8> = HashMap::new();
    for (k, &(i, _)) in fronts.iter().enumerate() {
        second_index.insert(i, (n + k) as u8);
    }
    for (rec_index, rec) in records.iter().enumerate() {
        match rec {
            MissionRecord::Main(i, m) => {
                let info_header = compile_mission(&mut cx, core, def, *i, rec_index, m, second_index.get(i).copied())?;
                cx.built.headers.push((rec_index as u8, info_header.0));
                cx.built.missions.push(info_header.1);
            }
            MissionRecord::Second(i, f) => {
                let m = &def.missions[*i];
                let (hd, info) = compile_second(&mut cx, core, def, *i, rec_index, m, f)?;
                cx.built.headers.push((rec_index as u8, hd));
                cx.built.missions.push(info);
            }
        }
    }
    // Story: prologue pages, scenes after wins, the staff roll.
    let mut story = Story::default();
    story.prologue = prologue_script(&mut cx, &def.prologue)?;
    for (i, m) in def.missions.iter().enumerate() {
        if !m.after.is_empty() {
            let cmds = cx.scene_cmds(&m.after)?;
            let s = cx.script(cmds);
            story.after_win.push((i, s));
        }
    }
    cx.built.story = story;
    let pictures = if SOURCES[def.source].art == WorldArt::OmegaLand && def.prologue.iter().any(|p| p.picture.is_some()) { crate::ds_story_art::narration_pictures() } else { Vec::new() };
    let credits = if def.credits.is_empty() {
        None
    } else {
        let sections: Vec<(Vec<crate::ds_credits::Line>, u32, bool)> = def
            .credits
            .iter()
            .map(|s| {
                let mut lines = vec![crate::ds_credits::Line::Heading(s.heading.to_string())];
                lines.extend(s.names.iter().map(|n| crate::ds_credits::Line::Name(n.to_string())));
                (lines, 120, s.secret)
            })
            .collect();
        crate::ds_credits::build_sections_secret(core, sections, &mut cx.built)
    };
    // The hidden bonds' quotes, wrapped to a CO page.
    let mut bonds = Vec::new();
    for b in &def.bonds {
        let t = crate::co_new::wrap_page(b.quote.as_bytes(), &widths);
        let mut z = t;
        z.push(0);
        bonds.push((b.co, cx.built.add(&z)));
    }
    if def.bonds.len() > 12 {
        return Err("at most 12 bonds".into());
    }
    let index_of = |k: &str| def.missions.iter().position(|m| m.key == k).map(|i| i as u8).ok_or(format!("no mission with the key {k:?}"));
    let keys = |v: &[&str]| v.iter().map(|k| index_of(k)).collect::<Result<Vec<u8>, String>>();
    let mut requires = Vec::new();
    for m in &def.missions {
        requires.push(match &m.needs {
            Needs::Start => Requires::Start,
            Needs::All(v) => Requires::All(keys(v)?),
            Needs::Any(v) => Requires::Any(keys(v)?),
            Needs::Bonds(v) => Requires::Bonds(keys(v)?),
        });
    }
    for (i, m) in def.missions.iter().enumerate() {
        if def.missions[..i].iter().any(|o| o.key == m.key) {
            return Err(format!("the key {:?} is used twice", m.key));
        }
    }
    let final_mission = index_of(def.final_mission)?;
    // Black Factory tables (32 days x 3 doors), one per mission that has its own.
    let mut factory_tables = Vec::new();
    for m in &def.missions {
        if m.factory.is_empty() {
            factory_tables.push(0);
            continue;
        }
        let mut t = [0u8; 96];
        for &(d, slots) in &m.factory {
            if d > 31 {
                return Err(format!("{}: a Black Factory table covers days 0..=31", m.key));
            }
            t[3 * d as usize..3 * d as usize + 3].copy_from_slice(&slots);
        }
        factory_tables.push(cx.built.add(&t));
    }
    let mut built = cx.built;
    let rules = Rules { conds: cx.conds, units: cx.units, fns: cx.fns };
    let _ = RULES[def.source].set(rules);
    let order: Vec<u8> = (0..n as u8).collect();
    if built.base + (built.blob.len() as u32) >= crate::ds_worldmap::BASE {
        return Err("the campaign does not fit its ROM range".into());
    }
    let roster = def.roster.clone();
    let custom = Custom {
        points: def
            .missions
            .iter()
            .map(|m| MapPoint { x: m.flag.0, y: m.flag.1, style: m.style, stars: m.stars })
            .collect(),
        requires,
        roster,
        recruits: def.missions.iter().map(|m| m.recruits.clone()).collect(),
        pools: def.missions.iter().map(|m| m.pool.clone()).collect(),
        bonds,
        marks: cx.marks.clone(),
        music: def.missions.iter().map(|m| m.music).collect(),
        onyx: def.missions.iter().map(|m| m.onyx).collect(),
        secret: if def.secret_mission.is_empty() { None } else { Some(index_of(def.secret_mission)?) },
        factory: factory_tables,
    };
    built.unhandled.clear();
    Ok(Model {
        label: source.label,
        built,
        missions: n,
        order,
        side_missions: Vec::new(),
        final_mission,
        credits,
        pictures,
        source,
        custom: Some(custom),
    })
}

enum MissionRecord<'a> {
    Main(usize, &'a MissionDef),
    Second(usize, &'a FrontDef),
}

fn prologue_script(cx: &mut Compiler, pages: &[Page]) -> Result<u32, Error> {
    if pages.is_empty() {
        return Ok(0);
    }
    if cx.art != WorldArt::OmegaLand {
        // AW2's own map: the pages are dialogue boxes (a picture is drawn
        // over Omega Land's map layer only: AW2's is not rebuilt after one).
        let lines = pages.iter().map(|p| Line { who: p.who.unwrap_or(Speaker::Trooper(colour::BLACK_HOLE)), text: p.text, only: None, partner: None, with: None }).collect();
        let cmds = cx.scene_cmds(&Scene { lines, song: None })?;
        return Ok(cx.script(cmds));
    }
    let mut s = Vec::new();
    for p in pages {
        if let Some(n) = p.picture {
            let stub = cx.stub(Magic::Flow(crate::ds_campaign::FLOW_PICTURE + n));
            s.push(cmd(0x00, stub, 0, 0, 0));
        }
        let id = cx.dialogue(p.text)?;
        s.push(cmd(0x1A, 0, id, 0, 0));
    }
    let back = cx.stub(Magic::Flow(crate::ds_campaign::FLOW_MAP_BACK));
    s.push(cmd(0x00, back, 0, 0, 0));
    Ok(cx.script(s))
}

fn rec8(o: u8, a: u8, b: u16, p: u32) -> [u8; 8] {
    let mut x = [0u8; 8];
    x[0] = o;
    x[1] = a;
    x[2..4].copy_from_slice(&b.to_le_bytes());
    x[4..8].copy_from_slice(&p.to_le_bytes());
    x
}

const END_REC: [u8; 8] = [8, 0, 0, 0, 0, 0, 0, 0];

/// A trigger list (records with their end) from groups of records.
fn list(groups: Vec<Vec<[u8; 8]>>) -> Vec<u8> {
    let mut b: Vec<u8> = groups.iter().flatten().flatten().copied().collect();
    b.extend_from_slice(&END_REC);
    b
}

fn compile_mission(
    cx: &mut Compiler,
    core: &Core,
    def: &CampaignDef,
    index: usize,
    rec_index: usize,
    m: &MissionDef,
    second: Option<u8>,
) -> Result<([u8; 0x5C], MissionInfo), Error> {
    let armies = m.armies.len();
    if !(2..=5).contains(&armies) {
        return Err(format!("{}: {armies} armies (2..=5)", m.key));
    }
    // Five armies (crate::five): armies 1..4 are the header's, army 5 is
    // Black Hole, the player's: set up from `Native::five`.
    let five = armies == 5;
    if five && m.armies[4].colour != colour::BLACK_HOLE {
        return Err(format!("{}: in a five-army mission the player's army (the fifth) is Black Hole's", m.key));
    }
    let player = if five { 5usize } else { 1 };
    cx.player = player as u8;
    cx.mission = index;
    let (w, h, mut tiles, own_units) = load_map(core, &m.map).map_err(|e| format!("{}: {e}", m.key))?;
    decorate(w, h, &mut tiles, &m.props, &m.structures).map_err(|e| format!("{}: {e}", m.key))?;
    // Scripts and trigger lists.
    let mut turn_start: Vec<Vec<[u8; 8]>> = Vec::new();
    let mut after_action: Vec<Vec<[u8; 8]>> = Vec::new();
    // Starting funds are set on day 1, with the intro.
    let mut intro_cmds = Vec::new();
    for (a, army) in m.armies.iter().enumerate() {
        if let Some(f) = army.funds {
            let s = cx.stub(Magic::Call(FUNDS | (a as u32 + 1), f));
            intro_cmds.push(cmd(0x00, s, 0, 0, 0));
        }
    }
    let intro_scene = cx.scene_cmds(&m.intro)?;
    intro_cmds.extend(intro_scene);
    if !intro_cmds.is_empty() {
        let s = cx.script(intro_cmds);
        turn_start.push(vec![rec8(0, player as u8, 1, 0), rec8(7, 0xFF, 0, s)]);
    }
    let team_of = |a: usize| if m.armies[a - 1].team == 0 { a as u8 } else { m.armies[a - 1].team };
    let player_team = team_of(player);
    let enemy = (1..=armies).find(|&a| team_of(a) != player_team && a != player).unwrap_or(2) as u16;
    for t in &m.triggers {
        let mut cmds = Vec::new();
        let mut ends = false;
        // A trigger that fires once latches a flag of its own.
        let latch = if t.once {
            let f = cx.next_flag;
            cx.next_flag += 1;
            if cx.next_flag == FLAG_HARD {
                cx.next_flag += 1;
            }
            if f > FLAG_LAST {
                return Err("out of trigger flags (96 per campaign)".into());
            }
            cmds.push(cmd(0x44, 0, f as u16, 0, 0));
            Some(f)
        } else {
            None
        };
        for a in &t.then {
            match a {
                Action::Spawn(units) => {
                    for army in 1..=4u8 {
                        let mine: Vec<&UnitDef> = units.iter().filter(|u| u.army == army).collect();
                        if mine.is_empty() {
                            continue;
                        }
                        let s = cx.stub(Magic::Call(SET_ARMY | army as u32, 0));
                        cmds.push(cmd(0x00, s, 0, 0, 0));
                        for u in mine {
                            let s = cx.stub(Magic::Call(SPAWN, u.x as u32 | (u.y as u32) << 8 | (u.kind as u32) << 16));
                            cmds.push(cmd(0x00, s, 0, 0, 0));
                        }
                        let s = cx.stub(Magic::Call(RESTORE_ARMY, 0));
                        cmds.push(cmd(0x00, s, 0, 0, 0));
                    }
                }
                Action::SetCo { army, co } => {
                    let s = cx.stub(Magic::Call(SET_CO | *army as u32, *co as u32));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::Strike { hp } => {
                    // (the power's function, but started on the process tree's
                    // root: `Proc_Start(script, 3)`, not blocking an event
                    // script's proc, which has no parent to hand it)
                    let mut f = crate::co_powers::strike_fn(crate::co_powers::METEOR_SCRIPT, *hp as u16 * 10);
                    f[2..4].copy_from_slice(&0x2103u16.to_le_bytes()); // movs r1, #3
                    let n = f.len();
                    f[n - 4..].copy_from_slice(&0x0801_C8F5u32.to_le_bytes());
                    let at = cx.built.add(&f) | 1;
                    let s = cx.stub(Magic::Call(STRIKE, at));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::Custom(f) => {
                    cx.fns.push(*f);
                    let s = cx.stub(Magic::Call(CUSTOM_FN | (cx.fns.len() as u32 - 1), 0));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::Scene(s) => cmds.extend(cx.scene_cmds(s)?),
                Action::AddFunds { army, funds } => {
                    let s = cx.stub(Magic::Call(FUNDS_ADD | *army as u32, *funds as u32));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::EarnBond(k) => {
                    let s = cx.stub(Magic::Call(BOND | *k as u32, 0));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::SetFunds { army, funds } => {
                    let s = cx.stub(Magic::Call(FUNDS | *army as u32, *funds));
                    cmds.push(cmd(0x00, s, 0, 0, 0));
                }
                Action::Win => {
                    cmds.extend(cx.scene_cmds(&m.victory)?);
                    cmds.push(cmd(0x40, 0, 1, 0, 0));
                    ends = true;
                }
                Action::Lose => {
                    cmds.push(cmd(0x40, 0, enemy, 0, 0));
                    ends = true;
                }
            }
        }
        let _ = ends;
        let script = cx.script(cmds);
        let cond = match latch {
            Some(f) => Cond::All(vec![Cond::Not(Box::new(Cond::Flag(f))), t.cond.clone()]),
            None => t.cond.clone(),
        };
        let pred = cx.cond(index, &cond);
        let group = vec![rec8(5, 0, 0, pred), rec8(7, 0xFF, 0, script)];
        match t.when {
            When::TurnStart => turn_start.push(group),
            When::AfterAction => after_action.push(group),
        }
    }
    let ev = |cx: &mut Compiler, groups: Vec<Vec<[u8; 8]>>| if groups.is_empty() { 0 } else { cx.built.add(&list(groups)) };
    let l0 = ev(cx, turn_start);
    let l3 = ev(cx, after_action);
    let mut hdr6 = Vec::new();
    for t in [l0, 0, 0, l3, 0, 0] {
        hdr6.extend_from_slice(&t.to_le_bytes());
    }
    let events = cx.built.add(&hdr6);
    // Objective script (the map menu's objective): the objective text.
    let obj_id = cx.dialogue(m.objective)?;
    let obj = cx.script(vec![cmd(0x17, 0, 19, 0, 0), cmd(0x38, 0, 19, 0, 0), cmd(0x19, 0, obj_id, 0, 0), cmd(0x18, 0, 0, 0, 0)]);
    let map = cx.built.add(&crate::ds_campaign_data::map_blob(w, h, &tiles));
    let units_bytes = if m.units.is_empty() && matches!(m.map, MapSrc::Built(_)) {
        deployment(Some(&mut cx.units), index, armies, &built_units(&m.map))?
    } else if m.units.is_empty() {
        match own_units {
            Some(u) => u,
            None => deployment(None, index, armies, &[])?,
        }
    } else {
        deployment(Some(&mut cx.units), index, armies, &m.units)?
    };
    let units = cx.built.add(&units_bytes);
    let name_id = cx.text(crate::ds_campaign_data::plain(m.title.as_bytes()))?;
    let info_text = cx.text(crate::ds_campaign_data::two_lines(m.objective.as_bytes(), cx.widths))?;
    // A recruit mission's panel shows a small star once its bond is earned.
    for t in &m.triggers {
        for a in &t.then {
            if let Action::EarnBond(k) = a {
                let plain = cx.built.texts.last().map_or(0, |t| t.1);
                let marked_id = cx.text(crate::ds_campaign_data::two_lines(format!("{} *", m.objective).as_bytes(), cx.widths))?;
                let marked = cx.built.texts.iter().find(|t| t.0 == marked_id).map_or(0, |t| t.1);
                cx.marks.push((info_text, plain, marked, *k));
            }
        }
    }
    let mut hd = [0u8; 0x5C];
    let w32 = |hd: &mut [u8; 0x5C], o: usize, v: u32| hd[o..o + 4].copy_from_slice(&v.to_le_bytes());
    let w16 = |hd: &mut [u8; 0x5C], o: usize, v: u16| hd[o..o + 2].copy_from_slice(&v.to_le_bytes());
    w32(&mut hd, 0x00, map);
    w32(&mut hd, 0x04, events);
    w32(&mut hd, 0x08, obj);
    w16(&mut hd, 0x14, name_id);
    hd[0x16] = 2;
    let structure = crate::survival_maps::Structure::of_tiles(&tiles);
    w32(&mut hd, 0x10, structure.map_or(0, |s| s.aw2_picture()));
    hd[0x17] = m.fog as u8;
    hd[0x18] = armies.min(4) as u8;
    w16(&mut hd, 0x1A, 1);
    w16(&mut hd, 0x1C, 1);
    w16(&mut hd, 0x1E, 1);
    w16(&mut hd, 0x20, if m.rank_days == 0 { 12 } else { m.rank_days });
    w16(&mut hd, 0x22, if m.rank_days == 0 { 12 } else { m.rank_days });
    w16(&mut hd, 0x24, m.day_limit);
    hd[0x26] = 0xFF;
    hd[0x27] = 0;
    hd[0x28] = 1;
    w32(&mut hd, 0x2C, map);
    w32(&mut hd, 0x30, map);
    w32(&mut hd, 0x34, units);
    w32(&mut hd, 0x38, units);
    let mut native = Native::default();
    let mut cos = [(0u8, 0u8); 4];
    let mut colours = [1u8, 2, 3, 4];
    let mut teams = [1u8, 2, 3, 4];
    for k in 0..4 {
        let a = m.armies.get(k);
        let spec = a.map_or(CoSpec::None, |a| a.co);
        let (nat, rec) = co_ids(spec);
        native.cos[k] = nat;
        cos[k] = rec;
        native.funds[k] = a.and_then(|a| a.funds);
        hd[0x3C + k] = nat.0;
        let col = a.map_or(k as u8 + 1, |a| a.colour).clamp(1, 5);
        colours[k] = col;
        hd[0x40 + k] = col;
        let team = a.map_or(k as u8 + 1, |a| if a.team == 0 { k as u8 + 1 } else { a.team });
        teams[k] = team;
        hd[0x44 + k] = team;
        hd[0x48 + 4 * k] = 0xFF;
        hd[0x49 + 4 * k] = 0xFF;
    }
    hd[0x58] = colours[0].clamp(1, 4);
    native.pool = m.pool.clone();
    native.setup = m.setup;
    if five {
        let (co, partner) = match m.armies[4].co {
            CoSpec::Fixed(c) => (c, NO_CO),
            CoSpec::Pair(a, b) => (a, b),
            _ => return Err(format!("{}: a five-army mission's player has a fixed CO or pair (no pick yet)", m.key)),
        };
        native.five = Some((co, partner, team_of(5) - 1));
    }
    let two_front = match (second, &m.front2) {
        (Some(s), Some(f)) => Some(two_front_of(s, f)?),
        _ => None,
    };
    let _ = (def, rec_index);
    let info = MissionInfo {
        index,
        name: m.title.to_string(),
        info_text,
        two_front,
        number: index as u8 + 1,
        cos,
        colours,
        teams,
        armies: armies as u8,
        pool: Vec::new(),
        day_limit: m.day_limit,
        width: w,
        height: h,
        look: m.look,
        weather: m.weather as u8,
        fog: m.fog,
        labs: Vec::new(),
        realtime: 0,
        unit_event_list: 0,
        native: Some(native),
    };
    Ok((hd, info))
}

fn two_front_of(second: u8, f: &FrontDef) -> Result<TwoFront, Error> {
    let mut cos = [NO_CO; 4];
    for (k, c) in f.cos.iter().enumerate() {
        cos[k] = match c {
            CoSpec::Pick => PICK,
            CoSpec::Fixed(c) => *c,
            CoSpec::Pair(a, _) => *a,
            CoSpec::None => NO_CO,
            CoSpec::PickPair => return Err("a second front picks one CO per army".into()),
        };
    }
    Ok(TwoFront {
        second,
        cos,
        control: [FrontControl::Cpu; 4],
        send: f.send,
        powers: false,
        sky: f.sky,
        posture: true,
    })
}

fn compile_second(
    cx: &mut Compiler,
    core: &Core,
    def: &CampaignDef,
    index: usize,
    rec_index: usize,
    m: &MissionDef,
    f: &FrontDef,
) -> Result<([u8; 0x5C], MissionInfo), Error> {
    let armies = m.armies.len();
    let (w, h, mut tiles, own_units) = load_map(core, &f.map).map_err(|e| format!("{} (second front): {e}", m.key))?;
    decorate(w, h, &mut tiles, &f.props, &f.structures).map_err(|e| format!("{} (second front): {e}", m.key))?;
    let map = cx.built.add(&crate::ds_campaign_data::map_blob(w, h, &tiles));
    let units_bytes = if f.units.is_empty() {
        own_units.unwrap_or(deployment(None, index, armies, &[])?)
    } else {
        // (named units are the main front's)
        deployment(None, index, armies, &f.units)?
    };
    let units = cx.built.add(&units_bytes);
    let events = cx.built.add(&[0u8; 24]);
    let mut hd = [0u8; 0x5C];
    hd[0..4].copy_from_slice(&map.to_le_bytes());
    hd[4..8].copy_from_slice(&events.to_le_bytes());
    hd[0x16] = 2;
    hd[0x17] = f.fog as u8;
    hd[0x18] = armies as u8;
    hd[0x1A] = 1;
    hd[0x1C] = 1;
    hd[0x1E] = 1;
    hd[0x26] = 0xFF;
    hd[0x28] = 1;
    hd[0x2C..0x30].copy_from_slice(&map.to_le_bytes());
    hd[0x30..0x34].copy_from_slice(&map.to_le_bytes());
    hd[0x34..0x38].copy_from_slice(&units.to_le_bytes());
    hd[0x38..0x3C].copy_from_slice(&units.to_le_bytes());
    let mut native = Native::default();
    let mut cos = [(0u8, 0u8); 4];
    let mut colours = [1u8, 2, 3, 4];
    let mut teams = [1u8, 2, 3, 4];
    for k in 0..4 {
        let a = m.armies.get(k);
        let spec = f.cos[k];
        let (nat, rec) = co_ids(spec);
        native.cos[k] = nat;
        cos[k] = (rec.0, 0);
        hd[0x3C + k] = nat.0;
        colours[k] = a.map_or(k as u8 + 1, |a| a.colour).clamp(1, 5);
        hd[0x40 + k] = colours[k];
        teams[k] = a.map_or(k as u8 + 1, |a| if a.team == 0 { k as u8 + 1 } else { a.team });
        hd[0x44 + k] = teams[k];
        hd[0x48 + 4 * k] = 0xFF;
        hd[0x49 + 4 * k] = 0xFF;
    }
    hd[0x58] = colours[0].clamp(1, 4);
    let _ = (def, rec_index);
    let info = MissionInfo {
        index: rec_index,
        name: format!("{} (second front)", m.title),
        info_text: 0,
        two_front: None,
        number: index as u8 + 1,
        cos,
        colours,
        teams,
        armies: armies as u8,
        pool: Vec::new(),
        day_limit: 0,
        width: w,
        height: h,
        look: 0,
        weather: f.weather as u8,
        fog: f.fog,
        labs: Vec::new(),
        realtime: 0,
        unit_event_list: 0,
        native: Some(native),
    };
    Ok((hd, info))
}

// --- Rules at run time -----------------------------------------------------------

const PLAYERS_PTR: u32 = 0x0849_9598;
const UNITS_PTR: u32 = 0x0849_9594;
const PLAYER: u32 = 0x3C;
const UNIT: u32 = 12;
const DAY: u32 = 0x0300_4080;
const CURRENT_ARMY: u32 = 0x0300_33EC;
/// `CreateUnitAt(x, y, type)`: a unit of the army moving now.
const CREATE_UNIT_AT: u32 = 0x0802_5CC8;

fn unit_addr(core: &Core, army: u8, slot: u8) -> u32 {
    // (a five-army battle gives army a the ids (a - 1) * 51 + 1.., crate::five)
    let stride = if crate::five::active(core) { 51 } else { 64 };
    core.raw_read_32(UNITS_PTR, -1) + UNIT * ((army as u32 - 1) * stride + slot as u32)
}

/// The death latch (one bit per named unit of the mission, set for good once
/// its record is empty, so a built unit reusing its slot is not it; bits
/// 24..31 are scratch) lives in the countdown's word (crate::ds_campaign::
/// COUNTDOWN, which the mission start clears and a mission saved halfway keeps).
pub const LATCH: u32 = crate::ds_campaign::COUNTDOWN;
const SCRATCH: u32 = LATCH + 3;

/// The named unit's record, and whether it is alive.
pub fn unit_by_name(core: &Core, name: &str) -> Option<(u32, bool)> {
    let src = crate::ds_campaign::source(core);
    let rules = RULES.get(src)?.get()?;
    let mission = crate::ds_campaign::mission(core) as usize;
    let (_, &(army, slot, bit)) = rules.units.iter().find(|(k, _)| k.0 == mission && k.1 == name)?;
    let a = unit_addr(core, army, slot);
    let dead = core.raw_read_32(LATCH, -1) >> bit & 1 != 0;
    Some((a, core.raw_read_8(a, -1) != 0 && !dead))
}

fn named(core: &Core, name: &'static str) -> Option<(u32, bool)> {
    unit_by_name(core, name)
}

/// An army's live units: (record, type, x, y).
pub fn units_of(core: &Core, army: u8) -> Vec<(u32, u8, u8, u8)> {
    (1..=50u8)
        .filter_map(|s| {
            let a = unit_addr(core, army, s);
            let t = core.raw_read_8(a, -1);
            (t != 0).then(|| (a, t, core.raw_read_8(a + 2, -1), core.raw_read_8(a + 3, -1)))
        })
        .collect()
}

/// The day.
pub fn day(core: &Core) -> u16 {
    core.raw_read_16(DAY, -1)
}

const MAP: u32 = 0x0201_E450;

/// The owner of the cell (0 neutral, 1..4): the terrain class byte's bits 5..7.
fn owner_at(core: &Core, x: u8, y: u8) -> u8 {
    let row = core.raw_read_16(MAP + 0x417A + 2 * y as u32, -1) as u32;
    core.raw_read_8(MAP + 0x1432 + row + x as u32, -1) >> 5
}

/// Every frame in a custom campaign's battle: the named units that are gone
/// stay gone ([`LATCH`]).
pub fn tick(core: &mut Core) {
    let src = crate::ds_campaign::source(core);
    let Some(rules) = RULES.get(src).and_then(|r| r.get()) else { return };
    let mission = crate::ds_campaign::mission(core) as usize;
    let mut latch = core.raw_read_32(LATCH, -1);
    let before = latch;
    for (k, &(army, slot, bit)) in rules.units.iter().filter(|(k, _)| k.0 == mission).map(|(k, v)| (k, v)) {
        let _ = k;
        if core.raw_read_8(unit_addr(core, army, slot), -1) == 0 {
            latch |= 1 << bit;
        }
    }
    if latch != before {
        core.raw_write_32(LATCH, -1, latch);
    }
}

/// The mission's own battle song: while a session is on and the selected
/// mission declares one, every CO's theme in the CO table (the pack's copy,
/// [`crate::co_roster::TABLE`], row +4) is that song, so every army's turn
/// plays it; the themes are put back when the session is over or the mission
/// has none.
pub fn music_tick(core: &mut Core, session: bool) {
    static SAVED: std::sync::Mutex<Vec<u16>> = std::sync::Mutex::new(Vec::new());
    let want = if session {
        crate::ds_campaign::campaign(core)
            .and_then(|c| c.model.custom.as_ref())
            .and_then(|c| c.music.get(crate::ds_campaign::mission(core) as usize).copied().flatten())
    } else {
        None
    };
    let mut saved = SAVED.lock().unwrap();
    let rows = crate::co_roster::ROOM;
    let at = |co: u32| crate::co_roster::TABLE + crate::co_roster::ROW * co + 4;
    match want {
        Some(song) => {
            if saved.is_empty() {
                *saved = (0..rows).map(|co| core.raw_read_16(at(co), -1)).collect();
            }
            for co in 0..rows {
                if core.raw_read_16(at(co), -1) != song {
                    core.raw_write_16(at(co), -1, song);
                }
            }
        }
        None => {
            if !saved.is_empty() {
                for (co, &s) in saved.iter().enumerate() {
                    core.raw_write_16(at(co as u32), -1, s);
                }
                saved.clear();
            }
        }
    }
}

/// Evaluates a condition on the live battle.
pub fn holds(core: &mut Core, c: &Cond) -> bool {
    match c {
        Cond::DayAtLeast(d) => core.raw_read_16(DAY, -1) >= *d,
        Cond::EveryDays { n, from } => {
            let d = core.raw_read_16(DAY, -1);
            d >= *from && *n > 0 && (d - from) % n == 0
        }
        Cond::UnitAt { name, x, y } => {
            named(core, name).is_some_and(|(a, alive)| alive && core.raw_read_8(a + 2, -1) == *x && core.raw_read_8(a + 3, -1) == *y)
        }
        Cond::NamedIn { name, area } => {
            named(core, name).is_some_and(|(a, alive)| alive && area.has(core.raw_read_8(a + 2, -1), core.raw_read_8(a + 3, -1)))
        }
        Cond::UnitAlive(n) => named(core, n).is_some_and(|(_, alive)| alive),
        Cond::UnitGone(n) => named(core, n).is_some_and(|(_, alive)| !alive),
        Cond::ArmyUnitsAtMost { army, n } => units_of(core, *army).len() <= *n as usize,
        Cond::UnitsIn { army, area, at_least } => units_of(core, *army).iter().filter(|u| area.has(u.2, u.3)).count() >= *at_least as usize,
        Cond::PropertiesAtLeast { army, n } => {
            crate::ds_campaign_rules::predicate(core, crate::ds_campaign_data::PROPERTY_COUNT | (*army as u32) << 8 | *n as u32)
        }
        Cond::PlayerHas(c) => {
            let army = crate::ds_campaign::player_army(core) as u32;
            crate::tag::army_co_of(core, army) == *c || crate::tag::partner(core, army) == Some(*c)
        }
        Cond::PartnerCo(c) => crate::tag::partner(core, crate::ds_campaign::player_army(core) as u32) == Some(*c),
        Cond::PlayerCo(c) => crate::tag::army_co_of(core, crate::ds_campaign::player_army(core) as u32) == *c,
        Cond::OwnerAt { x, y, army } => owner_at(core, *x, *y) == *army,
        Cond::ArmyDefeated(army) => {
            let p = core.raw_read_32(PLAYERS_PTR, -1) + PLAYER * *army as u32;
            core.raw_read_16(p + 0x14, -1) != 0
        }
        Cond::PlayerPair { a, b } => {
            let player = crate::ds_campaign::player_army(core) as u32;
            let lead = crate::tag::army_co_of(core, player);
            let partner = crate::tag::partner(core, player);
            (lead == *a && partner == Some(*b)) || (lead == *b && partner == Some(*a))
        }
        Cond::OnyxHitsAtMost(n) => crate::onyx::reversed_hits(core).is_some_and(|h| h <= *n),
        Cond::OnyxDestroyed => crate::onyx::reversed_hits(core) == Some(0),
        Cond::Flag(f) => crate::ds_campaign::campaign_flag(core, *f as u32),
        Cond::Not(c) => !holds(core, c),
        Cond::All(cs) => cs.iter().all(|c| holds(core, c)),
        Cond::Any(cs) => cs.iter().any(|c| holds(core, c)),
        Cond::Custom(f) => f(core),
    }
}

/// The army moving now, and its first unit id (the game keeps both).
fn set_current_army(core: &mut Core, army: u8) {
    const CURRENT_BASE: u32 = 0x0300_3F2C;
    let stride = if crate::five::active(core) { 51 } else { 64 };
    core.raw_write_16(CURRENT_ARMY, -1, army as u16);
    core.raw_write_16(CURRENT_BASE, -1, (army.max(1) as u16 - 1) * stride);
}

/// A custom campaign's magic functions: its conditions and actions.
pub fn rules(core: &mut Core, m: &Magic) -> u32 {
    match *m {
        Magic::Predicate(code) if code & 0xFF00_0000 == PRED => {
            let src = crate::ds_campaign::source(core);
            let cond = RULES.get(src).and_then(|r| r.get()).and_then(|r| r.conds.iter().find(|c| c.0 == code)).map(|c| c.1.clone());
            cond.is_some_and(|c| holds(core, &c)) as u32
        }
        Magic::Call(f, funds) if f & 0xFFF0_0000 == FUNDS => {
            let army = (f & 0xF) as u32;
            let p = core.raw_read_32(PLAYERS_PTR, -1) + PLAYER * army;
            core.raw_write_32(p, -1, funds);
            0
        }
        Magic::Call(f, delta) if f & 0xFFF0_0000 == FUNDS_ADD => {
            let army = (f & 0xF) as u32;
            let p = core.raw_read_32(PLAYERS_PTR, -1) + PLAYER * army;
            let v = (core.raw_read_32(p, -1) as i64 + delta as i32 as i64).clamp(0, 999_999) as u32;
            core.raw_write_32(p, -1, v);
            0
        }
        Magic::Call(f, _) if f & 0xFFF0_0000 == SET_ARMY => {
            let army = core.raw_read_16(CURRENT_ARMY, -1) as u8;
            core.raw_write_8(SCRATCH, -1, army);
            set_current_army(core, (f & 0xF) as u8);
            0
        }
        Magic::Call(RESTORE_ARMY, _) => {
            let army = core.raw_read_8(SCRATCH, -1);
            set_current_army(core, army);
            core.raw_write_8(SCRATCH, -1, 0);
            0
        }
        Magic::Call(SPAWN, packed) => {
            let (x, y, kind) = (packed as u8, (packed >> 8) as u8, (packed >> 16) as u8);
            let row = core.raw_read_16(MAP + 0x417A + 2 * y as u32, -1) as u32;
            if core.raw_read_8(MAP + 0x12 + row + x as u32, -1) != 0 {
                return 0;
            }
            let cpu = core.gba_mut().cpu_mut();
            cpu.set_gpr(0, x as i32);
            cpu.set_gpr(1, y as i32);
            cpu.set_gpr(2, kind as i32);
            cpu.set_thumb_pc(CREATE_UNIT_AT);
            crate::campaign_model::TAIL_CALLED
        }
        Magic::Call(STRIKE, at) => {
            // (the script's proc is r0, as the power's function gets it)
            core.gba_mut().cpu_mut().set_thumb_pc(at & !1);
            crate::campaign_model::TAIL_CALLED
        }
        Magic::Call(f, co) if f & 0xFFF0_0000 == SET_CO => {
            let p = core.raw_read_32(PLAYERS_PTR, -1) + PLAYER * (f & 0xF);
            core.raw_write_8(p + 0x1D, -1, co as u8);
            0
        }
        Magic::Call(f, _) if f & 0xFFF0_0000 == CUSTOM_FN => {
            let src = crate::ds_campaign::source(core);
            let func = RULES.get(src).and_then(|r| r.get()).and_then(|r| r.fns.get((f & 0xFFFF) as usize).copied());
            if let Some(func) = func {
                func(core);
            }
            0
        }
        Magic::Call(f, _) if f & 0xFFF0_0000 == BOND => {
            crate::ds_campaign::earn_bond(core, (f & 0xF) as u8);
            0
        }
        _ => 0,
    }
}

/// The roster index of an AW2 CO, if it is in the campaign's roster.
pub fn roster_index(model: &Model, co: u8) -> Option<usize> {
    model.custom.as_ref()?.roster.iter().position(|&(c, _)| c == co)
}

/// A CO's country as the CO screen's tabs number them (0 Orange Star, 1
/// Blue Moon, 2 Green Earth, 3 Yellow Comet, 4 Black Hole).
pub fn country(co: u8) -> u8 {
    if co == crate::co_new::CLONE_ANDY {
        return 4;
    }
    match crate::co_roster::ds_co(co) {
        Some(d) => crate::ds_campaign_rules::country(d),
        None => 4,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn property_tiles() {
        assert_eq!(property_tile(PropKind::Hq, 1), 0x1C5);
        assert_eq!(property_tile(PropKind::City, 0), 0x1C2);
    }

    #[test]
    fn stamps_fit() {
        let mut t = vec![PLAIN; 100];
        decorate(10, 10, &mut t, &[], &[(Structure::BlackFactory, 5, 5)]).unwrap();
        assert_eq!(t[5 * 10 + 5], 0x18D);
        assert!(decorate(10, 10, &mut t, &[], &[(Structure::BlackFactory, 0, 0)]).is_err());
    }

    #[test]
    fn faces() {
        assert_eq!(face(Speaker::Co(10, Mood::Happy)), 34);
        assert_eq!(face(Speaker::Trooper(5)), 23);
    }
}
