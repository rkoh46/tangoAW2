//! Act 1: Cinders. M1 Storm Landing (Von Bolt's recruit mission, a beach
//! assault with Black Crystals and an Obelisk), M2 The Sleeping Foundry (a Black
//! Factory that wakes on day 3, a set-piece defence) and M3 Blockade Runner (a
//! naval tag battle against Drake and Eagle). The design is
//! docs/BH_CAMPAIGN.md (sections 3.5, 4.1, 4.2 and 4.11); the maps are
//! `five/bh/bh01.txt` .. `bh03.txt`, built by `five/bhmap.py` into
//! `bh_map_data.rs`.
//!
//! Its missions are `MissionDef`s (docs/AW2.md "BH Campaign": adding a
//! mission); this file is the act's alone, so builders can work on acts in
//! parallel. A mission names what it needs by key (`Needs::All(vec!["bh01"])`),
//! not by index.

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

// --- Rules written in Rust --------------------------------------------------------

/// The player's army (army 1) is led by Sturm.
fn player_is_sturm(core: &mut Core) -> bool {
    let army = crate::ds_campaign::player_army(core) as u32;
    crate::tag::army_co_of(core, army) == co::STURM
}

/// Army 2's first power is ready: its meter is full for a normal power.
fn charge_jess(core: &mut Core) {
    let p = crate::tag::player(core, 2);
    // (the player block: CO +0x1D, powers used +0x25, meter +0x20)
    let (jess, uses) = (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x25, -1));
    let full = crate::tag::cop_cost(core, jess, uses);
    if core.raw_read_32(p + 0x20, -1) < full {
        core.raw_write_32(p + 0x20, -1, full);
    }
}

// --- M1 Storm Landing --------------------------------------------------------------

fn bh01() -> MissionDef {
    let mut m = MissionDef::new("bh01", "Storm Landing");
    m.objective = "Take the HQ. Von Bolt wants the biggest account in the world.";
    m.map = MapSrc::Built("bh01");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)).funds(6000),
        // Von Bolt in Green Earth's colours (his stolen surplus).
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)).funds(20000),
    ];
    // Von Bolt's army advances (Infantry and Mechs capture, the rest attacks); one Infantry guards his HQ at (19, 2).
    m.units = crate::bh_ai::orders_at(crate::bh_ai::built_units("bh01"), 1, crate::bh_ai::ATTACK, &[(18, 3)]);
    m.day_limit = 0;
    m.rank_days = 10;
    m.intro = crate::bh_text::scene("m01_pre");
    m.victory = crate::bh_text::scene("m01_post");
    m.after = crate::bh_text::scene("m01_map");
    m.recruits = vec![roster::VON_BOLT];
    // The win (Von Bolt routed or his HQ taken): the bond is earned (Sturm is fixed
    // in this mission, so it is automatic), then the victory scene.
    m.on_win = vec![Action::EarnBond(0)];
    m.triggers = vec![
        // Day 3: a Black Hole unit stands in a Crystal's light (within 2 of it).
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![
                Cond::DayAtLeast(3),
                Cond::Any(vec![
                    Cond::UnitsIn {
                        army: 1,
                        area: Rect::new(4, 4, 8, 8),
                        at_least: 1,
                    },
                    Cond::UnitsIn {
                        army: 1,
                        area: Rect::new(13, 6, 17, 10),
                        at_least: 1,
                    },
                ]),
            ]),
            vec![Action::Scene(crate::bh_text::scene("m01_day3"))],
        ),
        // Day 4: the loot sale: with six properties Von Bolt buys two Md Tanks.
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(4), Cond::PropertiesAtLeast { army: 2, n: 6 }]),
            vec![Action::Spawn(vec![
                UnitDef::new(2, unit::MD_TANK, 19, 4),
                UnitDef::new(2, unit::MD_TANK, 21, 4),
            ])],
        ),
        // Day 7: everything must go.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(7), vec![Action::Scene(crate::bh_text::scene("m01_day7"))]),
    ];
    m.flag = region::BLACK_HOLE[0];
    m.stars = 1;
    m
}

// --- M2 The Sleeping Foundry ---------------------------------------------------------

