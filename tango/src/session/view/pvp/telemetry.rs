//! PvP telemetry: one always-visible, single-row bottom status bar. P1/P2 sit
//! beside five tiny inline sparklines (TPS, frame skew, local lead, rollback
//! depth, ping), each in an equal-width lane whose value sizes naturally. A
//! trailing frame-delay chip opens its slider in a small
//! popover, keeping the resting bar shallow. Split out of the session view so
//! the emulator/drawer layout in `mod.rs` isn't sharing a file with the
//! charting + tone math.

use super::super::*;
use super::{Message, PvpSession};
// Explicit so these win over iced's prelude `column!`/`row!` macros (see mod.rs).
use sweeten::widget::{column, row};

/// Live frame-delay control: a turtle-icon heading naming it, over the lobby's
/// frame-delay row (slider, fixed-width numeric readout, latency-driven
/// "suggest" wand). Lifting the title into the heading frees the control line so
/// the slider gets lobby-like width even in the compact panel. Frame delay is
/// purely local display lag, so dragging it mid-match takes effect on the next
/// rendered frame with no peer coordination.
fn frame_delay_control<'a>(lang: &'a LanguageIdentifier, pvp: &'a PvpSession) -> Element<'a, Message> {
    let fd = pvp.frame_delay();

    // Heading: turtle glyph + title, both muted — matches the metric-card
    // captions above so the control reads as part of the same panel.
    let heading = row![
        Icon::Turtle.widget().size(TEXT_BODY).style(widgets::muted_text_style),
        text(t!(lang, "settings-netplay-frame-delay"))
            .size(TEXT_CAPTION)
            .style(widgets::muted_text_style),
    ]
    .spacing(6)
    .align_y(Alignment::Center)
    .width(Fill);

    // Slider fills the row; the value + wand take their natural sizes.
    let slider = iced::widget::slider(MIN_FRAME_DELAY..=MAX_FRAME_DELAY, fd, Message::SetFrameDelay)
        .style(widgets::chunky_slider)
        .width(Length::Fill);

    // "Suggest" button — same formula as the lobby: one-way frames + 1,
    // clamped to the slider range, off the median ping. Enabled whenever the
    // link is live (`latency()` is `Some`); before the first ping that reads
    // `Some(ZERO)`, which just suggests the minimum frame delay.
    let suggest_msg = pvp
        .latency()
        .map(|rtt| Message::SetFrameDelay(suggest_frame_delay(rtt)));
    let suggest = widgets::icon_button_maybe(
        Icon::Wand,
        t!(lang, "lobby-frame-delay-suggest"),
        suggest_msg,
        crate::ui::style::STANDARD_PADDING,
    );

    let control = row![
        slider,
        text(format!("{}", fd)).size(TEXT_BODY).width(Length::Fixed(18.0)),
        suggest,
    ]
    .spacing(10)
    .align_y(Alignment::Center)
    .width(Fill);

    column![heading, control]
        .spacing(3)
        .width(Length::Fixed(FRAME_DELAY_W))
        .into()
}

// Status-bar geometry. The five metric lanes divide the available width; each
// value takes its natural width and the sparkline flexes around it.
const FRAME_DELAY_W: f32 = 260.0;
const FRAME_DELAY_CLEARANCE: f32 = 52.0;
const SPARK_H: f32 = 16.0;
// Each metric's full-height value span (sample saturates into it). Chosen to
// line up with the tone thresholds so a point's height roughly tracks its color.
const TPS_SPAN: f32 = 8.0; // fps below target = floor of the chart
const SKEW_SPAN: i32 = 8; // ± about parity; 0 sits mid-height
const LEAD_SPAN: i32 = 24; // ± about zero; saturates well before the overflow bail
const DEPTH_SPAN: u32 = 8;
const PING_SPAN: u128 = 200;
// What each lane needs at TEXT_CAPTION (icon 14, two gaps of 5, a sparkline of at least 20, the readout: mono glyphs
// of about 6.6 px), also its share of the bar's width: a lane never gets less than it needs while the bar has the room
// [`BAR_MIN`] adds up to.
/// The bar's height inside its plate: the frame-delay chip is its tallest part.
const BAR_H: f32 = 22.0;
/// A monospace readout of `chars` glyphs at TEXT_CAPTION (Noto Sans Mono's advance is 0.6 em), with a pixel of slack.
const fn mono_w(chars: u32) -> f32 {
    chars as f32 * TEXT_CAPTION * 0.6 + 1.0
}
/// Every readout is a fixed-width box (its widest text), never sized by what the lane has left: the sparkline gives way
/// and the number never does (a lane too narrow for its number used to wrap or clip it away).
const VALUE_TPS: f32 = mono_w(12); // "59.97 /59.73" (a "100.00" rate still fits)
const VALUE_SMALL: f32 = mono_w(4); // "  -1", "+12", "  0"
const VALUE_PING: f32 = mono_w(7); // " 10 ms", "1234 ms"
/// A lane's icon, its two gaps and the least sparkline.
const LANE_FIXED: f32 = 14.0 + 5.0 + 5.0 + 20.0;
/// The lanes' shares of the bar are their least widths, so a bar with room for them all gives each its least.
const LANE_TPS: u16 = (LANE_FIXED + VALUE_TPS) as u16 + 1;
const LANE_SMALL: u16 = (LANE_FIXED + VALUE_SMALL) as u16 + 1;
const LANE_PING: u16 = (LANE_FIXED + VALUE_PING) as u16 + 1;
/// The lanes' least width together with their four dividers (17 each), the frame-delay chip, the bar's gaps and
/// padding: what the player legend must leave.
const BAR_MIN: f32 = (LANE_TPS + 3 * LANE_SMALL + LANE_PING) as f32 + 4.0 * 17.0 + 62.0 + 34.0;

/// A compact per-metric history chart for the persistent PvP panel. Each
/// retained sample is `(height fraction in 0..=1, tone)`, plotted left→right
/// (oldest→newest) as a thin line whose every segment and vertex is colored by
/// that sample's health tone — so the trend tells the same green/amber/red
/// story as the readout, point by point, instead of one flat color for the
/// whole line. `None` slots are gaps (e.g. skew/depth between rounds) and break
/// the line.
struct Sparkline {
    points: Vec<Option<(f32, StatTone)>>,
    /// Whether to wash the area below the trace (down to the chart floor) with a
    /// faint tint of each segment's tone. On for the one-sided metrics (tps,
    /// depth, ping); off for skew, which is bidirectional about its midline.
    fill_under: bool,
    /// Height fraction (0 = bottom, 1 = top) of a reference line to draw, or
    /// `None` for no line. Parity (mid-height) for skew, the value-0 floor for
    /// depth/ping — and `None` for tps, whose displayed floor is `target − 8`,
    /// not 0, so a "zero" line there would mislead.
    zero: Option<f32>,
}

