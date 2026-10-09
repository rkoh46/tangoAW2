//! The computer's orders in the BH Campaign: which of an enemy army's units advance, and how.
//!
//! A unit's deployment AI byte is its role (docs/AW2.md, "Goals" and "AI roles"): 0 holds where it stands (still
//! firing at what comes into reach; the engine keeps role-0 foot soldiers from walking off to capture), 1 goes for
//! the enemy HQ, 3 for the enemy's properties, 4 at the nearest enemy units. The map files carry no roles; every
//! mission gives them through [`orders`], so the audit is one rule in one place:
//!
//!   - Infantry and Mechs capture (3): the nearest neutral and player properties, bases first;
//!   - tanks, recon, indirect fire, Anti-Air, aircraft and warships attack units (4), or go for the HQ (1) in the
//!     missions where that is the threat (`armour`): indirect fire follows behind the front, as it is the same role;
//!   - transports (an APC, a Lander, a Black Boat) keep role 0: their own loading and unloading logic moves them;
//!   - only the garrisons a mission's design calls for hold (0): HQ guards, gate holders, a siege's inner guns.
//!
//! Reinforcements a trigger spawns have the default role 1 (the enemy HQ) unless they carry an order of their own;
//! [`spawn_orders`] gives the foot soldiers and indirect fire among them the roles above.

use crate::custom_campaign::{unit, Action, MissionDef, UnitDef, STAND};

/// Capture the enemy's properties.
pub const CAPTURE: u8 = 3;
/// Attack the nearest enemy units.
pub const ATTACK: u8 = 4;
/// Go for the enemy HQ.
pub const HQ: u8 = 1;

/// The role a unit of this kind gets when it advances. `armour` is what vehicles, ships and aircraft get
/// ([`ATTACK`] or [`HQ`]).
pub fn role_of(kind: u8, armour: u8) -> u8 {
    match kind {
        unit::INFANTRY | unit::MECH => CAPTURE,
        unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => ATTACK,
        unit::APC | unit::LANDER | unit::BLACK_BOAT => 0,
        _ => armour,
    }
}

/// True for a unit that has an order of its own already (a parked aircraft's 6, a stand, a frozen ring unit):
/// [`orders`] leaves it alone.
fn has_order(u: &UnitDef) -> bool {
    u.ai == 6 || u.ai == STAND || u.freeze
}

/// The orders for a mission's deployment: every unit of an army other than `player` advances by its kind
/// ([`role_of`]), except those `holds` names, which hold (role 0). Units with an order of their own are left.
pub fn orders(units: Vec<UnitDef>, player: u8, armour: u8, holds: impl Fn(&UnitDef) -> bool) -> Vec<UnitDef> {
    units
        .into_iter()
        .map(|mut u| {
            if u.army != player && !has_order(&u) {
                u.ai = if holds(&u) { 0 } else { role_of(u.kind, armour) };
            }
            u
        })
        .collect()
}

