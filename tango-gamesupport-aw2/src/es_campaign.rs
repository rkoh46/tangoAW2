//! The Emerald Sun Campaign: sixteen missions played as Emerald Sun, tangoAW2's sixth army (Roman-themed; `docs/dev/army-packs.md`), with four Roman
//! COs and a boss ([`crate::es_co`]). The second custom campaign on the BH Campaign's data-driven engine ([`crate::custom_campaign`]); the story is
//! `docs/ES_CAMPAIGN.md`, the dialogue `src/es_text/*.txt` ([`crate::es_text`]), the maps `five/es/spec/*.py` -> `five/es/*.txt` -> `es_map_data.rs`
//! (`aw2dev maps gen`), the missions `es_act1.rs` .. `es_act4.rs`. Developer guide: `docs/dev/es-campaign.md`.
//!
//! Until the user approves it the campaign is behind a development flag (`TANGOAW2_ES_CAMPAIGN`): the Campaign sub-menu still says "Coming soon".
//!
//! The player's army wears the Emerald Sun skin ([`crate::army_skin`]): it takes the colour the mission gives army 1, always one of the four of a normal game
//! (1..4) that no enemy or ally wears (a skin on colour 5 in a game that is not five-army corrupts the build menu: found by the mission sim). Black Hole's
//! inventions appear only in M9 and M13, the two missions against Black Hole (rule ES01 of `aw2dev maps lint`).

use mgba::core::Core;

use crate::campaign_model::Model;
use crate::custom_campaign::{co, colour, unit, *};
use crate::es_co;

/// The roster, in unlock order: Klaus is open at the start; Aurelia joins after M3, Cassius after M4, Livia and Colin (her tag partner) after M6, Kanbei (a tag partner) after M10.
pub const ROSTER: [(u8, bool); 6] = [
    (es_co::KLAUS, true),
    (es_co::AURELIA, false),
    (es_co::CASSIUS, false),
    (es_co::LIVIA, false),
    (co::COLIN, false),
    (co::KANBEI, false),
];

/// Roster indexes by name, for `recruits`.
pub mod roster {
    pub const KLAUS: u8 = 0;
    pub const AURELIA: u8 = 1;
    pub const CASSIUS: u8 = 2;
    pub const LIVIA: u8 = 3;
    pub const COLIN: u8 = 4;
    pub const KANBEI: u8 = 5;
}

/// The COs the player may lead with in a free-pick mission (Colin and Kanbei are tag partners only).
pub fn leads() -> Vec<u8> {
    vec![es_co::KLAUS, es_co::AURELIA, es_co::CASSIUS, es_co::LIVIA]
}

/// The campaign's source index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = 2;

/// The development flag: the campaign is playable (and the menu's "Coming soon" entry is replaced) when it is set.
pub fn dev_flag() -> bool {
    std::env::var_os("TANGOAW2_ES_CAMPAIGN").is_some()
}

/// The campaign's own EWRAM (registered in `ram_map.rs`): +0 a mission's hold counter (M13: turns the player has held the Harbour Office).
pub const STATE: u32 = 0x0203_C9F0;

/// The campaign is playable (the Dual Strike pack is on and the development flag is set).
pub fn available(core: &Core) -> bool {
    crate::ds_weather::is_on(core) && dev_flag()
}

/// The colour the player's army wears in an Emerald Sun battle (its skin sits on it), `None` outside one.
pub fn skin_colour(core: &Core) -> Option<u8> {
    if !crate::ds_campaign::active(core) || crate::ds_campaign::source(core) != SOURCE || !crate::pvp::in_battle(core) {
        return None;
    }
    let army = crate::ds_campaign::player_army(core) as u32;
    let c = core.raw_read_8(crate::five::players(core) + 0x3C * army + 0x1A, -1);
    (1..=5).contains(&c).then_some(c)
}

