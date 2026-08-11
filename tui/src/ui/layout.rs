use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState, Paragraph, Wrap},
    Frame,
};

use crate::app::{ActivePane, App, PROVIDERS};
use crate::i18n::t;
use crate::theme;
use crate::views::skills_manager;

/// Full-screen first-run API configuration wizard.
pub fn render_setup(frame: &mut Frame, app: &App) {
    let setup = match &app.setup {
        Some(s) => s,
        None => return,
    };
    let area = frame.area();
    let outer = Block::default()
        .borders(Borders::ALL)
        .border_style(theme::CORAL)
        .title(" VulnClaw · API Setup ");
    let inner = outer.inner(area);
    frame.render_widget(outer, area);

    let steps = ["1.Provider", "2.API Key", "3.Base URL", "4.Model"];
    let step_label = steps.get(setup.step as usize).copied().unwrap_or("");

    let mut lines: Vec<Line> = Vec::new();
    lines.push(Line::from(Span::styled(
        "Configure your LLM provider to enable L3 semantic review and Agent modes.",
        Style::default().fg(theme::TEXT_HINT),
    )));
    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        format!("Step: {step_label}"),
        Style::default()
            .fg(theme::ACTION)
            .add_modifier(Modifier::BOLD),
    )));
    lines.push(Line::from(""));

    if setup.step == 0 {
        for (i, p) in PROVIDERS.iter().enumerate() {
            let marker = if i == setup.provider_index { "▶ " } else { "  " };
            let style = if i == setup.provider_index {
                Style::default()
                    .fg(theme::ACTION)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme::TEXT_BODY)
            };
            lines.push(Line::from(Span::styled(
                format!("{marker}{}  ({})", p.label, p.name),
                style,
            )));
        }
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            "Up/Down select · Enter confirm",
            Style::default().fg(theme::TEXT_HINT),
        )));
    } else {
        let (prompt, prefix, field_val, mask) = match setup.step {
            1 => ("API Key", "API Key: ", setup.api_key.as_str(), true),
            2 => ("Base URL", "Base URL: ", setup.base_url.as_str(), false),
            3 => ("Model", "Model: ", setup.model.as_str(), false),
            _ => ("", "", "", false),
        };
        let display = if field_val.is_empty() {
            "<type here>".to_string()
        } else if mask {
            "*".repeat(field_val.chars().count())
        } else {
            field_val.to_string()
        };
        lines.push(Line::from(Span::styled(
            format!("{prompt}: {display}"),
            Style::default().fg(theme::TEXT_BODY),
        )));
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            "Type to edit · Enter next · Esc skip",
            Style::default().fg(theme::TEXT_HINT),
        )));
        let _ = prefix;
    }

    if !setup.message.is_empty() {
        lines.push(Line::from(""));
        let msg_style = if setup.error {
            Style::default().fg(theme::CORAL)
        } else {
            Style::default().fg(theme::TEXT_HINT)
        };
        lines.push(Line::from(Span::styled(setup.message.clone(), msg_style)));
    }

    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: true }), inner);

    // Place the terminal cursor on the editable line for text steps.
    if setup.step != 0 {
        let prefix = match setup.step {
            1 => "API Key: ",
            2 => "Base URL: ",
            3 => "Model: ",
            _ => "",
        };
        let input_line_y = inner.y + 4;
        let cursor_x = inner
            .x
            .saturating_add(prefix.chars().count() as u16)
            .saturating_add(setup.cursor as u16)
            .min(inner.right().saturating_sub(1));
        frame.set_cursor_position((cursor_x, input_line_y));
    }
}

