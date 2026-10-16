//! Text audit of the in-game ONLINE pages: every page at its longest strings, rendered on the real console as BMPs
//! (<out-dir>/NAME.bmp), with the canvas's record of every string (`online::audit`) checked against the window and
//! the screen it is drawn in, and against its neighbours on the line.
//!
//! Usage: [TANGOAW2_DS_ROM=<nds>] aw2_online_text_audit <rom> <out-dir>
//!
//! Prints `PROBLEM <case>: ...` for each string that leaves its box, and `done: N problems`.

use tango_gamesupport_aw2::online::{audit, mailbox, Status, HOST, LINK_DIRECT, LINK_RELAY, YOU};
use tango_match::{HostInput, Link};

const STATE: u32 = tango_gamesupport_aw2::online::STATE;

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

struct Ctx {
    link: tango_backend_mgba::SharedLink,
    out: std::path::PathBuf,
    problems: usize,
}

impl Ctx {
    /// Clears the lobby's blocks, lets `set` fill them, draws once and checks.
    fn page(&mut self, name: &str, set: impl FnOnce(&mut mgba::core::Core)) {
        let core = self.link.core_mut();
        core.raw_write_range(STATE, -1, &[0u8; 0x100]);
        core.raw_write_range(tango_gamesupport_aw2::online::SAVED, -1, &vec![0u8; tango_gamesupport_aw2::online::SAVED_LEN as usize]);
        core.raw_write_range(tango_gamesupport_aw2::online_browse::STATE, -1, &[0u8; 0x100]);
        // (the record's lines and the gamertag)
        core.raw_write_range(tango_gamesupport_aw2::online_stats::BASE, -1, &vec![0u8; 0x100 + 0x20 * 24]);
        set(core);
        // (the console's own screen follows the level: the menu's words and help)
        for _ in 0..3 {
            self.link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
        audit::start();
        let frame = self.link.solo_side().frame().expect("frame");
        let bad = audit::finish();
        write_bmp(&self.out.join(format!("{name}.bmp")), &frame);
        for b in &bad {
            println!("PROBLEM {name}: {b}");
        }
        self.problems += bad.len();
    }
}

fn w(core: &mut mgba::core::Core) -> impl FnMut(u32, &[u8]) + '_ {
    move |a, b| core.raw_write_range(a, -1, b)
}

fn level(core: &mut mgba::core::Core, l: u8) {
    core.raw_write_8(STATE, -1, l);
}

fn tag(core: &mut mgba::core::Core, name: &str, lines: &[String]) {
    tango_gamesupport_aw2::online_stats::sync(&mut w(core), name, lines);
}

fn status(core: &mut mgba::core::Core, s: Status, m: &str) {
    mailbox::write_status(&mut w(core), s, m);
}

/// A room of `n` players: (name, ready, flags, link kind, rtt).
fn room(core: &mut mgba::core::Core, hosting: bool, me: usize, names: &[&str], ready: &[bool], kinds: &[(u8, u32)]) {
    for (k, name) in names.iter().enumerate() {
        let mut flags = if k == 0 { HOST } else { 0 };
        if k == me {
            flags |= YOU;
        }
        mailbox::write_player(&mut w(core), k, Some((name, ready[k], flags)));
        if k != me {
            mailbox::write_link(&mut w(core), k, kinds[k].0, kinds[k].1);
        }
    }
    let _ = hosting;
}

fn typed(core: &mut mgba::core::Core, at: u32, len_at: u32, s: &str) {
    core.raw_write_range(at, -1, s.as_bytes());
    core.raw_write_8(len_at, -1, s.len() as u8);
}