/// Army colours in an Emerald Sun battle. A mission in which the player picks a CO starts with the game's own colours for that case (the player's
/// army in Black Hole's colour 5, the others' shuffled to the free ones: the BH Campaign's player is always Black Hole), not the mission's. Found in
/// the real game: M13's player wore Black Hole's colour and Kindle Orange Star's, and the Emerald Sun skin landed on Black Hole's inventions. Every
/// tick of such a battle the colour bytes are set to the mission's and the army's palette rows reloaded when one changes.
pub fn sync_colours(core: &mut Core) -> Vec<(u32, u8)> {
    let mut changed = Vec::new();
    if !crate::ds_campaign::active(core) || crate::ds_campaign::source(core) != SOURCE || !crate::pvp::in_battle(core) {
        return changed;
    }
    let Some(m) = crate::ds_campaign::campaign(core).and_then(|c| c.model.built.missions.get(core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize)) else {
        return changed;
    };
    let players = crate::five::players(core);
    for k in 0..m.armies.min(4) as u32 {
        let want = m.colours[k as usize].clamp(1, 5);
        let at = players + 0x3C * (k + 1) + 0x1A;
        let have = core.raw_read_8(at, -1);
        if have != 0 && have != want {
            core.raw_write_8(at, -1, want);
            changed.push((k, want));
        }
    }
    changed
}

/// After the skin is installed on the corrected colours: the army's palette rows on the screen take the (skinned) palettes of its colour.
pub fn reload_palettes(core: &mut Core, changed: &[(u32, u8)]) {
    for &(k, want) in changed {
        crate::pvp::force_slot_palettes(core, k, want);
    }
}

/// The world map's flags (map pixels on AW2's own map, 432 x 256): the legion's march from Green Earth's south coast round the continent, then
/// the home sea and Port Aurelium at the south edge.
pub mod region {
    pub const ACT1: [(i16, i16); 4] = [(350, 95), (372, 118), (332, 135), (345, 160)];
    pub const ACT2: [(i16, i16); 4] = [(290, 57), (205, 200), (340, 215), (115, 175)];
    pub const ACT3: [(i16, i16); 4] = [(160, 30), (250, 80), (275, 100), (190, 170)];
    pub const ACT4: [(i16, i16); 4] = [(240, 140), (300, 238), (262, 226), (230, 244)];
}

/// The campaign.
pub fn def() -> CampaignDef {
    let mut missions: Vec<MissionDef> = [crate::es_act1::missions(), crate::es_act2::missions(), crate::es_act3::missions(), crate::es_act4::missions()].concat();
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    let last = missions.last().map_or("es01", |m| m.key);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: crate::es_text::pages("prologue"),
        prologue_song: crate::es_text::song("prologue"),
        credits: credits(),
        missions,
        final_mission: last,
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "",
    }
}

/// The staff roll (lines at most 21 characters).
fn credits() -> Vec<CreditSection> {
    let sec = |heading: &'static str, names: &[&'static str]| CreditSection { heading, names: names.to_vec(), secret: false };
    vec![
        sec("EMERALD SUN", &["A tangoAW2 story", "Sol invictus"]),
        sec("THE LEGION", &["KLAUS", "The Legate", "AURELIA", "The Engineer"]),
        sec("THE LEGION", &["CASSIUS", "The Cavalry", "LIVIA", "The Quaestor"]),
        sec("THE SENATE", &["VARRO", "The Consul"]),
        sec("THE ACCORD", &["NELL, MAX, JAKE", "COLIN, SASHA, OLAF", "GRIT, KANBEI, SONJA", "GRIMM, SENSEI"]),
        sec("THE ACCORD", &["JESS, EAGLE, DRAKE", "JAVIER"]),
        sec("THE FREE PORT", &["ADDER, FLAK", "KINDLE, LASH"]),
        sec("ORIGINAL GAMES", &["Intelligent Systems", "Nintendo", "Advance Wars 2:", "Black Hole Rising", "Advance Wars:", "Dual Strike"]),
        sec("INSPIRED BY", &["The Jade Sun of", "Advance Wars By Web"]),
        sec("RESEARCH", &["The aw2bhr", "decompilation:", "Eebit, npiriou,", "Mad-Man-Dan,", "Veslyquix"]),
        sec("EMULATION", &["endrift (mGBA)", "Arisotura (melonDS)", "weenie, GreigaMaster", "and everyone in the", "Tango credits"]),
        sec("SPECIAL THANKS", &["Playtesting:", "the tangoAW2", "players"]),
        sec("NOTICE", &["Advance Wars is a", "trademark of", "Nintendo. tangoAW2", "is not affiliated", "with Nintendo or", "Intelligent Systems."]),
        sec("THE END", &["The sun does not set.", "The grain is paid."]),
    ]
}

