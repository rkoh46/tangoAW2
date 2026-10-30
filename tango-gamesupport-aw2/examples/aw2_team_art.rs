//! The game's own team-letter pictures ("A Team".."D Team", sprites 0xBD..0xC0) and tangoAW2's E read from the ROM at
//! run time, for the army screen (`army_cards::team_plate`): prints each sprite's group, size and writes `team_<id>.ppm`.
//!
//! Usage: aw2_team_art <rom> <out-dir>

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let mut link =
        tango_backend_mgba::SharedLink::boot(&rom, Some(&save), None, &tango_gamesupport_aw2::pvp::AW2E, None, None)
            .expect("boot");
    let core = link.core_mut();
    for id in 0xBD..=0xC1u32 {
        match tango_gamesupport_aw2::army_cards::team_glyph(core, (id - 0xBD) as u8) {
            Some((w, h, px)) => {
                println!("team {}: {w}x{h}", id - 0xBD);
                let mut ppm = format!("P6\n{w} {h}\n255\n").into_bytes();
                for p in px {
                    let c = p.unwrap_or((255, 0, 255));
                    ppm.extend_from_slice(&[c.0, c.1, c.2]);
                }
                std::fs::write(out.join(format!("team_{}.ppm", id - 0xBD)), ppm).unwrap();
            }
            None => println!("team {}: none", id - 0xBD),
        }
    }
}
