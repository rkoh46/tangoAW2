//! The Gauntlet mode's maps (docs/dev/gauntlet.md "The Gauntlet mode"): one battle per map against a fixed line-up of COs who come one after another, the player
//! with a free pick of one CO. Each map is a mission of a small custom campaign ([`def`]) played by the campaign engine (AW2's event engine runs only there), so the
//! gauntlet engine ([`crate::custom_campaign`]: `MissionDef::hidden`, `sleepers`, `cut_off`, `Action::Reveal`, `Cond::LineFallen`) works as in BH2's M31.
//! A new map is a spec (`five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`) and a function here added to [`def`]'s missions.

use mgba::core::Core;

use crate::custom_campaign::{co, colour, unit, *};

/// The Gauntlet's index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = 4;

/// Every CO the player may pick (all open from the start): AW2's, Dual Strike's, then tangoAW2's own (not Varro: a boss only).
pub const ROSTER: [(u8, bool); 36] = [
    (co::ANDY, true),
    (co::MAX, true),
    (co::SAMI, true),
    (co::NELL, true),
    (co::OLAF, true),
    (co::GRIT, true),
    (co::COLIN, true),
    (co::KANBEI, true),
    (co::SONJA, true),
    (co::SENSEI, true),
    (co::EAGLE, true),
    (co::DRAKE, true),
    (co::JESS, true),
    (co::HACHI, true),
    (co::STURM, true),
    (co::FLAK, true),
    (co::LASH, true),
    (co::ADDER, true),
    (co::HAWKE, true),
    (co::JAKE, true),
    (co::RACHEL, true),
    (co::SASHA, true),
    (co::GRIMM, true),
    (co::JAVIER, true),
    (co::JUGGER, true),
    (co::KOAL, true),
    (co::KINDLE, true),
    (co::VON_BOLT, true),
    (co::CLONE_ANDY, true),
    (co::CRUMB, true),
    (crate::es_co::KLAUS, true),
    (crate::es_co::AURELIA, true),
    (crate::es_co::CASSIUS, true),
    (crate::es_co::LIVIA, true),
    (crate::co_new::ASUKA, true),
    (crate::co_new::ARIA, true),
];

/// A line falls: the player holds its HQ, or its army was destroyed (the gauntlet engine's [`Cond::LineFallen`]).
fn fell(c: (u8, u8)) -> Cond {
    Cond::LineFallen { x: c.0, y: c.1 }
}

/// A wave: `kind` on each cell for `army`, every unit attacking (a taken cell lands on the nearest free one it can enter: `custom_campaign::landing`).
fn spawn(army: u8, list: &[(u8, (u8, u8))]) -> Action {
    Action::Spawn(list.iter().map(|&(k, (x, y))| UnitDef::new(army, k, x, y).attack()).collect())
}

/// The next CO arrives when the line at `hq` falls (and every line before it): the scene, the reveal (its HQ built, its zone's properties its own), its war chest, its wave.
fn arrive(hq: (u8, u8), before: &[(u8, u8)], army: u8, chest: fn(&mut Core), wave: &[(u8, (u8, u8))], scene: Scene) -> Trigger {
    let mut all = vec![fell(hq)];
    all.extend(before.iter().map(|&c| fell(c)));
    Trigger::new(When::AfterAction, Cond::All(all), vec![Action::Scene(scene), Action::Reveal(army), Action::Custom(chest), spawn(army, wave)])
}

/// An arriving army's funds: `base` and `rate` for every day before today (the slower the player, the richer the next line; it earns nothing while it sleeps: `cut_funds`).
fn war_chest(core: &mut Core, army: u8, base: u32, rate: u32) {
    let day = crate::custom_campaign::day(core).max(1) as u32;
    let p = crate::five::players(core) + 0x3C * army as u32;
    let f = core.raw_read_32(p, -1);
    core.raw_write_32(p, -1, (f + base + rate * (day - 1)).min(999_999));
}

