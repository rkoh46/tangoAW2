//! Act 2: Green Earth (M4 to M10) and the pass out of it (M11). Its missions
//! are `MissionDef`s (docs/AW2.md "BH Campaign": adding a mission); this file
//! is the act's alone, so builders can work on acts in parallel. A mission
//! names what it needs by key (`Needs::All(vec!["bh03"])`), not by index.
//!
//! The maps are `five/bh/bh04.txt` .. `bh11.txt` (built by `five/bhmap.py`
//! into `bh_map_data.rs`: roads, rivers, coasts and shoals joined as AW2 draws
//! them, reachability checked). The dialogue is the design bible's
//! (docs/BH_CAMPAIGN.md section 4.3, branch bh-design): a design row is one
//! box, its `@IF CO` groups are [`Line::only`] lines, its soldiers and
//! narration the Black Hole trooper's face.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::campaign_model::SendRule;
use crate::custom_campaign::{co, colour, unit, *};

// --- Writing helpers ---------------------------------------------------------------

/// The mission's rule "on day `d`, at the start of the player's turn, do these": fires once, on that
/// day (`EveryDays` with a period no mission reaches), without taking one of the campaign's 96
/// once-latch flags.
fn on_day(d: u16, cond: Option<Cond>, then: Vec<Action>) -> Trigger {
    let day = Cond::EveryDays { n: 1000, from: d };
    let cond = match cond {
        Some(c) => Cond::All(vec![day, c]),
        None => day,
    };
    Trigger::new(When::TurnStart, cond, then).repeating()
}

/// After each action, while the condition holds (a win or a loss: the match ends; or a one-way event).
fn after(cond: Cond, then: Vec<Action>) -> Trigger {
    Trigger::new(When::AfterAction, cond, then).repeating()
}

/// The enemy army is as good as routed: at most one unit left (the match's own rout, the last unit's
/// death, is decided before a trigger can play the victory scene and earn the bond), or its HQ is the
/// player's.
fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: 1 }])
}

/// An army's CO meter set to `pct` of its full meter (AW2's units: a CO Power's cost, `cop_cost`,
/// is the first power's full bar).
fn meter(core: &mut Core, army: u32, pct: u32) {
    let p = crate::tag::player(core, army);
    let co = crate::tag::army_co_of(core, army);
    let uses = core.raw_read_8(p + 0x25, -1);
    let full = crate::tag::cop_cost(core, co, uses);
    core.raw_write_32(p + 0x20, -1, full * pct / 100);
}

fn charge_army2_full(core: &mut Core) {
    meter(core, 2, 100);
}

fn charge_army2_60(core: &mut Core) {
    meter(core, 2, 60);
}

/// The units of a built map's text file, for a second front (whose deployment is the front's own).
fn built_units(name: &str) -> Vec<UnitDef> {
    let Some(m) = crate::bh_map_data::MAPS.iter().find(|m| m.name == name) else { return Vec::new() };
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
}

// --- The enemy's AI roles ----------------------------------------------------------
//
// The roles are `bh_ai`'s (Infantry and Mechs capture, vehicles, indirect fire, aircraft and ships attack units, a
// transport keeps its own logic); the map files' `hold` flag (AW2's role 1) is not used. What holds is each mission's
// deliberate garrison, by cell: the HQ guard (one soldier beside the HQ), M5's HQ and Com Tower crew (the raiders'
// target; the rest of the night crew scrambles, the aircraft stay parked), M9's yard guard at the port and M10's
// Citadel guns.

const ROLE_MISSIONS: [&str; 8] = ["bh04", "bh05", "bh06", "bh07", "bh08", "bh09", "bh10", "bh11"];

/// The cells of each mission's holders.
fn garrison(key: &str) -> &'static [(u8, u8)] {
    match key {
        "bh04" => &[(20, 8), (20, 10)],
        "bh05" => &[(19, 4), (20, 6)],
        "bh06" => &[(28, 15)],
        "bh07" => &[(26, 19)],
        "bh08" => &[(22, 8)],
        "bh09" => &[(23, 5), (23, 9), (24, 6), (24, 8)],
        "bh10" => &[(11, 4), (17, 4), (13, 4), (15, 4), (12, 3)],
        "bh11" => &[(24, 5), (24, 14)],
        _ => &[],
    }
}

