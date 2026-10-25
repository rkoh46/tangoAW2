//! The reconnect countdown of a room's match as a message box of the game's own look (presentation only).
//!
//! While the match waits for a player who dropped, the drive loop is paused: it sets [`tango_gamesupport::hold::set`] (who, seconds left) and
//! keeps handing the window a picture, and [`draw`] puts the box over it: AW2's window frame, Nell's portrait, the
//! game's font, the map not dimmed. The state is a static of the window's process, not console RAM: it is not part
//! of the simulation (every peer has its own countdown), so it must not be carried by rollback or checked by the
//! peers' state hashes.
//!
//! `TANGOAW2_FAKE_HOLD=<name>:<seconds>` shows the box without a match (test aid): the seconds count down from the
//! first picture. `TANGOAW2_FAKE_MIGRATION=<name>` shows the host migration's box (the new host's gamertag; a name
//! of `You` is this player).
//!
//! A host migration (the host left and the room goes on under its successor) is the same box with other words:
//! "Host left. <name> is hosting now... reconnecting".

use std::sync::Mutex;
use std::time::Instant;

use mgba::core::Core;

use crate::online::{text_width, wrap, Rgba, BLUE, GRAY_INK, H, INK, LIGHT_GRAY, SHADE, W};

static FAKE: Mutex<Option<Instant>> = Mutex::new(None);
static FACE: Mutex<Option<(Vec<u8>, [u8; 32])>> = Mutex::new(None);

/// Nell's id.
const NELL: u8 = 0;

/// Whether the box is up.
pub fn shown() -> bool {
    current().is_some() || migration().is_some()
}

fn migration() -> Option<(String, bool)> {
    if let Some(m) = tango_gamesupport::hold::migration() {
        return Some(m);
    }
    let name = std::env::var("TANGOAW2_FAKE_MIGRATION").ok()?;
    let you = name == "You";
    Some((name, you))
}

fn current() -> Option<(String, u32)> {
    if let Some(h) = tango_gamesupport::hold::get() {
        return Some(h);
    }
    let v = std::env::var("TANGOAW2_FAKE_HOLD").ok()?;
    let (name, secs) = v.rsplit_once(':')?;
    let secs: u32 = secs.parse().ok()?;
    let t0 = *FAKE.lock().unwrap().get_or_insert_with(Instant::now);
    Some((name.to_string(), secs.saturating_sub(t0.elapsed().as_secs() as u32)))
}

/// The lines of the box for a name and the seconds left, fitted to `width` pixels.
fn lines(core: &Core, name: &str, secs: u32, width: i32) -> (Vec<String>, Vec<String>) {
    let name = crate::online::fit(core, name, width - text_width(core, "Waiting for "));
    (
        vec![format!("Waiting for {name}"), format!("to reconnect... {secs}s")],
        wrap(
            core,
            if tango_gamesupport::hold::unranked() {
                "If they do not return, their army yields and you win."
            } else if tango_gamesupport::hold::host_wait() {
                "The match goes on without them if they do not return."
            } else {
                "Your match is saved for RESUME if they do not return."
            },
            width,
        ),
    )
}

/// The lines of the host migration's box: the host left, who hosts now (`you`: this player), and what happens next.
fn migration_lines(core: &Core, name: &str, you: bool, width: i32) -> (Vec<String>, Vec<String>) {
    let line = if you {
        "You are hosting now".to_string()
    } else {
        format!(
            "{} is hosting now",
            crate::online::fit(core, name, width - text_width(core, " is hosting now"))
        )
    };
    (
        vec!["Host left.".to_string(), line, "Reconnecting...".to_string()],
        wrap(core, "The match goes on in a few seconds.", width),
    )
}

/// The box over a 240 x 160 picture, if a hold is on.
pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 {
        return;
    }
    let migrating = migration();
    let Some((name, secs)) = migrating.clone().map(|(n, _)| (n, 0)).or_else(current) else {
        return;
    };
    let mut cv = Rgba(rgba);
    let (x, y, w, h) = (8, 30, W as i32 - 16, 98);
    crate::online::audit::cover(x, y, w, h);
    cv.window(x, y, w, h);
    // Nell's face in a frame, at the left.
    let (fx, fy, fs) = (x + 8, y + 10, 48);
    cv.rect(fx - 2, fy - 2, fs + 4, fs + 4, INK);
    {
        let mut face = FACE.lock().unwrap();
        if face.is_none() {
            *face = Some(crate::tag_ui::portrait48(core, NELL));
        }
        let (px, pal) = face.as_ref().unwrap();
        for yy in 0..fs {
            for xx in 0..fs {
                let (sx, sy) = (xx as usize, yy as usize);
                let t = 6 * (sy / 8) + sx / 8;
                let b = px.get(32 * t + 4 * (sy % 8) + (sx % 8) / 2).copied().unwrap_or(0);
                let v = ((b >> (4 * (sx & 1))) & 15) as usize;
                let c = u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]]);
                cv.put(fx + xx, fy + yy, crate::online::bgr(c));
            }
        }
    }
    let tx = fx + fs + 10;
    let tw = x + w - 8 - tx;
    let (head, note) = match migrating {
        Some((name, you)) => migration_lines(core, &name, you, tw),
        None => lines(core, &name, secs, tw),
    };
    let mut ty = y + 8;
    for l in &head {
        cv.text(core, tx, ty, l, INK, SHADE);
        ty += 13;
    }
    ty += 5;
    for l in &note {
        cv.text(core, tx, ty, l, GRAY_INK, SHADE);
        ty += 12;
    }
    // The way out, on its own line at the foot.
    let by = y + h - 17;
    cv.rect(x + 6, by - 3, w - 12, 1, LIGHT_GRAY);
    let t = "B: Disconnect";
    cv.text(core, x + (w - text_width(core, t)) / 2, by, t, BLUE, SHADE);
}
