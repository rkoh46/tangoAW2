//! The EXP box: after a battle that gave CO experience (the campaigns, the War Room, the Gauntlet, the end of a Survival run), the COs
//! that gained show it as Dual Strike's results do, in AW2's look: each human army's CO (a tag partner too) with its face, "+N EXP" and a
//! bar that fills from the old EXP to the new within the rank (1000 EXP a rank, crate::co_skills::rank), "Rank up!" when it crosses
//! one. A window of the game's own (red above, blue below), its font and the CO's face from the game (the Teams cards' mugs), over
//! AW2's results page the map is not dimmed (the model is [`crate::hold_box`]).
//!
//! When: [`crate::battle_points::results`] (a battle's end) and `survival_run_over` write what each CO had and has ([`record`], in EWRAM,
//! [`STATE`]); the box opens when AW2's results page has worked out its totals and waits for A (its proc script `0x08616184`, found
//! in the proc pool), or on Survival's results panel ([`crate::survival::results_up`]), and takes the pad while it is up ([`tick`]): A skips
//! the filling, then goes on to the next page of COs, then closes; the page under it takes the next A. Offline only (a room's results
//! give no EXP, and the pad is read only there).
//!
//! Everything the box shows is in EWRAM: the state machine, the frame it is on and the numbers, so that the picture is a function of the
//! console's memory. It is drawn over the finished picture ([`draw`], through `pvp`'s overlay).

use mgba::core::Core;

use crate::online::{text_width, Rgba, BLUE, GRAY_INK, H, INK, LIGHT_GRAY, RED, SHADE, W, WHITE, YELLOW};

/// tangoAW2's EWRAM 0x0203C640..0x0203C6AF: +0 state, +1 how many COs, +2 the page, +4 the frame (u16), then up to eight entries of 12
/// bytes from +8: CO (u8), army (u8), EXP before (u32 at +4), EXP after (u32 at +8).
pub const STATE: u32 = 0x0203_C640;
pub const STATE_LEN: u32 = 0x70;
const COUNT: u32 = STATE + 1;
const PAGE: u32 = STATE + 2;
const FRAME: u32 = STATE + 4;
const ENTRIES: u32 = STATE + 8;
const ENTRY: u32 = 12;
const MAX_ENTRIES: usize = 8;

/// The states: nothing; the numbers are recorded and the results page has not come; the box is up; it is closed and the pad is given back when A and B are let go.
pub const IDLE: u8 = 0;
pub const PENDING: u8 = 1;
pub const SHOWN: u8 = 2;
pub const CLOSING: u8 = 3;

/// The results page's wait-for-A proc (`ProcScr` script, with the page's tally worked out).
const RESULTS_WAIT: u32 = 0x0861_6184;
const PROCS: u32 = 0x0200_D610;
const PROC_SIZE: u32 = 0x6C;
const PROC_COUNT: u32 = 32;

const KEY_A: u32 = 1 << 0;
const KEY_B: u32 = 1 << 1;

/// COs on a page.
pub const PER_PAGE: usize = 3;
/// Frames before the bar starts, how long it takes, and when the box is settled.
const DELAY: u32 = 18;
const FILL: u32 = 66;
pub const SETTLED: u32 = DELAY + FILL;

/// (CO, army, EXP before, EXP after) of each CO that took part.
pub type Entry = (u8, u8, u32, u32);

/// The numbers of a battle's end: the box waits for the results page. Nothing is shown unless some CO gained.
pub fn record(core: &mut Core, entries: &[Entry]) {
    let entries = &entries[..entries.len().min(MAX_ENTRIES)];
    if !entries.iter().any(|e| e.3 > e.2) {
        return;
    }
    core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
    for (k, &(co, army, old, new)) in entries.iter().enumerate() {
        let at = ENTRIES + ENTRY * k as u32;
        core.raw_write_8(at, -1, co);
        core.raw_write_8(at + 1, -1, army);
        core.raw_write_32(at + 4, -1, old);
        core.raw_write_32(at + 8, -1, new);
    }
    core.raw_write_8(COUNT, -1, entries.len() as u8);
    core.raw_write_8(STATE, -1, PENDING);
}

/// A battle starts: nothing is waiting any more.
pub fn reset(core: &mut Core) {
    if core.raw_read_8(STATE, -1) != IDLE {
        core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
    }
}

pub fn state(core: &Core) -> u8 {
    core.raw_read_8(STATE, -1)
}