fn apply_roles(v: &mut [MissionDef]) {
    for key in ROLE_MISSIONS {
        let Some(m) = v.iter_mut().find(|m| m.key == key) else { continue };
        let base = if m.units.is_empty() {
            match &m.map {
                MapSrc::Built(n) => built_units(n),
                _ => Vec::new(),
            }
        } else {
            std::mem::take(&mut m.units)
        };
        m.units = crate::bh_ai::orders_at(base, 1, crate::bh_ai::ATTACK, garrison(key));
        if let Some(f) = &mut m.front2 {
            f.units = crate::bh_ai::orders_at(std::mem::take(&mut f.units), 1, crate::bh_ai::ATTACK, &[]);
        }
    }
}

// --- World map ---------------------------------------------------------------------

/// Act 2's flags on AW2's Green Earth (the east land, x 300..390, y 85..230), in the design's order
/// (docs/BH_CAMPAIGN.md 2.2, the grid mirrored onto the picture): M4 .. M11. M6 and M7 are the branch.
pub const FLAGS: [(i16, i16); 8] = [
    (365, 92),  // M4 Marshal in Green (north)
    (372, 118), // M5 Night Raid
    (332, 135), // M6 Stepping Stones (west coast, isles)
    (345, 160), // M7 Greenhaven Arsenal (south coast)
    (350, 135), // M8 The Twin Gates (heartland)
    (325, 190), // M9 The Loot Train
    (340, 215), // M10 Evergreen Citadel
    (333, 106), // M11 Exiles' Last Stand (the pass towards Yellow Comet)
];

// --- M4 Marshal in Green -------------------------------------------------------------

fn bh04() -> MissionDef {
    let mut m = MissionDef::new("bh04", "Marshal in Green");
    m.objective = "Capture Fort Verdant or rout Hawke.";
    m.map = MapSrc::Built("bh04");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)).funds(10000),
        // Hawke commands Green Earth's northern army in its colours.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::HAWKE)).funds(8000),
    ];
    m.fog = true;
    m.day_limit = 0;
    m.rank_days = 12;
    m.intro = crate::bh_text::scene("m04_pre");
    m.victory = crate::bh_text::scene("m04_post");
    m.after = crate::bh_text::scene("m04_map");
    m.triggers = vec![
        // Hawke's Md Tank wedge arrives on day 4 if the Marshal's valley was not scouted.
        on_day(
            4,
            Some(Cond::Not(Box::new(Cond::UnitsIn { army: 1, area: Rect::new(10, 0, 23, 17), at_least: 1 }))),
            vec![Action::Scene(crate::bh_text::scene("m04_wedge")), Action::Spawn(vec![
                UnitDef::new(2, unit::MD_TANK, 16, 8),
                UnitDef::new(2, unit::MD_TANK, 16, 10),
            ])],
        ),
        on_day(5, None, vec![Action::Scene(crate::bh_text::scene("m04_day5"))]),
        // Hawke's power is charged by day 6.
        on_day(6, None, vec![Action::Custom(charge_army2_full)]),
        on_day(10, None, vec![Action::Scene(crate::bh_text::scene("m04_day10"))]),
        // The win (the pitch is the victory scene; the bond is earned with it).
        after(beaten(2, (21, 9)), vec![Action::EarnBond(1), Action::Win]),
    ];
    m.recruits = vec![roster::HAWKE];
    m.needs = Needs::All(vec!["bh03"]);
    m.flag = FLAGS[0];
    m.stars = 2;
    m
}


// --- M5 Night Raid -------------------------------------------------------------------

/// Every parked aircraft of Green Earth (Fighters and Bombers) is destroyed.
fn aircraft_destroyed(core: &mut Core) -> bool {
    units_of(core, 2).iter().all(|u| u.1 != unit::FIGHTER && u.1 != unit::BOMBER)
}

