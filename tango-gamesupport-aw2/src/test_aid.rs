//! Test aid: `TANGOAW2_TEST_POKE=<file>` sets a live match's scenarios up on every peer, deterministically.
//!
//! The file is read by every client of the match (give each the same file: a client without it, or with another,
//! simulates a different match). The match engine calls [`apply`] on every simulated tick, before the tick's input
//! reaches the console ([`tango_match::Link::test_aid`]), so the script is part of the simulation like a pad: on a
//! rollback the tick is simulated again and the script is applied again to the same effect.
//!
//! Lines (blank lines and `#` comments skipped), `WHEN do COMMAND`, where WHEN is
//!
//! - `at TICK`: on that tick of the match;
//! - `when KEY=VALUE ...`: the first tick all hold, once: `army=N` (the army moving), `day=N`, `idle` (the map waits for
//!   the cursor, nothing running), `gap=N` (at least N ticks since the rule before it fired), `tick>=N`.
//!
//! and COMMAND is
//!
//! - `poke ADDR HEX`: raw bytes into the console's memory;
//! - `funds ARMY N`: the army's funds;
//! - `meter ARMY PCT`: the army's CO meter at PCT percent of its CO Power's price (more than 100 reaches the Super);
//! - `unit ARMY KIND X Y [HP]`: a new ready unit of the army (KIND: the game's number or a name: inf, mech, tank,
//!   recon, apc, artillery, rockets, lander, cruiser, battleship, sub, copter, ...) at the empty cell, HP 1..100;
//! - `move X Y X2 Y2`: the unit at one cell to another empty cell, ready again;
//! - `ready X Y`: the unit at the cell may act again; `done X Y`: it has acted (greyed);
//! - `hp X Y N`: its hit points (1..100);
//! - `kill X Y`: it is gone;
//! - `capture X Y N`: the unit at the cell has N capture points already;
//! - `log TEXT`: a line in the log.
//!
//! Every command logs what it did (`test-aid: ...`). A rule fires once per match; a rollback past its tick lets it fire
//! again. The tick counts from the match's first, which is the same on every peer.

use mgba::core::Core;
use std::sync::{Mutex, OnceLock};

const MAP: u32 = 0x0201_E450;
const UNITS_PTR: u32 = 0x0849_9594;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const DAY: u32 = 0x0300_4080;
const ROWS: u32 = 0x417A;
const PLANES: [u32; 2] = [0x12, 0x51A];

#[derive(Clone, Debug)]
struct Rule {
    at: Option<u32>,
    army: Option<u32>,
    day: Option<u32>,
    idle: bool,
    gap: u32,
    from_tick: u32,
    cmd: Vec<String>,
}

fn parse(text: &str) -> Vec<Rule> {
    let mut rules = Vec::new();
    for (no, line) in text.lines().enumerate() {
        let line = line.split('#').next().unwrap_or("").trim();
        if line.is_empty() {
            continue;
        }
        let Some((when, cmd)) = line.split_once(" do ") else {
            log::error!("test-aid: line {}: no `do`: {line:?}", no + 1);
            continue;
        };
        let mut rule = Rule {
            at: None,
            army: None,
            day: None,
            idle: false,
            gap: 0,
            from_tick: 0,
            cmd: cmd.split_whitespace().map(str::to_string).collect(),
        };
        let mut words = when.split_whitespace();
        match words.next() {
            Some("at") => rule.at = words.next().and_then(|v| v.parse().ok()),
            Some("when") => {
                for w in words {
                    let kv = |k: &str| w.strip_prefix(k).and_then(|v| v.parse::<u32>().ok());
                    if w == "idle" {
                        rule.idle = true;
                    } else if let Some(v) = kv("army=") {
                        rule.army = Some(v);
                    } else if let Some(v) = kv("day=") {
                        rule.day = Some(v);
                    } else if let Some(v) = kv("gap=") {
                        rule.gap = v;
                    } else if let Some(v) = kv("tick>=") {
                        rule.from_tick = v;
                    } else {
                        log::error!("test-aid: line {}: unknown condition {w:?}", no + 1);
                    }
                }
            }
            _ => log::error!(
                "test-aid: line {}: starts with neither `at` nor `when`: {line:?}",
                no + 1
            ),
        }
        rules.push(rule);
    }
    rules
}

fn rules() -> &'static [Rule] {
    static RULES: OnceLock<Vec<Rule>> = OnceLock::new();
    RULES.get_or_init(|| {
        let Some(path) = std::env::var_os("TANGOAW2_TEST_POKE") else { return Vec::new() };
        match std::fs::read_to_string(&path) {
            Ok(text) => {
                let rules = parse(&text);
                log::warn!("test-aid: {} rules from {:?}: this client simulates a scripted match; every peer needs the same file", rules.len(), path);
                rules
            }
            Err(e) => {
                log::error!("test-aid: {path:?}: {e}");
                Vec::new()
            }
        }
    })
}