fn bh02() -> MissionDef {
    let mut m = MissionDef::new("bh02", "The Sleeping Foundry");
    m.objective = "Hold the Foundry. Rout Green Earth or take its HQ.";
    m.map = MapSrc::Built("bh02");
    m.armies = vec![
        // Pre-deployed: no bases, no funds; the Foundry is the factory.
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        // Jess has real production (3 bases, an airport, income) and 14000 to start.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(14000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT];
    // Green Earth pushes: Infantry and Mechs take the bases and cities, the rest attacks; one Infantry guards the HQ at (11, 22).
    m.units = crate::bh_ai::orders_at(crate::bh_ai::built_units("bh02"), 1, crate::bh_ai::ATTACK, &[(10, 20)]);
    // Three of Green Earth's cities in the front lines start unclaimed: its Infantry and Mechs take them on days 2 to 4 (the
    // neutral cities in the middle are five days off), then march on.
    m.props = [(12, 14), (6, 20), (16, 20)].iter().map(|&(x, y)| Prop { kind: PropKind::City, owner: 0, x, y }).collect();
    m.day_limit = 0;
    m.rank_days = 11;
    m.intro = crate::bh_text::scene("m02_pre");
    m.victory = crate::bh_text::scene("m02_post");
    m.after = crate::bh_text::scene("m02_map");
    // The Foundry wakes on day 3 (table F2, docs/BH_CAMPAIGN.md 3.5): the
    // three doors, left to right.
    m.factory = vec![
        (3, [0, unit::TANK, 0]),
        (4, [unit::INFANTRY, 0, unit::INFANTRY]),
        (5, [0, unit::MD_TANK, 0]),
        (6, [unit::MECH, unit::RECON, unit::MECH]),
        (7, [0, 0, unit::TANK]),
        (8, [unit::TANK, 0, unit::TANK]),
        (9, [0, unit::MD_TANK, 0]),
        (10, [unit::INFANTRY, unit::INFANTRY, unit::INFANTRY]),
        (11, [0, unit::TANK, 0]),
        (12, [unit::MECH, 0, unit::MECH]),
        (13, [0, unit::MD_TANK, 0]),
        (14, [unit::TANK, 0, unit::TANK]),
        (16, [0, unit::MD_TANK, 0]),
    ];
    let wave = |units: Vec<UnitDef>| vec![Action::Spawn(units)];
    m.triggers = vec![
        // The last line of the opening is Sturm's own, or whoever else leads.
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(1), Cond::Custom(player_is_sturm)]),
            vec![Action::Scene(crate::bh_text::scene("m02_pre_sturm"))],
        ),
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![
                Cond::DayAtLeast(1),
                Cond::Not(Box::new(Cond::Custom(player_is_sturm))),
            ]),
            vec![Action::Scene(crate::bh_text::scene("m02_pre_other"))],
        ),
        // Day 3: the Foundry wakes; Green Earth's first wave comes up the road.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(3), vec![Action::Scene(crate::bh_text::scene("m02_day3"))]),
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(3),
            wave(vec![
                UnitDef::new(2, unit::TANK, 9, 22),
                UnitDef::new(2, unit::TANK, 10, 22),
                UnitDef::new(2, unit::TANK, 12, 22),
            ]),
        ),
        // Day 6: two Md Tanks and two Infantry.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(6), vec![Action::Scene(crate::bh_text::scene("m02_day6"))]),
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(6),
            wave(vec![
                UnitDef::new(2, unit::MD_TANK, 9, 22),
                UnitDef::new(2, unit::MD_TANK, 10, 22),
                UnitDef::new(2, unit::INFANTRY, 12, 22),
                UnitDef::new(2, unit::INFANTRY, 13, 22),
                UnitDef::new(2, unit::B_COPTER, 17, 22),
            ]),
        ),
        // Day 9: Jess arrives with her first power charged.
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(9),
            vec![
                Action::Custom(charge_jess),
                Action::Spawn(vec![
                    UnitDef::new(2, unit::MD_TANK, 9, 22),
                    UnitDef::new(2, unit::MD_TANK, 10, 22),
                    UnitDef::new(2, unit::ROCKETS, 12, 22),
                ]),
            ],
        ),
    ];
    m.flag = region::BLACK_HOLE[4];
    m.stars = 1;
    m
}

// --- M3 Blockade Runner -------------------------------------------------------------

/// The player holds the middle isle: two of its three cities.
fn holds_the_isle() -> Cond {
    let at = |x, y| Cond::OwnerAt { x, y, army: 1 };
    Cond::Any(vec![
        Cond::All(vec![at(11, 9), at(14, 8)]),
        Cond::All(vec![at(11, 9), at(14, 5)]),
        Cond::All(vec![at(14, 8), at(14, 5)]),
    ])
}

fn bh03() -> MissionDef {
    let mut m = MissionDef::new("bh03", "Blockade Runner");
    m.objective = "Break the blockade. Take the east HQ or rout the fleet.";
    m.map = MapSrc::Built("bh03");
    m.armies = vec![
        // The only two COs there are: the "Black Apocalypse" pair.
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::VON_BOLT)).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::DRAKE, co::EAGLE)).funds(14000),
    ];
    // The fleet and the air wings attack (the Landers load and unload as the computer does).
    m.units = crate::bh_ai::orders_at(crate::bh_ai::built_units("bh03"), 1, crate::bh_ai::ATTACK, &[]);
    m.day_limit = 0;
    m.rank_days = 14;
    // The isle's Black Cannon (inventions-list cell (11,5): its top left) and two minicannons are ours, and would
    // shoot the first enemy in reach at the first Black Hole turn start (a Submarine at (17,13) lost half its HP before
    // the player could act): jammed until day 2, they fire from day 3.
    m.jams = vec![
        JamDef { at: (11, 5), until: Cond::DayAtLeast(2) },
        JamDef { at: (12, 9), until: Cond::DayAtLeast(2) },
        JamDef { at: (14, 9), until: Cond::DayAtLeast(2) },
    ];
    m.intro = crate::bh_text::scene("m03_pre");
    m.victory = crate::bh_text::scene("m03_post");
    m.after = Scene::new({
        let mut v = crate::bh_text::lines("m03_map");
        v.extend(crate::bh_text::lines("m03_warroom"));
        v
    });
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::DayAtLeast(4), vec![Action::Scene(crate::bh_text::scene("m03_day4"))]),
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(8), holds_the_isle()]),
            vec![Action::Scene(crate::bh_text::scene("m03_day8"))],
        ),
    ];
    m.flag = region::BLACK_HOLE[5];
    m.stars = 2;
    m.needs = Needs::All(vec!["bh02"]);
    m
}

/// Act 1's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut one = bh01();
    one.needs = Needs::Start;
    let mut two = bh02();
    two.needs = Needs::All(vec!["bh01"]);
    vec![one, two, bh03()]
}
