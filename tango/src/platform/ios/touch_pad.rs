//! The on-screen GBA controller: D-pad, A, B, L, R, Start and Select
//! drawn over the session, and [`GameArea`], which keeps the game clear
//! of the controls in portrait.
//!
//! Each finger is tracked on its own, so a direction can be held with
//! B (AW2's fast cursor) or L/R. A finger can slide from one button to
//! another. The first finger down reaches the app as the mouse (see
//! ios/touch_mouse.rs), any other as a touch; both drive the pad.

use iced::advanced::layout;
use iced::advanced::renderer;
use iced::advanced::text::Renderer as _;
use iced::advanced::widget::{tree, Operation, Tree};
use iced::advanced::{Clipboard, Layout, Renderer as _, Shell, Widget};
use iced::{mouse, touch, Color, Element, Event, Length, Point, Rectangle, Size, Vector};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use tango_session::keys;

/// Whether the game is being stretched over the whole area right now
/// (landscape with "Stretch" on). Set when [`GameArea`] lays out, just
/// before the frame does, so the frame's own fit can follow it.
static STRETCHED: AtomicBool = AtomicBool::new(false);

pub fn stretched() -> bool {
    STRETCHED.load(Ordering::Relaxed)
}

/// The safe-area insets (top, left, bottom, right) in logical points the
/// app is padded by, kept here so the game and controls can reach past the
/// padding in landscape. Set by `view_in_safe_area` each frame.
static INSETS: [std::sync::atomic::AtomicU32; 4] = [const { std::sync::atomic::AtomicU32::new(0) }; 4];

pub fn set_insets(insets: [f32; 4]) {
    if insets != self::insets() {
        log::info!("safe area insets (top, left, bottom, right): {insets:?}");
    }
    for (a, v) in INSETS.iter().zip(insets) {
        a.store(v.to_bits(), Ordering::Relaxed);
    }
}

fn insets() -> [f32; 4] {
    [0, 1, 2, 3].map(|i| f32::from_bits(INSETS[i].load(Ordering::Relaxed)))
}

#[derive(Clone, Copy, PartialEq)]
enum Shape {
    Round,
    Pill,
    Cross,
}

struct Control {
    /// Key bits this control presses (the D-pad's depend on the finger).
    bits: u32,
    label: &'static str,
    rect: Rectangle,
    shape: Shape,
}

/// Where the game and each control go in a `size` area (logical points).
pub struct Placement {
    /// The game's area; the frame centers in it.
    pub game: Rectangle,
    /// Where the picture ends up in landscape (3:2 and centered, or all
    /// of `game` when stretched); controls over it are drawn fainter.
    picture: Option<Rectangle>,
    /// Stretching the game over `game`, aspect ignored.
    pub stretch: bool,
    /// The whole screen in landscape (the padded area plus the safe-area
    /// insets), and where its top-left corner is relative to the padded
    /// area's. Everything in this placement is in the whole screen's
    /// coordinates. In portrait: the area itself, at the origin.
    pub full: Size,
    pub origin: Point,
    controls: Vec<Control>,
}

const DPAD: u32 = keys::UP | keys::DOWN | keys::LEFT | keys::RIGHT;