/// When each rule fired (the tick), this process's view; ticks a rollback undid are forgotten.
static FIRED: Mutex<Vec<Option<u32>>> = Mutex::new(Vec::new());

/// Runs the script for this tick of the match. A pure function of the tick, the console and the rules' record, which
/// itself only holds ticks already simulated.
pub fn apply(core: &mut Core, tick: u32) {
    let rules = rules();
    if rules.is_empty() {
        return;
    }
    let mut fired = FIRED.lock().unwrap();
    if fired.len() != rules.len() {
        *fired = vec![None; rules.len()];
    }
    // (a tick simulated again after a rollback: whatever fired at or after it fires afresh, so drop it and look anew)
    let redo: Vec<usize> = (0..rules.len())
        .filter(|&i| fired[i].is_some_and(|t| t >= tick))
        .collect();
    for i in redo {
        fired[i] = None;
    }
    for (i, rule) in rules.iter().enumerate() {
        if fired[i].is_some() {
            continue;
        }
        let ok = match rule.at {
            Some(t) => t == tick,
            None => {
                tick >= rule.from_tick
                    && rule.army.is_none_or(|a| core.raw_read_8(CURRENT_ARMY, -1) as u32 == a)
                    && rule.day.is_none_or(|d| core.raw_read_16(DAY, -1) as u32 == d)
                    && (!rule.idle || crate::fog_view::phase(core) == crate::fog_view::Phase::Map)
                    && (rule.gap == 0 || i == 0 || fired[i - 1].is_some_and(|t| tick >= t + rule.gap))
            }
        };
        if ok {
            fired[i] = Some(tick);
            run(core, tick, &rule.cmd);
        }
    }
}

fn num(s: Option<&String>) -> u32 {
    let s = s.map_or("0", |s| s.as_str());
    s.strip_prefix("0x")
        .map_or_else(|| s.parse().unwrap_or(0), |h| u32::from_str_radix(h, 16).unwrap_or(0))
}

fn kind_of(s: &str) -> u32 {
    use crate::custom_campaign::unit as u;
    match s {
        "inf" | "infantry" => u::INFANTRY as u32,
        "mech" => u::MECH as u32,
        "mdtank" => u::MD_TANK as u32,
        "tank" => u::TANK as u32,
        "recon" => u::RECON as u32,
        "apc" => u::APC as u32,
        "neotank" => u::NEOTANK as u32,
        "artillery" | "arty" => u::ARTILLERY as u32,
        "rockets" => u::ROCKETS as u32,
        "antiair" | "aa" => u::ANTI_AIR as u32,
        "missiles" => u::MISSILES as u32,
        "fighter" => u::FIGHTER as u32,
        "bomber" => u::BOMBER as u32,
        "copter" | "bcopter" => u::B_COPTER as u32,
        "tcopter" => u::T_COPTER as u32,
        "battleship" => u::BATTLESHIP as u32,
        "cruiser" => u::CRUISER as u32,
        "lander" => u::LANDER as u32,
        "sub" => u::SUB as u32,
        n => num(Some(&n.to_string())),
    }
}

fn row(core: &Core, y: u32) -> u32 {
    core.raw_read_16(MAP + ROWS + 2 * y, -1) as u32
}

fn unit_id_at(core: &Core, x: u32, y: u32) -> u32 {
    core.raw_read_8(MAP + PLANES[0] + row(core, y) + x, -1) as u32
}

fn record(core: &Core, id: u32) -> u32 {
    core.raw_read_32(UNITS_PTR, -1) + 12 * id
}

fn set_cell(core: &mut Core, x: u32, y: u32, id: u8) {
    let r = row(core, y);
    for plane in PLANES {
        core.raw_write_8(MAP + plane + r + x, -1, id);
    }
}