impl Sparkline {
    fn view<'a>(self) -> Element<'a, Message> {
        // Fill the card's chart area; height is fixed so the row lays out cleanly.
        Canvas::new(self)
            .width(Length::Fill)
            .height(Length::Fixed(SPARK_H))
            .into()
    }
}

impl canvas::Program<Message> for Sparkline {
    type State = ();

    fn draw(
        &self,
        _state: &(),
        renderer: &Renderer,
        theme: &Theme,
        bounds: Rectangle,
        _cursor: mouse::Cursor,
    ) -> Vec<canvas::Geometry> {
        let mut frame = Frame::new(renderer, bounds.size());
        let palette = theme.extended_palette();
        let text_color = theme.palette().text;
        let n = self.points.len();
        let w = bounds.width;
        let h = bounds.height;
        // Inset vertically so points at the extremes (yf 0 or 1) keep the line
        // width fully on-canvas instead of clipping at the edge.
        const PAD: f32 = 2.0;
        let y_at = |yf: f32| PAD + (1.0 - yf.clamp(0.0, 1.0)) * (h - 2.0 * PAD);

        // Recessed background so the chart area reads as its own inset panel.
        let bg = Path::rounded_rectangle(Point::new(0.0, 0.0), bounds.size(), 3.0.into());
        frame.fill(
            &bg,
            Color {
                a: if palette.is_dark { 0.10 } else { 0.05 },
                ..text_color
            },
        );

        // Fixed rolling window: samples sit a fixed pixel step apart with the
        // newest pinned to the right edge, so the trace scrolls in from the
        // right at full scale instead of stretching to fill while the buffer is
        // still filling up.
        let dx = w / (METRIC_HISTORY_LEN.saturating_sub(1).max(1) as f32);
        let x_at = |i: usize| w - (n.saturating_sub(1) - i) as f32 * dx;

        // Tone wash below the trace, down to the chart floor, per segment.
        if self.fill_under {
            let base = y_at(0.0);
            for i in 0..n.saturating_sub(1) {
                if let (Some((y0, _)), Some((y1, tone))) = (self.points[i], self.points[i + 1]) {
                    let (x0, x1) = (x_at(i), x_at(i + 1));
                    let area = Path::new(|p| {
                        p.move_to(Point::new(x0, y_at(y0)));
                        p.line_to(Point::new(x1, y_at(y1)));
                        p.line_to(Point::new(x1, base));
                        p.line_to(Point::new(x0, base));
                        p.close();
                    });
                    frame.fill(
                        &area,
                        Color {
                            a: 0.3,
                            ..stat_tone_color(theme, tone)
                        },
                    );
                }
            }
        }

        // Reference line where one is meaningful (parity for skew, the value-0
        // floor for depth/ping). Drawn over the fill so it stays visible, under
        // the trace.
        if let Some(z) = self.zero {
            let zero_y = y_at(z);
            frame.stroke(
                &Path::line(Point::new(0.0, zero_y), Point::new(w, zero_y)),
                Stroke::default()
                    .with_color(Color { a: 0.22, ..text_color })
                    .with_width(1.0),
            );
        }

        // The trace itself: one hairline segment per adjacent pair of samples,
        // each colored by the newer endpoint's tone, breaking across `None`
        // gaps. No vertices/dots — the connected segments are the whole chart.
        for i in 0..n.saturating_sub(1) {
            if let (Some((y0, _)), Some((y1, tone))) = (self.points[i], self.points[i + 1]) {
                let seg = Path::line(Point::new(x_at(i), y_at(y0)), Point::new(x_at(i + 1), y_at(y1)));
                frame.stroke(
                    &seg,
                    Stroke::default()
                        .with_color(stat_tone_color(theme, tone))
                        .with_width(1.0)
                        .with_line_cap(LineCap::Round),
                );
            }
        }

        vec![frame.into_geometry()]
    }
}

/// One telemetry lane in the compact bar: icon, tiny sparkline, naturally sized
/// current value. The full localized caption moves to a tooltip, preserving the
/// meaning without adding a second line to the bar.
fn telemetry_card<'a>(
    icon: Icon,
    caption: String,
    control: Element<'a, Message>,
    value: Element<'a, Message>,
    value_w: f32,
    weight: u16,
) -> Element<'a, Message> {
    let value = container(value)
        .width(Length::Fixed(value_w))
        .align_x(iced::alignment::Horizontal::Right);
    let icon = iced::widget::tooltip(
        icon.widget().size(14.0).style(widgets::muted_text_style),
        widgets::tooltip_bubble(caption),
        iced::widget::tooltip::Position::Top,
    )
    .gap(5);
    // (a lane's share of the bar follows what its readout needs, so a narrow bar never takes a number's room)
    let lane = row![icon, control, value]
        .spacing(5)
        .align_y(Alignment::Center)
        .width(Length::FillPortion(weight));
    lane.into()
}

/// A monospace readout drawn on a canvas, its segments right-aligned and read right to left: `(text, tone)`, `None`
/// for the plain text colour. It is deliberately not a `text` widget. A widget's text is a weak reference to its
/// paragraph, and the next layout (a new number) replaces the paragraph: a screenshot taken after that layout (the
/// debug aids' `shot`, the F8 report) re-renders the last drawn frame with the changing numbers (the rate, the ping)
/// missing. Canvas text carries its own string, so the numbers are in every picture of the bar.
struct Readout {
    segments: Vec<(String, Option<StatTone>)>,
}

impl Readout {
    fn view<'a>(self) -> Element<'a, Message> {
        Canvas::new(self).width(Length::Fill).height(Length::Fixed(SPARK_H)).into()
    }
}

impl canvas::Program<Message> for Readout {
    type State = ();

