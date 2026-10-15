//! The Play tab: everything in one place. The full loadout selector
//! (family / save / patch pickers + save management, the latter in
//! [`save_manage`]) and the save viewer/editor fill the body, and a
//! netplay band rides the bottom —
//! the link-code strip + Fight CTA when idle, the full lobby
//! ([`lobby`]) once a connection attempt is in flight. The save view
//! stays on screen through it all, so what you're bringing to the
//! match is always visible (and switchable) even mid-lobby. The
//! selection state itself is App-level ([`Selection`])
//! so the lobby settings-resend sees every change made here live.

pub mod loadout_strip;
mod save_manage;

pub use save_manage::SaveAction;

use crate::i18n::t;
use crate::library::Catalog;
use crate::library::{game, rom};
use crate::ui::style::{self, STANDARD_PADDING, TEXT_BODY, TEXT_CAPTION, TEXT_TITLE};
use crate::ui::widgets;
use crate::{config, selection};
use iced::widget::{button, container, text, Space};
use iced::{Alignment, Element, Fill, Length};
use lucide_icons::Icon;
use sweeten::widget::{column, row, text_input};
use tango_library::loadout::Selection;
use unic_langid::LanguageIdentifier;

// ---------- Messages ----------

#[derive(Debug, Clone)]
pub enum Message {
    /// Loadout strip interaction. Routed by the App to the shared
    /// [`Selection`] — never reaches [`State::update`].
    Loadout(loadout_strip::Message),
    SaveEditor(std::sync::Arc<dyn tango_gamesupport::SaveEditorMessage>),

    LinkCodeChanged(String),
    FightPressed,
    /// Bottom strip: start the selected game on its own, with no link
    /// code, server or network.
    PlayOfflinePressed,
    /// In-game lobby READY (via `app/online.rs`): App loads the local
    /// save's raw SRAM, builds a NegotiatedState, and
    /// commits the local save.
    Ready,
    /// In-game lobby NOT READY (via `app/online.rs`). Sends an Uncommit packet.
    Unready,
    /// Soft-disable sentinel: the selector strip reroutes its
    /// controls here during handoff so they render inert without
    /// touching layout. The update handler drops it.
    Noop,

    SaveOpenFolder,
    /// Open an arbitrary folder in the OS file manager. Used by
    /// the no-saves / no-roms empty-state cards to give the user
    /// a one-click jump into the right directory.
    OpenSavesFolder(std::path::PathBuf),
    SaveDuplicateStart,
    SaveDuplicateDraftChanged(String),
    SaveDuplicateConfirm,
    SaveRenameStart,
    SaveRenameDraftChanged(String),
    SaveRenameConfirm,
    SaveDeleteStart,
    SaveDeleteConfirm,
    SaveActionCancel,
    SaveNewStart,
    SaveNewDraftChanged(String),
    /// (target variant, template name) — a template option fixes both,
    /// since the family's variants each ship their own templates.
    SaveNewTemplateSelected(rom::GameRef, String),
    SaveNewConfirm,
}

// ---------- Play tab state ----------

pub struct State {
    link_code: String,
    /// Inline state for the save-management actions (rename / delete).
    save_action: SaveAction,
    /// Entrance glide for the whole save-view pane under the selector
    /// strip, played by the App when the *family* changes — a family
    /// switch replaces the entire bottom of the tab. A save switch
    /// within the family plays the smaller entrance the save view
    /// itself owns instead, which only moves the panes under its
    /// sub-tab strip.
    save_body_enter: crate::ui::anim::Enter,
    /// Fade-through swap for the save-action row: the picker row
    /// morphs into whichever rename / delete / create form opens
    /// ([`State::save_action`]) and back.
    save_form: crate::ui::anim::Transition,
    /// The form that was open before `save_action` reset to
    /// `None`, frozen so the swap's exit half has something to
    /// render (the live form — including the rename draft — is
    /// already gone).
    save_action_exit: SaveAction,
}

impl Default for State {
    fn default() -> Self {
        Self {
            link_code: String::new(),
            save_action: SaveAction::None,
            save_body_enter: crate::ui::anim::Enter::default(),
            save_form: crate::ui::anim::Transition::swap(false),
            save_action_exit: SaveAction::None,
        }
    }
}