const W12: &str = "WWWWWWWWWWWW";
const W10: &str = "WWWWWWWWWW";

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    if std::env::var_os("TANGOAW2_DS_ROM").is_some() {
        tango_gamesupport_aw2::ds_pack::pack();
    }
    mailbox::boot_to_lobby();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    let link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, None, None).expect("boot");
    let mut c = Ctx { link, out, problems: 0 };
    let mut t = 0;
    while t < 3000 && tango_gamesupport_aw2::online_menu::cursor(c.link.core()).is_none() {
        c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
        t += 1;
    }
    for _ in 0..120 {
        c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
    }
    assert!(tango_gamesupport_aw2::online_menu::cursor(c.link.core()).is_some(), "the ONLINE screen did not come up");

    // --- gamertag corner, ONLINE hub ---
    for (name, tagname) in [("hub_tag_w", W10), ("hub_tag_none", "")] {
        c.page(name, |core| {
            level(core, 0);
            tag(core, tagname, &[]);
        });
    }
    c.page("hub_soon", |core| {
        level(core, 0);
        core.raw_write_8(STATE + 3, -1, 200);
        tag(core, W10, &[]);
        let p = tango_gamesupport_aw2::online_menu::menu_proc(core).unwrap();
        core.raw_write_16(p + 0x36, -1, 0);
    });
    for cur in 0..3u16 {
        c.page(&format!("hub_help{cur}"), |core| {
            level(core, 0);
            tag(core, "Nell", &[]);
            let p = tango_gamesupport_aw2::online_menu::menu_proc(core).unwrap();
            core.raw_write_16(p + 0x36, -1, cur);
        });
    }
    // --- LOBBY menu: the three helps, the notes ---
    for cur in 0..3u16 {
        c.page(&format!("lobby_help{cur}"), |core| {
            level(core, 1);
            tag(core, W10, &[]);
            let p = tango_gamesupport_aw2::online_menu::menu_proc(core).unwrap();
            core.raw_write_16(p + 0x36, -1, cur);
        });
    }
    let notes = [
        format!("{W12} disconnected - match saved. Resume it from ONLINE > RESUME"),
        format!("{W12} disconnected."),
        "The match is over.".to_string(),
        "You left the match.".to_string(),
        "The match could not start (the host's save did not unpack: unexpected end of..).".to_string(),
    ];
    for (k, n) in notes.iter().enumerate() {
        c.page(&format!("lobby_note{k}"), |core| {
            level(core, 1);
            tag(core, W10, &[]);
            mailbox::write_note(&mut w(core), n);
            status(core, Status::Back, "");
        });
    }
    // --- the room pages (host: level 2, guest: level 4) ---
    let names5 = [W12, "Gamertag10", "Nell", W12, "Fifth"];
    let kinds = [(0, 0), (LINK_RELAY, 255), (LINK_DIRECT, 23), (LINK_RELAY, 140), (LINK_DIRECT, 7)];
    for (lvl, who) in [(2u8, "host"), (4u8, "guest")] {
        for n in 2..=5usize {
            for (variant, pw, st, msg) in [
                ("wait", "", Status::Waiting, ""),
                ("pw", "UT", Status::Waiting, ""),
                ("pwfull", "WWWW", Status::Connected, ""),
            ] {
                c.page(&format!("room_{who}_{n}_{variant}"), |core| {
                    level(core, lvl);
                    tag(core, W10, &[]);
                    let me = if lvl == 2 { 0 } else { n - 1 };
                    room(core, lvl == 2, me, &names5[..n], &[false, true, false, true, false], &kinds);
                    typed(core, STATE + 0x5A, STATE + 0x59, pw);
                    if lvl == 2 {
                        mailbox::write_room(&mut w(core), "WWWWWW");
                    } else {
                        typed(core, STATE + 4, STATE + 2, "WWWWWW");
                    }
                    status(core, st, msg);
                });
            }
        }
        // ready states with every tag (START / READY / HOST / ...)
        c.page(&format!("room_{who}_5_ready"), |core| {
            level(core, lvl);
            let me = if lvl == 2 { 0 } else { 4 };
            room(core, lvl == 2, me, &names5, &[true; 5], &kinds);
            typed(core, STATE + 0x5A, STATE + 0x59, "UT");
            mailbox::write_room(&mut w(core), "ABCDEF");
            typed(core, STATE + 4, STATE + 2, "ABCDEF");
            status(core, Status::Connected, W12);
        });
    }
    // --- every message the app can put on the room and unranked pages ---
    let messages = [
        "No room with that code is open.",
        "The matchmaking server cannot be reached.",
        "Wrong password.",
        "The room is full.",
        "The match has already started.",
        "The host has another game or patch.",
        "Your tangoAW2 is older: update it to play.",
        "The host's tangoAW2 is older: they must update.",
        "The host's game is not one you have.",
        "You are not in the match this room resumes.",
        "Your gamertag is already in this room.",
        "This match needs the Dual Strike pack.",
        "The host stopped answering.",
        "The host's save did not arrive intact.",
        "The host's save did not unpack.",
        "The host's saved match did not unpack.",
        "The host closed the room.",
        "A player left before the match began.",
        "A player did not get the start in time.",
        "A player's link broke as the match began.",
        "Could not pack the save.",
        "Not connected.",
        "Could not connect.",
        "Server cannot be reached.",
        "Nobody else is looking.",
        "The other player left.",
        "@waiting4",
        "@waiting1",
        "Connected: joining...",
    ];
    for (k, m) in messages.iter().enumerate() {
        for (lvl, who) in [(2u8, "host"), (4u8, "guest"), (6u8, "unranked")] {
            let w4 = mailbox::waiting_for(&[W12.to_string(), W12.to_string(), W12.to_string(), W12.to_string()]);
            let w1 = mailbox::waiting_for(&[W10.to_string()]);
            let m = match *m {
                "@waiting4" => w4.as_str(),
                "@waiting1" => w1.as_str(),
                m => m,
            };
            let st = if m.starts_with("Waiting for") { Status::Waiting } else { Status::Failed };
            c.page(&format!("msg{k:02}_{who}"), |core| {
                level(core, lvl);
                if lvl != 6 {
                    let me = if lvl == 2 { 0 } else { 2 };
                    room(core, lvl == 2, me, &names5[..3], &[false; 3], &kinds);
                    mailbox::write_room(&mut w(core), "ABCDEF");
                    typed(core, STATE + 4, STATE + 2, "ABCDEF");
                }
                // (the mailbox cuts the message to what the console holds)
                status(core, st, m);
            });
        }
    }
    c.page("unranked_search", |core| {
        level(core, 6);
        status(core, Status::Waiting, "");
    });
    c.page("unranked_found", |core| {
        level(core, 6);
        status(core, Status::Connected, W12);
    });
    // --- code and password entry ---
    c.page("code_empty", |core| level(core, 3));
    c.page("code_full", |core| {
        level(core, 3);
        typed(core, STATE + 4, STATE + 2, "WWWWWW");
        core.raw_write_8(STATE + 1, -1, 36);
    });
    for (entry, who) in [(0u8, "make"), (1u8, "join")] {
        c.page(&format!("password_{who}"), |core| {
            level(core, 5);
            core.raw_write_8(STATE + 0x58, -1, entry);
            typed(core, STATE + 0x5A, STATE + 0x59, "WWWW");
            core.raw_write_8(STATE + 1, -1, 37);
        });
    }
    // --- browser ---
    let long_rows: Vec<tango_gamesupport_aw2::online_browse::Row> = (0..9)
        .map(|k| tango_gamesupport_aw2::online_browse::Row {
            code: format!("ABCD{k:02}"),
            host: [W12, "Gamertag10", "Nell", "A", W10][k % 5].to_string(),
            players: [5u8, 1, 3, 4, 2][k % 5],
            max: 5,
            locked: k % 2 == 0,
        })
        .collect();
    for (name, rows, net, ver, cur) in [
        ("browse_full", long_rows.clone(), tango_gamesupport_aw2::online_browse::Net::Ok, "0.10.12-beta", 0usize),
        ("browse_full_c1", long_rows.clone(), tango_gamesupport_aw2::online_browse::Net::Ok, "0.10.12-beta.3", 1),
        ("browse_full_c2", long_rows.clone(), tango_gamesupport_aw2::online_browse::Net::Ok, "0.7.1", 2),
        ("browse_full_c3", long_rows.clone(), tango_gamesupport_aw2::online_browse::Net::Ok, "0.7.1", 3),
        ("browse_full_c9", long_rows.clone(), tango_gamesupport_aw2::online_browse::Net::Ok, "0.10.12-beta.3", 9),
        ("browse_empty", vec![], tango_gamesupport_aw2::online_browse::Net::Ok, "0.7.1", 0),
        ("browse_looking", vec![], tango_gamesupport_aw2::online_browse::Net::Looking, "0.7.1", 0),
        ("browse_offline", vec![], tango_gamesupport_aw2::online_browse::Net::Offline, "0.7.1", 0),
    ] {
        c.page(name, |core| {
            level(core, 7);
            tango_gamesupport_aw2::online_browse::mailbox::write(&mut w(core), &rows, net, ver);
            core.raw_write_8(tango_gamesupport_aw2::online_browse::STATE + 1, -1, cur as u8);
            core.raw_write_8(tango_gamesupport_aw2::online_browse::STATE + 2, -1, cur.saturating_sub(7) as u8);
        });
    }
    // --- RESUME ---
    let saved: Vec<mailbox::SavedRow> = (0..6)
        .map(|k| mailbox::SavedRow {
            players: format!("{W12}, {W12}, {W12}, {W12}, {W12}"),
            map: "WWWWWWWWWWWWWWWWWWWWWWWWWWW".to_string(),
            tail: format!("Day 99 {} Sep 14:05", 20 + k),
        })
        .collect();
    c.page("resume_rows", |core| {
        level(core, 8);
        mailbox::write_saved(&mut w(core), &saved);
        core.raw_write_8(STATE + 0x6A, -1, 2);
    });
    c.page("resume_empty", |core| level(core, 8));
    // --- gamertag entry and STATS ---
    c.page("tag_entry", |core| {
        level(core, 9);
        tag(core, W10, &[]);
        tango_gamesupport_aw2::online_stats::open_entry(core, 0);
    });
    c.page("tag_entry_empty", |core| {
        level(core, 9);
    });
    let mut lines = vec![
        "Battles played\t99999".to_string(),
        "Won\t99999".to_string(),
        "Lost\t99999".to_string(),
        "Win rate\t100%".to_string(),
        "Units destroyed\t99999".to_string(),
        "Units lost\t99999".to_string(),
        "CO powers used\t99999".to_string(),
        "Days played\t99999".to_string(),
        "Last opponents".to_string(),
    ];
    for k in 0..8 {
        let who: String = format!("{W12} +3");
        lines.push(format!("  {who}\t{}", if k % 2 == 0 { "Won" } else { "Lost" }));
    }
    c.page("stats_full", |core| {
        level(core, 10);
        tag(core, W10, &lines);
    });
    c.page("stats_scrolled", |core| {
        level(core, 10);
        tag(core, W10, &lines);
        core.raw_write_8(tango_gamesupport_aw2::online_stats::BASE + 0x20, -1, 8);
    });
    c.page("stats_empty", |core| {
        level(core, 10);
        tag(core, W10, &[]);
    });
    // The Teams screen's own record (the CO list): the console as Play offline reaches Versus' Teams.
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, None, None).expect("boot");
    let mut c = Ctx { link, out: c.out.clone(), problems: c.problems };
    {
        let (a, b, d, e) = (1u32, 1u32 << 3, 1u32 << 7, 0u32);
        let wait = |c: &mut Ctx, n: u32| {
            for _ in 0..n {
                c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
            }
        };
        let press = |c: &mut Ctx, k: u32| {
            for _ in 0..8 {
                c.link.tick([HostInput::keys(k), HostInput::keys(0)]);
            }
            for _ in 0..6 {
                c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
            }
        };
        let _ = e;
        wait(&mut c, 700);
        press(&mut c, b);
        wait(&mut c, 300);
        press(&mut c, a);
        wait(&mut c, 150);
        press(&mut c, d);
        wait(&mut c, 60);
        for _ in 0..3 {
            press(&mut c, a);
            wait(&mut c, 150);
        }
    }
    armies(&mut c);
    proposals(&mut c);
    println!("done: {} problems", c.problems);
}