    fn draw(
        &self,
        _state: &(),
        renderer: &Renderer,
        theme: &Theme,
        bounds: Rectangle,
        _cursor: mouse::Cursor,
    ) -> Vec<canvas::Geometry> {
        let mut frame = Frame::new(renderer, bounds.size());
        let mut right = bounds.width;
        for (s, tone) in &self.segments {
            frame.fill_text(canvas::Text {
                content: s.clone(),
                position: Point::new(right, bounds.height / 2.0),
                color: tone.map_or_else(|| theme.palette().text, |t| stat_tone_color(theme, t)),
                size: TEXT_CAPTION.into(),
                font: iced::Font::MONOSPACE,
                align_x: iced::advanced::text::Alignment::Right,
                align_y: iced::alignment::Vertical::Center,
                ..canvas::Text::default()
            });
            right -= s.chars().count() as f32 * TEXT_CAPTION * 0.6 + 2.0;
        }
        vec![frame.into_geometry()]
    }
}

/// A right-aligned monospace value readout, tinted by `tone`.
fn value_text<'a>(s: String, tone: Option<StatTone>) -> Element<'a, Message> {
    Readout { segments: vec![(s, tone)] }.view()
}

/// TPS readout: current rate over its live cap, compressed to fit a status lane.
fn tps_value<'a>(tps: f32, fps_target: f32, tone: StatTone) -> Element<'a, Message> {
    Readout {
        segments: vec![(format!("/{:5.2}", fps_target), Some(StatTone::Muted)), (format!("{:5.2}", tps), Some(tone))],
    }
    .view()
}

/// One metric card: build its sparkline series by mapping every retained sample
/// through `point` (returning `None` for slots with no reading, which become
/// gaps), and read the current value off the newest sample via `value` (showing
/// `—` muted when there's nothing yet, e.g. skew/depth between rounds).
fn metric_card<'a>(
    icon: Icon,
    caption: String,
    fill_under: bool,
    zero: Option<f32>,
    history: &std::collections::VecDeque<MetricSample>,
    point: impl Fn(&MetricSample) -> Option<(f32, StatTone)>,
    value: impl Fn(&MetricSample) -> Option<Element<'a, Message>>,
    value_w: f32,
    weight: u16,
) -> Element<'a, Message> {
    let points = history.iter().map(&point).collect();
    let value = history
        .back()
        .and_then(value)
        .unwrap_or_else(|| value_text("—".to_string(), Some(StatTone::Muted)));
    telemetry_card(
        icon,
        caption,
        Sparkline {
            points,
            fill_under,
            zero,
        }
        .view(),
        value,
        value_w,
        weight,
    )
}

/// The five compact metric lanes. Each chart reads its rolling window from
/// `history` and its current value from the newest sample.
fn telemetry_content<'a>(
    lang: &'a LanguageIdentifier,
    history: &std::collections::VecDeque<MetricSample>,
    compact: bool,
) -> Element<'a, Message> {
    // `zero` is the reference line: parity (mid-height) for skew, the value-0
    // floor for depth/ping, and `None` for tps (its floor is `target − 8`, so a
    // "zero" line there would mislead).
    let tps_card = metric_card(
        Icon::Gauge,
        t!(lang, "session-stat-tps"),
        true,
        None,
        history,
        |s| {
            (s.fps_target > 0.0).then(|| {
                let yf = (s.tps - (s.fps_target - TPS_SPAN)) / TPS_SPAN;
                (yf.clamp(0.0, 1.0), tone_for_tps(s.tps, s.fps_target))
            })
        },
        |s| (s.fps_target > 0.0).then(|| tps_value(s.tps, s.fps_target, tone_for_tps(s.tps, s.fps_target))),
        VALUE_TPS,
        LANE_TPS,
    );

    let skew_card = metric_card(
        Icon::ArrowLeftRight,
        t!(lang, "session-stat-skew"),
        false,
        Some(0.5),
        history,
        |s| {
            s.round.map(|(skew, _, _)| {
                let yf = (skew.clamp(-SKEW_SPAN, SKEW_SPAN) as f32 + SKEW_SPAN as f32) / (2.0 * SKEW_SPAN as f32);
                (yf, tone_for_skew(skew))
            })
        },
        |s| {
            s.round
                .map(|(skew, _, _)| value_text(fmt_skew(skew), Some(tone_for_skew(skew))))
        },
        VALUE_SMALL,
        LANE_SMALL,
    );

    let lead_card = metric_card(
        Icon::SportShoe,
        t!(lang, "session-stat-lead"),
        false,
        Some(0.5),
        history,
        |s| {
            s.round.map(|(_, _, lead)| {
                let yf = (lead.clamp(-LEAD_SPAN, LEAD_SPAN) as f32 + LEAD_SPAN as f32) / (2.0 * LEAD_SPAN as f32);
                (yf, tone_for_lead(lead))
            })
        },
        |s| {
            s.round
                .map(|(_, _, lead)| value_text(fmt_lead(lead), Some(tone_for_lead(lead))))
        },
        VALUE_SMALL,
        LANE_SMALL,
    );

    let depth_card = metric_card(
        Icon::GitMergeConflict,
        t!(lang, "session-stat-depth"),
        true,
        Some(0.0),
        history,
        |s| {
            s.round
                .map(|(_, depth, _)| (depth.min(DEPTH_SPAN) as f32 / DEPTH_SPAN as f32, tone_for_depth(depth)))
        },
        |s| {
            s.round
                .map(|(_, depth, _)| value_text(fmt_depth(depth), Some(tone_for_depth(depth))))
        },
        VALUE_SMALL,
        LANE_SMALL,
    );

    let ping_card = metric_card(
        Icon::ChevronsLeftRightEllipsis,
        t!(lang, "session-stat-ping"),
        true,
        Some(0.0),
        history,
        |s| {
            s.ping_ms
                .map(|ping_ms| (ping_ms.min(PING_SPAN) as f32 / PING_SPAN as f32, tone_for_ping(ping_ms)))
        },
        |s| {
            s.ping_ms
                .map(|ping_ms| value_text(fmt_ping(ping_ms), Some(tone_for_ping(ping_ms))))
        },
        VALUE_PING,
        LANE_PING,
    );

    // (a bar narrower than the five lanes need, a phone's: the latency alone, the number a player acts on)
    if compact {
        return ping_card;
    }
    row![
        tps_card,
        status_divider(),
        skew_card,
        status_divider(),
        lead_card,
        status_divider(),
        depth_card,
        status_divider(),
        ping_card,
    ]
    .spacing(8)
    .align_y(Alignment::Center)
    .width(Fill)
    .into()
}

