//! Live-PvP session view: the telemetry deck (see [`telemetry`]), and the disconnect /
//! reconnect modals. The [`Message`]s those controls emit are handled in
//! [`crate::session::update::pvp`].

use super::*;
use crate::session::pvp::PvpSession;
pub use crate::session::update::pvp::Message;
use crate::session::Message as SessionMessage;
use tango_gamesupport::OpaqueBuildWarnings;
// Explicit so these win over iced's prelude `column!`/`row!` macros (see mod.rs).
use sweeten::widget::{column, row};

mod telemetry;
use telemetry::{frame_delay_overlay, telemetry_panel};

/// Live PvP: the emulator, telemetry, and the disconnect / reconnect
/// modals. (No Tango match-setup UI: setup happens in the game's own
/// ONLINE screens.)
pub(crate) fn view<'a>(p: &'a PvpSession, ctx: Ctx<'a>) -> Element<'a, SessionMessage> {
    let Ctx { lang, state, .. } = ctx;
    let now = iced::time::Instant::now();
    let frame = framebuffer_view(
        ctx,
        None,
        iced::alignment::Horizontal::Center,
        iced::alignment::Vertical::Center,
    );
    let body = emulator_body(frame, true, ctx.landscape_stretch);
    let mut game_stack = stack![body];
    if state.controls_anim.visible(now) {
        // Settings + tear-down, top-right; a live link routes the
        // tear-down through the disconnect confirm (whose copy
        // carries the unplug framing); once the link is already gone
        // (`latency()` = None ⇒ remote dropped) there's nothing left
        // to protect, so it closes directly. Pushed BEFORE the setup
        // drawers so an open drawer layers over them rather than the
        // buttons intruding on the pane.
        let tear_down_msg = if p.latency().is_some() {
            SessionMessage::Pvp(Message::OpenDisconnectConfirm)
        } else {
            SessionMessage::Close
        };
        game_stack = game_stack.push(corner_commands_overlay(lang, state, tear_down_msg));
    }
    // Advisory only: invalid committed builds never alter the running
    // session, but remain explicit until the player dismisses this card.
    if let Some(o) = build_warning_overlay(lang, state) {
        game_stack = game_stack.push(o.map(SessionMessage::Pvp));
    }

    // Telemetry is a real status region below the game stack, not an overlay:
    // it is always present, never covers the emulator or setup drawers, and
    // its fixed lanes update without moving neighboring readings.
    let game = container(game_stack).width(Fill).height(Fill);
    let layout = column![game, telemetry_panel(lang, p, state).map(SessionMessage::Pvp)]
        .width(Fill)
        .height(Fill);
    let mut stacked = stack![layout];

    if let Some(o) = frame_delay_overlay(lang, p, state) {
        stacked = stacked.push(o.map(SessionMessage::Pvp));
    }

    if let Some(o) = disconnect_overlay(lang, state) {
        stacked = stacked.push(o);
    }
    // The auto-reconnect modal. Above the disconnect-confirm so that if
    // the link drops while that prompt is open, "Reconnecting…" reads over it.
    if let Some(o) = reconnecting_overlay(lang, p) {
        stacked = stacked.push(o);
    }
    finish_session_stack(lang, state, stacked)
}

/// A non-modal, height-capped warning for the opponent's invalid committed
/// build. Their save is validated locally from the exact bytes the match runs,
/// so a modified peer cannot suppress the warning by lying on the wire.
/// Exact opponent details are shown even when their setup drawer is blinded:
/// once the build violates the rules, the violations take precedence over the
/// setup-privacy preference.
fn build_warning_overlay(lang: &LanguageIdentifier, state: &State) -> Option<Element<'static, Message>> {
    const WARNING_WIDTH: f32 = 600.0;
    const WARNING_MAX_HEIGHT: f32 = 360.0;

    let panes = state.pvp_panes.as_ref()?;
    if panes.build_warning_dismissed {
        return None;
    }
    let warnings = panes.opponent_build_warnings.as_ref()?;

    let warning_text_style = |theme: &iced::Theme| iced::widget::text::Style {
        color: Some(theme.palette().warning),
    };
    let header = row![
        Icon::AlertTriangle
            .widget()
            .size(TEXT_BODY + 2.0)
            .style(warning_text_style),
        text(t!(lang, "session-build-warning-title"))
            .size(TEXT_BODY + 2.0)
            .style(warning_text_style),
        horizontal_space(),
        widgets::icon_button(
            Icon::X,
            t!(lang, "session-build-warning-dismiss"),
            Message::DismissBuildWarning,
            [4.0, 4.0],
        ),
    ]
    .spacing(8)
    .align_y(Alignment::Center);

    let expanded = panes.build_warning_violations_expanded;
    let toggle = widgets::labeled_icon_button(
        if expanded { Icon::ChevronUp } else { Icon::ChevronDown },
        if expanded {
            t!(lang, "session-build-warning-hide-violations")
        } else {
            t!(lang, "session-build-warning-show-violations")
        },
        Message::ToggleBuildWarningViolations,
        [6.0, 8.0],
        widgets::neutral,
    );
    let mut body = column![header, toggle].spacing(10).width(Fill);
    if expanded {
        let violations = build_warning_violations(warnings, lang);
        body = body.push(
            iced::widget::scrollable(violations)
                .style(widgets::chunky_scrollable)
                .height(Length::Shrink)
                .width(Fill),
        );
    }
    let panel = container(body)
        .width(Length::Fixed(WARNING_WIDTH))
        .max_height(WARNING_MAX_HEIGHT)
        .padding(16)
        .style(build_warning_plate);

    // Claim only the card's own mouse region. The rest of this full-window
    // placement stays transparent, so controls and gameplay input outside the
    // warning remain usable while it is visible.
    let panel = iced::widget::mouse_area(panel).interaction(iced::mouse::Interaction::Idle);
    Some(
        container(panel)
            .width(Fill)
            .height(Fill)
            .align_x(iced::alignment::Horizontal::Center)
            .align_y(iced::alignment::Vertical::Top)
            .padding(16)
            .into(),
    )
}

