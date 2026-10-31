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
    m.held_more = vec![CINDER_SENSEI, CINDER_HAWKE]; // (Hawke's too: his army must still stand while he says his last line, else AW2 draws face 0, Nell's; the Win trigger ends the battle)
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
    Scene::new(vec![Line::say(co::HAWKE, "Hmph. The sea and the sky were yours today. Enjoy it while it lasts.")])
}

// --- Gauntlet 02, Iron Crown and Asuka's Keep -------------------------------------------------------------------------------------------------------------

/// The HQs of stage one (five/gauntlet/spec/gauntlet_02.py): Grit's (on the field), Jess's, Kanbei's and Rachel's (hidden). The player is the fifth army (Black Hole's colour wearing the Emerald Sun skin).
pub const IRON_GRIT: (u8, u8) = (8, 9);
pub const IRON_JESS: (u8, u8) = (24, 5);
pub const IRON_KANBEI: (u8, u8) = (34, 6);
pub const IRON_RACHEL: (u8, u8) = (30, 20);
/// Asuka's HQ on stage two (five/gauntlet/spec/gauntlet_02b.py).
pub const KEEP_ASUKA: (u8, u8) = (22, 5);
/// The most funds the player carries into Asuka's Keep, and what Asuka holds her fortress with.
const KEEP_CARRY_CAP: u32 = 40000;
const KEEP_ASUKA_FUNDS: u32 = 80000;

/// Jess's wave: the forests of the north (tanks, Md Tanks, APCs, artillery, foot soldiers).
const JESS_WAVE: [(u8, (u8, u8)); 14] = [
    (unit::TANK, (23, 6)),
    (unit::TANK, (24, 4)),
    (unit::TANK, (25, 4)),
    (unit::MD_TANK, (24, 7)),
    (unit::MD_TANK, (22, 7)),
    (unit::MD_TANK, (24, 8)),
    (unit::APC, (23, 5)),
    (unit::APC, (22, 8)),
    (unit::INFANTRY, (21, 6)),
    (unit::INFANTRY, (23, 7)),
    (unit::ARTILLERY, (24, 3)),
    (unit::ANTI_AIR, (26, 6)),
    (unit::RECON, (20, 8)),
    (unit::MECH, (21, 7)),
];

/// Kanbei's wave: the keep's plateau (infantry and mechs, a Mega Tank and a Md Tank, artillery and rockets at the south pass).
const KANBEI_WAVE: [(u8, (u8, u8)); 15] = [
    (unit::INFANTRY, (32, 3)),
    (unit::INFANTRY, (35, 3)),
    (unit::INFANTRY, (31, 4)),
    (unit::INFANTRY, (37, 4)),
    (unit::INFANTRY, (33, 5)),
    (unit::INFANTRY, (35, 5)),
    (unit::MECH, (33, 6)),
    (unit::MECH, (35, 6)),
    (unit::MECH, (32, 7)),
    (unit::MECH, (33, 8)),
    (unit::MEGATANK, (35, 8)),
    (unit::MD_TANK, (37, 8)),
    (unit::ANTI_AIR, (31, 8)),
    (unit::ARTILLERY, (34, 9)),
    (unit::ROCKETS, (32, 9)),
];

/// Rachel's wave: the lowlands (Recons and Tanks to flank, Md Tanks, copters, artillery).
const RACHEL_WAVE: [(u8, (u8, u8)); 16] = [
    (unit::RECON, (29, 18)),
    (unit::RECON, (33, 17)),
    (unit::TANK, (31, 20)),
    (unit::TANK, (29, 20)),
    (unit::TANK, (31, 21)),
    (unit::MD_TANK, (28, 19)),
    (unit::MD_TANK, (30, 19)),
    (unit::MD_TANK, (33, 20)),
    (unit::ARTILLERY, (31, 22)),
    (unit::ROCKETS, (29, 22)),
    (unit::B_COPTER, (31, 19)),
    (unit::B_COPTER, (33, 19)),
    (unit::INFANTRY, (27, 20)),
    (unit::INFANTRY, (32, 21)),
    (unit::MECH, (29, 21)),
    (unit::ANTI_AIR, (29, 17)),
];

fn jess_chest(core: &mut Core) {
    war_chest(core, 2, 20000, 1000);
}
fn kanbei_chest(core: &mut Core) {
    war_chest(core, 3, 20000, 1500);
}
fn rachel_chest(core: &mut Core) {
    war_chest(core, 4, 25000, 2000);
}