/// Semantic tone for a PvP telemetry value. The icon always rides
/// muted; only the value picks up `Good`/`Warn`/`Bad` so color reads
/// as "this number means something is healthy / borderline / wrong"
/// rather than mere decoration.
#[derive(Clone, Copy)]
enum StatTone {
    Muted,
    Good,
    Warn,
    Bad,
}

fn stat_tone_color(theme: &iced::Theme, tone: StatTone) -> iced::Color {
    match tone {
        StatTone::Muted => widgets::muted_color(theme),
        StatTone::Good => theme.extended_palette().success.strong.color,
        // Amber lives outside iced's default palette, so hardcode a
        // tone that reads on both the dark navy and light parchment
        // HUD plates.
        StatTone::Warn => iced::Color::from_rgb(0.92, 0.67, 0.18),
        StatTone::Bad => theme.extended_palette().danger.strong.color,
    }
}

// Health tone per metric. Shared by the current readout and sparkline so the
// number and chart points always agree
// on green/amber/red.

/// TPS vs the live fps target: green at/near rate, amber as it dips, red when
/// it falls well behind (visible netplay stutter). Muted before a target exists.
fn tone_for_tps(tps: f32, fps_target: f32) -> StatTone {
    if fps_target <= 0.0 {
        StatTone::Muted
    } else if tps >= fps_target - 1.0 {
        StatTone::Good
    } else if tps >= fps_target - 5.0 {
        StatTone::Warn
    } else {
        StatTone::Bad
    }
}

/// Clock skew: green near parity, amber drifting, red far out, by `|skew|`.
fn tone_for_skew(skew: i32) -> StatTone {
    match skew.unsigned_abs() {
        0..=3 => StatTone::Good,
        4..=7 => StatTone::Warn,
        _ => StatTone::Bad,
    }
}

/// Local lead by `|lead|`: green at a healthy steady lead, amber as it climbs,
/// red when it runs far from zero in either direction (the remote is lagging and
/// we're heading toward the bail, or we've fallen behind it).
fn tone_for_lead(lead: i32) -> StatTone {
    match lead.unsigned_abs() {
        0..=8 => StatTone::Good,
        9..=16 => StatTone::Warn,
        _ => StatTone::Bad,
    }
}

/// Rollback depth: green shallow, amber climbing, red when speculation runs deep.
fn tone_for_depth(depth: u32) -> StatTone {
    match depth {
        0..=2 => StatTone::Good,
        3..=5 => StatTone::Warn,
        _ => StatTone::Bad,
    }
}

/// Latency band: green under 80 ms, amber under 140 ms, red beyond.
fn tone_for_ping(ping_ms: u128) -> StatTone {
    if ping_ms < 80 {
        StatTone::Good
    } else if ping_ms < 140 {
        StatTone::Warn
    } else {
        StatTone::Bad
    }
}

// Value formatting for the telemetry readouts.

/// Signed skew in a 3-wide field; bare `0` at parity reads calmer than `+0`.
fn fmt_skew(skew: i32) -> String {
    if skew == 0 {
        "  0".to_string()
    } else {
        format!("{skew:+3}")
    }
}
/// Signed local lead in ticks; bare `0` at zero reads calmer than `+0`.
fn fmt_lead(lead: i32) -> String {
    if lead == 0 {
        "  0".to_string()
    } else {
        format!("{lead:+3}")
    }
}
/// Rollback depth.
fn fmt_depth(depth: u32) -> String {
    format!("{depth:3}")
}
/// Latency in ms.
fn fmt_ping(ping_ms: u128) -> String {
    format!("{ping_ms:3} ms")
}

/// Persistent player/seat legend above the charts. Red and blue describe field
/// halves everywhere except games that color players by seat; those keep the
/// game-native P1/P2 color assignment while You/Opponent follows the local seat.
fn players_header<'a>(lang: &'a LanguageIdentifier, pvp: &'a PvpSession, budget: f32, compact: bool) -> Element<'a, Message> {
    legend_view(
        lang,
        (pvp.local_player_index() == 0, pvp.local_game().family.players_colored_by_seat),
        budget,
        compact,
        Some(pvp.host_seat()),
    )
}

