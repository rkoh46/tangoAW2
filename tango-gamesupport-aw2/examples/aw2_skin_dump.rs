//! The writes an army skin makes (tango_gamesupport_aw2::army_skin::plan), as JSON, for `aw2dev armyskin`.
//!
//! Usage: aw2_skin_dump <aw2.gba> <colour 1..5> [skin.toml]   (the repository's Emerald Sun when no file is given)

use tango_gamesupport_aw2::army_skin::{self, RomFile, Skin};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: aw2_skin_dump <aw2.gba> <colour 1..5> [skin.toml]");
        std::process::exit(2);
    }
    let rom = std::fs::read(&args[1]).expect("rom");
    let host: u8 = args[2].parse().expect("colour");
    let skin = match args.get(3) {
        Some(p) => Skin::parse(&std::fs::read_to_string(p).expect("skin file")).expect("skin"),
        None => army_skin::emerald_sun().clone(),
    };
    let patches = army_skin::plan(&RomFile(&rom), &skin, host);
    let hex = |d: &[u8]| d.iter().map(|b| format!("{b:02x}")).collect::<String>();
    let out = serde_json::json!({
        "skin": skin.id,
        "name": skin.name,
        "host": host,
        "ramp": skin.ramp.iter().map(|&c| { let (r, g, b) = army_skin::rgb_of(c); [r, g, b] }).collect::<Vec<_>>(),
        "patches": patches.iter().map(|p| serde_json::json!({"what": p.what, "addr": p.addr, "hex": hex(&p.data)})).collect::<Vec<_>>(),
    });
    println!("{out}");
}