/// Side-effects bubble-up. Mirrors the [`crate::tabs::replays::Effect`]
/// convention: pure UI-state mutations happen inside
/// [`State::update`]; anything that requires App-level
/// collaborators (session host, file system, clipboard) comes back
/// as an `Effect` for the caller to interpret.
#[derive(Debug)]
pub enum Effect {
    /// Kick off netplay (autostart / Discord join). The `LinkIdent`
    /// variant tells the app handler whether to route via matchmaking
    /// signaling or direct TCP transport.
    Connect { ident: crate::netplay::LinkIdent },
    /// In-game NOT READY — drop our commitment and tell the peer.
    Unready,
    /// In-game READY — App reads the local save SRAM and commits it.
    ReadyWithSave,
    /// `open::that(_)` on a file or folder.
    OpenPath(std::path::PathBuf),
    /// Reveal in the OS file manager with the file selected.
    RevealPath(std::path::PathBuf),
    /// Copy plain text to the clipboard.
    CopyText(String),
    /// Copy HTML to the clipboard with a plain-text alternative.
    CopyHtml { text: String, html: String },
    /// Copy a raster image to the clipboard.
    CopyImage(image::RgbaImage),
    /// User pressed Play → start a single-player session from the
    /// current selection.
    StartSinglePlayer,
    /// User pressed Training → start a training session (single-player
    /// ride + do-nothing dummy controller) from the current selection.
    StartTraining,
    /// Duplicate the currently-selected save file as `new_stem` (no
    /// extension; the handler keeps the source's).
    SaveDuplicate { new_stem: String },
    /// Rename the currently-selected save to `new_stem` (no
    /// extension; rename_save adds `.sav`).
    SaveRename { new_stem: String },
    /// Delete the currently-selected save file.
    SaveDelete,
    /// Create a fresh save in the saves dir from a bundled
    /// template.
    SaveNew {
        name: String,
        template: String,
        /// The concrete variant to create the save for (a family can
        /// have several owned-ROM variants). The handler looks up this
        /// game's template and adopts it as the loadout's game.
        game: rom::GameRef,
    },
    /// Task returned from the save view's `ui.update`. Generic pipe
    /// so save_editor-internal side effects (e.g. the scroll-to-top
    /// snap on tab change) flow through without per-feature
    /// Effect variants.
    SaveEditorTask(iced::Task<Message>),
    /// Global save editor committed: the edit session already staged
    /// everything into the in-memory save and serialized it — write
    /// `sram` to the loaded save's path on disk.
    SaveEditCommit { sram: Vec<u8> },
    /// Global save editor: discard all staged edits, reloading the on-disk
    /// original.
    SaveEditCancel,
}

impl State {
    /// Apply a tab message. See [`crate::tabs::replays::Effect`]
    /// for the side-effect surface convention.
    pub fn update(
        &mut self,
        msg: Message,
        scanners: &Catalog,
        config: &config::Config,
        loaded: Option<&mut selection::LoadedSave>,
        loadout: &Selection,
    ) -> Option<Effect> {
        let action_before = self.save_action.clone();
        let effect = self.update_inner(msg, scanners, config, loaded, loadout);
        let now = iced::time::Instant::now();
        // Freeze the closing form (with its draft) for the
        // save-action swap's exit half to render.
        if self.save_action == SaveAction::None && action_before != SaveAction::None {
            self.save_action_exit = action_before;
        }
        self.save_form.set(self.save_action != SaveAction::None, now);
        effect
    }

    /// Prefill the link-code input from an external source — the CLI
    /// `Join <code>` argument or a Discord join secret.
    pub fn adopt_link_code(&mut self, code: String) {
        self.link_code = code;
    }

    /// Play the family-switch entrance: a family change replaces the
    /// entire bottom of the tab, so the whole save-view pane under the
    /// selector strip glides in.
    pub fn animate_family_switch(&mut self, now: iced::time::Instant) {
        self.save_body_enter.start(now);
    }