fn build_warning_violations(warnings: &OpaqueBuildWarnings, lang: &LanguageIdentifier) -> Element<'static, Message> {
    let mut rows = column![].spacing(4);
    for violation in warnings.format(lang) {
        rows = rows.push(
            row![
                text("•").size(TEXT_CAPTION),
                text(violation).size(TEXT_CAPTION).width(Fill),
            ]
            .spacing(7)
            .align_y(Alignment::Start),
        );
    }
    rows.into()
}

fn build_warning_plate(theme: &iced::Theme) -> iced::widget::container::Style {
    let warning = theme.palette().warning;
    let background = widgets::mix(
        theme.palette().background,
        warning,
        if theme.extended_palette().is_dark { 0.13 } else { 0.08 },
    );
    iced::widget::container::Style {
        background: Some(iced::Background::Color(background)),
        text_color: Some(theme.palette().text),
        border: iced::Border {
            radius: widgets::tech_radius(12.0),
            width: 1.5,
            color: iced::Color { a: 0.85, ..warning },
        },
        shadow: iced::Shadow {
            color: iced::Color { a: 0.22, ..warning },
            offset: iced::Vector::new(0.0, 4.0),
            blur_radius: 14.0,
        },
        snap: false,
    }
}

/// Disconnect confirmation modal (PvP-only). Centered panel with a
/// dimmed click-to-dismiss backdrop — same shape as app.rs's
/// in-session Settings modal so the two read as the same family
/// of "this interrupts what you're doing" dialogs. Sits above
/// the options popover in the stack so it covers the menu if
/// the user somehow re-opened it.
fn disconnect_overlay<'a>(lang: &'a LanguageIdentifier, state: &'a State) -> Option<Element<'a, SessionMessage>> {
    let now = iced::time::Instant::now();
    if !state.disconnect.visible(now) {
        return None;
    }
    let progress = state.disconnect.progress(now);
    let title = text(t!(lang, "playback-disconnect-prompt")).size(TEXT_BODY + 4.0);
    let body_text = text(t!(lang, "playback-disconnect-detail")).style(widgets::muted_text_style);
    let cancel_btn = widgets::labeled_icon_button(
        Icon::X,
        t!(lang, "playback-cancel"),
        SessionMessage::Pvp(Message::CloseDisconnectConfirm),
        [8.0, 14.0],
        widgets::neutral,
    );
    let disconnect_btn = widgets::labeled_icon_button(
        Icon::Unplug,
        t!(lang, "playback-disconnect"),
        SessionMessage::Close,
        [8.0, 14.0],
        widgets::danger_button,
    );
    let buttons = row![horizontal_space(), cancel_btn, disconnect_btn]
        .spacing(8)
        .align_y(Alignment::Center);
    let panel = container(column![title, body_text, buttons].spacing(14).width(Fill))
        .width(Fill)
        .max_width(420.0)
        .padding(20)
        .style(widgets::panel);
    // Dim + click-swallow + centering come from the shared
    // scaffolding; the dismiss handler is only armed while the
    // modal is actually open so a click during the fade-out can't
    // re-fire the close.
    Some(widgets::modal_layer(
        anim::pop(panel, progress, 8.0),
        0.55 * progress,
        SessionMessage::NoOp,
        state
            .disconnect
            .shown()
            .then_some(SessionMessage::Pvp(Message::CloseDisconnectConfirm)),
    ))
}

