//! Lists a campaign's day-based triggers (`aw2_campaign_waves [bh|es|bh2|gauntlet] [mission key]`), one tab-separated line each:
//! mission key, day, units spawned (army of the first unit, cells x:y;...), scene boxes. A trigger counts when its condition names a day (`EveryDays`, `DayAtLeast`,
//! also inside `All`/`Any`) and it spawns units or plays a scene. Used by `aw2dev bh2 waves` (docs/dev/bh2-maps.md); needs no ROM.
use tango_gamesupport_aw2::custom_campaign::{Action, Cond};

fn day_of(c: &Cond) -> Option<u16> {
    match c {
        Cond::DayAtLeast(d) => Some(*d),
        Cond::EveryDays { from, .. } => Some(*from),
        Cond::All(v) | Cond::Any(v) => v.iter().find_map(day_of),
        _ => None,
    }
}

fn main() {
    let def = match std::env::args().nth(1).as_deref() {
        Some("es") => tango_gamesupport_aw2::es_campaign::def(),
        Some("gauntlet") => tango_gamesupport_aw2::gauntlet_mode::def(),
        Some("bh") => tango_gamesupport_aw2::bh_campaign::def(),
        _ => tango_gamesupport_aw2::bh2_campaign::def(),
    };
    let only = std::env::args().nth(2);
    for m in &def.missions {
        if only.as_deref().is_some_and(|k| k != m.key) {
            continue;
        }
        for t in m.triggers.iter().chain(m.front2_triggers.iter()) {
            let Some(day) = day_of(&t.cond) else { continue };
            let mut spawn = String::from("-");
            let mut boxes = 0usize;
            for a in &t.then {
                match a {
                    Action::Spawn(units) if !units.is_empty() => {
                        spawn = format!("{}", units.iter().map(|u| format!("{}:{}:{}:{}", u.army, u.kind, u.x, u.y)).collect::<Vec<_>>().join(";"));
                    }
                    Action::Scene(s) => boxes += s.lines.len() + s.more.iter().map(|p| p.lines.len()).sum::<usize>(),
                    _ => {}
                }
            }
            if spawn != "-" || boxes > 0 {
                println!("{}\t{}\t{}\t{}", m.key, day, spawn, boxes);
            }
        }
    }
}