// --- Gauntlet 01, Cinder Sea -------------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_01.py): the player's, Drake's, Sensei's (hidden), Hawke's (hidden).
pub const CINDER_PLAYER: (u8, u8) = (3, 18);
pub const CINDER_DRAKE: (u8, u8) = (27, 18);
pub const CINDER_SENSEI: (u8, u8) = (3, 3);
pub const CINDER_HAWKE: (u8, u8) = (29, 3);

/// Sensei's wave: copters and airborne infantry on the north-west island, a Fighter, a Cruiser off its port.
const SENSEI_WAVE: [(u8, (u8, u8)); 12] = [
    (unit::B_COPTER, (5, 3)),
    (unit::B_COPTER, (8, 3)),
    (unit::B_COPTER, (4, 5)),
    (unit::B_COPTER, (8, 6)),
    (unit::T_COPTER, (2, 5)),
    (unit::MECH, (5, 4)),
    (unit::MECH, (6, 4)),
    (unit::INFANTRY, (3, 5)),
    (unit::INFANTRY, (5, 6)),
    (unit::FIGHTER, (6, 3)),
    (unit::ANTI_AIR, (2, 4)),
    (unit::CRUISER, (10, 5)),
];

/// Hawke's wave: Bombers, a Stealth and a Fighter over the volcano island, troops on it, a carrier group and a Black Boat off its shores.
const HAWKE_WAVE: [(u8, (u8, u8)); 12] = [
    (unit::BOMBER, (28, 4)),
    (unit::BOMBER, (29, 6)),
    (unit::STEALTH, (30, 4)),
    (unit::FIGHTER, (30, 2)),
    (unit::INFANTRY, (28, 3)),
    (unit::INFANTRY, (29, 2)),
    (unit::ANTI_AIR, (30, 5)),
    (unit::MISSILES, (22, 7)),
    (unit::BATTLESHIP, (19, 4)),
    (unit::CARRIER, (27, 9)),
    (unit::SUB, (31, 2)),
    (unit::BLACK_BOAT, (31, 7)),
];

fn sensei_chest(core: &mut Core) {
    war_chest(core, 3, 15000, 1000);
}
fn hawke_chest(core: &mut Core) {
    war_chest(core, 4, 20000, 1500);
}

/// Cinder Sea: the player (Orange Star, a free CO) against Drake (Green Earth), then Sensei (Yellow Comet), then Hawke (Black Hole) on his volcano island.
fn cinder_sea() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_01", "Cinder Sea");
    m.objective = "Sink Drake's line, then Sensei's, then take Hawke's HQ on the volcano island.";
    m.map = MapSrc::Built("gauntlet_01");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).team(2).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).team(2).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::HAWKE)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_01");
    m.rank_days = 24;
    // (the player's army has no team of its own written here: team 0 is its own army number, 1; the three enemies share team 2: with team 1 they were the player's allies)
    // the gauntlet: Drake's and Sensei's HQs are held (taking one defeats nobody: the line's survivors fight on, cut off from their income); Hawke's is the last
    m.held_hq = Some(CINDER_DRAKE);
    m.held_more = vec![CINDER_SENSEI];
    m.sleepers = vec![(3, vec![CINDER_DRAKE]), (4, vec![CINDER_DRAKE, CINDER_SENSEI])];
    m.cut_off = vec![(2, CINDER_DRAKE), (3, CINDER_SENSEI)];
    m.hidden = vec![
        Hidden { army: 3, hq: CINDER_SENSEI, zone: Rect::new(0, 0, 12, 9) },
        Hidden { army: 4, hq: CINDER_HAWKE, zone: Rect::new(18, 0, 31, 9) },
    ];
    m.triggers = vec![
        arrive(CINDER_DRAKE, &[], 3, sensei_chest, &SENSEI_WAVE, sensei_arrives()),
        arrive(CINDER_SENSEI, &[CINDER_DRAKE], 4, hawke_chest, &HAWKE_WAVE, hawke_arrives()),
        // Hawke's line is the last: when it falls (his HQ taken or his army routed) the battle is won at once, whatever Drake's and Sensei's cut-off survivors still hold
        Trigger::new(When::AfterAction, Cond::All(vec![fell(CINDER_HAWKE), fell(CINDER_SENSEI), fell(CINDER_DRAKE)]), vec![Action::Win]),
    ];
    // (no Setup phase: the battle starts on day 1 with the map's deployment)
    m.setup = false;
    // Hawke's volcano: from day 3 it erupts every day on 3 cells of the ring round its mountain wall (3 HP, any army's units, never below 1)
    m.volcano = Some(crate::campaign_model::VolcanoDef::new(3, 1, 3, &crate::campaign_model::ring(21, 0, 28, 7)).per_eruption(3));
    m.intro = intro();
    m.victory = victory();
    m.stars = 3;
    m
}

