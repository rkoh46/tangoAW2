//! Preview of Dual Strike's CO selection screens ([`tango_gamesupport_aw2::ds_coselect`]) as PPMs: Versus' Teams screen
//! with two and five armies, and the CO screen with one, two and three cards.
//!
//! Usage: TANGOAW2_DS_ROM=<Dual Strike ROM or pack> ds_coselect_preview <out dir>
//! With `PREVIEW_SKIN=1,3` the armies at those places (0-based) wear the first skin (Emerald Sun): its colours and emblem on their cards.

use tango_gamesupport_aw2::ds_coselect::{render_cell, art_mug, art_name, render_pick, render_versus, Card, Cell, PickView, Slot, Stop, Tab, VersusArmy, H, W};

fn save(path: std::path::PathBuf, rgba: &[u8]) {
    let mut ppm = format!("P6\n{W} {H}\n255\n").into_bytes();
    for px in rgba.chunks(4) {
        ppm.extend_from_slice(&px[..3]);
    }
    std::fs::write(path, ppm).unwrap();
}

fn main() {
    let out = std::path::PathBuf::from(std::env::args().nth(1).expect("out dir"));
    std::fs::create_dir_all(&out).unwrap();
    tango_gamesupport_aw2::ds_pack::pack().expect("TANGOAW2_DS_ROM");
    // Every Dual Strike CO's Versus cell, for the check sheet against the clean game's.
    for ds in 1..=27u8 {
        let mut cell = vec![0u8; 24 * 48 * 4];
        if render_cell(&mut cell, ds) {
            let mut ppm = b"P6\n24 48\n255\n".to_vec();
            for px in cell.chunks(4) {
                ppm.extend_from_slice(&px[..3]);
            }
            std::fs::write(out.join(format!("cell{ds}.ppm")), ppm).unwrap();
        }
    }
    let skinned: Vec<usize> = std::env::var("PREVIEW_SKIN").unwrap_or_default().split(',').filter_map(|x| x.parse().ok()).collect();
    let skin = |i: usize| skinned.contains(&i).then_some(0usize);
    let mut buf = vec![0u8; W * H * 4];
    let mains = [26u8, 2, 8, 15, 17];
    let parts = [Some(13u8), Some(3), Some(5), None, None];
    for n in [2usize, 5] {
        let armies: Vec<VersusArmy> = (0..n)
            .map(|i| VersusArmy { colour: i as u8, skin: skin(i), main: art_mug(mains[i]), partner: parts[i].and_then(art_mug), tab: if i == 0 { Tab::Player(1) } else { Tab::Cpu } })
            .collect();
        assert!(render_versus(&mut buf, &armies, Stop::Main(0)));
        save(out.join(format!("versus{n}.ppm")), &buf);
        assert!(render_versus(&mut buf, &armies, Stop::None));
        save(out.join(format!("versus{n}_plain.ppm")), &buf);
    }
    let order: Vec<u8> = (1..=27).collect();
    for (name, ncards) in [("pick1", 1usize), ("pick2", 2), ("pick3", 3), ("pick4", 4)] {
        let cards: Vec<Card> = (0..ncards)
            .map(|i| Card {
                colour: i as u8,
                skin: skin(i),
                main: Slot { name: art_name(mains[i]) },
                partner: if ncards > 1 { Some(Slot { name: parts[i].and_then(art_name) }) } else { None },
            })
            .collect();
        let cells: Vec<Cell> = order
            .iter()
            .enumerate()
            .map(|(k, &d)| Cell { mug: if k % 5 == 4 { None } else { art_mug(d) }, flag: match k { 0 => Some((0, 1, skin(0))), 1 => Some((0, 2, skin(0))), 2 => Some((1, 1, skin(1))), _ => None } })
            .collect();
        let v = PickView { cards, active: Some((0, false)), cells, cursor: 5 };
        assert!(render_pick(&mut buf, &v));
        save(out.join(format!("{name}.ppm")), &buf);
    }
}