/// A scene on a day's start (the stage's day scenes).
fn on_day(d: u16, then: Vec<Action>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: d }, then).repeating()
}

/// Iron Crown, stage one: the player (a free CO, the Emerald Sun army, the fifth) against Grit (Blue Moon), Jess (Green Earth), Kanbei (Yellow Comet) and Rachel (Orange Star), one after another on one land map; Rachel's fall moves
/// the battle in place to Asuka's Keep (stage two). Every enemy colour is fixed in its army's data (a colour pick for the player offers the colour the enemies leave free: Black Hole's here, `player_colours`).
fn iron_crown() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_02", "Iron Crown");
    m.objective = "Break Grit's river line, then Jess's, Kanbei's and Rachel's, and take Asuka's Keep.";
    m.map = MapSrc::Built("gauntlet_02");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(1).funds(9000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).team(1).funds(0),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(0),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::RACHEL)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.player_skins = vec![0]; // Emerald Sun only
    m.skin = Some((5, 0)); // the player's army wears Emerald Sun (skin 0) on the colour the enemies leave free
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_02"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.rank_days = 40;
    m.held_hq = Some(IRON_GRIT);
    m.held_more = vec![IRON_JESS, IRON_KANBEI, IRON_RACHEL];
    m.sleepers = vec![(2, vec![IRON_GRIT]), (3, vec![IRON_GRIT, IRON_JESS]), (4, vec![IRON_GRIT, IRON_JESS, IRON_KANBEI])];
    m.cut_off = vec![(1, IRON_GRIT), (2, IRON_JESS), (3, IRON_KANBEI)];
    m.hidden = vec![
        Hidden { army: 2, hq: IRON_JESS, zone: Rect::new(18, 0, 29, 12) },
        Hidden { army: 3, hq: IRON_KANBEI, zone: Rect::new(30, 0, 39, 13) },
        Hidden { army: 4, hq: IRON_RACHEL, zone: Rect::new(19, 14, 39, 25) },
    ];
    m.triggers = vec![
        arrive(IRON_GRIT, &[], 2, jess_chest, &JESS_WAVE, jess_arrives()),
        arrive(IRON_JESS, &[IRON_GRIT], 3, kanbei_chest, &KANBEI_WAVE, kanbei_arrives()),
        arrive(IRON_KANBEI, &[IRON_GRIT, IRON_JESS], 4, rachel_chest, &RACHEL_WAVE, rachel_arrives()),
        // Rachel's line is the last of stage one: a scene, then the battle moves on to Asuka's Keep
        Trigger::new(
            When::AfterAction,
            Cond::All(vec![fell(IRON_RACHEL), fell(IRON_KANBEI), fell(IRON_JESS), fell(IRON_GRIT)]),
            vec![Action::Scene(keep_switch()), Action::NextStage],
        ),
    ];
    m.setup = false;
    // Stage two: Asuka's Keep. The player's survivors land on the cells the map deploys the first army on; the player's skin moves to Orange Star's colour (Asuka is Black Hole's).
    let keep = crate::es_campaign::deployment("gauntlet_02b");
    let mut st = StageDef::new(MapSrc::Built("gauntlet_02b"));
    st.deploy = keep.iter().filter(|u| u.army == 1).map(|u| (u.x, u.y)).collect();
    st.units = keep.into_iter().filter(|u| u.army == 2).collect();
    st.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Keep),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(KEEP_ASUKA_FUNDS),
    ];
    st.skin = Some((1, 0));
    st.weather = Weather::Rain; // Asuka's rain: the fortress is fogged
    st.fog = true;
    st.carry = Carry::All;
    st.funds_cap = Some(KEEP_CARRY_CAP);
    st.held = vec![KEEP_ASUKA];
    st.intro = keep_intro();
    st.victory = keep_victory();
    st.triggers = vec![
        on_day(4, vec![Action::Scene(keep_day4())]),
        on_day(8, vec![Action::Scene(keep_day8())]),
        // her HQ is held (taking it defeats nobody) so her army stands while she says her last line with her own face; the Win ends the battle
        Trigger::new(When::AfterAction, fell(KEEP_ASUKA), vec![Action::Win]),
    ];
    m.stages = vec![st];
    m.intro = iron_intro();
    m.stars = 3;
    m
}