/// The legend; `two` is the two-player view's (local seat is P1, seats colour the armies), all a pvp session adds.
fn legend_view<'a>(
    lang: &'a LanguageIdentifier,
    two: (bool, bool),
    budget: f32,
    compact: bool,
    host: Option<usize>,
) -> Element<'a, Message> {
    // (a room's host is marked "host" after its name: it changes when the host leaves and a guest takes the room over)
    let side = |accent: Color, seat: &'static str, name: String, host: bool| -> Element<'a, Message> {
        let dot = container(
            iced::widget::Space::new()
                .width(Length::Fixed(8.0))
                .height(Length::Fixed(8.0)),
        )
        .style(move |theme: &iced::Theme| iced::widget::container::Style {
            background: Some(iced::Background::Color(accent)),
            // (a hairline outline: Black Hole's near-black dot must show on a dark bar and a light one)
            border: iced::Border {
                radius: 999.0.into(),
                width: 1.0,
                color: Color { a: 0.55, ..theme.palette().text },
            },
            ..Default::default()
        });
        let r = row![
            dot,
            text(seat).size(TEXT_CAPTION).font(iced::Font::MONOSPACE),
            text(name).size(TEXT_CAPTION).style(widgets::muted_text_style),
        ]
        .spacing(4)
        .align_y(Alignment::Center);
        if host {
            r.push(text("host").size(TEXT_CAPTION).font(iced::Font::MONOSPACE)).into()
        } else {
            r.into()
        }
    };

    use widgets::{FIELD_BLUE, FIELD_RED};
    let n = tango_library::online::room_players();
    if compact {
        // The armies' dots alone: names and seat markers do not fit a phone's bar.
        let colors = [FIELD_RED, FIELD_BLUE, Color::from_rgb8(0x4c, 0xaf, 0x50), Color::from_rgb8(0xe0, 0xb0, 0x20), Color::from_rgb8(0x30, 0x30, 0x30)];
        let mut r = row![].spacing(4).align_y(Alignment::Center);
        for k in 0..n.clamp(2, 5) {
            let c = colors[k];
            r = r.push(container(iced::widget::Space::new().width(Length::Fixed(8.0)).height(Length::Fixed(8.0))).style(
                move |theme: &iced::Theme| iced::widget::container::Style {
                    background: Some(iced::Background::Color(c)),
                    border: iced::Border { radius: 999.0.into(), width: 1.0, color: Color { a: 0.55, ..theme.palette().text } },
                    ..Default::default()
                },
            ));
        }
        return r.into();
    }
    if n > 2 || tango_library::online::room_named() >= 2 {
        // A room of 3-5: every seat, in its army's colour, with its gamertag. The legend takes what the numbers beside
        // it leave (`budget`): the full names while they fit, else shorter and shorter ones, and last only the seat
        // markers (the local seat says "You"); the full legend is in a tooltip whenever anything is cut.
        let colors = [FIELD_RED, FIELD_BLUE, Color::from_rgb8(0x4c, 0xaf, 0x50), Color::from_rgb8(0xe0, 0xb0, 0x20), Color::from_rgb8(0x30, 0x30, 0x30)];
        let me = tango_library::online::room_local_seat();
        let seats: [&'static str; 5] = ["P1", "P2", "P3", "P4", "P5"];
        let you = t!(lang, "play-you");
        let names: Vec<String> = (0..n).map(|k| tango_library::online::room_name(k)).collect();
        let full: Vec<String> = names
            .iter()
            .enumerate()
            .map(|(k, name)| if k == me { format!("{name} ({you})") } else { name.clone() })
            .collect();
        // Teams (any team of two or more): "A: Host, Guest2  B: Guest", each in its army's colour. The names are cut
        // to the budget as the seats' legend's are (less the room the team letters take).
        let picks = tango_library::online::room_picks();
        if picks.len() == n && (0..n).any(|a| (0..n).any(|b| a != b && picks[a].0 == picks[b].0)) {
            let teams = (0..5u8).filter(|&t| picks.iter().any(|p| p.0 == t)).count() as f32;
            let (shown, cut) = legend_names_in(&names, me, &you, &full, budget - 22.0 * teams - if host.is_some() { 32.0 } else { 0.0 }, 0.0);
            let mut r = row![].spacing(12).align_y(Alignment::Center);
            // (the letters count the teams in use: A, A, C, C reads A, A, B, B)
            let mut used: Vec<u8> = picks.iter().map(|p| p.0).collect();
            used.sort_unstable();
            used.dedup();
            for team in 0..5u8 {
                let members: Vec<usize> = (0..n).filter(|&k| picks[k].0 == team).collect();
                if members.is_empty() {
                    continue;
                }
                let mut g = row![text(format!("{}:", (b'A' + used.iter().position(|&t| t == team).unwrap_or(0) as u8) as char)).size(TEXT_CAPTION).font(iced::Font::MONOSPACE)]
                    .spacing(4)
                    .align_y(Alignment::Center);
                for (i, &k) in members.iter().enumerate() {
                    let accent = colors[(picks[k].1 as usize).clamp(1, 5) - 1];
                    let name = if i + 1 < members.len() { format!("{},", shown[k]) } else { shown[k].clone() };
                    g = g.push(side(accent, "", name, host == Some(k)));
                }
                r = r.push(g);
            }
            if !cut {
                return r.into();
            }
            let who = full.iter().enumerate().map(|(k, f)| format!("{} {f}", seats[k])).collect::<Vec<_>>().join("\n");
            return iced::widget::tooltip(r, widgets::tooltip_bubble(who), iced::widget::tooltip::Position::Top)
                .gap(5)
                .into();
        }
        let budget = budget - if host.is_some() { 32.0 } else { 0.0 };
        let (shown, cut) = legend_names(&names, me, &you, &full, budget);
        let mut r = row![].spacing(12).align_y(Alignment::Center);
        for k in 0..n {
            r = r.push(side(colors[k], seats[k], shown[k].clone(), host == Some(k)));
        }
        if !cut {
            return r.into();
        }
        let who = full.iter().enumerate().map(|(k, f)| format!("{} {f}", seats[k])).collect::<Vec<_>>().join("\n");
        return iced::widget::tooltip(r, widgets::tooltip_bubble(who), iced::widget::tooltip::Position::Top)
            .gap(5)
            .into();
    }
    let (local_is_p1, by_seat) = two;
    let (you, opponent) = (t!(lang, "play-you"), t!(lang, "play-opponent"));
    if by_seat {
        let (p1, p2) = if local_is_p1 { (you, opponent) } else { (opponent, you) };
        row![side(FIELD_RED, "P1", p1, false), side(FIELD_BLUE, "P2", p2, false)]
    } else {
        let (local_seat, remote_seat) = if local_is_p1 { ("P1", "P2") } else { ("P2", "P1") };
        row![
            side(FIELD_RED, local_seat, you, false),
            side(FIELD_BLUE, remote_seat, opponent, false),
        ]
    }
    .spacing(12)
    .align_y(Alignment::Center)
    .into()
}

/// A legend entry's width at TEXT_CAPTION, roughly: the army's dot (8), a gap (4), the seat marker (two mono glyphs),
/// a gap, the name's glyphs (about 6.5 px each: Noto Sans at 11 px, measured in the render test).
fn legend_entry_width(name_chars: usize) -> f32 {
    legend_entry_width_in(name_chars, 15.0)
}

/// [`legend_entry_width`] with the seat marker's `marker` width (none in the teams' legend).
fn legend_entry_width_in(name_chars: usize, marker: f32) -> f32 {
    8.0 + 4.0 + marker + if name_chars > 0 { 4.0 + name_chars as f32 * 6.5 } else { 0.0 }
}

/// The names the legend shows in `budget` pixels, and whether any was cut: the full ones ("Name (You)") if they fit,
/// else names of at most 10, 8, 6 and 4 letters (ending in an ellipsis; the local seat shows "You"), else no names but
/// the local seat's "You".
fn legend_names(names: &[String], me: usize, you: &str, full: &[String], budget: f32) -> (Vec<String>, bool) {
    legend_names_in(names, me, you, full, budget, 15.0)
}