/// In-place LLM settings editor. It intentionally renders from a draft held
/// by the app; persistence happens only after the Save row is activated.
pub fn render_config_panel(frame: &mut Frame, app: &App) {
    let Some(panel) = app.config_panel.as_ref() else {
        return;
    };
    let area = frame.area();
    let width = if area.width < 48 {
        48
    } else {
        area.width.min(88)
    };
    let height = if area.height < 16 {
        16
    } else {
        area.height.min(28)
    };
    let outer_area = Rect {
        x: area.x + area.width.saturating_sub(width) / 2,
        y: area.y + area.height.saturating_sub(height) / 2,
        width,
        height,
    };
    let title = format!(" {} ", t("tui.native_config.title"));
    let outer = Block::default()
        .borders(Borders::ALL)
        .border_style(theme::CORAL)
        .style(Style::default().bg(theme::PANEL))
        .title(title);
    let inner = outer.inner(outer_area);
    frame.render_widget(outer, outer_area);

    let mut lines = vec![Line::from(Span::styled(
        panel.summary(),
        Style::default().fg(theme::TEXT_HINT),
    ))];
    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        t("tui.native_config.title"),
        Style::default().fg(theme::ACTION).add_modifier(Modifier::BOLD),
    )));

    let mut row_y = 3u16;
    let mut add_row = |label: &str, value: String, active: bool| {
        let marker = if active { "▶ " } else { "  " };
        let style = if active {
            Style::default().fg(theme::TEXT_BODY).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(theme::TEXT_SOFT)
        };
        lines.push(Line::from(vec![
            Span::styled(marker, Style::default().fg(theme::ACTION)),
            Span::styled(format!("{label:<10}"), Style::default().fg(theme::TEXT_MUTED)),
            Span::styled(value, style),
        ]));
        row_y += 1;
    };

    let base_offset = usize::from(panel.has_base_url_row());
    let provider_hint = if panel.provider_dropdown {
        t("tui.native_config.choose")
    } else {
        t("tui.native_config.enter_to_edit")
    };
    add_row(
        &t("tui.native_config.label_provider"),
        format!("{}  ({})", panel.provider, provider_hint),
        panel.focus == 0,
    );
    if panel.has_base_url_row() {
        add_row(
            &t("tui.native_config.label_base_url"),
            panel.base_url.clone(),
            panel.focus == 1,
        );
    }
    let key_value = if panel.api_key.is_empty() {
        "—".to_owned()
    } else if panel.reveal_key {
        panel.api_key.clone()
    } else {
        "•".repeat(panel.api_key.chars().count().min(8))
    };
    add_row(
        &t("tui.native_config.label_api_key"),
        key_value,
        panel.focus == 1 + base_offset,
    );
    add_row(
        &t("tui.native_config.label_model"),
        if panel.model.is_empty() {
            t("tui.native_config.none")
        } else {
            panel.model.clone()
        },
        panel.focus == 2 + base_offset,
    );
    let fetch_focused = panel.focus == 3 + base_offset;
    let save_focused = panel.focus == 4 + base_offset;
    let active_style = Style::default().fg(theme::TEXT_BODY).add_modifier(Modifier::BOLD);
    let inactive_style = Style::default().fg(theme::TEXT_SOFT);
    let fetch_suffix = if panel.loading {
        t("tui.native_config.suffix_loading")
    } else if !panel.can_fetch() {
        t("tui.native_config.suffix_disabled")
    } else {
        String::new()
    };
    let save_suffix = if panel.can_save() {
        String::new()
    } else {
        t("tui.native_config.suffix_disabled")
    };
    lines.push(Line::from(vec![
        Span::styled(
            if fetch_focused || save_focused { "▶ " } else { "  " },
            Style::default().fg(theme::ACTION),
        ),
        Span::styled(
            format!("{:<10}", t("tui.native_config.label_actions")),
            Style::default().fg(theme::TEXT_MUTED),
        ),
        Span::styled(
            format!("[{}{}]", t("tui.native_config.fetch"), fetch_suffix),
            if fetch_focused { active_style } else { inactive_style },
        ),
        Span::raw("  "),
        Span::styled(
            format!("[{}{}]", t("tui.native_config.save"), save_suffix),
            if save_focused { active_style } else { inactive_style },
        ),
    ]));
    row_y += 1;
    let _ = row_y;

    if panel.provider_dropdown {
        lines.push(Line::from(Span::styled(
            t("tui.native_config.providers_hint"),
            Style::default().fg(theme::TEXT_HINT),
        )));
        for provider in &panel.providers {
            let marker = if provider.name == panel.provider { "▶ " } else { "  " };
            lines.push(Line::from(Span::styled(
                format!("{marker}{} ({})", provider.label, provider.name),
                if provider.name == panel.provider {
                    Style::default().fg(theme::ACTION).add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(theme::TEXT_SOFT)
                },
            )));
        }
    } else if panel.model_dropdown {
        lines.push(Line::from(Span::styled(
            t("tui.native_config.models_hint"),
            Style::default().fg(theme::TEXT_HINT),
        )));
        for model in panel.models.iter().take(8) {
            let marker = if model == &panel.model { "▶ " } else { "  " };
            lines.push(Line::from(Span::styled(
                format!("{marker}{model}"),
                if model == &panel.model {
                    Style::default().fg(theme::ACTION).add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(theme::TEXT_SOFT)
                },
            )));
        }
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        t("tui.native_config.nav_hint"),
        Style::default().fg(theme::TEXT_HINT),
    )));
    if !panel.message.is_empty() {
        lines.push(Line::from(Span::styled(
            panel.message.clone(),
            if panel.error {
                Style::default().fg(theme::CORAL)
            } else {
                Style::default().fg(theme::SEAFOAM)
            },
        )));
    }
    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: true }), inner);

    if panel.editing {
        let field_index = panel.focus + 3;
        let cursor_y = inner.y + field_index as u16;
        let label_width = 12u16;
        let cursor_x = inner
            .x
            .saturating_add(label_width)
            .saturating_add(panel.cursor as u16)
            .min(inner.right().saturating_sub(1));
        frame.set_cursor_position((cursor_x, cursor_y));
    }
}