/// The automatic mid-match reconnect modal: shown while a dropped direct link is
/// being transparently rebuilt ([`PvpSession::is_reconnecting`]). The emulator
/// is paused underneath, so this is a static notice rather than an animated
/// one — plus a Disconnect escape hatch (routes through [`Message::Close`], same
/// as the confirm dialog's) so the user can abandon the wait. Pushed last in
/// [`view`] so it sits above every other layer.
fn reconnecting_overlay<'a>(lang: &'a LanguageIdentifier, pvp: &'a PvpSession) -> Option<Element<'a, SessionMessage>> {
    if !pvp.is_reconnecting() {
        return None;
    }
    // A room names who the match waits for: its countdown is the game's own message box over the match's picture
    // (tangoAW2's `hold_box`, B to disconnect), not this modal. This one is for a plain link being rebuilt.
    if pvp.waiting_for().is_some_and(|(name, _)| !name.is_empty()) {
        return None;
    }
    let title = text(t!(lang, "playback-reconnecting")).size(TEXT_BODY + 4.0);
    let body_text = text(t!(lang, "playback-reconnecting-detail")).style(widgets::muted_text_style);
    // Depleting bar for the time left before give-up, in place of a text
    // countdown: it fills the panel width (no wrap/min-width pitfall) and the
    // coordinator ticks the session redraw ~30 fps while paused so it eases down.
    let time_left = pvp.reconnect_progress().unwrap_or(0.0);
    let progress = iced::widget::progress_bar(0.0..=1.0, time_left)
        .length(Fill)
        .girth(6.0)
        .style(|theme: &iced::Theme| iced::widget::progress_bar::Style {
            background: iced::Background::Color(iced::Color {
                a: 0.12,
                ..iced::Color::WHITE
            }),
            bar: iced::Background::Color(theme.extended_palette().primary.base.color),
            border: iced::Border {
                radius: 3.0.into(),
                ..Default::default()
            },
        });
    let disconnect_btn = widgets::labeled_icon_button(
        Icon::Unplug,
        t!(lang, "playback-disconnect"),
        SessionMessage::Close,
        [8.0, 14.0],
        widgets::danger_button,
    );
    let buttons = row![horizontal_space(), disconnect_btn]
        .spacing(8)
        .align_y(Alignment::Center);
    let panel = container(column![title, body_text, progress, buttons].spacing(14).width(Fill))
        .width(Fill)
        .max_width(420.0)
        .padding(20)
        .style(widgets::panel);
    // Solid dim, no dismiss-on-press: the user leaves only via Disconnect (or
    // the link returning, which clears the overlay on its own).
    Some(widgets::modal_layer(panel.into(), 0.55, SessionMessage::NoOp, None))
}

#[cfg(test)]
mod build_warning_tests {
    use super::*;
    use tango_library::lang::FALLBACK_LANG;

    #[derive(Debug)]
    struct TestBuildWarnings;

    impl tango_gamesupport::BuildWarnings for TestBuildWarnings {
        fn format(&self, lang: &LanguageIdentifier) -> Vec<String> {
            vec![if lang.language.as_str() == "ja" {
                "シークレットチップ：使用不可".to_string()
            } else {
                "SecretChip: illegal".to_string()
            }]
        }
    }

    #[test]
    fn warning_chrome_is_translated_in_every_supported_language() {
        let english = [
            t!(&FALLBACK_LANG, "session-build-warning-title"),
            t!(&FALLBACK_LANG, "session-build-warning-show-violations"),
            t!(&FALLBACK_LANG, "session-build-warning-hide-violations"),
        ];
        for language in crate::i18n::SUPPORTED_LANGS.iter().skip(1) {
            assert_ne!(t!(language, "session-build-warning-title"), english[0]);
            assert_ne!(t!(language, "session-build-warning-show-violations"), english[1]);
            assert_ne!(t!(language, "session-build-warning-hide-violations"), english[2]);
        }
    }

    #[test]
    fn blinded_opponent_still_gets_an_exact_warning() {
        let mut state = State::new();
        state.pvp_panes = Some(crate::session::update::pvp::PvpPanes {
            local_loaded: None,
            // `None` is exactly how a blinded opponent is represented.
            opponent_loaded: None,
            opponent_build_warnings: Some(std::sync::Arc::new(TestBuildWarnings)),
            build_warning_dismissed: false,
            build_warning_violations_expanded: false,
        });

        assert!(build_warning_overlay(&FALLBACK_LANG, &state).is_some());
        assert_eq!(
            state
                .pvp_panes
                .as_ref()
                .unwrap()
                .opponent_build_warnings
                .as_ref()
                .unwrap()
                .format(&FALLBACK_LANG),
            ["SecretChip: illegal"]
        );
        assert_eq!(
            state
                .pvp_panes
                .as_ref()
                .unwrap()
                .opponent_build_warnings
                .as_ref()
                .unwrap()
                .format(&"ja-JP".parse().unwrap()),
            ["シークレットチップ：使用不可"]
        );

        assert!(!state.pvp_panes.as_ref().unwrap().build_warning_violations_expanded);
        let _ = crate::session::update::pvp::update(&mut state, Message::ToggleBuildWarningViolations);
        assert!(state.pvp_panes.as_ref().unwrap().build_warning_violations_expanded);
    }
}