    fn update_inner(
        &mut self,
        msg: Message,
        scanners: &Catalog,
        config: &config::Config,
        loaded: Option<&mut selection::LoadedSave>,
        loadout: &Selection,
    ) -> Option<Effect> {
        match msg {
            // Routed to the shared Selection at App level before this
            // dispatch is reached.
            Message::Loadout(_) => None,
            Message::LinkCodeChanged(s) => {
                // Direct-TCP commands (/host, /connect) need slashes,
                // spaces, dots, colons, brackets — pass them through.
                // Link codes are lowercased as typed: matchmaking is
                // case-sensitive, so this keeps a code read aloud or
                // retyped from a screenshot from missing its lobby.
                let filtered: String = if s.starts_with('/') {
                    s
                } else {
                    s.chars()
                        .filter(|c| c.is_ascii_alphanumeric() || *c == '-')
                        .map(|c| c.to_ascii_lowercase())
                        .collect()
                };
                self.link_code = filtered.chars().take(100).collect();
                None
            }
            Message::PlayOfflinePressed => Some(Effect::StartSinglePlayer),
            Message::FightPressed => {
                let ident = crate::netplay::LinkIdent::parse(self.link_code.trim())?;
                Some(Effect::Connect { ident })
            }
            Message::Noop => None,
            Message::Ready => Some(Effect::ReadyWithSave),
            Message::Unready => Some(Effect::Unready),
            Message::SaveEditor(msg) => {
                // `ui.update` folds the message into save-view state —
                // staging edits straight into the loaded data — and
                // hands back what's left for the App: clipboard copies,
                // launches, the committed SRAM. Everything else flows
                // through as a generic save-view-internal task.
                let data = loaded?;
                let (sv_task, outcome) = data.editor.update(&config.language, data, &*msg);
                match outcome {
                    Some(tango_gamesupport::SaveEditorEvent::CopyText(s)) => Some(Effect::CopyText(s)),
                    Some(tango_gamesupport::SaveEditorEvent::CopyHtml { text, html }) => {
                        Some(Effect::CopyHtml { text, html })
                    }
                    Some(tango_gamesupport::SaveEditorEvent::CopyImage(img)) => Some(Effect::CopyImage(img)),
                    Some(tango_gamesupport::SaveEditorEvent::Play) => Some(Effect::StartSinglePlayer),
                    Some(tango_gamesupport::SaveEditorEvent::Training) => Some(Effect::StartTraining),
                    Some(tango_gamesupport::SaveEditorEvent::Commit { sram }) => Some(Effect::SaveEditCommit { sram }),
                    Some(tango_gamesupport::SaveEditorEvent::Cancel) => Some(Effect::SaveEditCancel),
                    None => Some(Effect::SaveEditorTask(sv_task.map(Message::SaveEditor))),
                }
            }
            m @ (Message::SaveOpenFolder
            | Message::OpenSavesFolder(_)
            | Message::SaveDuplicateStart
            | Message::SaveDuplicateDraftChanged(_)
            | Message::SaveDuplicateConfirm
            | Message::SaveRenameStart
            | Message::SaveRenameDraftChanged(_)
            | Message::SaveRenameConfirm
            | Message::SaveDeleteStart
            | Message::SaveDeleteConfirm
            | Message::SaveActionCancel
            | Message::SaveNewStart
            | Message::SaveNewDraftChanged(_)
            | Message::SaveNewTemplateSelected(..)
            | Message::SaveNewConfirm) => self.update_save_manage(m, scanners, config, loadout),
        }
    }
}