pub fn render(frame: &mut Frame, app: &App) {
    if app.config_panel.is_some() {
        render_config_panel(frame, app);
        return;
    }
    if app.setup.is_some() {
        render_setup(frame, app);
        return;
    }
    frame.render_widget(
        Block::default().style(Style::default().bg(theme::BG)),
        frame.area(),
    );
    // Compact single-line composer (CodeWhale Compact density): one input row,
    // no bordered title box that reads as a second line. The command palette and
    // the task-confirmation prompt get their own taller regions when active.
    let composer_height = if app.pending_task.is_some() {
        3
    } else if app.palette_visible() {
        7
    } else {
        1
    };
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(6),
            Constraint::Length(composer_height),
            Constraint::Length(1),
        ])
        .split(frame.area());
    render_header(frame, app, rows[0]);
    render_phase_strip(frame, app, rows[1]);
    render_workbench(frame, app, rows[2]);
    render_composer(frame, app, rows[3]);
    render_hotbar(frame, app, rows[4]);
}

fn render_header(frame: &mut Frame, app: &App, area: Rect) {
    let mut spans = vec![
        Span::styled(
            " VulnClaw ",
            Style::default().fg(theme::ACTION).add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            format!(" {} ", app.mode.label()),
            Style::default()
                .fg(theme::mode_color(app.mode.label()))
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            format!("| {} ", app.permission.label()),
            Style::default().fg(theme::permission_color(app.permission.label())),
        ),
        Span::raw("| "),
    ];
    if app.worker_active {
        // Live "working" cluster: spinning glyph, bouncing equalizer, and a
        // running elapsed-time readout — all animate off the wall clock so the
        // surface feels alive without any extra state.
        spans.push(Span::styled(
            format!("{} running", theme::spinner_frame(true)),
            Style::default().fg(theme::GOLD),
        ));
        spans.push(Span::raw(" "));
        spans.push(Span::styled(
            theme::equalizer_frame(),
            Style::default().fg(theme::SEAFOAM),
        ));
        spans.push(Span::raw(" "));
        spans.push(Span::styled(
            theme::elapsed_label(app.worker_started_at),
            Style::default().fg(theme::TEXT_SOFT),
        ));
    } else {
        spans.push(Span::styled("idle", Style::default().fg(theme::TEXT_HINT)));
    }
    frame.render_widget(
        Paragraph::new(Line::from(spans)).style(Style::default().bg(theme::CHROME)),
        area,
    );
}

