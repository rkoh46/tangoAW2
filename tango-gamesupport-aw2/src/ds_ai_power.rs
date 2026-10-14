//! Dual Strike's power use for the CPU (phase B of docs/AW2.md "Dual Strike's CPU").
//!
//! **AW2** considers its power in `AiDeliberateCoPower` (`0x0805DB70`, the context `*0x0816DA4C`, +0 the army),
//! the per-unit routine of the pass `0x0805CE21`, which the pass list runs three times a turn (positions 0, 4
//! and 17 of `0x085766E8`; 0, 4 and 21 of the fog list `0x08576738`). It takes the Super CO Power whenever it is
//! paid for and the CO's AI function agrees, else the CO Power by the meter's lead over its cost and a roll.
//!
//! **Dual Strike** (`AiPlayer_TryUsePower` `0x020995C4`) checks three times a turn too (phases 3, 9 and 27; 3, 9
//! and 32 in fog or rain), and most COs agree only at the first, before any unit moves. In order:
//! 1. with a partner and both Super Powers paid for: the Tag Power, if the CO's hook agrees to a Super (else
//!    nothing);
//! 2. Colin's CO Power as soon as it is paid for (his hook permitting);
//! 3. the Super, if paid for: with a partner only while the partner's meter is at most template byte 8 % full
//!    and the turn's roll at most byte 9;
//! 4. the CO Power, if paid for, no partner's Super ready, the meter not past the CO Power's cost by more than
//!    byte 4 % (6 with a partner) of the gap to the Super's, and the roll under byte 5 (7): a CO with 0 there
//!    never uses its CO Power and saves for the Super.
//!
//! The hooks ([`crate::ds_ai::Hook`]): most COs only at the first check; Andy with a hurt unit; Olaf not the CO
//! Power in snow; Sonja the CO Power only in fog or rain; Sasha also with 30000 funds and an enemy nearer its
//! power; Drake any time in fog or rain, else the Super after the first check; Eagle only at the last check
//! (Dual Strike then runs the unit phases again after Lightning Strike; AW2's passes do not run twice: here
//! his Super comes at the last check and the units that have not moved yet move after it); Colin's CO Power
//! while he owns a factory; Hawke always; Hachi anything while he owns a factory; Kindle her CO Power with
//! enemies on properties.
//!
//! **Here** a trap after `AiDeliberateCoPower`'s prologue ([`DECIDE`], r5 the context) decides and goes on at
//! AW2's own Super call (`0x0805DBB2`: announcement, `PayForPower(army, 2)`, which [`crate::tag`] turns into
//! the Tag Power when both are ready), its CO Power call (`0x0805DC74`) or its return. The first check is the
//! pass index `*0x03004770` = 1, the last 18 (22 with the fog list). The roll is the deterministic one
//! ([`crate::ds_ai::roll`]) per check. After a power the threat limits are rolled again at the top (Dual
//! Strike's `AiProfile_RerandomiseForPlayer`).

use mgba::core::Core;

use crate::ds_ai::*;

pub const DECIDE: u32 = 0x0805_DB78;
const SUPER: u32 = 0x0805_DBB2;
const POWER: u32 = 0x0805_DC74;
const NOTHING: u32 = 0x0805_DC92;
const PASS: u32 = 0x0300_4770;
const PLAY_ST: u32 = 0x0300_3FC0;

#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) enum Choice {
    Nothing,
    Power,
    Super,
}

/// What [`decide`] works from: the army's meters and the battle around it.
pub(crate) struct Meter {
    pub charge: u32,
    pub cop: u32,
    pub scop: u32,
    pub partner: Option<(u32, u32)>,
}

impl Meter {
    fn read(core: &Core, army: u32) -> Meter {
        let p = crate::five::players(core) + 0x3C * army;
        let co = core.raw_read_8(p + 0x1D, -1);
        let uses = core.raw_read_8(p + 0x25, -1);
        let partner = crate::tag::partner(core, army).map(|b| {
            (crate::tag::partner_charge(core, army), crate::tag::scop_cost(core, b, crate::tag::partner_uses(core, army)))
        });
        Meter {
            charge: core.raw_read_32(p + 0x20, -1),
            cop: crate::tag::cop_cost(core, co, uses),
            scop: crate::tag::scop_cost(core, co, uses),
            partner,
        }
    }

    fn super_ready(&self) -> bool {
        self.scop > 0 && self.charge >= self.scop
    }

    /// AW2's `0x0804423C`: a CO without a CO Power is ready for it when its Super is.
    fn power_ready(&self) -> bool {
        if self.cop == 0 { self.super_ready() } else { self.charge >= self.cop }
    }

    fn partner_super_ready(&self) -> bool {
        self.partner.is_some_and(|(c, s)| s > 0 && c >= s)
    }
}

/// The army owns a base, airport or port (`gAiTurnState->factoryDomainsOwn`).
pub(crate) fn owns_factory(b: &Board, army: u32) -> bool {
    (0..b.class.len()).any(|i| matches!(b.class[i], C_BASE | C_AIRPORT | C_PORT) && b.owns(i, army))
}