impl State {
    pub fn view<'a>(
        &'a self,
        lang: &'a LanguageIdentifier,
        scanners: &'a Catalog,
        loadout: &'a Selection,
        loaded: Option<&'a selection::LoadedSave>,
        streamer_mode: bool,
        config: &'a config::Config,
        // The startup scan hasn't landed yet, so empty scanners mean
        // "not read yet" rather than "nothing installed".
        scanning: bool,
        netplay_phase: &'a crate::netplay::Phase,
        handoff_pending: bool,
    ) -> Element<'a, Message> {
        let now = iced::time::Instant::now();
        let mut save_body = self.body(
            lang,
            scanners,
            loadout,
            loaded,
            streamer_mode,
            config,
            scanning,
            netplay_phase,
        );
        // A family switch replaces the entire bottom of the tab, so
        // the whole pane glides in (the App starts `save_body_enter`
        // when `loadout.family()` flips); save switches within the
        // family animate inside the save view instead.
        if let Some(p) = self.save_body_enter.progress(now) {
            save_body = crate::ui::anim::slide_in(save_body, p, iced::Vector::new(0.0, 20.0));
        }

        // Selector strip + save-view body live inside a single
        // PANE_GAP-padded column so every pane in that area shares
        // the same inset from the window edges and gap from one
        // another. The hud_scanline_bottom + bottom band sit OUTSIDE
        // that padding so they remain edge-to-edge bottom bars.
        // The strip goes inert during the handoff window: the PvP
        // session is being built from the committed state and
        // selection changes would only confuse.
        //
        // It's absent entirely until the startup scan lands: there is
        // nothing to select from yet, so the pickers would offer empty
        // lists and then have the restored selection replace them under
        // the user. The scanning card holds the pane on its own.
        let mut inner = column![].spacing(style::PANE_GAP).padding(style::PANE_GAP).height(Fill);
        if !scanning {
            inner = inner.push(self.selector_strip(lang, scanners, loadout, config, handoff_pending));
        }
        let inner = inner.push(save_body);

        let mut col = column![].width(Fill).height(Fill);
        col = col.push(inner);
        // tangoAW2: the Dual Strike pack is an older version's and the
        // scan found no .nds to rebuild it from (it rebuilds on its own
        // when there is one): the old pack plays, short of what is new.
        if !scanning && tango_library::ds_pack_outdated() {
            col = col.push(
                container(
                    row![
                        Icon::Info.widget().size(14.0),
                        text(t!(lang, "ds-pack-outdated"))
                            .size(TEXT_CAPTION)
                            .style(widgets::muted_text_style),
                    ]
                    .spacing(8)
                    .align_y(Alignment::Center),
                )
                .width(Fill)
                .padding([6, 16]),
            );
        }
        // The bottom band is just the Play button. Online play (room,
        // lobby, READY) is the game's own ONLINE screens; the app
        // drives them from the mailbox and shows no match setup here.
        let bottom = self.bottom_strip(
            lang,
            streamer_mode,
            loadout.patch_ready(scanners),
            loadout.is_playable(),
        );
        col = col.push(column![widgets::hud_scanline_bottom(), bottom].width(Fill));
        col.into()
    }

    /// Picks between the save view, an empty-state hint, or a "pick a
    /// save" hint based on what the user has installed and selected.
    fn body<'a>(
        &'a self,
        lang: &'a LanguageIdentifier,
        scanners: &'a Catalog,
        loadout: &'a Selection,
        loaded: Option<&'a selection::LoadedSave>,
        streamer_mode: bool,
        config: &'a config::Config,
        scanning: bool,
        netplay_phase: &'a crate::netplay::Phase,
    ) -> Element<'a, Message> {
        // The startup scan is still running. Gated on the scan itself,
        // not on any one scanner being empty: the four phases publish as
        // they finish, so between ROMs landing and saves landing an
        // emptiness test reads as "you own games but no saves" — and
        // with the strip hidden there'd be nothing on screen to fix it
        // with. One state until the whole scan is in. Same card shape as
        // the empty states below, so landing on the real one doesn't
        // move anything.
        if scanning {
            return empty_state_card(
                t!(lang, "empty-scanning-title"),
                vec![t!(lang, "empty-scanning-body")],
                None,
            );
        }
        // No ROMs at all: explain where to put them.
        if scanners.roms.read().is_empty() {
            let roms_path = config.roms_path();
            return empty_state_card(
                t!(lang, "empty-no-roms-title"),
                vec![t!(lang, "empty-no-roms-body"), roms_path.display().to_string()],
                Some((t!(lang, "save-open-folder"), roms_path)),
            );
        }
        // Family selected but no save files anywhere in it.
        if let Some(family) = loadout.family() {
            let saves = scanners.saves.read();
            let has_saves =
                game::games_in_family(family).any(|g| saves.get(&g).map(|v| !v.is_empty()).unwrap_or(false));
            if !has_saves && loadout.save().is_none() {
                let saves_path = config.saves_path();
                return empty_state_card(
                    t!(lang, "empty-no-saves-title"),
                    vec![t!(lang, "empty-no-saves-body"), saves_path.display().to_string()],
                    Some((t!(lang, "save-open-folder"), saves_path)),
                );
            }
        }
        self.save_editor(
            lang,
            loaded,
            streamer_mode,
            netplay_phase,
            loadout.patch_ready(scanners),
        )
    }

    fn selector_strip<'a>(
        &'a self,
        lang: &'a LanguageIdentifier,
        scanners: &'a Catalog,
        loadout: &'a Selection,
        config: &'a config::Config,
        inert: bool,
    ) -> Element<'a, Message> {
        // Inert during the PvP handoff window — the loadout pickers
        // reroute to Noop so a mid-spawn selection change can't
        // contradict the committed state, without the strip changing
        // shape.
        let gate = move |m: loadout_strip::Message| if inert { Message::Noop } else { Message::Loadout(m) };
        let game_row: Element<'a, Message> = loadout_strip::game_row(loadout, lang, scanners).map(gate);
        let save_picker: Element<'a, Message> =
            Element::from(loadout_strip::save_picker(loadout, lang, scanners, config).width(Length::Fill)).map(gate);
        let save_row = self.save_action_row(lang, scanners, loadout, save_picker);

        container(column![game_row, save_row].spacing(6))
            .padding(style::PANE_PADDING)
            .width(Fill)
            .style(widgets::pane)
            .into()
    }

    fn save_editor<'a>(
        &'a self,
        lang: &'a LanguageIdentifier,
        loaded: Option<&'a selection::LoadedSave>,
        streamer_mode: bool,
        netplay_phase: &'a crate::netplay::Phase,
        patch_ready: bool,
    ) -> Element<'a, Message> {
        let playable = matches!(netplay_phase, crate::netplay::Phase::Idle) && patch_ready;
        let Some(loaded) = loaded else {
            return container(text(t!(lang, "play-no-selection")).size(TEXT_BODY))
                .center(Fill)
                .into();
        };
        // Play button is the singleplayer entry point — disabled
        // whenever a netplay attempt is anywhere in flight so it
        // can't fight with the lobby for the same save/emulator slot,
        // and while the selected patch isn't on disk, since the session
        // would otherwise boot the game unpatched.
        let play_button = Some(playable);
        loaded
            .editor
            .view(
                lang,
                loaded,
                streamer_mode,
                play_button,
                true,
                // The save editor is always available (no longer experimental).
                true,
            )
            .map(Message::SaveEditor)
    }

    /// The idle bottom band: link-code input + Fight CTA. The lobby
    /// band replaces this strip for every in-flight netplay phase, so
    /// this strip is pure "enter a link code and fight" —
    /// singleplayer lives in the save view's Play button. An empty
    /// input is fair game: Fight generates a random code on the spot
    /// (see the FightPressed handler) which never renders here on the
    /// way in — it debuts in the lobby's connection line and only
    /// lands in this input when the lobby band leaves. In streamer
    /// mode the input renders secure (masked) — typed, pasted, and
    /// restored-generated codes are all scrapeable off a stream
    /// otherwise.
    ///
    /// `patch_ready` is false while the selected patch isn't on disk:
    /// committing to a match then would negotiate a setup we can't
    /// actually run, so the CTA waits.
    fn bottom_strip<'a>(
        &'a self,
        lang: &'a LanguageIdentifier,
        _streamer_mode: bool,
        patch_ready: bool,
        playable: bool,
    ) -> Element<'a, Message> {
        const BOTTOM_SIZE: f32 = 15.0;
        const BOTTOM_CTA_PAD: [f32; 2] = [10.0, 22.0];
        // Offline: the same single-player session the save view's Play
        // button starts, offered here so it never depends on a save
        // editor or a connection.
        let offline_button: Element<'a, Message> = {
            let label = row![
                Icon::Gamepad2.widget().size(BOTTOM_SIZE),
                text(t!(lang, "play-offline")).size(BOTTOM_SIZE),
            ]
            .spacing(8)
            .align_y(Alignment::Center);
            // The main way in: the game, where ONLINE is.
            let mut btn = button(label)
                .padding(BOTTOM_CTA_PAD)
                .height(Length::Fixed(crate::ui::style::BAR_CONTROL_HEIGHT))
                .width(Length::Fill)
                .style(|theme: &iced::Theme, status| ready_button_style(theme, status));
            if playable && patch_ready {
                btn = btn.on_press(Message::PlayOfflinePressed);
            }
            iced::widget::tooltip(
                btn,
                text(t!(lang, "play-offline-tooltip")).size(TEXT_CAPTION),
                iced::widget::tooltip::Position::Top,
            )
            .into()
        };

        // (the link code and its Fight button have no place here: online play is in the game)
        let strip = row![offline_button];
        container(strip.spacing(10).align_y(Alignment::Center).padding([10, 8]))
            .width(Fill)
            .style(widgets::hud_bar)
            .into()
    }
}