pub fn place(size: Size, stretch: bool) -> Placement {
    let (w, h) = (size.width, size.height);
    let portrait = h > w * 1.1;
    let pad = 12.0;
    let mut controls = Vec::new();
    let game;
    let mut picture = None;
    let mut full = size;
    let mut origin = Point::ORIGIN;
    let mut shift = Vector::new(0.0, 0.0);
    // Button diameter.
    let u;
    // Vertical center of the D-pad and face buttons, and the bottom row.
    let (cy, bottom);
    if portrait {
        // The game across the top, controls in the space below.
        let gh = (w / 1.5).min(h * 0.55);
        game = Rectangle::new(Point::ORIGIN, Size::new(w, gh));
        let region_h = h - gh;
        u = (w * 0.17).min(region_h * 0.2).clamp(44.0, 96.0);
        let shoulder_y = gh + pad;
        controls.push(Control {
            bits: keys::L,
            label: "L",
            rect: Rectangle::new(Point::new(pad, shoulder_y), Size::new(1.8 * u, 0.7 * u)),
            shape: Shape::Pill,
        });
        controls.push(Control {
            bits: keys::R,
            label: "R",
            rect: Rectangle::new(Point::new(w - pad - 1.8 * u, shoulder_y), Size::new(1.8 * u, 0.7 * u)),
            shape: Shape::Pill,
        });
        bottom = h - pad - 0.55 * u;
        let top = shoulder_y + 0.7 * u + pad;
        cy = (top + bottom - pad) / 2.0;
    } else {
        // Fit: the picture as large as fits between the controls' columns
        // (full screen height at most, under the home indicator); Stretch:
        // the whole screen. The controls stay inside the safe area.
        u = (h * 0.11).clamp(40.0, 52.0);
        // A tall landscape area is an iPad window: its title-bar buttons sit
        // in the top-left corner, so the shoulder buttons start below them.
        let top = if h > 600.0 { pad + 28.0 } else { pad };
        let d = 2.6 * u;
        let [it, il, ib, ir] = insets();
        let (fw, fh) = (w + il + ir, h + it + ib);
        full = Size::new(fw, fh);
        origin = Point::new(-il, -it);
        shift = Vector::new(il, it);
        let margin = il.max(ir) + pad + d + 8.0;
        let pw = (fw - 2.0 * margin).min(fh * 1.5).max(0.0);
        let fit = Rectangle::new(Point::new((fw - pw) / 2.0, (fh - pw / 1.5) / 2.0), Size::new(pw, pw / 1.5));
        let whole = Rectangle::new(Point::ORIGIN, full);
        game = if stretch { whole } else { fit };
        picture = Some(game);
        controls.push(Control {
            bits: keys::L,
            label: "L",
            rect: Rectangle::new(Point::new(pad, top), Size::new(1.8 * u, 0.7 * u)),
            shape: Shape::Pill,
        });
        controls.push(Control {
            bits: keys::R,
            label: "R",
            rect: Rectangle::new(Point::new(w - pad - 1.8 * u, top), Size::new(1.8 * u, 0.7 * u)),
            shape: Shape::Pill,
        });
        bottom = h - pad - 0.55 * u;
        cy = h * 0.55;
    }
    let d = 2.6 * u;
    controls.push(Control {
        bits: DPAD,
        label: "",
        rect: Rectangle::new(Point::new(pad, cy - d / 2.0), Size::new(d, d)),
        shape: Shape::Cross,
    });
    // A up and right of B, as on the console.
    controls.push(Control {
        bits: keys::A,
        label: "A",
        rect: Rectangle::new(Point::new(w - pad - u, cy - 0.95 * u), Size::new(u, u)),
        shape: Shape::Round,
    });
    controls.push(Control {
        bits: keys::B,
        label: "B",
        rect: Rectangle::new(Point::new(w - pad - 2.15 * u, cy - 0.05 * u), Size::new(u, u)),
        shape: Shape::Round,
    });
    let pill = Size::new(1.5 * u, 0.55 * u);
    let (select_x, start_x) = if portrait {
        (w / 2.0 - pill.width - pad / 2.0, w / 2.0 + pad / 2.0)
    } else {
        (pad + d / 2.0 - pill.width / 2.0, w - pad - 1.6 * u - pill.width / 2.0)
    };
    controls.push(Control {
        bits: keys::SELECT,
        label: "SELECT",
        rect: Rectangle::new(Point::new(select_x, bottom), pill),
        shape: Shape::Pill,
    });
    controls.push(Control {
        bits: keys::START,
        label: "START",
        rect: Rectangle::new(Point::new(start_x, bottom), pill),
        shape: Shape::Pill,
    });
    for c in &mut controls {
        c.rect = c.rect + shift;
    }
    Placement {
        game,
        picture,
        stretch: stretch && !portrait,
        full,
        origin,
        controls,
    }
}

/// Grow a hit box so a near miss still lands.
fn hit_box(r: Rectangle) -> Rectangle {
    let m = r.width.min(r.height) * 0.2;
    Rectangle::new(
        Point::new(r.x - m, r.y - m),
        Size::new(r.width + 2.0 * m, r.height + 2.0 * m),
    )
}