/// Live progress bar — mirrors CodeWhale's phase strip so a running scan shows
/// its current phase and finding count instead of a frozen transcript.
fn render_phase_strip(frame: &mut Frame, app: &App, area: Rect) {
    let line = if app.worker_active {
        if let Some(receipt) = app.active_receipt.as_ref() {
            let mut spans = vec![Span::styled(
                format!(" {} {}  ·  ", theme::spinner_frame(true), receipt.phase),
                Style::default().fg(theme::SEAFOAM),
            )];
            // The finding count pulses gold while a run is live and has already
            // surfaced something, so a fresh hit reads as a heartbeat.
            let fc_style = if receipt.findings > 0 && theme::blink_on() {
                Style::default()
                    .fg(theme::GOLD)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme::SEAFOAM)
            };
            spans.push(Span::styled(
                format!("{} finding(s)", receipt.findings),
                fc_style,
            ));
            spans.push(Span::styled(
                format!("  ·  {}", receipt.command),
                Style::default().fg(theme::SEAFOAM),
            ));
            Line::from(spans)
        } else {
            Line::from(Span::styled(
                format!(" {} working", theme::spinner_frame(true)),
                Style::default().fg(theme::SEAFOAM),
            ))
        }
    } else if let Some(receipt) = app.last_receipt.as_ref() {
        Line::from(Span::styled(
            format!(
                " {}  ·  {} finding(s)  ·  {}",
                receipt.phase, receipt.findings, receipt.command
            ),
            Style::default().fg(theme::TEXT_HINT),
        ))
    } else {
        Line::from(Span::styled(" ready", Style::default().fg(theme::TEXT_HINT)))
    };
    frame.render_widget(
        Paragraph::new(line).style(Style::default().bg(theme::CHROME)),
        area,
    );
}

fn render_workbench(frame: &mut Frame, app: &App, area: Rect) {
    let panels = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length(28),
            Constraint::Min(36),
            Constraint::Length(40),
        ])
        .split(area);
    let sidebar = skills_manager::render(app).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(theme::BORDER)
            .style(Style::default().bg(theme::PANEL))
            .title(if app.active_pane == ActivePane::Workspace {
                "Workspace *"
            } else {
                "Workspace"
            }),
    );
    frame.render_widget(sidebar, panels[0]);
    crate::ui::transcript::render(frame, app, panels[1]);
    crate::ui::findings::render(frame, app, panels[2]);
}

fn render_composer(frame: &mut Frame, app: &App, area: Rect) {
    if app.pending_task.is_some() {
        frame.render_widget(
            Paragraph::new("TUI confirmation is required. Press Y to start, or Esc to cancel.")
                .wrap(Wrap { trim: true })
                .block(Block::default().borders(Borders::ALL).border_style(theme::CORAL).title("Task confirmation required")),
            area,
        );
        return;
    }

    if app.palette_visible() {
        let rows = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Length(6), Constraint::Length(1)])
            .split(area);
        render_command_palette(frame, app, rows[0]);
        render_composer_input(frame, app, rows[1]);
    } else {
        render_composer_input(frame, app, area);
    }
}