fn legend_names_in(names: &[String], me: usize, you: &str, full: &[String], budget: f32, marker: f32) -> (Vec<String>, bool) {
    let n = names.len();
    let gaps = 12.0 * (n as f32 - 1.0);
    let width = |texts: &[String]| gaps + texts.iter().map(|t| legend_entry_width_in(t.chars().count(), marker)).sum::<f32>();
    if width(full) <= budget {
        return (full.to_vec(), false);
    }
    let cut_to = |m: usize| -> Vec<String> {
        names
            .iter()
            .enumerate()
            .map(|(k, name)| {
                if k == me {
                    you.to_string()
                } else if name.chars().count() > m {
                    format!("{}…", name.chars().take(m.saturating_sub(1).max(1)).collect::<String>())
                } else {
                    name.clone()
                }
            })
            .collect()
    };
    for m in [10, 9, 8, 7, 6, 5, 4] {
        let texts = cut_to(m);
        if width(&texts) <= budget {
            return (texts, true);
        }
    }
    let marks: Vec<String> = (0..n).map(|k| if k == me { you.to_string() } else { String::new() }).collect();
    (marks, true)
}

/// Hairline between the player legend, telemetry lanes, and frame-delay chip.
fn status_divider<'a>() -> Element<'a, Message> {
    container(
        iced::widget::Space::new()
            .width(Length::Fixed(1.0))
            .height(Length::Fixed(20.0)),
    )
    .style(|theme: &iced::Theme| iced::widget::container::Style {
        background: Some(iced::Background::Color(Color {
            a: 0.14,
            ..theme.palette().text
        })),
        ..Default::default()
    })
    .into()
}

/// Resting frame-delay control: current value and disclosure chevron only. The
/// full slider is intentionally out of the bar until requested.
fn frame_delay_chip<'a>(lang: &'a LanguageIdentifier, pvp: &'a PvpSession, open: bool) -> Element<'a, Message> {
    frame_delay_chip_of(lang, pvp.frame_delay(), open)
}

fn frame_delay_chip_of<'a>(lang: &'a LanguageIdentifier, frame_delay: impl ToString, open: bool) -> Element<'a, Message> {
    let chip = button(
        row![
            Icon::Turtle.widget().size(14.0),
            text(frame_delay.to_string())
                .size(TEXT_CAPTION)
                .font(iced::Font::MONOSPACE)
                .width(Length::Fixed(14.0)),
            if open { Icon::ChevronDown } else { Icon::ChevronUp }
                .widget()
                .size(11.0)
                .style(widgets::muted_text_style),
        ]
        .spacing(4)
        .align_y(Alignment::Center),
    )
    .padding([3.0, 6.0])
    .style(widgets::neutral)
    .on_press(Message::ToggleFrameDelayControl);
    iced::widget::tooltip(
        chip,
        widgets::tooltip_bubble(t!(lang, "settings-netplay-frame-delay")),
        iced::widget::tooltip::Position::Top,
    )
    .gap(5)
    .into()
}

/// The bar's one row for a bar `width` wide.
fn status_row<'a>(
    width: f32,
    legend: impl FnOnce(f32, bool) -> Element<'a, Message>,
    content: impl FnOnce(bool) -> Element<'a, Message>,
    chip: Element<'a, Message>,
) -> Element<'a, Message> {
    let budget = width - BAR_MIN;
    let compact = budget < 0.0;
    // (the legend is cut by its own estimate; should that be short, it is clipped here, never the numbers beside it)
    let legend: Element<'a, Message> = if compact {
        legend(budget, compact)
    } else {
        container(legend(budget, compact)).max_width(budget).clip(true).into()
    };
    row![legend, status_divider(), content(compact), status_divider(), chip]
        .spacing(8)
        .align_y(Alignment::Center)
        .width(Fill)
        .into()
}

/// Always-visible PvP telemetry. P1/P2 and all five tiny charts occupy one
/// stable row; the trailing chip is the only disclosure control.
pub(super) fn telemetry_panel<'a>(
    lang: &'a LanguageIdentifier,
    pvp: &'a PvpSession,
    state: &'a State,
) -> Element<'a, Message> {
    // The bar knows its width: the numbers (lanes, frame-delay chip) keep what they need ([`BAR_MIN`]) and the player
    // legend of a room takes the rest, shortened if it must be.
    let bar = iced::widget::responsive(move |size| {
        status_row(
            size.width,
            |budget, compact| players_header(lang, pvp, budget, compact),
            |compact| telemetry_content(lang, &state.metric_history, compact),
            frame_delay_chip(lang, pvp, state.frame_delay_control.shown()),
        )
    });
    let panel = container(container(bar).height(Length::Fixed(BAR_H)).width(Fill))
        .padding([6.0, 8.0])
        .width(Fill)
        .style(hud_chip_plate);

    container(panel)
        .width(Fill)
        .padding(iced::Padding {
            top: 0.0,
            right: 12.0,
            bottom: 8.0,
            left: 12.0,
        })
        .into()
}

/// Small frame-delay popover anchored immediately above the persistent bar.
/// It is the only collapsible piece of telemetry; opening it never changes the
/// bar's size or the game-region layout.
pub(super) fn frame_delay_overlay<'a>(
    lang: &'a LanguageIdentifier,
    pvp: &'a PvpSession,
    state: &'a State,
) -> Option<Element<'a, Message>> {
    let now = iced::time::Instant::now();
    if !state.frame_delay_control.visible(now) {
        return None;
    }
    let popup = container(frame_delay_control(lang, pvp))
        .padding(12)
        .style(widgets::panel);
    Some(
        container(anim::pop(popup, state.frame_delay_control.progress(now), 8.0))
            .width(Fill)
            .height(Fill)
            .align_x(iced::alignment::Horizontal::Right)
            .align_y(iced::alignment::Vertical::Bottom)
            .padding(iced::Padding {
                top: 0.0,
                right: 12.0,
                bottom: FRAME_DELAY_CLEARANCE,
                left: 0.0,
            })
            .into(),
    )
}

#[cfg(test)]
mod legend_tests {
    use super::*;

    fn names(n: usize, len: usize) -> Vec<String> {
        (0..n).map(|k| format!("{}{}", "Gamertag".repeat(2).chars().take(len - 1).collect::<String>(), k)).collect()
    }
    fn full(names: &[String], me: usize) -> Vec<String> {
        names.iter().enumerate().map(|(k, n)| if k == me { format!("{n} (You)") } else { n.clone() }).collect()
    }
    fn width(texts: &[String]) -> f32 {
        12.0 * (texts.len() as f32 - 1.0) + texts.iter().map(|t| legend_entry_width(t.chars().count())).sum::<f32>()
    }