/// The box is up.
pub fn shown(core: &Core) -> bool {
    state(core) == SHOWN
}

fn count(core: &Core) -> usize {
    (core.raw_read_8(COUNT, -1) as usize).min(MAX_ENTRIES)
}

fn entry(core: &Core, k: usize) -> Entry {
    let at = ENTRIES + ENTRY * k as u32;
    (
        core.raw_read_8(at, -1),
        core.raw_read_8(at + 1, -1),
        core.raw_read_32(at + 4, -1),
        core.raw_read_32(at + 8, -1),
    )
}

fn pages(core: &Core) -> usize {
    count(core).div_ceil(PER_PAGE).max(1)
}

/// AW2's results page has its totals and waits for A.
fn results_page_waits(core: &Core) -> bool {
    (0..PROC_COUNT).any(|k| core.raw_read_32(PROCS + PROC_SIZE * k, -1) == RESULTS_WAIT)
}

/// A Survival run's EXP is for the run's end: its panel, not the results page of the last map before it.
fn ready(core: &Core) -> bool {
    if crate::survival::on(core) {
        crate::survival::results_up(core)
    } else {
        results_page_waits(core)
    }
}

/// Each frame, offline (before the screens that read the pad): opens the box when the page is up, takes the pad while it is open.
pub fn tick(core: &mut Core, keys: u32, prev: u32) -> u32 {
    match state(core) {
        PENDING => {
            if ready(core) {
                core.raw_write_8(STATE, -1, SHOWN);
                core.raw_write_8(PAGE, -1, 0);
                core.raw_write_16(FRAME, -1, 0);
                // (the press that came with the page does not skip the box)
                return keys & !(KEY_A | KEY_B);
            }
            keys
        }
        SHOWN => {
            let frame = core.raw_read_16(FRAME, -1) as u32;
            core.raw_write_16(FRAME, -1, (frame + 1).min(0xFFF0) as u16);
            if (keys & !prev) & (KEY_A | KEY_B) != 0 {
                if frame < SETTLED {
                    core.raw_write_16(FRAME, -1, SETTLED as u16);
                } else if (core.raw_read_8(PAGE, -1) as usize) + 1 < pages(core) {
                    core.raw_write_8(PAGE, -1, core.raw_read_8(PAGE, -1) + 1);
                    core.raw_write_16(FRAME, -1, 0);
                } else {
                    core.raw_write_8(STATE, -1, CLOSING);
                }
            }
            0
        }
        CLOSING => {
            // The A that closed it is not the page's: the pad comes back when the keys are up.
            if keys & (KEY_A | KEY_B) == 0 {
                core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
                return keys;
            }
            keys & !(KEY_A | KEY_B)
        }
        _ => keys,
    }
}

// --- The numbers -----------------------------------------------------------------------------

/// How far the bar is at `frame` of a page: 0 to 1000 (eased out).
pub fn progress(frame: u32) -> u32 {
    if frame <= DELAY {
        return 0;
    }
    let t = (frame - DELAY).min(FILL) * 1000 / FILL;
    // (1 - (1 - t)^3)
    let u = 1000 - t;
    1000 - u * u / 1000 * u / 1000
}

/// The EXP the bar shows at `frame`: from `old` to `new`.
pub fn shown_exp(old: u32, new: u32, frame: u32) -> u32 {
    old + ((new.saturating_sub(old)) as u64 * progress(frame) as u64 / 1000) as u32
}

/// (rank, the bar's fill 0..=1000) of an EXP: 1000 EXP a rank, up to Dual Strike's rank 100 (a full bar there).
pub fn rank_fill(exp: u32) -> (u32, u32) {
    let rank = (exp / 1000).min(100);
    (rank, if rank >= 100 { 1000 } else { exp % 1000 })
}

// --- Drawing ---------------------------------------------------------------------------------

const FACE: i32 = 24;
const ROW: i32 = 31;