fn iron_intro() -> Scene {
    Scene::new(vec![
        Line::say(co::GRIT, "Hey! Welcome to the Iron Crown. This river and these hills are mine."),
        Line::say(co::GRIT, "If you want to cross the Aube, you'll have to get past my artillery first!"),
        Line::say(co::GRIT, "And I'm not the only one waiting out here. Don't get comfortable!"),
    ])
}

fn jess_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::GRIT, Mood::Sad, "Dang! They crossed my river and I couldn't stop them. Jess, you're up!"),
        Line::feel(co::JESS, Mood::Happy, "You got it, Grit! The forest is on my side, so watch your step!"),
        Line::say(co::JESS, "I'm going to show you how Green Earth fights. Ready or not!"),
    ])
}

fn kanbei_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::JESS, Mood::Sad, "Oh no! The forest wasn't enough? Kanbei, please take over!"),
        Line::say(co::KANBEI, "I understand. You have fought well to reach my mountains."),
        Line::say(co::KANBEI, "But courage alone does not take a keep. Come, let us see you climb."),
    ])
}

fn rachel_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::KANBEI, Mood::Sad, "The keep has fallen. Rachel, the lowlands are yours to hold."),
        Line::feel(co::RACHEL, Mood::Happy, "You came all this way? Nice! Let's see if you can handle Orange Star's best!"),
        Line::say(co::RACHEL, "I'm Rachel, and I won't let you take another step!"),
    ])
}

fn keep_switch() -> Scene {
    Scene::new(vec![
        Line::feel(co::RACHEL, Mood::Sad, "No way! My whole line is gone? That wasn't supposed to happen!"),
        Line::say(crate::co_new::ASUKA, "Rachel, retire. The file on this army is almost complete."),
        Line::say(crate::co_new::ASUKA, "Come to my keep. I have prepared for you."),
    ])
}

fn keep_intro() -> Scene {
    Scene::new(vec![
        Line::say(crate::co_new::ASUKA, "I have read your every move. Observe."),
        Line::say(crate::co_new::ASUKA, "Every gate and every gun of this keep stands where you will step."),
        Line::say(crate::co_new::ASUKA, "The rain will blind you. It will not blind me. Begin."),
    ])
}

fn keep_day4() -> Scene {
    Scene::new(vec![Line::say(crate::co_new::ASUKA, "Day four. You crossed the river, as predicted. The next page is the wall.")])
}

fn keep_day8() -> Scene {
    Scene::new(vec![Line::say(crate::co_new::ASUKA, "Your army grows thin and my file does not. Surrender is also in the record.")])
}

fn keep_victory() -> Scene {
    Scene::new(vec![
        Line::say(crate::co_new::ASUKA, "Impossible. I did not record this ending."),
        Line::say(crate::co_new::ASUKA, "No. Not impossible, only unrecorded. Well played. I will update the file."),
    ])
}