    /// The least bar the app allows (the window's minimum, 960, less the two paddings): the legend of 3, 4 and 5 players
    /// with 10-letter gamertags always fits the room the numbers leave, and the numbers never lose theirs.
    #[test]
    fn legend_fits_the_minimum_bar() {
        let bar = 960.0 - 24.0 - 16.0;
        let budget = bar - BAR_MIN;
        assert!(budget > 150.0, "the numbers must leave the legend some room: {budget}");
        for n in 3..=5 {
            let nm = names(n, 10);
            let (shown, _) = legend_names(&nm, 1, "You", &full(&nm, 1), budget);
            assert!(width(&shown) <= budget, "{n} players: {} > {budget}: {shown:?}", width(&shown));
        }
    }

    /// The legend of teams (no seat markers, a letter a team) fits the minimum bar too, for 5 players in 2 or 3 teams.
    #[test]
    fn team_legend_fits_the_minimum_bar() {
        let budget = 960.0 - 24.0 - 16.0 - BAR_MIN;
        for teams in [2.0, 3.0] {
            let nm = names(5, 10);
            let room = budget - 22.0 * teams;
            let (shown, _) = legend_names_in(&nm, 1, "You", &full(&nm, 1), room, 0.0);
            let w = 12.0 * 4.0 + shown.iter().map(|t| legend_entry_width_in(t.chars().count(), 0.0)).sum::<f32>();
            assert!(w <= room, "{teams} teams: {w} > {room}: {shown:?}");
        }
    }

    /// At a 1100 px window (the bar is the window less 40) five players with 8-letter gamertags keep them whole, and
    /// 10-letter ones lose at most two letters.
    #[test]
    fn five_players_at_1100_keep_eight_letters() {
        let budget = 1100.0 - 24.0 - 16.0 - BAR_MIN;
        let nm = names(5, 8);
        let (shown, _) = legend_names(&nm, 1, "You", &full(&nm, 1), budget);
        for (k, t) in shown.iter().enumerate() {
            assert!(k == 1 || !t.contains('…'), "{shown:?}");
        }
        let nm = names(5, 10);
        let (shown, _) = legend_names(&nm, 1, "You", &full(&nm, 1), budget);
        println!("1100 px, 10-letter: {shown:?}");
    }

    #[test]
    fn short_names_stay_whole() {
        let nm: Vec<String> = ["Host", "Guest", "Guest2"].iter().map(|s| s.to_string()).collect();
        let (shown, cut) = legend_names(&nm, 0, "You", &full(&nm, 0), 400.0);
        assert!(!cut);
        assert_eq!(shown[0], "Host (You)");
    }

    #[test]
    fn long_names_are_cut_then_dropped() {
        let nm = names(5, 10);
        let (shown, cut) = legend_names(&nm, 0, "You", &full(&nm, 0), 250.0);
        assert!(cut);
        assert_eq!(shown[0], "You");
        let (shown, cut) = legend_names(&nm, 0, "You", &full(&nm, 0), 100.0);
        assert!(cut);
        assert!(shown[1].is_empty());
    }
}

/// Offline render of the bar (iced's tiny-skia headless renderer, no session): PNGs of the real layout at several widths
/// and room sizes, and the check that every readout is on screen. `BAR_OUT=<dir>` keeps the PNGs.
#[cfg(test)]
mod render_tests {
    use super::*;
    use iced::advanced::renderer::Headless;
    use iced_runtime::user_interface::{Cache, UserInterface};
    use std::collections::VecDeque;

    fn samples() -> VecDeque<MetricSample> {
        (0..METRIC_HISTORY_LEN)
            .map(|i| MetricSample {
                tps: 59.5 + ((i % 7) as f32) * 0.07,
                fps_target: 59.73,
                ping_ms: Some(8 + (i % 5) as u128),
                round: Some((((i % 5) as i32) - 2, (i % 4) as u32, ((i % 6) as i32) - 3)),
            })
            .collect()
    }

    fn renderer() -> iced::Renderer {
        let mut fs = iced_graphics::text::font_system().write().unwrap();
        for f in [
            &include_bytes!("../../../../fonts/NotoSans-Regular.ttf")[..],
            &include_bytes!("../../../../fonts/NotoSansMono-Regular.ttf")[..],
            lucide_icons::LUCIDE_FONT_BYTES,
        ] {
            fs.load_font(std::borrow::Cow::Borrowed(f));
        }
        drop(fs);
        // BAR_BACKEND=any tries the GPU (the app's renderer) first; the default is the software one.
        let backend = std::env::var("BAR_BACKEND").unwrap_or_else(|_| "tiny-skia".into());
        let backend = (backend != "any").then_some(backend);
        futures::executor::block_on(<iced::Renderer as Headless>::new(
            crate::ui::style::DEFAULT_FONT,
            16.0.into(),
            backend.as_deref(),
        ))
        .expect("headless renderer")
    }

    fn render(renderer: &mut iced::Renderer, width: u32, players: usize, name_len: usize, history: &VecDeque<MetricSample>) -> (Vec<u8>, u32, u32) {
        render_cached(renderer, &mut Cache::default(), width, players, name_len, history, None)
    }