fn bh05() -> MissionDef {
    let mut m = MissionDef::new("bh05", "Night Raid");
    m.objective = "Destroy 8 aircraft, take the Com Tower. 9 days.";
    m.map = MapSrc::Built("bh05");
    // The parked aircraft stay parked: AI byte 6 (measured: bytes 1..5 let them fly off and strike; 6 holds them
    // where they stand), with no ammunition (the crews are asleep): grounded targets. The alarm
    // wave carries the threat; the engine has no rearm action, so they are not scrambled.
    m.units = built_units("bh05")
        .into_iter()
        .map(|mut u| {
            if u.army == 2 && (u.kind == unit::FIGHTER || u.kind == unit::BOMBER) {
                // Unmanned planes on a night raid: empty guns, held where they stand (a thimble of fuel would crash them on day 2).
                u.ai = 6;
                u = u.ammo(0);
            }
            u
        })
        .collect();
    // A pre-deployed raid: no bases, no funds, on either side.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 9;
    m.rank_days = 7;
    m.intro = crate::bh_text::scene("m05_pre");
    m.victory = crate::bh_text::scene("m05_post");
    m.after = crate::bh_text::scene("m05_map");
    m.triggers = vec![
        // The alarm: two Tanks and an Anti-Air arrive by the east road (the design's three and two, trimmed: measured too strong).
        on_day(
            3,
            None,
            vec![
                Action::Scene(crate::bh_text::scene("m05_day3")),
                Action::Spawn(vec![
                    UnitDef::new(2, unit::TANK, 23, 8),
                    UnitDef::new(2, unit::TANK, 23, 7),
                    UnitDef::new(2, unit::ANTI_AIR, 23, 9),
                ]),
            ],
        ),
        on_day(6, None, vec![Action::Scene(crate::bh_text::scene("m05_day6"))]),
        // Eight aircraft gone and the tower taken.
        after(Cond::All(vec![Cond::Custom(aircraft_destroyed), Cond::OwnerAt { x: 19, y: 3, army: 1 }]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh04"]);
    m.flag = FLAGS[1];
    m.stars = 2;
    m
}

// --- M6 Stepping Stones --------------------------------------------------------------

fn bh06() -> MissionDef {
    let mut m = MissionDef::new("bh06", "Stepping Stones");
    m.objective = "Hop the isles and capture Drake's HQ.";
    m.map = MapSrc::Built("bh06");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).funds(14000),
    ];
    m.day_limit = 0;
    m.rank_days = 16;
    m.intro = crate::bh_text::scene("m06_pre");
    m.victory = crate::bh_text::scene("m06_post");
    m.after = crate::bh_text::scene("m06_map");
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(crate::bh_text::scene("m06_day5"))]),
        // The Carrier launches Fighters every third day from day 5 (from its isle's air).
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 3, from: 5 }, vec![Action::Spawn(vec![UnitDef::new(2, unit::FIGHTER, 24, 10)])]).repeating(),
        on_day(12, None, vec![Action::Scene(crate::bh_text::scene("m06_day12"))]),
        after(beaten(2, (28, 14)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh05"]);
    m.flag = FLAGS[2];
    m.stars = 2;
    m
}

// --- M7 Greenhaven Arsenal -----------------------------------------------------------

/// Factory table F7 (docs/BH_CAMPAIGN.md 3.5): per day the three doors' units (0 none).
const F7: [(u8, [u8; 3]); 11] = [
    (2, [unit::TANK, 0, unit::TANK]),
    (3, [0, unit::ANTI_AIR, 0]),
    (4, [unit::MD_TANK, 0, 0]),
    (5, [unit::MISSILES, unit::MECH, 0]),
    (6, [0, unit::NEOTANK, 0]),
    (7, [unit::INFANTRY, unit::INFANTRY, unit::INFANTRY]),
    (9, [0, unit::RECON, unit::ANTI_AIR]),
    (11, [unit::MD_TANK, 0, unit::MD_TANK]),
    (13, [0, unit::MD_TANK, 0]),
    (15, [unit::NEOTANK, 0, unit::ANTI_AIR]),
    (17, [unit::MD_TANK, 0, unit::MD_TANK]),
];

fn bh07() -> MissionDef {
    let mut m = MissionDef::new("bh07", "Greenhaven Arsenal");
    m.objective = "Wake the Black Factory, take Eagle's HQ.";
    m.map = MapSrc::Built("bh07");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::HAWKE)).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).funds(26000),
    ];
    m.day_limit = 0;
    m.rank_days = 16;
    m.factory = F7.to_vec();
    // The port at (9, 20) is Black Hole's (the map tool owns a property by the nearest HQ).
    m.props = vec![Prop { kind: PropKind::Port, owner: 1, x: 9, y: 20 }];
    m.intro = crate::bh_text::scene("m07_pre");
    m.victory = crate::bh_text::scene("m07_post");
    m.after = crate::bh_text::scene("m07_map");
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(crate::bh_text::scene("m07_day6"))]),
        // Eagle's funds: +5000 on day 10, a second Bomber on day 12.
        on_day(10, None, vec![Action::Scene(crate::bh_text::scene("m07_day10")), Action::AddFunds { army: 2, funds: 5000 }]),
        on_day(12, None, vec![Action::Scene(crate::bh_text::scene("m07_day12")), Action::Spawn(vec![UnitDef::new(2, unit::BOMBER, 26, 14)])]),
        on_day(
            13,
            None,
            vec![Action::Scene(crate::bh_text::scene("m07_day13"))],
        ),
        after(beaten(2, (25, 19)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh05"]);
    m.flag = FLAGS[3];
    m.stars = 2;
    m
}

// --- M8 The Twin Gates ---------------------------------------------------------------

/// The second front's outcome (crate::two_front's state byte: 2 won, 3 lost).
fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn second_front_lost(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 3
}

fn bh08() -> MissionDef {
    let mut m = MissionDef::new("bh08", "The Twin Gates");
    m.objective = "Take both gates. The dusk gate's CO joins.";
    m.map = MapSrc::Built("bh08");
    // The player picks two COs: the main front's, then the second front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(11000),
    ];
    m.day_limit = 0;
    m.rank_days = 16;
    // The dusk gate's Black Factory is dormant (an all-zero table): AW2's computer-Black-Hole turn calls
    // the factory spawner, which on a map without a factory wrote garbage and reset the game on day 2 (the
    // player's army there is played by Auto CO).
    m.factory = vec![(0, [0, 0, 0])];
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh08b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: built_units("bh08b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::JAVIER), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = crate::bh_text::scene("m08_pre");
    m.victory = crate::bh_text::scene("m08_post");
    m.after = crate::bh_text::scene("m08_map");
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(crate::bh_text::scene("m08_front2_post"))]),
        Trigger::new(
            When::TurnStart,
            Cond::Custom(second_front_lost),
            vec![Action::Scene(crate::bh_text::scene("m08_front2_lost"))],
        ),
        after(beaten(2, (22, 9)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh06", "bh07"]);
    m.flag = FLAGS[4];
    m.stars = 3;
    m
}

// --- M9 The Loot Train ---------------------------------------------------------------

/// The loading yard at the east end (the rail depot's city at (26, 7)): where the Vault APCs must arrive.
const PORT_YARD: Rect = Rect::new(24, 6, 27, 8);
const VAULTS: [&str; 3] = ["vault1", "vault2", "vault3"];

/// (Vault APCs alive, of them in the port's yard).
fn vaults(core: &mut Core) -> (usize, usize) {
    let (mut alive, mut home) = (0, 0);
    for n in VAULTS {
        if let Some((a, true)) = unit_by_name(core, n) {
            alive += 1;
            if PORT_YARD.has(core.raw_read_8(a + 2, -1), core.raw_read_8(a + 3, -1)) {
                home += 1;
            }
        }
    }
    (alive, home)
}

/// All three trucks are home.
fn all_three_home(core: &mut Core) -> bool {
    vaults(core) == (3, 3)
}

/// Two trucks are home and the third is gone.
fn two_home_third_gone(core: &mut Core) -> bool {
    vaults(core) == (2, 2)
}

/// Fewer than two trucks survive.
fn trucks_lost(core: &mut Core) -> bool {
    vaults(core).0 < 2
}

/// A truck has passed the first bridge (x = 8): Javier's comms raise the alarm.
fn alarm(core: &mut Core) -> bool {
    VAULTS.iter().any(|n| unit_by_name(core, n).is_some_and(|(a, alive)| alive && core.raw_read_8(a + 2, -1) >= 8))
}

fn bh09() -> MissionDef {
    let mut m = MissionDef::new("bh09", "The Loot Train");
    m.objective = "Escort 2 of 3 Vault APCs to the loading yard.";
    m.map = MapSrc::Built("bh09");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::VON_BOLT)).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::JAVIER, co::DRAKE)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 16;
    m.rank_days = 12;
    m.intro = crate::bh_text::scene("m09_pre");
    m.after = crate::bh_text::scene("m09_map");
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(crate::bh_text::scene("m09_day4"))]),
        on_day(9, None, vec![Action::Scene(crate::bh_text::scene("m09_day9"))]),
        // Javier's comms: a truck past the first bridge wakes a pursuit behind it.
        Trigger::new(
            When::AfterAction,
            Cond::Custom(alarm),
            vec![Action::Spawn(vec![
                // (the pursuit chases the trucks: role 4, not the default HQ role, which would stop at Von Bolt's HQ beside them)
                UnitDef::new(2, unit::TANK, 0, 6).attack(),
                UnitDef::new(2, unit::TANK, 0, 8).attack(),
                UnitDef::new(2, unit::RECON, 0, 7).attack(),
            ])],
        ),
        after(
            Cond::Custom(all_three_home),
            vec![
                Action::Scene(crate::bh_text::scene("m09_all_home")),
                Action::Win,
            ],
        ),
        after(
            Cond::Custom(two_home_third_gone),
            vec![
                Action::Scene(crate::bh_text::scene("m09_two_home")),
                Action::Win,
            ],
        ),
        after(Cond::Custom(trucks_lost), vec![Action::Lose]),
    ];
    m.needs = Needs::All(vec!["bh08"]);
    m.flag = FLAGS[5];
    m.stars = 3;
    m
}