// ---------- Save-action form helpers ----------

/// Centered card used for the no-roms / no-saves hints. Title is
/// rendered larger, body lines stack underneath in muted text.
/// When `folder` is provided, appends an "Open Folder" button —
/// usually the same path as the body's last line, so the user
/// can click straight through instead of copy-pasting it into
/// their file manager.
fn empty_state_card(
    title: String,
    body_lines: Vec<String>,
    open_folder: Option<(String, std::path::PathBuf)>,
) -> Element<'static, Message> {
    let mut col = column![
        // Lucide "info" glyph sized up so the card has a clear
        // visual anchor — without it the empty state was just a
        // floating title + paragraph, which read as a flash of
        // text rather than a deliberate placeholder.
        Icon::Info.widget().size(28.0),
        text(title).size(TEXT_TITLE),
    ]
    .spacing(10)
    .align_x(Alignment::Center);
    for line in body_lines {
        col = col.push(text(line).size(TEXT_CAPTION).style(widgets::muted_text_style));
    }
    if let Some((label, path)) = open_folder {
        col = col.push(Space::new().height(4)).push(widgets::labeled_icon_button(
            Icon::Folder,
            label,
            Message::OpenSavesFolder(path),
            STANDARD_PADDING,
            widgets::neutral,
        ));
    }
    container(container(col.padding(28).max_width(520)).style(widgets::panel))
        .padding(24)
        .center(Fill)
        .into()
}

