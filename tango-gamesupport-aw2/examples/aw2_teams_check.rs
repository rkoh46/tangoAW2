//! In-game army picking on Versus' Teams screen.
//!
//! Boots the console as Play offline does, goes to Versus → Bean Island →
//! Teams, presses SELECT on army 1 until it reaches Black Hole, moves to
//! army 2 and presses L, then starts the battle and prints each army's
//! colour.
//!
//! Usage: [AW2_TEAMS_TABS=k] [AW2_TEAMS_COS=1] aw2_teams_check <rom> <out-dir>

use tango_match::{HostInput, Link};

const A: u32 = 1;
const SELECT: u32 = 1 << 2;
const START: u32 = 1 << 3;
const RIGHT: u32 = 1 << 4;
const DOWN: u32 = 1 << 7;
const UP: u32 = 1 << 6;
const B: u32 = 1 << 1;
const L: u32 = 1 << 9;

fn write_bmp(path: &std::path::Path, rgba: &[u8]) {
    let (w, h) = (240u32, 160u32);
    let mut out = Vec::new();
    out.extend_from_slice(b"BM");
    out.extend_from_slice(&(54 + w * h * 3).to_le_bytes());
    out.extend_from_slice(&[0, 0, 0, 0, 54, 0, 0, 0, 40, 0, 0, 0]);
    out.extend_from_slice(&(w as i32).to_le_bytes());
    out.extend_from_slice(&(-(h as i32)).to_le_bytes());
    out.extend_from_slice(&[1, 0, 24, 0]);
    out.extend_from_slice(&[0u8; 24]);
    for px in rgba.chunks(4) {
        out.extend_from_slice(&[px[2], px[1], px[0]]);
    }
    std::fs::write(path, out).unwrap();
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
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
    // Campaign to Versus: one step on AW2's wheel, two with the pack's Gauntlet between them (by the cursor, as aw2test does)
    for _ in 0..4 {
        if link.core_mut().raw_read_8(0x0300_591C, -1) == 3 {
            break;
        }
        press(&mut link, DOWN);
        wait(&mut link, 60);
    }
    // AW2_TEAMS_TABS=k: the map list's tab k to the right of 2P (3P, 4P, 5P Predeploy...): a Teams screen of more armies
    let tabs: u32 = std::env::var("AW2_TEAMS_TABS").ok().and_then(|v| v.parse().ok()).unwrap_or(0);
    for i in 0..3 {
        if i == 2 {
            for _ in 0..tabs {
                press(&mut link, RIGHT);
                wait(&mut link, 30);
            }
        }
        press(&mut link, A); // Versus, New, Bean Island (or the first map of the tab)
        wait(&mut link, 150);
    }
    let shot = |link: &mut tango_backend_mgba::SharedLink, name: &str| {
        write_bmp(&out.join(format!("{name}.bmp")), &link.side(0).frame().unwrap());
    };
    shot(&mut link, "teams_0");
    // AW2_TEAMS_COS=1: army 1's card for every CO of the Teams list (DOWN steps to the next), as co_NN.bmp
    if std::env::var_os("AW2_TEAMS_COS").is_some() {
        let n = tango_gamesupport_aw2::tag_ui::teams_list(link.core()).len();
        for i in 0..n {
            shot(&mut link, &format!("co_{i:02}"));
            press(&mut link, DOWN);
            wait(&mut link, 25);
        }
        return;
    }
    // (the card's tab, a partner pick: the cursor's other stops)
    press(&mut link, DOWN);
    wait(&mut link, 20);
    shot(&mut link, "teams_tab");
    press(&mut link, UP);
    wait(&mut link, 20);
    press(&mut link, START);
    wait(&mut link, 40);
    shot(&mut link, "teams_partner");
    press(&mut link, RIGHT);
    wait(&mut link, 20);
    shot(&mut link, "teams_partner_next");
    press(&mut link, B);
    wait(&mut link, 40);
    for i in 1..=4 {
        press(&mut link, SELECT);
        wait(&mut link, 20);
        shot(&mut link, &format!("teams_{i}"));
    }
    press(&mut link, RIGHT);
    wait(&mut link, 20);
    press(&mut link, RIGHT);
    wait(&mut link, 20);
    press(&mut link, L);
    wait(&mut link, 20);
    shot(&mut link, "teams_army2_L");
    press(&mut link, A);
    wait(&mut link, 100);
    press(&mut link, A);
    wait(&mut link, 700);
    shot(&mut link, "battle");
    let (mode, colours) = tango_gamesupport_aw2::pvp::army_state(link.core());
    println!("mode {mode}, battle army colours {colours:?}");
}
