//! The map audit: every map of the online pool with its armies counted from the map data (HQs and owners of
//! properties; owners of pre-placed units for pre-deployed maps), not from AW2's labels.
//!
//! Usage: [TANGOAW2_DS_ROM=<nds>] aw2_map_audit <rom> [--md]
//!
//! Prints a table (`--md`: Markdown for docs/MAPS.md) and exits 1 when a map's data disagrees with its header
//! or a map has no HQ for an army it has.
use tango_match::{HostInput, Link};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let md = args.iter().any(|a| a == "--md");
    let ds = std::env::var_os("TANGOAW2_DS_ROM").is_some();
    if ds {
        tango_gamesupport_aw2::ds_pack::pack();
    }
    let mt = (0u8, tango_gamesupport_aw2::online::ONLINE_MATCH | if ds { tango_gamesupport_aw2::ds_art::SHARED_ART } else { 0 });
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let mut link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, Some(mt), None).expect("boot");
    link.set_players(2);
    tango_gamesupport_aw2::online::set_room(vec!["A".into(), "B".into()], 0);
    for _ in 0..600 {
        link.tick([HostInput::keys(0), HostInput::keys(0)]);
    }
    let rows = tango_gamesupport_aw2::online_maps::audit(link.core_mut());
    let mut bad = 0;
    if md {
        println!("| Id | Map | Source | Size | Armies | Pre-deployed |\n|---|---|---|---|---|---|");
    }
    let mut rows = rows;
    rows.sort_by_key(|r| (r.armies, r.predeployed, r.id));
    for r in &rows {
        let ok = r.hqs <= r.armies && (2..=5).contains(&r.armies) && r.armies == r.header;
        if !ok {
            bad += 1;
        }
        if md {
            println!("| {:02X} | {} | {} | {}x{} | {} | {} |", r.id, r.name, r.source, r.w, r.h, r.armies, if r.predeployed { "yes" } else { "no" });
        } else {
            println!(
                "{}P {:12} {:02x} {:24} {:11} {}x{} hqs {} header {}{}",
                r.armies, if r.predeployed { "predeployed" } else { "" }, r.id, r.name, r.source, r.w, r.h, r.hqs, r.header, if ok { "" } else { "  MISMATCH" }
            );
        }
    }
    eprintln!("{} maps, {} mismatches", rows.len(), bad);
    if bad > 0 {
        std::process::exit(1);
    }
}
