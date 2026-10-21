//! Central message dispatch and screen transition bookkeeping.

use super::{App, EnterScope, Message, ScreenKey, PANE_SLIDE, ROOT_SLIDE};
use crate::tabs;

impl App {
    pub fn update(&mut self, message: Message) -> iced::Task<Message> {
        let screen_before = self.screen_key();
        let family_before = self.loadout.family();
        let task = self.update_inner(message);
        let now = iced::time::Instant::now();
        let screen_after = self.screen_key();
        if screen_before != screen_after {
            self.screen_enter.start(now);
            self.screen_enter_scope = match (screen_before, screen_after) {
                (ScreenKey::Tabs(t1), ScreenKey::Tabs(t2)) => {
                    // The nav strip lays the tabs out in declaration
                    // order, so the discriminants double as nav
                    // positions: moving right brings the new pane in
                    // from the right, moving left from the left.
                    let dx = if (t2 as u8) > (t1 as u8) {
                        PANE_SLIDE
                    } else {
                        -PANE_SLIDE
                    };
                    EnterScope::Body { dx }
                }
                // Closing a session descends — the menu comes back
                // in from above, mirroring the rise that brought
                // the session up.
                (ScreenKey::Session, _) => EnterScope::Root { dy: -ROOT_SLIDE },
                _ => EnterScope::Root { dy: ROOT_SLIDE },
            };
        }
        // A different family swaps the entire bottom of the tab —
        // rise the whole save-view pane in. A different game or save
        // within the family only re-renders the save's content, and
        // that entrance rides in with the reloaded save itself: its
        // view state is minted by the load and starts its own rise.
        if family_before != self.loadout.family() {
            self.play.animate_family_switch(now);
        }
        task
    }