// ---------- Commit-button styling (Fight + Ready) ----------

/// Style for the Play button: accent (primary) so it reads as the
/// call-to-action in the strip. Primary on steroids: brighter
/// gradient, huge primary glow, chunky 2 px border.
fn ready_button_style(theme: &iced::Theme, status: button::Status) -> button::Style {
    let primary = theme.palette().primary;
    if tango_ui::style::is_advance_wars(theme) {
        return widgets::aw_fight_button(status);
    }
    {
        // Disabled state defers to the standard neutral
        // button so it reads as a plainly-greyed-out button
        // — the dim-primary-fill version this used to
        // render looked like a corrupted variant of the
        // lit-up state rather than a disabled affordance.
        if matches!(status, button::Status::Disabled) {
            return crate::ui::widgets::neutral(theme, status);
        }
        // Inline expansion of the battle-button kernel with
        // every dial cranked: bigger glow, brighter top stop,
        // 2 px border so the button reads as a console
        // affordance rather than a CSS rectangle.
        let lighter = widgets::mix(primary, iced::Color::WHITE, 0.30);
        let darker = widgets::mix(primary, iced::Color::BLACK, 0.25);
        let (top, bottom, glow_alpha, offset_y, blur) = match status {
            button::Status::Hovered => (
                widgets::mix(lighter, iced::Color::WHITE, 0.18),
                widgets::mix(primary, iced::Color::WHITE, 0.05),
                0.95,
                8.0,
                28.0,
            ),
            button::Status::Pressed => (darker, widgets::mix(darker, iced::Color::BLACK, 0.12), 0.35, 2.0, 14.0),
            button::Status::Disabled => unreachable!("handled above"),
            button::Status::Active => (lighter, darker, 0.75, 6.0, 22.0),
        };
        button::Style {
            background: Some(iced::Background::Gradient(iced::Gradient::Linear(
                iced::gradient::Linear::new(0.0)
                    .add_stop(0.0, top)
                    .add_stop(1.0, bottom),
            ))),
            text_color: widgets::on_accent(primary),
            border: iced::Border {
                radius: widgets::tech_radius(10.0),
                width: 2.0,
                color: widgets::mix(primary, iced::Color::WHITE, 0.45),
            },
            shadow: iced::Shadow {
                color: iced::Color {
                    a: glow_alpha,
                    ..primary
                },
                offset: iced::Vector::new(0.0, offset_y),
                blur_radius: blur,
            },
            snap: false,
        }
    }
}