/// The bits a finger at `p` (relative to the area) presses.
fn bits_at(placement: &Placement, p: Point) -> u32 {
    let mut bits = 0;
    for c in &placement.controls {
        if !hit_box(c.rect).contains(p) {
            continue;
        }
        if c.bits == DPAD {
            let center = c.rect.center();
            let (dx, dy) = (p.x - center.x, p.y - center.y);
            if dx.hypot(dy) < c.rect.width * 0.1 {
                continue;
            }
            // Four-way: the dominant axis only, so the map cursor never
            // wanders off diagonally.
            bits |= if dx.abs() > dy.abs() {
                if dx > 0.0 {
                    keys::RIGHT
                } else {
                    keys::LEFT
                }
            } else if dy > 0.0 {
                keys::DOWN
            } else {
                keys::UP
            };
        } else {
            bits |= c.bits;
        }
    }
    bits
}

/// The mouse stands in for the first finger.
const MOUSE: u64 = u64::MAX;

#[derive(Default)]
struct State {
    fingers: HashMap<u64, Point>,
    bits: u32,
}

pub struct TouchPad<'a, Message> {
    stretch: bool,
    on_change: Box<dyn Fn(u32) -> Message + 'a>,
}

impl<'a, Message> TouchPad<'a, Message> {
    pub fn new(stretch: bool, on_change: impl Fn(u32) -> Message + 'a) -> Self {
        Self {
            stretch,
            on_change: Box::new(on_change),
        }
    }
}

impl<Message> Widget<Message, iced::Theme, iced::Renderer> for TouchPad<'_, Message> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<State>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(State::default())
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Fill, Length::Fill)
    }

    fn layout(&mut self, _tree: &mut Tree, _renderer: &iced::Renderer, limits: &layout::Limits) -> layout::Node {
        // The node is the padded area; its child the whole screen the
        // controls are placed on (see `Placement::full`).
        let size = limits.max();
        let p = place(size, self.stretch);
        layout::Node::with_children(size, vec![layout::Node::new(p.full).move_to(p.origin)])
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &iced::Renderer,
        _clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_mut::<State>();
        let bounds = layout.children().next().unwrap().bounds();
        // Stepped aside for a controller or keyboard: any touch brings
        // the controls back (and does nothing else).
        if super::touch_controls_hidden() {
            if !state.fingers.is_empty() || state.bits != 0 {
                state.fingers.clear();
                state.bits = 0;
                shell.publish((self.on_change)(0));
            }
            if matches!(
                event,
                Event::Mouse(mouse::Event::ButtonPressed(_)) | Event::Touch(touch::Event::FingerPressed { .. })
            ) && cursor.is_over(bounds)
            {
                super::show_touch_controls();
                shell.request_redraw();
            }
            return;
        }
        let placement = place(layout.bounds().size(), self.stretch);
        let local = |p: Point| Point::new(p.x - bounds.x, p.y - bounds.y);
        let on_control = |p: Point| bits_at(&placement, local(p)) != 0;

        let mut owned = false;
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                if let Some(p) = cursor.position() {
                    if on_control(p) {
                        state.fingers.insert(MOUSE, p);
                        owned = true;
                    }
                }
            }
            Event::Mouse(mouse::Event::CursorMoved { position }) => {
                if let Some(f) = state.fingers.get_mut(&MOUSE) {
                    *f = *position;
                    owned = true;
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left))
            | Event::Mouse(mouse::Event::CursorLeft) => {
                owned = state.fingers.remove(&MOUSE).is_some();
            }
            Event::Touch(touch::Event::FingerPressed { id, position }) => {
                if on_control(*position) {
                    state.fingers.insert(id.0, *position);
                    owned = true;
                }
            }
            Event::Touch(touch::Event::FingerMoved { id, position }) => {
                if let Some(f) = state.fingers.get_mut(&id.0) {
                    *f = *position;
                    owned = true;
                }
            }
            Event::Touch(touch::Event::FingerLifted { id, .. } | touch::Event::FingerLost { id, .. }) => {
                owned = state.fingers.remove(&id.0).is_some();
            }
            _ => {}
        }
        if !owned {
            return;
        }
        shell.capture_event();
        let bits = state
            .fingers
            .values()
            .fold(0, |acc, p| acc | bits_at(&placement, local(*p)));
        if bits != state.bits {
            state.bits = bits;
            shell.publish((self.on_change)(bits));
            shell.request_redraw();
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
        _renderer: &iced::Renderer,
    ) -> mouse::Interaction {
        // A drag target, so a finger sliding across the pad stays a
        // press instead of turning into a scroll (ios/touch_mouse.rs).
        if super::touch_controls_hidden() {
            return mouse::Interaction::None;
        }
        let state = tree.state.downcast_ref::<State>();
        if state.fingers.contains_key(&MOUSE) {
            return mouse::Interaction::Grabbing;
        }
        let bounds = layout.children().next().unwrap().bounds();
        match cursor.position() {
            Some(p) if bits_at(&place(layout.bounds().size(), self.stretch), Point::new(p.x - bounds.x, p.y - bounds.y)) != 0 => {
                mouse::Interaction::Grab
            }
            _ => mouse::Interaction::None,
        }
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut iced::Renderer,
        _theme: &iced::Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        _viewport: &Rectangle,
    ) {
        if super::touch_controls_hidden() {
            return;
        }
        let state = tree.state.downcast_ref::<State>();
        let bounds = layout.children().next().unwrap().bounds();
        // A layer of its own: the game frame is a shader primitive, which
        // iced draws after the quads of its layer — over the controls.
        renderer.with_layer(bounds, |renderer| {
            draw_controls(state, renderer, bounds, place(layout.bounds().size(), self.stretch))
        });
    }
}