/// The units of a built map's text file (the map's `hold` flag is AW2's role 1, "go for the HQ": [`orders`] replaces it).
pub fn built_units(name: &str) -> Vec<UnitDef> {
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

/// [`orders`] with the holders named by their cells: the same cell in a front's own deployment is another unit.
pub fn orders_at(units: Vec<UnitDef>, player: u8, armour: u8, holders: &[(u8, u8)]) -> Vec<UnitDef> {
    orders(units, player, armour, |u| holders.contains(&(u.x, u.y)))
}

/// The roles of reinforcements: a spawned unit that carries no order (`ai` 0) has the default role 1 (the enemy
/// HQ); foot soldiers get [`CAPTURE`] and indirect fire [`ATTACK`], the rest keep the HQ role (the reinforcement
/// is the threat). `player` is the army that keeps what it has (army 1; M28's player is the fifth army).
pub fn spawn_orders(m: &mut MissionDef) {
    let player = if m.key == "bh28" { 5 } else { 1 };
    let fix = |u: &mut UnitDef| {
        if u.army != player && u.ai == 0 && !u.freeze && u.name.is_none() {
            u.ai = match u.kind {
                unit::INFANTRY | unit::MECH => CAPTURE,
                unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => ATTACK,
                _ => 0,
            };
        }
    };
    for t in m.triggers.iter_mut().chain(m.front2_triggers.iter_mut()) {
        for a in t.then.iter_mut() {
            if let Action::Spawn(v) = a {
                v.iter_mut().for_each(fix);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kinds_get_their_roles() {
        assert_eq!(role_of(unit::INFANTRY, ATTACK), CAPTURE);
        assert_eq!(role_of(unit::MECH, HQ), CAPTURE);
        assert_eq!(role_of(unit::ARTILLERY, HQ), ATTACK);
        assert_eq!(role_of(unit::ANTI_AIR, ATTACK), ATTACK);
        assert_eq!(role_of(unit::MD_TANK, HQ), HQ);
        assert_eq!(role_of(unit::LANDER, ATTACK), 0);
    }

    #[test]
    fn holders_and_the_player_are_left_alone() {
        let v = vec![
            UnitDef::new(1, unit::TANK, 1, 1),
            UnitDef::new(2, unit::INFANTRY, 5, 5),
            UnitDef::new(2, unit::INFANTRY, 6, 5),
            UnitDef::new(2, unit::TANK, 7, 5),
            UnitDef::new(2, unit::TANK, 8, 5).stand(),
        ];
        let o = orders_at(v, 1, ATTACK, &[(6, 5)]);
        assert_eq!(o.iter().map(|u| u.ai).collect::<Vec<_>>(), vec![0, CAPTURE, 0, ATTACK, STAND]);
    }

    /// The audit of the whole campaign (docs/AW2.md, "AI roles"): the computer's armies are given orders, and only a minority holds.
    #[test]
    fn every_mission_gives_the_enemy_orders_and_only_a_minority_holds() {
        // Missions whose design holds a larger share, by name: M14's ring (frozen until day 3), M29 and M30's camp, M31's road blocks.
        const DESIGNED: [&str; 4] = ["bh14", "bh29", "bh30", "bh31"];
        let d = crate::bh_campaign::def();
        for m in &d.missions {
            let player = if m.key == "bh28" { 5 } else { 1 };
            assert!(!m.units.is_empty(), "{}: no deployment", m.key);
            let foes: Vec<&UnitDef> = m.units.iter().filter(|u| u.army != player).collect();
            let held = foes.iter().filter(|u| u.ai == 0 || u.ai == STAND || u.freeze).count();
            assert!(!foes.is_empty(), "{}: no enemy units", m.key);
            if !DESIGNED.contains(&m.key) {
                assert!(held * 10 <= foes.len() * 3, "{}: {held} of {} enemy units hold", m.key, foes.len());
                // (a held foot soldier is a garrison; the rest of the foot soldiers capture or march)
                for u in foes.iter().filter(|u| matches!(u.kind, unit::INFANTRY | unit::MECH) && u.ai != 0 && u.ai != STAND) {
                    assert!(u.ai == CAPTURE || u.ai == HQ || u.ai == 6, "{}: a foot soldier at ({}, {}) has role {}", m.key, u.x, u.y, u.ai);
                }
            }
        }
    }

    /// Reinforcements: foot soldiers capture and indirect fire attacks, instead of the default HQ role.
    #[test]
    fn spawned_foot_soldiers_and_guns_have_orders() {
        let d = crate::bh_campaign::def();
        for m in &d.missions {
            let player = if m.key == "bh28" { 5 } else { 1 };
            for t in &m.triggers {
                for a in &t.then {
                    let Action::Spawn(v) = a else { continue };
                    for u in v.iter().filter(|u| u.army != player && u.name.is_none() && !u.freeze) {
                        match u.kind {
                            unit::INFANTRY | unit::MECH => assert_eq!(u.ai, CAPTURE, "{}: a spawned foot soldier", m.key),
                            unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => assert_eq!(u.ai, ATTACK, "{}: spawned indirect fire", m.key),
                            _ => {}
                        }
                    }
                }
            }
        }
    }
}