/// The CO's hook for a CO Power (`k` 1) or a Super (2) at this check.
fn hook(core: &Core, b: &Board, army: u32, h: Hook, k: u8, first: bool, last: bool) -> bool {
    let fog = foggy(core);
    match h {
        Hook::Never => false,
        Hook::First => first,
        Hook::Hurt => first && b.units.iter().any(|u| u.army == army && !u.carried() && u.hp < 91),
        Hook::NotSnow => b.weather != 1 || k == 2,
        Hook::FogPower => !(k == 1 && !fog) && first,
        Hook::Funds => {
            if k == 2 && first {
                return true;
            }
            let own = core.raw_read_32(crate::five::players(core) + 0x3C * army + 0x20, -1);
            funds(core, army) >= 30000
                && (1..=5u32).any(|a| {
                    b.playing[a as usize] && !b.same_team(a, army) && core.raw_read_32(crate::five::players(core) + 0x3C * a + 0x20, -1) > own
                })
        }
        Hook::Drake => fog || !(k == 2 && first),
        Hook::Last => last,
        Hook::Colin => (k == 1 && owns_factory(b, army)) || (k == 2 && first),
        Hook::Always => true,
        Hook::Hachi => {
            owns_factory(b, army)
                || (k == 2
                    && (first
                        || (0..b.class.len()).any(|i| b.class[i] == C_CITY && b.owns(i, army) && b.at[i] == 0)))
        }
        Hook::Kindle => {
            if k == 2 {
                return first;
            }
            let foes: Vec<&Unit> =
                b.units.iter().filter(|u| b.playing[u.army as usize % 6] && !b.same_team(u.army, army) && u.t != OOZIUM && !u.carried()).collect();
            let on = foes.iter().filter(|u| PROPERTIES.contains(&b.class[b.idx(u.x, u.y)])).count();
            on != 0 && (on * 5 >= foes.len() || on >= 5)
        }
    }
}

/// `AiPlayer_TryUsePower` for army `army` with CO `co` at a check (`first`, `last`) with this `roll` (0..99).
pub(crate) fn decide(core: &Core, b: &Board, army: u32, co: u8, prof: &Profile, m: &Meter, roll: u32, first: bool, last: bool) -> (Choice, &'static str) {
    let h = |k: u8| hook(core, b, army, prof.hook, k, first, last);
    if m.partner.is_some() && m.super_ready() && m.partner_super_ready() {
        return if h(2) { (Choice::Super, "tag power") } else { (Choice::Nothing, "tag power: not now") };
    }
    if crate::tag::ds_id(co) == Some(17) && m.power_ready() && h(1) {
        return (Choice::Power, "Colin's CO Power");
    }
    if m.super_ready() {
        if let Some((c, s)) = m.partner {
            if c * 100 / s.max(1) > prof.power[4] as u32 {
                return (Choice::Nothing, "super: the partner's meter is high");
            }
            if roll > prof.power[5] as u32 {
                return (Choice::Nothing, "super: the roll");
            }
        }
        if h(2) {
            return (Choice::Super, "super");
        }
    }
    if !m.power_ready() {
        return (Choice::Nothing, "-");
    }
    if m.partner_super_ready() {
        return (Choice::Nothing, "power: the partner's Super is ready");
    }
    let (gap, chance) = if m.partner.is_some() { (prof.power[2], prof.power[3]) } else { (prof.power[0], prof.power[1]) };
    let threshold = m.cop as i64 + (m.scop as i64 - m.cop as i64) * gap as i64 / 100;
    if (m.charge as i64) > threshold {
        return (Choice::Nothing, "power: saving for the Super");
    }
    if roll >= chance as u32 {
        return (Choice::Nothing, "power: the roll");
    }
    if h(1) { (Choice::Power, "power") } else { (Choice::Nothing, "power: not now") }
}

/// Dual Strike decides this army's power (so [`crate::tag`]'s own rule for AW2's CPU stands aside).
pub(crate) fn deciding(core: &Core, army: u32) -> bool {
    in_scope(core, army, OFF_POWER) && profile(army_co(core, army).0).is_some()
}

fn decide_trap(core: &mut Core) {
    let ctx = core.gba().cpu().gpr(5) as u32;
    let army = core.raw_read_16(ctx, -1) as u32;
    if !deciding(core, army) {
        return;
    }
    let (co, mode) = army_co(core, army);
    let to = if mode != 0 || !powers_on(core) || crate::tag::phase(core, army) != 0 {
        NOTHING
    } else {
        let prof = profile(co).unwrap();
        let b = Board::read(core);
        let m = Meter::read(core, army);
        let pass = core.raw_read_32(PASS, -1);
        let fog = core.raw_read_8(PLAY_ST + 0x0D, -1) != 0;
        let (first, last) = (pass == 1, pass == if fog { 22 } else { 18 });
        let r = roll(core, army, Roll::Power, pass, 100);
        let (choice, why) = decide(core, &b, army, co, &prof, &m, r, first, last);
        if logging() && (choice != Choice::Nothing || m.power_ready()) {
            let foes: Vec<&Unit> = b.units.iter().filter(|u| b.playing[u.army as usize % 6] && !b.same_team(u.army, army) && !u.carried()).collect();
            let on = foes.iter().filter(|u| PROPERTIES.contains(&b.class[b.idx(u.x, u.y)])).count();
            log(&format!(
                "dsai power day {} army {army} co {co} template {} hook {:?} pass {pass} meter {}/{}/{} partner {:?} roll {r}: {choice:?} ({why}; enemies {} on properties {on})",
                b.day, prof.template, prof.hook, m.charge, m.cop, m.scop, m.partner, foes.len()
            ));
        }
        match choice {
            Choice::Nothing => NOTHING,
            Choice::Power => POWER,
            Choice::Super => SUPER,
        }
    };
    if to != NOTHING {
        // Dual Strike's `AiProfile_RerandomiseForPlayer`: the threat limits at the top for the rest of the turn.
        set_profile_roll(core, army, if behaviour(core, army) == DEFENSE { 0 } else { 100 });
    }
    core.gba_mut().cpu_mut().set_thumb_pc(to);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(DECIDE, Box::new(decide_trap))]
}