/// The Gauntlet mode's maps as a campaign (its missions; no prologue, staff roll or world map: the mode starts a map from Select Mode).
pub fn def() -> CampaignDef {
    let mut missions = vec![cinder_sea(), iron_crown()];
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

    /// The text map's rows (five/gauntlet/*.txt: the rows are the lines of the map's width after the header).
    fn rows(text: &'static str, w: usize) -> Vec<&'static str> {
        text.lines().filter(|l| l.len() == w && !l.starts_with('#') && !l.contains(' ')).collect()
    }

    #[test]
    fn iron_crown_is_a_gauntlet_of_four_in_five_armies() {
        let d = def();
        assert_eq!(d.missions.len(), 2, "Cinder Sea and Iron Crown");
        let m = &d.missions[1];
        assert_eq!(m.key, "gauntlet_02");
        let cos: Vec<_> = m.armies.iter().map(|a| a.co).collect();
        assert!(matches!(cos[0], CoSpec::Fixed(c) if c == co::GRIT));
        assert!(matches!(cos[1], CoSpec::Fixed(c) if c == co::JESS));
        assert!(matches!(cos[2], CoSpec::Fixed(c) if c == co::KANBEI));
        assert!(matches!(cos[3], CoSpec::Fixed(c) if c == co::RACHEL));
        assert!(matches!(cos[4], CoSpec::Pick), "the player (the fifth army) picks one CO");
        let colours: Vec<_> = m.armies.iter().map(|a| a.colour).collect();
        assert_eq!(colours, vec![colour::BLUE_MOON, colour::GREEN_EARTH, colour::YELLOW_COMET, colour::ORANGE_STAR, colour::BLACK_HOLE], "every enemy colour is fixed on its army");
        assert_eq!(m.hidden.iter().map(|h| h.army).collect::<Vec<_>>(), vec![2, 3, 4], "Jess, Kanbei and Rachel are hidden");
        assert_eq!(m.held_hq, Some(IRON_GRIT));
        assert_eq!(m.held_more, vec![IRON_JESS, IRON_KANBEI, IRON_RACHEL]);
        assert_eq!(m.sleepers.len(), 3);
        assert_eq!(m.cut_off.len(), 3);
        assert_eq!(m.triggers.len(), 4, "three arrivals and the stage switch");
        assert_eq!(m.player_skins, vec![0], "the player is Emerald Sun");
        assert_eq!(m.skin, Some((5, 0)), "on the fifth army's colour, the one the enemies leave free");
        assert!(!m.setup);
        let map = crate::custom_campaign::built_map("gauntlet_02").expect("the map is built (aw2dev maps gen --campaign gauntlet)");
        assert_eq!((map.width, map.height, map.armies), (40, 26, 5));
        assert!(map.width as u32 * map.height as u32 <= 1288, "the engine's five-army limit");
        // no hidden army has a unit on the map at the start (their waves land when they arrive)
        assert!(map.units.iter().all(|u| u.army == 1 || u.army == 5));
    }

    #[test]
    fn iron_crown_waves_land_on_ground_and_inside_their_zones() {
        let m = &def().missions[1];
        let r = rows(include_str!("../five/gauntlet/gauntlet_02.txt"), 40);
        assert_eq!(r.len(), 26);
        let at = |c: (u8, u8)| r[c.1 as usize].as_bytes()[c.0 as usize] as char;
        for (army, wave) in [(2u8, &JESS_WAVE[..]), (3, &KANBEI_WAVE[..]), (4, &RACHEL_WAVE[..])] {
            let zone = m.hidden.iter().find(|h| h.army == army).unwrap().zone;
            for &(kind, c) in wave {
                assert!(".Rf".contains(at(c)), "army {army}: kind {kind} at {c:?} stands on {:?}", at(c));
                assert!(c.0 as i32 >= zone.x0 as i32 && c.0 as i32 <= zone.x1 as i32 && c.1 as i32 >= zone.y0 as i32 && c.1 as i32 <= zone.y1 as i32, "army {army} {c:?} is outside its zone");
            }
        }
        // the hidden HQs' cells are plain ground until their lines come (the HQ is built on them)
        for hq in [IRON_JESS, IRON_KANBEI, IRON_RACHEL] {
            assert!(".R".contains(at(hq)), "{hq:?} is {:?}", at(hq));
        }
        assert_eq!(at(IRON_GRIT), '1');
    }

    #[test]
    fn asuka_keep_is_the_second_stage() {
        let m = &def().missions[1];
        assert_eq!(m.stages.len(), 1);
        let st = &m.stages[0];
        assert!(matches!(st.armies[0].co, CoSpec::Keep), "the player's CO comes along");
        assert_eq!(st.armies[0].colour, colour::ORANGE_STAR, "the player's skin moves off Black Hole's colour");
        assert!(matches!(st.armies[1].co, CoSpec::Fixed(c) if c == crate::co_new::ASUKA));
        assert_eq!(st.armies[1].colour, colour::BLACK_HOLE, "Asuka shows Black Hole's colours");
        assert_eq!(st.skin, Some((1, 0)), "Emerald Sun on the first army");
        assert_eq!(st.held, vec![KEEP_ASUKA]);
        assert_eq!(st.funds_cap, Some(KEEP_CARRY_CAP));
        assert!(matches!(st.carry, Carry::All));
        assert!(st.units.iter().all(|u| u.army == 2), "only Asuka's units: the survivors replace the player's");
        assert!(st.deploy.len() >= 30, "room for the survivors: {}", st.deploy.len());
        assert_eq!(st.triggers.len(), 3, "two day scenes and the Win");
        let map = crate::custom_campaign::built_map("gauntlet_02b").expect("the stage's map is built");
        assert_eq!((map.width, map.height, map.armies), (30, 22, 2));
        let r = rows(include_str!("../five/gauntlet/gauntlet_02b.txt"), 30);
        assert_eq!(r[KEEP_ASUKA.1 as usize].as_bytes()[KEEP_ASUKA.0 as usize], b'2');
        let text = include_str!("../five/gauntlet/gauntlet_02b.txt");
        assert!(text.contains("\nblackhole"), "the stage's map allows Black Hole's inventions");
    }
}