fn render_composer_input(frame: &mut Frame, app: &App, composer_area: Rect) {
    let content = if app.input.is_empty() {
        "Type / for commands"
    } else {
        app.input.as_str()
    };
    let style = if app.input.is_empty() {
        Style::default().fg(theme::TEXT_HINT)
    } else {
        Style::default().fg(theme::TEXT_BODY)
    };
    // Single-line prompt — no bordered title box (which read as a second line).
    // The leading marker + text + cursor all live on this one row.
    frame.render_widget(
        Paragraph::new(Line::from(vec![
            Span::styled(
                " > ",
                Style::default()
                    .fg(theme::ACTION)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(content, style),
        ]))
        .style(Style::default().bg(theme::PLATE)),
        composer_area,
    );
    if !app.input.is_empty() {
        let cursor_x = composer_area
            .x
            .saturating_add(3)
            .saturating_add(app.input[..app.input_cursor].chars().count() as u16)
            .min(composer_area.right().saturating_sub(1));
        frame.set_cursor_position((cursor_x, composer_area.y));
    }
}

fn render_command_palette(frame: &mut Frame, app: &App, area: Rect) {
    let commands = app.suggested_commands();
    let items = commands
        .iter()
        .map(|item| {
            ListItem::new(Line::from(vec![
                Span::styled(item.command, Style::default().fg(theme::ACTION)),
                Span::raw("  "),
                Span::styled(item.description, Style::default().fg(theme::TEXT_MUTED)),
            ]))
        })
        .collect::<Vec<_>>();
    let mut state = ListState::default().with_selected(Some(app.palette_selection));
    frame.render_stateful_widget(
        List::new(items)
            .highlight_style(
                Style::default()
                    .fg(theme::TEXT_BODY)
                    .bg(theme::PLATE)
                    .add_modifier(Modifier::BOLD),
            )
            .block(
                Block::default()
                    .borders(Borders::ALL)
                    .border_style(theme::BORDER)
                    .title("Commands"),
            ),
        area,
        &mut state,
    );
}

fn render_hotbar(frame: &mut Frame, app: &App, area: Rect) {
    let (text, style) = if !app.toast.is_empty() {
        (
            app.toast.as_str(),
            Style::default()
                .fg(theme::SEAFOAM)
                .add_modifier(Modifier::BOLD),
        )
    } else if app.pending_task.is_some() {
        (
            " Y confirm | Esc cancel",
            Style::default().fg(theme::TEXT_HINT),
        )
    } else if app.worker_active {
        (
            " Running — Ctrl+C abort | Tab mode | ↑/↓ scroll | Ctrl+Y copy pane",
            Style::default().fg(theme::TEXT_HINT),
        )
    } else {
        (
            " Tab mode | Shift+Tab safeguard | Ctrl+P/N history | Ctrl+←/→ panel | ↑/↓ scroll | Ctrl+T thinking | F5 chain | Ctrl+S save | Ctrl+R restore | Ctrl+Y copy pane | Ctrl+C exit",
            Style::default().fg(theme::TEXT_HINT),
        )
    };
    frame.render_widget(
        Paragraph::new(Span::styled(text, style)).style(Style::default().bg(theme::CHROME)),
        area,
    );
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;
    use std::time::Instant;

    use ratatui::{backend::TestBackend, Terminal};

    use super::render;
    use crate::app::{App, OperationReceipt};

    #[test]
    fn renders_a_composer_centered_security_workbench() {
        let (sender, _) = mpsc::channel();
        let app = App::new(sender);
        let mut terminal = Terminal::new(TestBackend::new(120, 28)).unwrap();

        terminal.draw(|frame| render(frame, &app)).unwrap();

        let rendered = terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>();
        assert!(rendered.contains("Session transcript"));
        assert!(rendered.contains("Findings inspector (0)"));
        assert!(rendered.contains("Type / for commands"));
        assert!(rendered.contains("Tab mode"));
        assert!(rendered.contains("ready"));
        assert!(!rendered.contains("[Skills] [Findings] [Output]"));
    }

    #[test]
    fn header_shows_live_timer_and_running_state_while_a_worker_is_active() {
        let (sender, _) = mpsc::channel();
        let mut app = App::new(sender);
        app.worker_active = true;
        app.worker_started_at = Some(Instant::now());
        app.active_receipt = Some(OperationReceipt {
            command: "task run https://example.com".into(),
            phase: "Running".into(),
            findings: 0,
        });
        let mut terminal = Terminal::new(TestBackend::new(120, 28)).unwrap();

        terminal.draw(|frame| render(frame, &app)).unwrap();

        let rendered = terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>();
        assert!(rendered.contains("running"), "header must read 'running'");
        assert!(rendered.contains("⏱"), "header must show the live elapsed timer");
    }

    #[test]
    fn slash_input_renders_the_command_palette() {
        let (sender, _) = mpsc::channel();
        let mut app = App::new(sender);
        app.insert_text("/");
        let mut terminal = Terminal::new(TestBackend::new(120, 28)).unwrap();

        terminal.draw(|frame| render(frame, &app)).unwrap();

        let rendered = terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>();
        assert!(rendered.contains("Commands"));
        assert!(rendered.contains("/scan "));
    }

    #[test]
    fn composer_placeholder_renders_on_a_single_row() {
        let (sender, _) = mpsc::channel();
        let app = App::new(sender); // empty input -> placeholder path
        let mut terminal = Terminal::new(TestBackend::new(80, 24)).unwrap();
        terminal.draw(|frame| render(frame, &app)).unwrap();
        let buf = terminal.backend().buffer();
        let mut rows_with_placeholder = 0;
        for y in 0..24u16 {
            let line: String = (0..80u16)
                .map(|x| buf.cell((x, y)).map(|c| c.symbol().to_string()).unwrap_or_default())
                .collect();
            if line.contains("Type / for commands") {
                rows_with_placeholder += 1;
            }
        }
        assert_eq!(
            rows_with_placeholder, 1,
            "the composer placeholder must render on exactly one row"
        );
    }

    #[test]
    fn task_confirmation_replaces_the_composer() {
        let (sender, _) = mpsc::channel();
        let mut app = App::new(sender);
        app.pending_task = Some(vec!["task".into(), "run".into()]);
        let mut terminal = Terminal::new(TestBackend::new(120, 28)).unwrap();

        terminal.draw(|frame| render(frame, &app)).unwrap();

        let rendered = terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>();
        assert!(rendered.contains("Task confirmation required"));
        assert!(rendered.contains("Y confirm"));
    }

    fn buffer_text(terminal: &Terminal<TestBackend>) -> String {
        terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>()
    }

    /// ratatui TestBackend pads fullwidth glyphs with empty spacer cells.
    fn compact(text: &str) -> String {
        text.chars().filter(|c| !c.is_whitespace()).collect()
    }

    fn fixture_panel() -> crate::app::ConfigPanelState {
        crate::app::ConfigPanelState::from_json(&serde_json::json!({
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret-value",
            "model": "gpt-4o",
            "providers": [
                {"provider": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o"},
                {"provider": "custom", "label": "Custom", "base_url": "", "default_model": ""}
            ]
        }))
        .expect("valid config panel fixture")
    }

    #[test]
    fn config_panel_renders_english_chrome() {
        let (sender, _) = mpsc::channel();
        let mut app = App::new(sender);
        crate::i18n::set_lang(crate::i18n::Lang::En);
        let mut panel = fixture_panel();
        panel.message = crate::i18n::t("tui.native_config.fetch_idle");
        app.config_panel = Some(panel);
        let mut terminal = Terminal::new(TestBackend::new(100, 30)).unwrap();
        terminal.draw(|frame| render(frame, &app)).unwrap();
        let rendered = buffer_text(&terminal);
        assert!(rendered.contains("Configure LLM"), "rendered={rendered}");
        assert!(rendered.contains("Provider"), "rendered={rendered}");
        assert!(rendered.contains("API key"), "rendered={rendered}");
        assert!(rendered.contains("[Fetch]"), "rendered={rendered}");
        assert!(rendered.contains("[Save]"), "rendered={rendered}");
        assert!(rendered.contains("Press Fetch to load models."), "rendered={rendered}");
    }

    #[test]
    fn config_panel_renders_chinese_chrome() {
        let (sender, _) = mpsc::channel();
        let mut app = App::new(sender);
        crate::i18n::set_lang(crate::i18n::Lang::Zh);
        let mut panel = fixture_panel();
        panel.message = crate::i18n::t("tui.native_config.fetch_idle");
        app.config_panel = Some(panel);
        let mut terminal = Terminal::new(TestBackend::new(100, 30)).unwrap();
        terminal.draw(|frame| render(frame, &app)).unwrap();
        let rendered = compact(&buffer_text(&terminal));
        assert!(rendered.contains("配置LLM"), "rendered={rendered}");
        assert!(rendered.contains("提供商"), "rendered={rendered}");
        assert!(rendered.contains("API密钥"), "rendered={rendered}");
        assert!(rendered.contains("[拉取]"), "rendered={rendered}");
        assert!(rendered.contains("[保存]"), "rendered={rendered}");
        assert!(rendered.contains("按「拉取」加载模型。"), "rendered={rendered}");
    }
}
