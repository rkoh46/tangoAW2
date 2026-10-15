//! Preview of the online SELECT YOUR ARMY page with 2..5 fake seats (PPMs into <out-dir>).
//!
//! Usage: TANGOAW2_DS_ROM=<nds> aw2_armysel_preview <rom> <out-dir>
//!
//!
//!
//! Boots the console as Play offline does, goes to Versus → Bean Island →
//! Teams, presses SELECT on army 1 until it reaches Black Hole, moves to
//! army 2 and presses L, then starts the battle and prints each army's
//! colour.
//!
//! Usage: aw2_teams_check <rom> <out-dir>

use tango_match::{HostInput, Link};

const A: u32 = 1;
const START: u32 = 1 << 3;
const DOWN: u32 = 1 << 7;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    tango_gamesupport_aw2::ds_pack::pack();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let mut link =
        tango_backend_mgba::SharedLink::boot(&rom, Some(&save), None, &tango_gamesupport_aw2::pvp::AW2E, None, None)
            .expect("boot");
    let wait = |link: &mut tango_backend_mgba::SharedLink, n: u32| {
        for _ in 0..n {
            link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
    };
    let press = |link: &mut tango_backend_mgba::SharedLink, keys: u32| {
        for _ in 0..8 {
            link.tick([HostInput::keys(keys), HostInput::keys(0)]);
        }
        for _ in 0..6 {
            link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
    };
    wait(&mut link, 700);
    press(&mut link, START);
    wait(&mut link, 300);
    press(&mut link, A);
    wait(&mut link, 150);
    press(&mut link, DOWN);
    wait(&mut link, 60);
    for _ in 0..3 {
        press(&mut link, A);
        wait(&mut link, 150);
    }
    let core = link.core_mut();
    let list = tango_gamesupport_aw2::tag_ui::teams_list(core);
    let find = |core: &mgba::core::Core, name: &str| {
        list.iter().position(|&c| tango_gamesupport_aw2::online_teams::co_label(core, c) == name)
    };
    for (i, &c) in list.iter().enumerate() {
        println!("{i}: {}", tango_gamesupport_aw2::online_teams::co_label(core, c));
    }
    let vb = find(core, "Von Bolt").unwrap_or(1) as u8;
    let ca = find(core, "Clone Andy").unwrap_or(2) as u8;
    let sat = list.len().min(7) as u8;
    let cos = [vb, ca, 0, 3, sat];
    let names = ["Gamertag10", "Hostname", "Guest", "Nell", "XxLongNamexX"];
    let colours = [1u8, 2, 4, 3, 5];
    // (players, local seat, field, ready flags)
    let cases: [(usize, usize, u8, [bool; 5], &str); 9] = [
        (2, 1, 0, [false; 5], "2"),
        (3, 0, 2, [false; 5], "3_partner"),
        (3, 0, 0, [false; 5], "3_co"),
        (3, 2, 1, [false; 5], "3"),
        (4, 1, 0, [true, false, false, false, false], "4"),
        (5, 4, 0, [true, false, false, true, false], "5"),
        (5, 2, 1, [true, false, false, true, false], "5_colour"),
        (5, 3, 2, [false, true, false, false, false], "5_partner"),
        (5, 0, 3, [false, false, false, false, false], "5_ready"),
    ];
    for (n, local, field, ready, tag) in cases {
        let mut ram = vec![0u8; 0x100];
        ram[0] = 1;
        ram[2] = n as u8;
        for s in 0..n {
            let b = 0x10 + 0x10 * s;
            ram[b] = cos[s];
            ram[b + 1] = colours[s];
            ram[b + 2] = if s % 2 == 1 { 0xFF } else { cos[(s + 1) % 5] };
            ram[b + 3] = if s == local { field } else { 0 };
            ram[b + 4] = ready[s] as u8;
        }
        core.raw_write_range(tango_gamesupport_aw2::online_teams::SEL, -1, &ram);
        tango_gamesupport_aw2::online::set_room(names[..n].iter().map(|s| s.to_string()).collect(), local);
        core.raw_write_8(tango_gamesupport_aw2::ds_weather::DS_ON, -1, 1);
        let mut rgba = vec![0u8; 240 * 160 * 4];
        tango_gamesupport_aw2::online_teams::draw(core, &mut rgba);
        let mut ppm = b"P6\n240 160\n255\n".to_vec();
        for px in rgba.chunks(4) {
            ppm.extend_from_slice(&px[..3]);
        }
        std::fs::write(out.join(format!("armysel_{tag}.ppm")), ppm).unwrap();
    }
    // Every CO's face in both row styles: pages of 5 (compact) and 3 (full size) seats, main CO and the next as partner.
    for (n, tag) in [(5usize, "c"), (3, "f")] {
        for (page, chunk) in (0..list.len()).collect::<Vec<_>>().chunks(n).enumerate() {
            let mut ram = vec![0u8; 0x100];
            ram[0] = 1;
            ram[2] = n as u8;
            for (s, &idx) in chunk.iter().enumerate() {
                let b = 0x10 + 0x10 * s;
                ram[b] = idx as u8;
                ram[b + 1] = colours[s];
                ram[b + 2] = list[(idx + 1) % list.len()];
            }
            core.raw_write_range(tango_gamesupport_aw2::online_teams::SEL, -1, &ram);
            tango_gamesupport_aw2::online::set_room(chunk.iter().map(|&i| format!("#{i}")).collect::<Vec<_>>(), 99);
            let mut rgba = vec![0u8; 240 * 160 * 4];
            tango_gamesupport_aw2::online_teams::draw(core, &mut rgba);
            let mut ppm = b"P6\n240 160\n255\n".to_vec();
            for px in rgba.chunks(4) {
                ppm.extend_from_slice(&px[..3]);
            }
            std::fs::write(out.join(format!("faces_{tag}{page}.ppm")), ppm).unwrap();
        }
    }
}