// --- M10 Evergreen Citadel -----------------------------------------------------------

fn bh10() -> MissionDef {
    let mut m = MissionDef::new("bh10", "Evergreen Citadel");
    m.objective = "Siege the Citadel and capture its HQ.";
    m.map = MapSrc::Built("bh10");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::HAWKE)).funds(8000),
        // Production is deliberate: Green Earth owns two bases and an airport (all kept clear of units) and starts
        // with 4000, so the garrison is reinforced by a couple of units early and then only by city income;
        // Black Hole owns a base, an airport and its Fighter.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::EAGLE, co::JESS)).funds(4000),
    ];
    m.day_limit = 0;
    m.rank_days = 16;
    m.intro = crate::bh_text::scene("m10_pre");
    m.victory = crate::bh_text::scene("m10_post");
    // The end of Act II: Crumb's flag, then the Allied council Hawke's listening post intercepts.
    m.after = Scene::new({
        let mut v = crate::bh_text::lines("m10_map");
        v.extend(crate::bh_text::lines("m10_warroom"));
        v
    });
    m.triggers = vec![
        // Eagle and Jess start with their powers 60% charged.
        on_day(1, None, vec![Action::Custom(charge_army2_60)]),
        on_day(6, None, vec![Action::Scene(crate::bh_text::scene("m10_day6"))]),
        on_day(12, None, vec![Action::Scene(crate::bh_text::scene("m10_day12"))]),
        after(beaten(2, (14, 3)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh09"]);
    m.flag = FLAGS[6];
    m.stars = 3;
    m
}

// --- M11 Exiles' Last Stand ----------------------------------------------------------

fn bh11() -> MissionDef {
    let mut m = MissionDef::new("bh11", "Ashfall Pass");
    m.objective = "Break Green Earth and Yellow Comet under Mount Ember.";
    m.map = MapSrc::Built("bh11");
    m.look = 3; // the Wasteland look: ash and cinder
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::VON_BOLT, co::HAWKE)).funds(14000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).team(2).funds(11000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).team(2).funds(11000),
    ];
    m.day_limit = 0;
    m.rank_days = 16;
    m.intro = crate::bh_text::scene("m11_pre");
    m.victory = crate::bh_text::scene("m11_post");
    m.after = crate::bh_text::scene("m11_map");
    let paratroopers = vec![
        UnitDef::new(3, unit::INFANTRY, 1, 6),
        UnitDef::new(3, unit::INFANTRY, 1, 12),
        UnitDef::new(3, unit::INFANTRY, 2, 7),
        UnitDef::new(3, unit::INFANTRY, 2, 11),
        UnitDef::new(3, unit::INFANTRY, 3, 6),
    ];
    m.triggers = vec![
        // TODO(engine): from day 3 Mount Ember erupts once a day on 3 marked cells of the Rim Track (the 28 cells
        // of the road ring round it), marked a turn ahead, hitting any army's units there for 5 HP (never below
        // 1): hook the eruption call here (`ds_campaign_rules`' volcano) when the engine has it. Today the
        // volcano is the map's picture and its mountains; the day 3 and day 8 scenes below play on their days.
        on_day(
            3,
            None,
            vec![Action::Scene(crate::bh_text::scene("m11_day3"))],
        ),
        on_day(5, None, vec![Action::Scene(crate::bh_text::scene("m11_day5")), Action::Spawn(paratroopers.clone())]),
        on_day(8, None, vec![Action::Scene(crate::bh_text::scene("m11_day8"))]),
        on_day(10, None, vec![Action::Spawn(paratroopers)]),
        after(Cond::All(vec![beaten(2, (25, 3)), beaten(3, (25, 17))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh10"]);
    m.flag = FLAGS[7];
    m.stars = 3;
    m
}

/// Act 2's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until act 1's M3 is in the tree, a placeholder keeps act 2's `needs` valid)
    if !crate::bh_act1::missions().iter().any(|m| m.key == "bh03") {
        v.push(dev_stub_bh03());
    }
    v.push(bh04());
    v.push(bh05());
    v.push(bh06());
    v.push(bh07());
    v.push(bh08());
    v.push(bh09());
    v.push(bh10());
    v.push(bh11());
    apply_roles(&mut v);
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh04") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}

/// Development fallback: a stand-in for act 1's M3 when it is not in the tree yet.
fn dev_stub_bh03() -> MissionDef {
    let mut m = MissionDef::new("bh03", "Placeholder Three");
    m.objective = "Rout the Green Earth force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    // (locked behind the bonds: with the placeholder campaign's last mission "bh02" won the campaign is over)
    m.needs = Needs::Bonds(vec!["bh02"]);
    m.flag = region::BLACK_HOLE[2];
    m
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ds_campaign_data::wrap_dialogue;

    fn scenes(m: &MissionDef) -> Vec<(String, &Scene)> {
        let mut v = vec![(format!("{} intro", m.key), &m.intro), (format!("{} victory", m.key), &m.victory), (format!("{} after", m.key), &m.after)];
        for (i, t) in m.triggers.iter().enumerate() {
            for a in &t.then {
                if let Action::Scene(s) = a {
                    v.push((format!("{} trigger {i}", m.key), s));
                }
            }
        }
        v
    }

    #[test]
    fn act_two_is_m4_to_m11_in_order() {
        let keys: Vec<&str> = missions().iter().map(|m| m.key).filter(|k| *k >= "bh04").collect();
        assert_eq!(keys, ["bh04", "bh05", "bh06", "bh07", "bh08", "bh09", "bh10", "bh11"]);
    }

    #[test]
    fn every_map_is_built_and_every_mission_has_scenes_and_a_flag_in_green_earth() {
        for m in missions().iter().filter(|m| m.key >= "bh04") {
            let MapSrc::Built(name) = &m.map else { panic!("{}: not a built map", m.key) };
            assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *name), "{}: map {name} is not built (five/bhmap.py)", m.key);
            if let Some(f) = &m.front2 {
                let MapSrc::Built(n2) = &f.map else { panic!("{}: second front not built", m.key) };
                assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *n2), "{}: map {n2}", m.key);
            }
            assert!(!m.intro.is_empty() && !m.after.is_empty(), "{}: scenes", m.key);
            // AW2's Green Earth, the east land
            assert!((300..=390).contains(&m.flag.0) && (85..=230).contains(&m.flag.1), "{}: flag {:?} off Green Earth", m.key, m.flag);
        }
    }

    #[test]
    fn the_branch_and_the_gate() {
        let ms = missions();
        let get = |k: &str| ms.iter().find(|m| m.key == k).unwrap();
        assert_eq!(get("bh06").needs, Needs::All(vec!["bh05"]));
        assert_eq!(get("bh07").needs, Needs::All(vec!["bh05"]));
        assert_eq!(get("bh08").needs, Needs::All(vec!["bh06", "bh07"]));
        assert_eq!(get("bh04").recruits, vec![roster::HAWKE]);
        assert!(get("bh04").triggers.iter().any(|t| t.then.iter().any(|a| matches!(a, Action::EarnBond(1)))));
    }

    /// Every line of every scene fits one box (two lines of AW2's 176 pixels).
    /// Run with the AW2 ROM: `TANGOAW2_AW2_ROM=... cargo test -p tango-gamesupport-aw2 --lib bh_act2 -- --ignored`.
    #[test]
    #[ignore]
    fn dialogue_fits_the_boxes() {
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").unwrap()).unwrap();
        let widths = rom[0x4C_36E4..][..256].to_vec();
        let mut checked = 0;
        for m in missions().iter().filter(|m| m.key >= "bh04") {
            for (name, scene) in scenes(m) {
                for l in &scene.lines {
                    let t = wrap_dialogue(l.text.as_bytes(), &widths);
                    let boxes: Vec<&[u8]> = t.split(|&c| c == 0x0F).filter(|b| !b.is_empty()).collect();
                    assert_eq!(boxes.len(), 1, "{name}: {:?} needs {} boxes", l.text, boxes.len());
                    let lines = boxes[0].split(|&c| c == b'\r').count();
                    assert!(lines <= 2, "{name}: {:?} needs {lines} lines", l.text);
                    checked += 1;
                }
            }
        }
        assert!(checked > 150, "{checked} lines checked");
    }
}
