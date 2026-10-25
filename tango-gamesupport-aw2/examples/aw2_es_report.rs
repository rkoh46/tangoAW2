//! The Emerald Sun Campaign's missions as tab-separated rows for the kit (`aw2dev campaign difficulty`, `campaign check`; docs/dev/es-campaign.md):
//!   M  key title day_limit fog weather armies objective look
//!   A  key army colour team co funds
//!   S  key day army kind x y        (a unit a trigger spawns, with the day it fires: 0 when the rule has no day)
//!   P  key x y kind owner           (a property a mission hands out)
//!   N  key boxes                    (text boxes of its scenes)
use tango_gamesupport_aw2::custom_campaign::{Action, Cond, CoSpec, UnitDef};

fn day_of(c: &Cond) -> u16 {
    match c {
        Cond::DayAtLeast(d) => *d,
        Cond::EveryDays { from, .. } => *from,
        Cond::All(v) => v.iter().map(day_of).max().unwrap_or(0),
        _ => 0,
    }
}

fn co_text(c: &CoSpec) -> String {
    match c {
        CoSpec::None => "none".into(),
        CoSpec::Fixed(a) => format!("{a}"),
        CoSpec::Pair(a, b) => format!("{a}+{b}"),
        CoSpec::Pick => "pick".into(),
        CoSpec::PickPair => "pickpair".into(),
        CoSpec::PickPartner(a) => format!("{a}+pick"),
    }
}

fn main() {
    let def = tango_gamesupport_aw2::es_campaign::def();
    for m in &def.missions {
        println!("M\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}", m.key, m.title, m.day_limit, m.fog as u8, m.weather as u8, m.armies.len(), m.objective, m.look);
        for (i, a) in m.armies.iter().enumerate() {
            println!("A\t{}\t{}\t{}\t{}\t{}\t{}", m.key, i + 1, a.colour, a.team, co_text(&a.co), a.funds.map_or(-1, |f| f as i64));
        }
        for t in &m.triggers {
            let day = day_of(&t.cond);
            for a in &t.then {
                if let Action::Spawn(v) = a {
                    for u in v {
                        let UnitDef { army, kind, x, y, .. } = *u;
                        println!("S\t{}\t{}\t{}\t{}\t{}\t{}", m.key, day, army, kind, x, y);
                    }
                }
            }
        }
        for p in &m.props {
            println!("P\t{}\t{}\t{}\t{}\t{}", m.key, p.x, p.y, p.kind as u8, p.owner);
        }
        let mut boxes = m.intro.all_lines().len() + m.victory.all_lines().len() + m.after.all_lines().len();
        for t in &m.triggers {
            for a in &t.then {
                if let Action::Scene(s) = a {
                    boxes += s.all_lines().len();
                }
            }
        }
        println!("N\t{}\t{}", m.key, boxes);
    }
}