    fn update_inner(&mut self, message: Message) -> iced::Task<Message> {
        match message {
            Message::NoOp => iced::Task::none(),
            Message::AnimTick => iced::Task::none(),
            Message::Quit => self.quit(),
            Message::Exit => iced::exit(),
            Message::TabSelected(t) => {
                self.tab = t;
                // A tab switch unmounts the input settings pane's capture
                // wrapper, so key/button releases stop arriving — drop the
                // held set rather than show stale-lit binding chips on the
                // way back.
                self.settings.held = Default::default();
                // Clicking a scanner-backed tab re-runs the scan in the
                // background — there are no Rescan buttons; this is how
                // new files on disk get noticed. Cheap when nothing
                // changed (stat-fingerprint gated, see Catalog::rescan).
                // Deliberately not limited to *entering* the tab: pressing
                // the tab you are already on is what a user reaches for
                // when they have just dropped a file in, and it is the
                // only gesture left that means "look again".
                // Play additionally throws away the loaded bundle after
                // the scan, even when the selected paths did not change:
                // the click is an explicit reload from disk, including
                // discarding staged edits and rebuilding ROM assets.
                // Settings doesn't read the scanners, so skip it there.
                if !self.is_rescanning() {
                    if let Some(followup) = t.rescan_followup() {
                        return self.rescan_off_thread(followup);
                    }
                }
                iced::Task::none()
            }
            // Loadout strip interactions route to the shared
            // App-level Loadout — the tab never sees them.
            // Every dispatch below is followed by a Settings resend —
            // the netplay handler dedupes against the last-sent value
            // via `Settings: Eq`, so unchanged dispatches are free.
            Message::Play(tabs::play::Message::Loadout(m)) => {
                let task = self.update_loadout(m);
                iced::Task::batch([task, self.resend_settings_if_lobby()])
            }
            Message::Play(m) => {
                let task = self.update_play(m);
                iced::Task::batch([task, self.resend_settings_if_lobby()])
            }
            Message::DiscordTick => {
                self.handle_discord_tick();
                match self.debug.due_shot() {
                    Some((path, exit)) => iced::window::latest()
                        .and_then(iced::window::screenshot)
                        .map(move |s| Message::DebugScreenshot(s, path.clone(), exit)),
                    None => iced::Task::none(),
                }
            }
            Message::RunShotTick => match self.debug.due_shot() {
                Some((path, exit)) => iced::window::latest()
                    .and_then(iced::window::screenshot)
                    .map(move |s| Message::DebugScreenshot(s, path.clone(), exit)),
                None => iced::Task::none(),
            },
            Message::ReportMark => {
                // A problem report: the moment marked in the session's log, the window's picture saved beside it.
                let stamp = chrono::Local::now().format("%Y%m%d-%H%M%S").to_string();
                let path = self.config.logs_path().join(format!("report-{stamp}.png"));
                log::warn!(
                    "=== REPORT (F8) {stamp}: the player marked this moment; screenshot {} ===",
                    path.display()
                );
                iced::window::latest()
                    .and_then(iced::window::screenshot)
                    .map(move |s| Message::DebugScreenshot(s, path.clone(), false))
            }
            Message::DebugScreenshot(shot, path, exit) => {
                super::debug_aids::save_png(&shot, &path);
                if exit {
                    return iced::exit();
                }
                iced::Task::none()
            }
            Message::AiDebugTick => self.ai_debug_tick(),
            Message::PadScriptTick => {
                let seq = self.session.is_active().then(|| self.session.install_seq());
                let solo = self
                    .session
                    .active_as::<crate::session::singleplayer::SinglePlayerSession>();
                let mut cond = |c: &str| {
                    let mut read = |a: u32, b: &mut [u8]| {
                        if let Some(solo) = solo {
                            solo.peek(a, b);
                        }
                    };
                    tango_library::online::condition(&mut read, c)
                };
                if let Some(keys) = self.debug.pad_keys(seq, &mut cond) {
                    self.session.set_scripted_keys(keys);
                }
                if let (Some(text), Some(solo)) = (self.debug.take_script_typed(), solo) {
                    let mut read = |a: u32, b: &mut [u8]| {
                        solo.peek(a, b);
                    };
                    let mut write = |a: u32, b: &[u8]| {
                        solo.poke(a, b);
                    };
                    tango_library::online::type_chars(&mut read, &mut write, text.as_bytes());
                }
                match self.debug.take_script_shot() {
                    Some(path) => iced::window::latest()
                        .and_then(iced::window::screenshot)
                        .map(move |s| Message::DebugScreenshot(s, path.clone(), false)),
                    None => iced::Task::none(),
                }
            }
            Message::Window(id, ev) => self.update_window(id, ev),
            Message::WindowScaleQueried { id, scale } => {
                // Cap how big the window can get dragged. A surface is
                // the window size in *physical* pixels, so on a wide
                // enough desktop a drag-resize can walk it past what
                // the GPU will configure — and that isn't an error the
                // app gets to handle, it's a panic from inside wgpu.
                // iced converts this cap back to physical with the
                // same `scale × ui_scale` it reports sizes with, so
                // what winit ends up enforcing is exactly
                // `MAX_SURFACE_SIZE` physical pixels — which stays the
                // right cap even if either scale changes later.
                let (min_w, min_h) = crate::window::MINIMUM_RESOLUTION;
                let scale = (scale * self.config.ui_scale).max(0.01);
                let cap = crate::MAX_SURFACE_SIZE / scale;
                let max = iced::Size::new(cap.max(min_w as f32), cap.max(min_h as f32));
                iced::window::set_max_size(id, Some(max))
            }
            Message::WindowMaximizedQueried { size, maximized } => {
                if !maximized {
                    self.config.last_window_size = Some((size.width, size.height));
                }
                self.config.last_window_maximized = maximized;
                self.persist_config();
                iced::Task::none()
            }
            Message::Replays(m) => self.update_replays(m),
            Message::Settings(m) => self.update_settings(m),
            Message::Welcome(m) => self.update_welcome(m),
            Message::Session(m) => self.update_session(m),
            Message::Netplay(delivery) => self.update_netplay(delivery),
            Message::PvpSessionBuilt(ticket, slot) => {
                let Some(result) = slot.lock().unwrap().take() else {
                    return iced::Task::none();
                };
                self.finish_pvp_handoff(ticket, result)
            }
            Message::RoomMatchBuilt(slot) => {
                let Some(result) = slot.lock().unwrap().take() else {
                    return iced::Task::none();
                };
                self.finish_room_match(result)
            }
            Message::Rescanned(followup) => self.finish_rescan(followup),
        }
    }
}