/// The box over a 240 x 160 picture, when it is up.
pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 || !shown(core) {
        return;
    }
    let page = core.raw_read_8(PAGE, -1) as usize;
    let frame = core.raw_read_16(FRAME, -1) as u32;
    let n = count(core);
    let rows: Vec<Entry> = (page * PER_PAGE..n.min(page * PER_PAGE + PER_PAGE)).map(|k| entry(core, k)).collect();
    if rows.is_empty() {
        return;
    }
    let mut cv = Rgba(rgba);
    let (w, h) = (W as i32 - 12, 22 + ROW * rows.len() as i32 + 17);
    let (x, y) = (6, (H as i32 - h) / 2);
    crate::online::audit::cover(x, y, w, h);
    cv.window(x, y, w, h);
    // The title, with the page when there is more than one.
    let title = if pages(core) > 1 { format!("EXP  {}/{}", page + 1, pages(core)) } else { "EXP".to_string() };
    cv.text(core, x + 8, y + 5, &title, INK, SHADE);
    cv.rect(x + 6, y + 18, w - 12, 1, LIGHT_GRAY);
    for (k, &(co, _army, old, new)) in rows.iter().enumerate() {
        let ry = y + 22 + ROW * k as i32;
        // The face in a frame.
        let (fx, fy) = (x + 8, ry + 2);
        cv.rect(fx - 1, fy - 1, FACE + 2, FACE + 2, INK);
        crate::online_teams::draw_face(core, &mut cv, co, fx, fy, FACE);
        let tx = fx + FACE + 8;
        let right = x + w - 8;
        let gain = new.saturating_sub(old);
        // Line one: the name, "Rank up!" once the bar has gone over a rank, and "+N EXP" at the right.
        let plus = format!("+{gain} EXP");
        let pw = text_width(core, &plus);
        let now = shown_exp(old, new, frame);
        let up = rank_fill(now).0 > rank_fill(old).0;
        let upw = text_width(core, "Rank up!");
        let room = right - tx - pw - 6 - if rank_fill(new).0 > rank_fill(old).0 { upw + 6 } else { 0 };
        let name = crate::online::fit(core, &crate::online_teams::co_label(core, co), room.max(20));
        let nx = cv.text(core, tx, ry + 2, &name, INK, SHADE);
        if up {
            // (a blink, as the game's own attention text)
            if frame / 6 % 4 != 3 {
                cv.text(core, nx + 6, ry + 2, "Rank up!", RED, SHADE);
            }
        }
        cv.text(core, right - pw, ry + 2, &plus, BLUE, SHADE);
        // Line two: the rank, and the bar.
        let (rank, fill) = rank_fill(now);
        let label = format!("Rank {rank}");
        cv.text(core, tx, ry + 15, &label, GRAY_INK, SHADE);
        let bx = tx + 40;
        let bw = right - bx;
        cv.rect(bx - 1, ry + 15, bw + 2, 9, INK);
        cv.rect(bx, ry + 16, bw, 7, WHITE);
        let filled = bw * fill as i32 / 1000;
        cv.rect(bx, ry + 16, filled, 7, if fill >= 1000 { YELLOW } else { BLUE });
        // a light line on the top of the fill, as the game's gauges
        cv.rect(bx, ry + 16, filled, 1, if fill >= 1000 { WHITE } else { (136, 160, 255) });
    }
    // The way on, at the foot.
    let by = y + h - 15;
    cv.rect(x + 6, by - 3, w - 12, 1, LIGHT_GRAY);
    let more = frame >= SETTLED && page + 1 < pages(core);
    let t = if frame < SETTLED { "A: Skip" } else if more { "A: Next" } else { "A: OK" };
    cv.text(core, x + (w - text_width(core, t)) / 2, by, t, BLUE, SHADE);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_bar_fills_from_old_to_new() {
        assert_eq!(shown_exp(1200, 1900, 0), 1200);
        assert_eq!(shown_exp(1200, 1900, DELAY), 1200);
        assert_eq!(shown_exp(1200, 1900, SETTLED), 1900);
        assert_eq!(shown_exp(1200, 1900, SETTLED + 500), 1900);
        let mut last = 0;
        for f in 0..=SETTLED {
            let v = shown_exp(0, 5000, f);
            assert!(v >= last);
            last = v;
        }
        assert_eq!(last, 5000);
    }

    #[test]
    fn a_rank_is_a_thousand() {
        assert_eq!(rank_fill(0), (0, 0));
        assert_eq!(rank_fill(999), (0, 999));
        assert_eq!(rank_fill(1000), (1, 0));
        assert_eq!(rank_fill(2450), (2, 450));
        assert_eq!(rank_fill(100_000), (100, 1000));
    }

    #[test]
    fn it_fits() {
        assert!(ENTRIES + ENTRY * MAX_ENTRIES as u32 <= STATE + STATE_LEN);
        // a full page's box fits the screen
        assert!(22 + ROW * PER_PAGE as i32 + 17 <= H as i32);
    }
}