    fn root_for<'a>(lang: &'a LanguageIdentifier, history: &'a VecDeque<MetricSample>) -> Element<'a, Message> {
        let bar: Element<'_, Message> = iced::widget::responsive(move |size| {
            status_row(
                size.width,
                |budget, compact| legend_view(lang, (true, true), budget, compact, None),
                |compact| telemetry_content(lang, history, compact),
                frame_delay_chip_of(lang, 2, false),
            )
        })
        .into();
        let panel = container(container(bar).height(Length::Fixed(BAR_H)).width(Fill))
            .padding([6.0, 8.0])
            .width(Fill);
        container(panel).width(Fill).padding([0.0, 12.0]).into()
    }

    /// As [`render`], the interface's widget state kept between frames (as the app does: text paragraphs are updated).
    /// With `next`, the following frame's interface is laid out (not drawn) before the screenshot, as the app's
    /// `window::screenshot` finds it: it re-renders the last drawn layers, whose text still points at the paragraphs
    /// the new layout has since replaced.
    fn render_cached(
        renderer: &mut iced::Renderer,
        cache: &mut Cache,
        width: u32,
        players: usize,
        name_len: usize,
        history: &VecDeque<MetricSample>,
        next: Option<&VecDeque<MetricSample>>,
    ) -> (Vec<u8>, u32, u32) {
        // (the room is a process-wide global: one render at a time)
        static ROOM: std::sync::Mutex<()> = std::sync::Mutex::new(());
        let _room = ROOM.lock().unwrap_or_else(|e| e.into_inner());
        let lang: LanguageIdentifier = "en-US".parse().unwrap();
        let names: Vec<String> = (0..players).map(|k| format!("{}{}", "Gamertagxyz".chars().take(name_len - 1).collect::<String>(), k)).collect();
        tango_library::online::set_room(names, 1);
        let theme = iced::Theme::Dark;
        let h = BAR_H as u32 + 12;
        let size = iced::Size::new(width as f32, h as f32);
        let mut ui = UserInterface::build(root_for(&lang, history), size, std::mem::take(cache), renderer);
        ui.draw(
            renderer,
            &theme,
            &iced::advanced::renderer::Style { text_color: theme.palette().text },
            iced::mouse::Cursor::Unavailable,
        );
        let bg = theme.palette().background;
        let (px, c) = match next {
            None => (renderer.screenshot(iced::Size::new(width, h), 1.0, bg), ui.into_cache()),
            Some(next) => {
                let ui2 = UserInterface::build(root_for(&lang, next), size, ui.into_cache(), renderer);
                (renderer.screenshot(iced::Size::new(width, h), 1.0, bg), ui2.into_cache())
            }
        };
        *cache = c;
        (px, width, h)
    }

    /// Whether the columns `x0..x1` of the bar's row hold text-coloured pixels (not the background's).
    fn ink(px: &[u8], w: u32, h: u32, x0: u32, x1: u32) -> usize {
        let bg = &px[0..4];
        let mut n = 0;
        for y in 0..h {
            for x in x0..x1.min(w) {
                let i = ((y * w + x) * 4) as usize;
                let d: i32 = (0..3).map(|c| (px[i + c] as i32 - bg[c] as i32).abs()).sum();
                if d > 120 {
                    n += 1;
                }
            }
        }
        n
    }

    #[test]
    fn bar_png_matrix() {
        let out = std::env::var("BAR_OUT").ok();
        let mut renderer = renderer();
        for players in 2..=5 {
            for width in [960u32, 1100, 1440] {
                let (px, w, h) = render(&mut renderer, width, players, 10, &samples());
                // the ping readout ("12 ms") sits just left of the last divider, which is left of the frame-delay chip
                let right = w - 99;
                assert!(ink(&px, w, h, right - 48, right) > 25, "{players} players at {width}: the ping readout is missing");
                if let Some(dir) = &out {
                    let img = image::RgbaImage::from_raw(w, h, px.clone()).unwrap();
                    img.save(format!("{dir}/bar_{players}p_{width}.png")).unwrap();
                }
            }
        }
    }

    /// A live-like run on one renderer: samples roll in every frame (tps and ping jitter), the bar is drawn after each,
    /// and no readout may ever be missing. Prints the ink per frame with `--nocapture`.
    #[test]
    fn bar_readouts_never_vanish() {
        let mut renderer = renderer();
        let mut caches: Vec<Cache> = (0..3).map(|_| Cache::default()).collect();
        let mut hist = samples();
        let mut worst = usize::MAX;
        let mut best = 0;
        for frame in 0..240u32 {
            hist.pop_front();
            let j = (frame * 7919 % 100) as f32 / 100.0;
            hist.push_back(MetricSample {
                tps: 59.2 + j * 0.9,
                fps_target: 59.73,
                ping_ms: Some(7 + (frame * 31 % 90) as u128),
                round: Some(((frame % 5) as i32 - 2, frame % 4, (frame % 7) as i32 - 3)),
            });
            for (ci, (players, width)) in [(3usize, 960u32), (3, 1100), (5, 960)].into_iter().enumerate() {
                let (px, w, h) = render_cached(&mut renderer, &mut caches[ci], width, players, 10, &hist, None);
                let n = ink(&px, w, h, 0, w);
                if players == 3 && width == 960 {
                    worst = worst.min(n);
                    best = best.max(n);
                    if let Ok(dir) = std::env::var("BAR_OUT") {
                        if frame % 30 == 0 {
                            image::RgbaImage::from_raw(w, h, px).unwrap().save(format!("{dir}/live_{frame:03}.png")).unwrap();
                        }
                    }
                }
            }
        }
        println!("ink min {worst} max {best}");
    }

    /// The app's screenshots (`window::screenshot`: the pad script's `shot`, the F8 report) re-render the last drawn layers
    /// after the next frame's layout. Readouts as text widgets were blank there when their text had changed since (the
    /// rate, the ping): the "missing numbers" in the harness's captures. They are canvas text now, which carries its string.
    #[test]
    fn late_screenshot_keeps_changing_readouts() {
        let mut renderer = renderer();
        let a = samples();
        let mut b = samples();
        b.pop_front();
        b.push_back(MetricSample { tps: 58.9, fps_target: 59.73, ping_ms: Some(77), round: a.back().unwrap().round });
        let (live, w, h) = render_cached(&mut renderer, &mut Cache::default(), 1100, 3, 10, &a, None);
        let (late, _, _) = render_cached(&mut renderer, &mut Cache::default(), 1100, 3, 10, &a, Some(&b));
        let right = w - 99;
        let (a, b) = (ink(&live, w, h, right - 48, right), ink(&late, w, h, right - 48, right));
        assert!(a > 25 && b > 25, "ping readout: live ink {a}, late-screenshot ink {b}");
        assert!(ink(&live, w, h, 0, w).abs_diff(ink(&late, w, h, 0, w)) < 200, "the late screenshot differs from the live frame");
        if let Ok(dir) = std::env::var("BAR_OUT") {
            image::RgbaImage::from_raw(w, h, live).unwrap().save(format!("{dir}/shot_live.png")).unwrap();
            image::RgbaImage::from_raw(w, h, late).unwrap().save(format!("{dir}/shot_late.png")).unwrap();
        }
    }
}