fn paint(c: &mut Ctx, name: &str, save: bool, draw: impl FnOnce(&mgba::core::Core, &mut [u8])) {
    let mut rgba = vec![0u8; 240 * 160 * 4];
    audit::start();
    draw(c.link.core(), &mut rgba);
    let bad = audit::finish();
    if save {
        write_bmp(&c.out.join(format!("{name}.bmp")), &rgba);
    }
    for b in &bad {
        println!("PROBLEM {name}: {b}");
    }
    c.problems += bad.len();
}

/// SELECT YOUR ARMY: every CO as a seat's pick at its widest (arrows on), long gamertags, 2..5 seats.
fn armies(c: &mut Ctx) {
    use tango_gamesupport_aw2::online_teams as ot;
    let core = c.link.core_mut();
    let list = tango_gamesupport_aw2::tag_ui::teams_list(core);
    let labels: Vec<String> = list.iter().map(|&co| ot::co_label(core, co)).collect();
    let widest = (0..list.len()).max_by_key(|&i| tango_gamesupport_aw2::online::text_width(core, &labels[i])).unwrap();
    println!("armies: {} COs, widest {:?}", list.len(), labels[widest]);
    let by_name = |n: &str| labels.iter().position(|l| l == n);
    let names = [W12, "Gamertag10", "Nell", W10, "Xx"];
    let colours = [1u8, 2, 4, 3, 5];
    for tags_on in [false, true] {
        for n in 2..=5usize {
            for (field, fname) in [(0u8, "co"), (3u8, "partner"), (2u8, "team"), (4u8, "ready")] {
                if field == 3 && !tags_on {
                    continue;
                }
                // every CO in seat 0..n (the widest first), so each is drawn on each seat's row
                let mut cos: Vec<usize> = (0..list.len()).collect();
                cos.sort_by_key(|&i| std::cmp::Reverse(tango_gamesupport_aw2::online::text_width(c.link.core(), &labels[i])));
                for (k, chunk) in cos.chunks(n).enumerate() {
                    for local in 0..n {
                        if k > 0 && local != n - 1 {
                            continue;
                        }
                        let core = c.link.core_mut();
                        let mut ram = vec![0u8; 0x100];
                        ram[0] = 1;
                        ram[2] = n as u8;
                        for s in 0..n {
                            let b = 0x10 + 0x10 * s;
                            ram[b] = chunk[s % chunk.len()] as u8;
                            ram[b + 1] = colours[s];
                            ram[b + 2] = if tags_on { list[(chunk[s % chunk.len()] + 1) % list.len()] } else { 0xFF };
                            ram[b + 5] = [0u8, 0, 1, 1, 2][s];
                            ram[b + 3] = if s == local { field } else { 0 };
                            ram[b + 4] = (field == 4 && s != local) as u8;
                        }
                        core.raw_write_range(ot::SEL, -1, &ram);
                        tango_gamesupport_aw2::online::set_room(names[..n].iter().map(|s| s.to_string()).collect(), local);
                        core.raw_write_8(tango_gamesupport_aw2::ds_weather::DS_ON, -1, tags_on as u8);
                        let save = k == 0 && local == n - 1 || (k == 0 && local == 0 && n == 5);
                        let tag = format!("army_{}p_{}{}_s{local}_{}", n, fname, if tags_on { "_tag" } else { "" }, labels[chunk[0]].replace(' ', ""));
                        paint(c, &tag, save, |core, rgba| ot::draw(core, rgba));
                    }
                }
            }
        }
    }
    // the notes and bars
    for (n, local, ready, note, tag) in [(3usize, 0usize, false, true, "note"), (3, 2, true, false, "waiting"), (2, 1, false, false, "bar_guest")] {
        let core = c.link.core_mut();
        let mut ram = vec![0u8; 0x100];
        ram[0] = 1;
        ram[2] = n as u8;
        for s in 0..n {
            let b = 0x10 + 0x10 * s;
            ram[b] = by_name("Von Bolt").unwrap_or(1) as u8;
            ram[b + 1] = colours[s];
            ram[b + 2] = 0xFF;
            ram[b + 3] = if s == local { 2 } else { 0 };
            ram[b + 4] = (ready && s == local) as u8;
        }
        if note {
            ram[4] = 100;
        }
        core.raw_write_range(ot::SEL, -1, &ram);
        tango_gamesupport_aw2::online::set_room(names[..n].iter().map(|s| s.to_string()).collect(), local);
        paint(c, &format!("army_{tag}"), true, |core, rgba| ot::draw(core, rgba));
    }
}

/// UNRANKED's map pick: the bar over SELECT MAP's own screen at its longest (both gamertags, the widest map name).
fn proposals(c: &mut Ctx) {
    use tango_gamesupport_aw2::unranked as un;
    let core = c.link.core_mut();
    let mut widest = (0, 1u8);
    for id in 1..100u8 {
        let w = tango_gamesupport_aw2::online::text_width(core, &un::map_name(core, id));
        if w > widest.0 {
            widest = (w, id);
        }
    }
    println!("unranked: widest map name #{} ({} px)", widest.1, widest.0);
    for local in 0..2usize {
        tango_gamesupport_aw2::online::set_room(vec![W12.to_string(), W12.to_string()], local);
        for (picks, phase, tag) in [(0u8, 0u8, "first"), (1, 0, "second"), (2, 1, "played0"), (2, 1, "played1")] {
            let core = c.link.core_mut();
            un::set_state(core, picks, [widest.1, widest.1], phase, tag.ends_with('1') as u8);
            paint(c, &format!("unranked_s{local}_{tag}"), true, |core, rgba| un::paint_bar(core, rgba));
        }
    }
}
