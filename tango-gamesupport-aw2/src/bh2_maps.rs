//! The BH2 Campaign's mission maps (`five/bh2/spec/bh2_NN.py` -> `five/bh2/bh2_NN.txt` -> `bh2_map_data.rs`, built by `aw2dev maps gen --campaign bh2`; docs/dev/bh2-maps.md).
//! The campaign is not registered in any menu yet: maps and pictures come first. This module holds the plain facts the missions will rely on, as tests over the generated data.

#[cfg(test)]
mod tests {
    use crate::bh2_map_data::MAPS;

    /// Act I: M1..M5 (M4 has a second front, the sky map `bh2_04b`).
    const ACT1: [&str; 6] = ["bh2_01", "bh2_02", "bh2_03", "bh2_04", "bh2_04b", "bh2_05"];

    #[test]
    fn act_one_maps_are_built() {
        for name in ACT1 {
            assert!(MAPS.iter().any(|m| m.name == name), "{name} is missing from bh2_map_data.rs (run `aw2dev maps gen --campaign bh2`)");
        }
    }

    #[test]
    fn maps_fit_the_games_limits() {
        for m in MAPS {
            let (w, h) = (m.width as usize, m.height as usize);
            assert!(w <= 64 && h <= 40 && w * h <= 1288, "{}: {w}x{h} is past the map limits (64 x 40, 1288 cells)", m.name);
            assert_eq!(m.tiles.len(), w * h, "{}", m.name);
            for u in m.units {
                assert!((u.x as usize) < w && (u.y as usize) < h, "{}: a unit off the map at ({}, {})", m.name, u.x, u.y);
                assert!(u.army >= 1 && u.army <= m.armies, "{}: army {}", m.name, u.army);
            }
        }
    }

    #[test]
    fn no_army_fields_more_than_fifty_units() {
        for m in MAPS {
            for a in 1..=m.armies {
                let n = m.units.iter().filter(|u| u.army == a).count();
                assert!(n <= 50, "{}: army {a} starts with {n} units (at most 50)", m.name);
            }
        }
    }

    #[test]
    fn m2_has_its_named_crate_truck() {
        let m = MAPS.iter().find(|m| m.name == "bh2_02").expect("bh2_02");
        let crate_ = m.units.iter().find(|u| u.name == "crate").expect("the crate truck");
        assert_eq!((crate_.army, crate_.kind), (1, 7), "the crate is Black Hole's APC");
    }

    #[test]
    fn the_sky_front_is_air_only() {
        let m = MAPS.iter().find(|m| m.name == "bh2_04b").expect("bh2_04b");
        // Stealth 12, Fighter 16, Bomber 17: no ground unit, no Copter, no Anti-Air
        assert!(m.units.iter().all(|u| matches!(u.kind, 12 | 16 | 17)), "the sky front holds only Fighters, Bombers and Stealths");
    }
}
