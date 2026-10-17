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
    let sources = args.iter().any(|a| a == "--sources");
    let needs = args.iter().any(|a| a == "--needs-pack");
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
    if md && !sources && !needs {
        println!("| Id | Map | Source | Size | Armies | Units placed | Bases | Airports | Ports | Pre-deployed | Needs DS pack |\n|---|---|---|---|---|---|---|---|---|---|---|");
    }
    let mut rows = rows;
    rows.sort_by_key(|r| (r.armies, r.predeployed, r.id));
    for r in &rows {
        let ok = r.hqs <= r.armies && (2..=5).contains(&r.armies) && r.armies == r.header;
        if !ok {
            bad += 1;
        }
        if sources || needs {
        } else if md {
            println!(
                "| {:02X} | {} | {} | {}x{} | {} | {} | {} | {} | {} | {} | {} |",
                r.id, r.name, r.source, r.w, r.h, r.armies, r.placed, r.bases, r.airports, r.ports, if r.predeployed { "yes" } else { "no" }, if r.needs_pack { "yes" } else { "no" }
            );
        } else {
            println!(
                "{}P {:12} {:02x} {:24} {:11} {}x{} hqs {} units {} bases {} airports {} ports {} header {}{}",
                r.armies, if r.predeployed { "predeployed" } else { "" }, r.id, r.name, r.source, r.w, r.h, r.hqs, r.placed, r.bases, r.airports, r.ports, r.header, if ok { "" } else { "  MISMATCH" }
            );
        }
    }
    if needs {
        println!("| Id | Map | Source | Armies |\n|---|---|---|---|");
        for r in rows.iter().filter(|r| r.needs_pack && r.source == "tangoAW2") {
            println!("| {:02X} | {} | {} | {} |", r.id, r.name, r.source, r.armies);
        }
        println!("\nPlus all {} Dual Strike maps (Versus and War Room).", rows.iter().filter(|r| r.source.starts_with("DS ")).count());
        return;
    }
    // How many maps each source puts on each tab of the player-count lists (2P, 2P Predeploy, .. 5P Predeploy).
    if sources {
        let mut by: std::collections::BTreeMap<&str, [u32; 8]> = Default::default();
        for r in &rows {
            by.entry(r.source).or_default()[2 * (r.armies as usize - 2) + r.predeployed as usize] += 1;
        }
        println!("| Source | 2P | 2P Predeploy | 3P | 3P Predeploy | 4P | 4P Predeploy | 5P | 5P Predeploy | All |\n|---|---|---|---|---|---|---|---|---|---|");
        let mut total = [0u32; 8];
        for (src, c) in &by {
            println!("| {src} | {} | {} |", c.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(" | "), c.iter().sum::<u32>());
            for k in 0..8 {
                total[k] += c[k];
            }
        }
        println!("| **All** | {} | **{}** |", total.iter().map(|v| format!("**{v}**")).collect::<Vec<_>>().join(" | "), total.iter().sum::<u32>());
        return;
    }
    for n in 2..=5u8 {
        let plain = rows.iter().filter(|r| r.armies == n && !r.predeployed).count();
        let pre = rows.iter().filter(|r| r.armies == n && r.predeployed).count();
        eprintln!("{n}P: {plain} plain, {pre} predeploy");
    }
    eprintln!("{} maps, {} mismatches", rows.len(), bad);
    if bad > 0 {
        std::process::exit(1);
    }
}