fn draw_controls(state: &State, renderer: &mut iced::Renderer, bounds: Rectangle, placement: Placement) {
    {
        // Over the picture a control gets a dark backing (readable on bright
        // plains and on dark sea alike), a stronger outline and full white
        // label; beside it, the plain translucent look.
        let over = std::cell::Cell::new(false);
        let fill = |held: bool| match (over.get(), held) {
            (true, true) => Color::from_rgba(1.0, 1.0, 1.0, 0.6),
            (true, false) => Color::TRANSPARENT,
            (false, true) => Color::from_rgba(1.0, 1.0, 1.0, 0.45),
            (false, false) => Color::from_rgba(1.0, 1.0, 1.0, 0.16),
        };
        let edge = || Color::from_rgba(1.0, 1.0, 1.0, if over.get() { 0.95 } else { 0.5 });
        let label_color = |held: bool| match (over.get(), held) {
            (true, true) => Color::from_rgba(0.0, 0.0, 0.0, 0.9),
            (true, false) => Color::WHITE,
            _ => Color::from_rgba(1.0, 1.0, 1.0, 0.85),
        };
        let quad = |renderer: &mut iced::Renderer, r: Rectangle, radius: f32, held: bool| {
            if over.get() {
                renderer.fill_quad(
                    renderer::Quad {
                        bounds: r,
                        border: iced::Border {
                            radius: radius.into(),
                            ..Default::default()
                        },
                        ..renderer::Quad::default()
                    },
                    Color::from_rgba(0.0, 0.0, 0.0, 0.5),
                );
            }
            renderer.fill_quad(
                renderer::Quad {
                    bounds: r,
                    border: iced::Border {
                        color: edge(),
                        width: if over.get() { 2.0 } else { 1.5 },
                        radius: radius.into(),
                    },
                    ..renderer::Quad::default()
                },
                fill(held),
            );
        };
        // Centered in `r`.
        let label = |renderer: &mut iced::Renderer, text: &str, r: Rectangle, size: f32, font: iced::Font, held: bool| {
            renderer.fill_text(
                iced::advanced::Text {
                    content: text.to_string(),
                    bounds: r.size(),
                    size: iced::Pixels(size),
                    line_height: iced::widget::text::LineHeight::default(),
                    font,
                    align_x: iced::advanced::text::Alignment::Center,
                    align_y: iced::alignment::Vertical::Center,
                    shaping: iced::advanced::text::Shaping::Advanced,
                    wrapping: iced::advanced::text::Wrapping::None,
                },
                r.center(),
                label_color(held),
                bounds,
            );
        };
        let bold = iced::Font {
            weight: iced::font::Weight::Bold,
            ..crate::ui::style::DEFAULT_FONT
        };
        let icons = iced::Font::with_name("lucide");
        for c in &placement.controls {
            let is_over = placement.picture.is_some_and(|p| p.intersects(&c.rect));
            over.set(is_over);
            let r = c.rect + Vector::new(bounds.x, bounds.y);
            let held = state.bits & c.bits != 0;
            match c.shape {
                Shape::Round => {
                    quad(renderer, r, r.width / 2.0, held);
                    label(renderer, c.label, r, r.height * 0.42, bold, held);
                }
                Shape::Pill => {
                    quad(renderer, r, r.height / 2.0, held);
                    let size = r.height * if c.label.len() > 1 { 0.34 } else { 0.5 };
                    label(renderer, c.label, r, size, bold, held);
                }
                Shape::Cross => {
                    // A plus sign of three-by-three cells; each arm lights
                    // with its direction.
                    let cell = r.width / 3.0;
                    let arm = |dx: f32, dy: f32| {
                        Rectangle::new(Point::new(r.x + dx * cell, r.y + dy * cell), Size::new(cell, cell))
                    };
                    let radius = cell * 0.25;
                    quad(renderer, arm(1.0, 1.0), 0.0, false);
                    use lucide_icons::Icon;
                    for (bit, dx, dy, icon) in [
                        (keys::UP, 1.0, 0.0, Icon::ChevronUp),
                        (keys::DOWN, 1.0, 2.0, Icon::ChevronDown),
                        (keys::LEFT, 0.0, 1.0, Icon::ChevronLeft),
                        (keys::RIGHT, 2.0, 1.0, Icon::ChevronRight),
                    ] {
                        let a = arm(dx, dy);
                        quad(renderer, a, radius, state.bits & bit != 0);
                        label(renderer, &char::from(icon).to_string(), a, cell * 0.5, icons, state.bits & bit != 0);
                    }
                }
            }
        }
    }
}

