use crate::i18n::{t, SUPPORTED_LANGS};
use crate::ui::style::{STANDARD_PADDING, TEXT_BODY, TEXT_CAPTION, TEXT_DISPLAY, TEXT_TITLE};
use crate::ui::widgets;
use iced::widget::{button, container, text, Space};
use iced::{Alignment, Element, Fill};
use lucide_icons::Icon;
use sweeten::widget::{column, row};
use unic_langid::LanguageIdentifier;

#[derive(Debug, Clone)]
pub enum Message {
    Continue,
    LanguageSelected(LanguageIdentifier),
    OpenRomsFolder,
    RescanRoms,
}

/// Welcome: drop the Advance Wars 2 ROM (required; Dual Strike's is
/// optional) in the data folder, then continue. Mirrors the legacy app's `gui/welcome.rs` layout —
/// language picker at top, step rows with status glyphs, gated
/// Continue button.
pub fn view<'a>(
    lang: &'a LanguageIdentifier,
    roms_count: usize,
    has_ds: bool,
    roms_path: &std::path::Path,
    rescanning: bool,
) -> Element<'a, Message> {
    let has_roms = roms_count > 0;

    // Language selector — lets the user switch first so the
    // rest of the welcome flow shows in the language they picked.
    // Same `LanguageChoice` wrapper the settings picker uses so the
    // dropdown shows each language's endonym (e.g. "日本語") rather
    // than its locale code.
    let lang_options: Vec<crate::i18n::LanguageChoice> = SUPPORTED_LANGS
        .iter()
        .map(|id| crate::i18n::LanguageChoice::new(id.clone()))
        .collect();
    let lang_selected = lang_options.iter().find(|c| &c.id == lang).cloned();
    let lang_picker = widgets::picker(lang_options, lang_selected, |c: crate::i18n::LanguageChoice| {
        Message::LanguageSelected(c.id)
    });

    // Step header: status glyph (check once done, refresh while
    // pending) + title. `label` is pre-resolved (t! at the call site).
    let step_header = |done: bool, label: String| {
        let icon = if done { Icon::Check } else { Icon::RefreshCw };
        row![icon.widget().size(16.0), text(label).size(TEXT_TITLE)]
            .spacing(8)
            .align_y(Alignment::Center)
    };

    // Step 1 — ROMs. On iOS the folder is the app's own in the Files
    // app (its path is a container's, meaningless to a player), and the
    // button imports through the Files picker.
    let ios = cfg!(target_os = "ios");
    let (description, folder, open_label) = if ios {
        (
            t!(lang, "welcome-step-roms-description-ios"),
            t!(lang, "welcome-roms-folder-ios"),
            t!(lang, "welcome-import-roms"),
        )
    } else {
        (
            t!(lang, "welcome-step-roms-description"),
            roms_path.display().to_string(),
            t!(lang, "welcome-open-folder"),
        )
    };
    let mut roms_block = column![
        step_header(has_roms, t!(lang, "welcome-step-roms")),
        text(description).size(TEXT_CAPTION).style(widgets::muted_text_style),
        text(folder).size(TEXT_CAPTION).font(iced::Font::MONOSPACE),
        row![
            widgets::labeled_icon_button(
                if ios { Icon::FileInput } else { Icon::Folder },
                open_label,
                Message::OpenRomsFolder,
                STANDARD_PADDING,
                widgets::neutral,
            ),
            widgets::labeled_icon_button_maybe(
                Icon::RefreshCw,
                t!(lang, "rescan"),
                (!rescanning).then_some(Message::RescanRoms),
                STANDARD_PADDING,
                widgets::neutral,
            ),
        ]
        .spacing(8),
    ]
    .spacing(6);
    if has_roms {
        let found = if has_ds {
            t!(lang, "welcome-roms-found-both")
        } else {
            t!(lang, "welcome-roms-found-aw2")
        };
        roms_block = roms_block.push(text(found).size(TEXT_CAPTION).style(widgets::success_text_style));
    }

    // Step 2 — continue. Gated until the Advance Wars 2 ROM is detected.
    let mut continue_btn = button(text(t!(lang, "welcome-continue"))).padding(STANDARD_PADDING);
    if has_roms {
        continue_btn = continue_btn.style(widgets::primary_button).on_press(Message::Continue);
    } else {
        continue_btn = continue_btn.style(widgets::neutral);
    }

    let mut continue_block = column![].spacing(6);
    if !has_roms {
        continue_block = continue_block.push(
            text(t!(lang, "welcome-roms-needed"))
                .size(TEXT_CAPTION)
                .style(widgets::muted_text_style),
        );
    }
    continue_block = continue_block.push(Space::new().height(8)).push(continue_btn);

    let card = container(
        column![
            row![
                text(t!(lang, "welcome-title")).size(TEXT_DISPLAY),
                Space::new().width(Fill),
                lang_picker
            ]
            .align_y(Alignment::Center),
            text(t!(lang, "welcome-subtitle"))
                .size(TEXT_BODY)
                .style(widgets::muted_text_style),
            Space::new().height(16),
            roms_block,
            Space::new().height(12),
            continue_block,
        ]
        .spacing(8)
        .align_x(Alignment::Start)
        .padding(24)
        .max_width(560),
    )
    // In the Advance Wars look the steps sit in a menu box, so they
    // read against the field backdrop.
    .max_width(560)
    .style(|theme: &iced::Theme| {
        if tango_ui::style::is_advance_wars(theme) {
            tango_ui::widgets::aw_box()
        } else {
            iced::widget::container::Style::default()
        }
    });
    container(card).center(Fill).into()
}