/// The campaign's source `load`.
pub fn load(core: &Core) -> Option<Model> {
    match compile(core, &def()) {
        Ok(m) => Some(m),
        Err(e) => {
            eprintln!("Emerald Sun Campaign: {e}");
            None
        }
    }
}

// --- Writing helpers (shared by the acts) ---------------------------------------------------

/// "On day `d`, at the start of the player's turn, do these": fires once, on that day (`EveryDays` with a period no mission reaches), without taking one of
/// the campaign's 96 once-latch flags.
pub fn on_day(d: u16, cond: Option<Cond>, then: Vec<Action>) -> Trigger {
    let day = Cond::EveryDays { n: 1000, from: d };
    let cond = match cond {
        Some(c) => Cond::All(vec![day, c]),
        None => day,
    };
    Trigger::new(When::TurnStart, cond, then).repeating()
}

/// After each action, while the condition holds (a win or a loss, or a one-way event).
pub fn after(cond: Cond, then: Vec<Action>) -> Trigger {
    Trigger::new(When::AfterAction, cond, then).repeating()
}

/// A mission's deployment from its built map: the enemy's units advance by kind ([`crate::bh_ai`]), those the map marks `hold` stay.
pub fn deployment(map: &str) -> Vec<UnitDef> {
    crate::bh_ai::orders(crate::bh_ai::built_units(map), 1, crate::bh_ai::ATTACK, |u| u.ai == 1)
}

/// The same with the vehicles going for the enemy HQ (a mission whose threat is the push on the HQ).
pub fn deployment_hq(map: &str) -> Vec<UnitDef> {
    crate::bh_ai::orders(crate::bh_ai::built_units(map), 1, crate::bh_ai::HQ, |u| u.ai == 1)
}

/// A reinforcement list: `kind` on each cell for `army`.
pub fn wave(army: u8, kind: u8, cells: &[(u8, u8)]) -> Vec<UnitDef> {
    cells.iter().map(|&(x, y)| UnitDef::new(army, kind, x, y)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roster_order() {
        assert_eq!(ROSTER[0], (es_co::KLAUS, true));
        assert!(ROSTER[1..].iter().all(|r| !r.1));
        assert_eq!(ROSTER[roster::LIVIA as usize].0, es_co::LIVIA);
        assert_eq!(ROSTER[roster::KANBEI as usize].0, co::KANBEI);
        assert!(ROSTER.len() as u32 <= crate::ds_campaign::BOND_SHIFT);
    }

    /// AW2 stops an army's production, and a reinforcement a trigger spawns, at 50 units (found by the sim: Varro, at 50, built and received nothing): a start of
    /// more than 40 leaves too little to build and to send.
    #[test]
    fn no_army_starts_with_more_than_40_units() {
        for m in &def().missions {
            let units = if m.units.is_empty() { Vec::new() } else { m.units.clone() };
            for a in 1..=m.armies.len() as u8 {
                let n = units.iter().filter(|u| u.army == a).count();
                assert!(n <= 40, "{}: army {a} starts with {n} units", m.key);
            }
        }
    }

    /// The skin sits on army 1's colour: one of AW2's four, worn by no other army of the mission.
    #[test]
    fn the_player_wears_a_colour_of_its_own() {
        for m in &def().missions {
            let p = m.armies[0].colour;
            assert!((1..=4).contains(&p), "{}: the player's colour {p}", m.key);
            assert!(m.armies[1..].iter().all(|a| a.colour != p), "{}: another army wears the player's colour {p}", m.key);
        }
    }

    #[test]
    fn every_mission_has_its_own_world_map_flag_and_a_map() {
        let d = def();
        let mut seen = std::collections::BTreeMap::new();
        for m in &d.missions {
            if let Some(other) = seen.insert(m.flag, m.key) {
                panic!("{} and {} share the flag {:?}", other, m.key, m.flag);
            }
            if let MapSrc::Built(n) = &m.map {
                assert!(built_map(n).is_some(), "{}: no built map {n}", m.key);
            }
        }
    }
}