impl<'a, Message: 'a> From<TouchPad<'a, Message>> for Element<'a, Message> {
    fn from(w: TouchPad<'a, Message>) -> Self {
        Element::new(w)
    }
}

/// Lays its content out in [`Placement::game`] of its own area: the
/// game sits above the controls in portrait.
pub struct GameArea<'a, Message> {
    stretch: bool,
    content: Element<'a, Message>,
}

impl<'a, Message> GameArea<'a, Message> {
    pub fn new(content: impl Into<Element<'a, Message>>, stretch: bool) -> Self {
        Self {
            stretch,
            content: content.into(),
        }
    }
}

impl<Message> Widget<Message, iced::Theme, iced::Renderer> for GameArea<'_, Message> {
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Fill, Length::Fill)
    }

    fn layout(&mut self, tree: &mut Tree, renderer: &iced::Renderer, limits: &layout::Limits) -> layout::Node {
        let size = limits.max();
        let placement = place(size, self.stretch);
        STRETCHED.store(placement.stretch, Ordering::Relaxed);
        let game = placement.game;
        let child = self.content.as_widget_mut().layout(
            &mut tree.children[0],
            renderer,
            &layout::Limits::new(Size::ZERO, game.size()),
        );
        layout::Node::with_children(
            size,
            vec![child.move_to(Point::new(game.x + placement.origin.x, game.y + placement.origin.y))],
        )
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &iced::Renderer,
        operation: &mut dyn Operation,
    ) {
        self.content.as_widget_mut().operate(
            &mut tree.children[0],
            layout.children().next().unwrap(),
            renderer,
            operation,
        );
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &iced::Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout.children().next().unwrap(),
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &iced::Renderer,
    ) -> mouse::Interaction {
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout.children().next().unwrap(),
            cursor,
            viewport,
            renderer,
        )
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut iced::Renderer,
        theme: &iced::Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout.children().next().unwrap(),
            cursor,
            viewport,
        );
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &iced::Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<iced::advanced::overlay::Element<'b, Message, iced::Theme, iced::Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout.children().next().unwrap(),
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Message: 'a> From<GameArea<'a, Message>> for Element<'a, Message> {
    fn from(w: GameArea<'a, Message>) -> Self {
        Element::new(w)
    }
}