pub fn run(core: &mut Core, tick: u32, cmd: &[String]) {
    let a = |i: usize| num(cmd.get(i));
    match cmd.first().map(String::as_str) {
        Some("poke") => {
            let hex = cmd.get(2).map_or("", |s| s.as_str());
            let bytes: Vec<u8> = (0..hex.len() / 2)
                .filter_map(|i| u8::from_str_radix(&hex[2 * i..2 * i + 2], 16).ok())
                .collect();
            core.raw_write_range(a(1), -1, &bytes);
            log::info!("test-aid @{tick}: poke {:08x} {hex}", a(1));
        }
        Some("funds") => {
            let p = crate::tag::player(core, a(1));
            core.raw_write_32(p, -1, a(2));
            log::info!("test-aid @{tick}: army {} funds {}", a(1), a(2));
        }
        Some("meter") => {
            crate::bh_act5b::meter(core, a(1), a(2));
            log::info!("test-aid @{tick}: army {} meter {}%", a(1), a(2));
        }
        Some("unit") => {
            let (army, kind, x, y) = (a(1), kind_of(cmd.get(2).map_or("", |s| s.as_str())), a(3), a(4));
            let hp = if cmd.len() > 5 { a(5).clamp(1, 100) } else { 100 };
            let stride = if crate::five::active(core) { 51 } else { 64 };
            if unit_id_at(core, x, y) != 0 {
                log::error!("test-aid @{tick}: unit: ({x},{y}) is occupied");
                return;
            }
            let Some(id) = (1..stride)
                .map(|s| (army - 1) * stride + s)
                .find(|&id| core.raw_read_8(record(core, id), -1) == 0)
            else {
                log::error!("test-aid @{tick}: unit: army {army} has no free slot");
                return;
            };
            // a copy of a unit of the kind anywhere (its ammo and fuel are the kind's), else a foot soldier's
            let template = (1..255)
                .map(|i| record(core, i))
                .find(|&r| core.raw_read_8(r, -1) as u32 == kind);
            let mut rec = [0u8; 12];
            match template {
                Some(t) => core.raw_read_range(t, -1, &mut rec),
                None => rec = [kind as u8, 0, 0, 0, 100, 0, 99, 0, 0, 0, 0, 4],
            }
            rec[1] = 0;
            rec[2] = x as u8;
            rec[3] = y as u8;
            let w = u16::from_le_bytes([rec[4], rec[5]]) & 0x07FF & !0x7F | hp as u16;
            rec[4..6].copy_from_slice(&w.to_le_bytes());
            rec[7] = 0;
            rec[8] = 0;
            core.raw_write_range(record(core, id), -1, &rec);
            set_cell(core, x, y, id as u8);
            log::info!("test-aid @{tick}: army {army} unit {id} kind {kind} at ({x},{y}) hp {hp}");
        }
        Some("move") => {
            let (id, x2, y2) = (unit_id_at(core, a(1), a(2)), a(3), a(4));
            if id == 0 || unit_id_at(core, x2, y2) != 0 {
                log::error!(
                    "test-aid @{tick}: move: no unit at ({},{}) or ({x2},{y2}) occupied",
                    a(1),
                    a(2)
                );
                return;
            }
            set_cell(core, a(1), a(2), 0);
            set_cell(core, x2, y2, id as u8);
            let r = record(core, id);
            core.raw_write_8(r + 1, -1, 0);
            core.raw_write_8(r + 2, -1, x2 as u8);
            core.raw_write_8(r + 3, -1, y2 as u8);
            log::info!("test-aid @{tick}: unit {id} to ({x2},{y2})");
        }
        Some("ready") => {
            let id = unit_id_at(core, a(1), a(2));
            if id != 0 {
                core.raw_write_8(record(core, id) + 1, -1, 0);
            }
            log::info!("test-aid @{tick}: unit {id} ready");
        }
        Some("done") => {
            let id = unit_id_at(core, a(1), a(2));
            if id != 0 {
                let r = record(core, id) + 1;
                core.raw_write_8(r, -1, core.raw_read_8(r, -1) | 1);
            }
            log::info!("test-aid @{tick}: unit {id} done");
        }
        Some("hp") => {
            let id = unit_id_at(core, a(1), a(2));
            if id != 0 {
                let r = record(core, id) + 4;
                let w = core.raw_read_16(r, -1) & !0x7F | a(3).clamp(1, 100) as u16;
                core.raw_write_16(r, -1, w);
            }
            log::info!("test-aid @{tick}: unit {id} hp {}", a(3));
        }
        Some("kill") => {
            let id = unit_id_at(core, a(1), a(2));
            if id != 0 {
                core.raw_write_range(record(core, id), -1, &[0u8; 12]);
                set_cell(core, a(1), a(2), 0);
            }
            log::info!("test-aid @{tick}: unit {id} removed from ({},{})", a(1), a(2));
        }
        Some("capture") => {
            let id = unit_id_at(core, a(1), a(2));
            if id != 0 {
                let r = record(core, id) + 4;
                let w = core.raw_read_16(r, -1) & 0x07FF | (a(3).min(20) as u16) << 11;
                core.raw_write_16(r, -1, w);
            }
            log::info!("test-aid @{tick}: unit {id} capture points {}", a(3));
        }
        Some("log") => log::info!("test-aid @{tick}: {}", cmd[1..].join(" ")),
        other => log::error!("test-aid @{tick}: unknown command {other:?}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_rules() {
        let r = parse("# x\nat 5 do funds 1 9000\nwhen army=2 day=1 idle gap=30 do unit 2 inf 3 4 50 # c\nbroken\n");
        assert_eq!(r.len(), 2);
        assert_eq!(r[0].at, Some(5));
        assert_eq!((r[1].army, r[1].day, r[1].idle, r[1].gap), (Some(2), Some(1), true, 30));
        assert_eq!(r[1].cmd.len(), 6);
    }
}