fn intro() -> Scene {
    Scene::new(vec![
        Line::say(co::DRAKE, "Ahoy! Welcome to the Cinder Sea. These are my waters."),
        Line::say(co::DRAKE, "Want to cross them? You'll have to get past my fleet first."),
        Line::say(co::DRAKE, "And mind the smoke up north. That old volcano's been grumbling all week."),
    ])
}

fn sensei_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::DRAKE, Mood::Sad, "Blast! My flagship's gone under. Sensei, the sea's yours now."),
        Line::feel(co::SENSEI, Mood::Happy, "Hoho! Drake's beaten? Then it's an old man's turn."),
        Line::say(co::SENSEI, "My copters have been itching to fly. Let's see how you handle the sky!"),
    ])
}

fn hawke_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::SENSEI, Mood::Sad, "Well, well. Beaten by a youngster. I'm getting too old for this."),
        Line::say(co::HAWKE, "So you broke through Drake and Sensei. Impressive."),
        Line::say(co::HAWKE, "But this island is mine, and the mountain answers to me. You will burn here."),
    ])
}

fn victory() -> Scene {
    Scene::new(vec![Line::feel(co::HAWKE, Mood::Sad, "Hmph. The sea and the sky were yours today. Enjoy it while it lasts.")])
}

/// The Gauntlet mode's maps as a campaign (its missions; no prologue, staff roll or world map: the mode starts a map from Select Mode).
pub fn def() -> CampaignDef {
    let mut missions = vec![cinder_sea()];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: Vec::new(),
        prologue_song: None,
        prologue_scenes: Vec::new(),
        credits: Vec::new(),
        missions,
        final_mission: "gauntlet_01",
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cinder_sea_is_a_gauntlet_of_three() {
        let d = def();
        let m = &d.missions[0];
        assert_eq!(m.key, "gauntlet_01");
        let cos: Vec<_> = m.armies.iter().map(|a| a.co).collect();
        assert!(matches!(cos[0], CoSpec::Pick), "the player picks one CO");
        assert!(matches!(cos[1], CoSpec::Fixed(c) if c == co::DRAKE));
        assert!(matches!(cos[2], CoSpec::Fixed(c) if c == co::SENSEI));
        assert!(matches!(cos[3], CoSpec::Fixed(c) if c == co::HAWKE));
        assert_eq!(m.hidden.iter().map(|h| h.army).collect::<Vec<_>>(), vec![3, 4]);
        assert_eq!(m.triggers.len(), 3, "Sensei and Hawke each arrive once; Hawke's fall wins");
        assert!(!m.setup, "no Setup phase");
        let map = crate::custom_campaign::built_map("gauntlet_01").expect("the map is built (five/bhmap.py --campaign gauntlet)");
        assert_eq!((map.width, map.height, map.armies), (32, 22, 4));
    }

    #[test]
    fn the_roster_is_every_co_once() {
        let mut ids: Vec<u8> = ROSTER.iter().map(|r| r.0).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), ROSTER.len());
        assert!(ROSTER.iter().all(|r| r.1), "every CO is open from the start");
    }
}
