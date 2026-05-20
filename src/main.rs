use std::{env, io, mem};

use crossterm::{
    event::{
        self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers,
        MouseButton, MouseEventKind,
    },
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Alignment, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph},
    Frame, Terminal,
};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

const FREE_MODELS: &[(&str, &str)] = &[
    ("openrouter/free",                                  "Auto (Free Router)"),
    ("meta-llama/llama-3.3-70b-instruct:free",           "Llama 3.3 70B"),
    ("meta-llama/llama-3.1-8b-instruct:free",            "Llama 3.1 8B"),
    ("meta-llama/llama-3.2-3b-instruct:free",            "Llama 3.2 3B"),
    ("meta-llama/llama-3.2-1b-instruct:free",            "Llama 3.2 1B"),
    ("google/gemma-3-27b-it:free",                       "Gemma 3 27B"),
    ("google/gemma-3-12b-it:free",                       "Gemma 3 12B"),
    ("google/gemma-3-4b-it:free",                        "Gemma 3 4B"),
    ("google/gemma-3-1b-it:free",                        "Gemma 3 1B"),
    ("google/gemma-3n-e4b-it:free",                      "Gemma 3n E4B"),
    ("deepseek/deepseek-r1:free",                        "DeepSeek R1"),
    ("deepseek/deepseek-chat-v3-0324:free",              "DeepSeek V3"),
    ("deepseek/deepseek-prover-v2:free",                 "DeepSeek Prover V2"),
    ("mistralai/mistral-7b-instruct:free",               "Mistral 7B"),
    ("mistralai/mistral-small-3.1-24b-instruct:free",    "Mistral Small 24B"),
    ("qwen/qwen-2.5-72b-instruct:free",                  "Qwen 2.5 72B"),
    ("qwen/qwen-2.5-7b-instruct:free",                   "Qwen 2.5 7B"),
    ("qwen/qwen3-14b:free",                              "Qwen3 14B"),
    ("qwen/qwen3-8b:free",                               "Qwen3 8B"),
    ("microsoft/phi-3-mini-128k-instruct:free",          "Phi-3 Mini 128K"),
    ("microsoft/phi-3-medium-128k-instruct:free",        "Phi-3 Medium 128K"),
    ("nousresearch/hermes-3-llama-3.1-405b:free",        "Hermes 3 405B"),
    ("openchat/openchat-7b:free",                        "OpenChat 7B"),
    ("huggingfaceh4/zephyr-7b-beta:free",                "Zephyr 7B"),
    ("liquid/lfm-7b:free",                               "LFM 7B"),
    ("gryphe/mythomax-l2-13b:free",                      "MythoMax 13B"),
];

// ── types ──────────────────────────────────────────────────────────────────────

#[derive(Clone)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ApiMessage {
    role: String,
    content: String,
}

#[derive(Deserialize)]
struct ApiResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: ApiContent,
}

#[derive(Deserialize)]
struct ApiContent {
    content: String,
}

struct App {
    history: Vec<Message>,
    input: String,
    thinking: bool,
    in_chat: bool,
    model_select_open: bool,
    selected_model_idx: usize,
    model_list_state: ListState,
    frame_count: u64,
    chat_scroll: u16,
    total_chat_lines: u16,
    chat_view_height: u16,
    model_btn_rect: Rect,
    popup_rect: Rect,
    tx: mpsc::Sender<Result<String, String>>,
    rx: mpsc::Receiver<Result<String, String>>,
}

impl App {
    fn new() -> Self {
        let (tx, rx) = mpsc::channel(10);
        let mut model_list_state = ListState::default();
        model_list_state.select(Some(0));
        Self {
            history: Vec::new(),
            input: String::new(),
            thinking: false,
            in_chat: false,
            model_select_open: false,
            selected_model_idx: 0,
            model_list_state,
            frame_count: 0,
            chat_scroll: 0,
            total_chat_lines: 0,
            chat_view_height: 0,
            model_btn_rect: Rect::default(),
            popup_rect: Rect::default(),
            tx,
            rx,
        }
    }

    fn model_id(&self) -> &str { FREE_MODELS[self.selected_model_idx].0 }
    fn model_name(&self) -> &str { FREE_MODELS[self.selected_model_idx].1 }

    fn submit(&mut self) {
        let text = self.input.trim().to_string();
        if text.is_empty() || self.thinking { return; }
        self.history.push(Message { role: "user".into(), content: text });
        self.input.clear();
        self.thinking = true;
        self.in_chat = true;
        self.chat_scroll = 0;

        let api_key = env::var("OPENROUTER_API_KEY").unwrap_or_default();
        let model = self.model_id().to_string();
        let messages: Vec<ApiMessage> = self.history.iter()
            .map(|m| ApiMessage { role: m.role.clone(), content: m.content.clone() })
            .collect();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            let _ = tx.send(fetch(api_key, model, messages).await).await;
        });
    }
}

async fn fetch(api_key: String, model: String, messages: Vec<ApiMessage>) -> Result<String, String> {
    let resp = Client::new()
        .post("https://openrouter.ai/api/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&serde_json::json!({ "model": model, "messages": messages }))
        .timeout(std::time::Duration::from_secs(60))
        .send().await.map_err(|e| e.to_string())?;
    let data: ApiResponse = resp.json().await.map_err(|e| e.to_string())?;
    Ok(data.choices[0].message.content.clone())
}

// ── markdown ───────────────────────────────────────────────────────────────────

fn word_wrap(text: &str, width: usize) -> Vec<String> {
    if width == 0 { return vec![text.to_string()]; }
    if text.is_empty() { return vec![String::new()]; }
    let mut result: Vec<String> = Vec::new();
    let mut line = String::new();
    for word in text.split(' ').filter(|w| !w.is_empty()) {
        let wlen = word.chars().count();
        if line.is_empty() {
            if wlen > width {
                for chunk in word.chars().collect::<Vec<_>>().chunks(width) {
                    let s: String = chunk.iter().collect();
                    if chunk.len() == width { result.push(s); } else { line = s; }
                }
            } else {
                line = word.to_string();
            }
        } else if line.chars().count() + 1 + wlen <= width {
            line.push(' ');
            line.push_str(word);
        } else {
            result.push(mem::take(&mut line));
            if wlen > width {
                for chunk in word.chars().collect::<Vec<_>>().chunks(width) {
                    let s: String = chunk.iter().collect();
                    if chunk.len() == width { result.push(s); } else { line = s; }
                }
            } else {
                line = word.to_string();
            }
        }
    }
    if !line.is_empty() { result.push(line); }
    if result.is_empty() { result.push(String::new()); }
    result
}

fn parse_inline(text: &str, color: Color) -> Line<'static> {
    let mut spans: Vec<Span<'static>> = Vec::new();
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;
    let mut buf = String::new();

    while i < chars.len() {
        if i + 1 < chars.len() && chars[i] == '*' && chars[i + 1] == '*' {
            if !buf.is_empty() { spans.push(Span::styled(mem::take(&mut buf), Style::default().fg(color))); }
            i += 2;
            let start = i;
            while i < chars.len() && !(i + 1 < chars.len() && chars[i] == '*' && chars[i + 1] == '*') { i += 1; }
            let inner: String = chars[start..i].iter().collect();
            spans.push(Span::styled(inner, Style::default().fg(color).add_modifier(Modifier::BOLD)));
            if i + 1 < chars.len() { i += 2; }
        } else if chars[i] == '`' {
            if !buf.is_empty() { spans.push(Span::styled(mem::take(&mut buf), Style::default().fg(color))); }
            i += 1;
            let start = i;
            while i < chars.len() && chars[i] != '`' { i += 1; }
            let inner: String = chars[start..i].iter().collect();
            spans.push(Span::styled(inner, Style::default().fg(Color::Cyan)));
            if i < chars.len() { i += 1; }
        } else if chars[i] == '*' {
            if !buf.is_empty() { spans.push(Span::styled(mem::take(&mut buf), Style::default().fg(color))); }
            i += 1;
            let start = i;
            while i < chars.len() && chars[i] != '*' { i += 1; }
            let inner: String = chars[start..i].iter().collect();
            spans.push(Span::styled(inner, Style::default().fg(color).add_modifier(Modifier::DIM)));
            if i < chars.len() { i += 1; }
        } else {
            buf.push(chars[i]);
            i += 1;
        }
    }
    if !buf.is_empty() { spans.push(Span::styled(buf, Style::default().fg(color))); }
    if spans.is_empty() { spans.push(Span::styled(String::new(), Style::default().fg(color))); }
    Line::from(spans)
}

fn format_content(content: &str, color: Color, width: usize) -> Vec<Line<'static>> {
    let mut lines: Vec<Line<'static>> = Vec::new();
    let mut in_code = false;
    let w = width.max(10);

    for raw in content.lines() {
        let trimmed = raw.trim();

        if trimmed.starts_with("```") {
            if !in_code {
                in_code = true;
                let lang = trimmed.trim_start_matches('`').trim();
                if !lang.is_empty() {
                    lines.push(Line::from(Span::styled(
                        format!("  {}", lang),
                        Style::default().fg(Color::DarkGray),
                    )));
                }
            } else {
                in_code = false;
            }
            continue;
        }

        if in_code {
            lines.push(Line::from(Span::styled(
                format!("  \u{2502} {}", raw),
                Style::default().fg(Color::Cyan),
            )));
            continue;
        }

        if trimmed.is_empty() {
            lines.push(Line::from(""));
            continue;
        }

        // Headings
        let hashes = raw.chars().take_while(|&c| c == '#').count();
        if hashes > 0 && hashes <= 3 {
            if let Some(rest) = raw.get(hashes..).and_then(|s| s.strip_prefix(' ')) {
                let style = match hashes {
                    1 => Style::default().fg(Color::White).add_modifier(Modifier::BOLD).add_modifier(Modifier::UNDERLINED),
                    2 => Style::default().fg(Color::White).add_modifier(Modifier::BOLD),
                    _ => Style::default().fg(Color::White),
                };
                for chunk in word_wrap(rest, w) {
                    lines.push(Line::from(Span::styled(chunk, style)));
                }
                continue;
            }
        }

        // Horizontal rule
        if trimmed.len() >= 3 && trimmed.chars().all(|c| c == '-') {
            lines.push(Line::from(Span::styled(
                "\u{2500}".repeat(w.min(60)),
                Style::default().fg(Color::DarkGray),
            )));
            continue;
        }

        // Bullets
        let bullet_text = if let Some(t) = trimmed.strip_prefix("- ").or_else(|| trimmed.strip_prefix("* ")) {
            Some(t)
        } else {
            None
        };
        if let Some(text) = bullet_text {
            let prefix = "  \u{2022} ";
            let avail = w.saturating_sub(4).max(10);
            for (idx, chunk) in word_wrap(text, avail).iter().enumerate() {
                let pad = if idx == 0 { prefix.to_string() } else { "    ".to_string() };
                let mut sv = vec![Span::styled(pad, Style::default().fg(Color::DarkGray))];
                sv.extend(parse_inline(chunk, color).spans);
                lines.push(Line::from(sv));
            }
            continue;
        }

        // Numbered list
        let num_end = raw.chars().take_while(|c| c.is_ascii_digit()).count();
        if num_end > 0 {
            let after = &raw[num_end..];
            if after.starts_with(". ") {
                let num = &raw[..num_end];
                let text = &after[2..];
                let prefix = format!("  {}. ", num);
                let avail = w.saturating_sub(prefix.len()).max(10);
                for (idx, chunk) in word_wrap(text, avail).iter().enumerate() {
                    let pad = if idx == 0 { prefix.clone() } else { " ".repeat(prefix.len()) };
                    let mut sv = vec![Span::styled(pad, Style::default().fg(Color::DarkGray))];
                    sv.extend(parse_inline(chunk, color).spans);
                    lines.push(Line::from(sv));
                }
                continue;
            }
        }

        // Regular text
        for chunk in word_wrap(raw, w) {
            lines.push(parse_inline(&chunk, color));
        }
    }

    lines
}

// ── rendering ──────────────────────────────────────────────────────────────────

fn render(f: &mut Frame, app: &mut App) {
    if app.in_chat {
        render_chat(f, app);
    } else {
        render_home(f, app);
    }
    if app.model_select_open {
        render_model_popup(f, app);
    }
}

fn render_home(f: &mut Frame, app: &mut App) {
    let area = f.area();

    let title_y = (area.height * 38 / 100).saturating_sub(1).min(area.height.saturating_sub(8));
    let title_area = Rect { x: 0, y: title_y, width: area.width, height: 1 };
    f.render_widget(
        Paragraph::new("C O S M O S")
            .style(Style::default().fg(Color::White).add_modifier(Modifier::BOLD))
            .alignment(Alignment::Center),
        title_area,
    );

    let box_w = area.width.saturating_sub(8).min(72).max(40);
    let box_h: u16 = 6;
    let box_x = area.width.saturating_sub(box_w) / 2;
    let box_y = title_y + 3;

    if box_y + box_h <= area.height {
        render_input_box(f, app, Rect { x: box_x, y: box_y, width: box_w, height: box_h }, true);
    }
}

fn render_chat(f: &mut Frame, app: &mut App) {
    let area = f.area();
    let input_h: u16 = 5;
    let msg_h = area.height.saturating_sub(input_h);

    render_messages(f, app, Rect { x: 0, y: 0, width: area.width, height: msg_h });
    render_input_box(f, app, Rect { x: 0, y: msg_h, width: area.width, height: input_h }, false);
}

fn render_messages(f: &mut Frame, app: &mut App, area: Rect) {
    let pad: u16 = 4;
    let inner_w = area.width.saturating_sub(pad * 2) as usize;
    if inner_w < 4 || area.height == 0 { return; }

    let mut all_lines: Vec<Line> = Vec::new();

    for msg in &app.history {
        if msg.role == "user" {
            all_lines.push(Line::from(Span::styled(
                "you",
                Style::default().fg(Color::DarkGray),
            )));
            for line in format_content(&msg.content, Color::White, inner_w) {
                all_lines.push(line);
            }
        } else {
            let model_label = format!(
                "cosmos  ·  {}",
                app.model_name()
            );
            all_lines.push(Line::from(Span::styled(
                model_label,
                Style::default().fg(Color::DarkGray),
            )));
            for line in format_content(&msg.content, Color::Gray, inner_w) {
                all_lines.push(line);
            }
        }
        all_lines.push(Line::from(""));
        all_lines.push(Line::from(""));
    }

    if app.thinking {
        let dots = match (app.frame_count / 10) % 3 { 0 => "·", 1 => "· ·", _ => "· · ·" };
        all_lines.push(Line::from(Span::styled(
            format!("cosmos  ·  {}", app.model_name()),
            Style::default().fg(Color::DarkGray),
        )));
        all_lines.push(Line::from(Span::styled(
            dots.to_string(),
            Style::default().fg(Color::DarkGray),
        )));
    }

    let total = all_lines.len() as u16;
    app.total_chat_lines = total;
    app.chat_view_height = area.height;

    let max_scroll = total.saturating_sub(area.height);
    app.chat_scroll = app.chat_scroll.min(max_scroll);
    let scroll = max_scroll.saturating_sub(app.chat_scroll);

    // Scroll indicator
    if app.chat_scroll > 0 {
        let indicator = format!("↓ scroll down ({})", app.chat_scroll);
        let ind_area = Rect { x: area.x + pad, y: area.y + area.height.saturating_sub(1), width: area.width.saturating_sub(pad * 2), height: 1 };
        f.render_widget(
            Paragraph::new(indicator)
                .style(Style::default().fg(Color::DarkGray))
                .alignment(Alignment::Right),
            ind_area,
        );
    }

    f.render_widget(
        Paragraph::new(all_lines).scroll((scroll, 0)),
        Rect { x: area.x + pad, y: area.y, width: area.width.saturating_sub(pad * 2), height: area.height },
    );
}

fn render_input_box(f: &mut Frame, app: &mut App, area: Rect, center_ph: bool) {
    f.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray)),
        area,
    );
    if area.height < 4 || area.width < 8 { return; }

    let pad: u16 = 2;
    let ix = area.x + pad;
    let iy = area.y + 1;
    let iw = area.width.saturating_sub(pad * 2);
    let ih = area.height.saturating_sub(2);
    if ih < 2 { return; }

    let text_h = ih.saturating_sub(1);
    let toolbar_y = iy + text_h;
    let toolbar = Rect { x: ix, y: toolbar_y, width: iw, height: 1 };

    // Text / placeholder
    if app.input.is_empty() {
        let ph_y = if center_ph && text_h > 1 { iy + text_h / 2 } else { iy };
        f.render_widget(
            Paragraph::new("What's on your mind?...")
                .style(Style::default().fg(Color::DarkGray))
                .alignment(if center_ph { Alignment::Center } else { Alignment::Left }),
            Rect { x: ix, y: ph_y, width: iw, height: 1 },
        );
        if !app.model_select_open { f.set_cursor_position((ix, iy)); }
    } else {
        let w = iw as usize;
        let char_count = app.input.chars().count();
        let visible: String = if char_count > w {
            let skip = char_count - w;
            app.input.chars().skip(skip).collect()
        } else {
            app.input.clone()
        };
        f.render_widget(
            Paragraph::new(visible.as_str()).style(Style::default().fg(Color::White)),
            Rect { x: ix, y: iy, width: iw, height: text_h },
        );
        if !app.model_select_open {
            let cx = (ix + visible.chars().count() as u16).min(area.x + area.width - 2);
            f.set_cursor_position((cx, iy));
        }
    }

    // Toolbar: + left, model right
    f.render_widget(
        Paragraph::new("+").style(Style::default().fg(Color::DarkGray)),
        toolbar,
    );
    let mname = app.model_name().to_string();
    let mname_len = mname.chars().count() as u16;
    let mbx = toolbar.x + toolbar.width.saturating_sub(mname_len);
    app.model_btn_rect = Rect { x: mbx, y: toolbar_y, width: mname_len, height: 1 };
    f.render_widget(
        Paragraph::new(mname).style(Style::default().fg(Color::DarkGray)).alignment(Alignment::Right),
        toolbar,
    );
}

fn render_model_popup(f: &mut Frame, app: &mut App) {
    let area = f.area();
    let pw = 52u16.min(area.width.saturating_sub(4));
    let ph = (FREE_MODELS.len() as u16 + 2).min(area.height.saturating_sub(2));
    let px = area.width.saturating_sub(pw) / 2;
    let py = area.height.saturating_sub(ph) / 2;
    let popup = Rect { x: px, y: py, width: pw, height: ph };
    app.popup_rect = popup;

    f.render_widget(Clear, popup);
    f.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Gray))
            .title(Span::styled(" model ", Style::default().fg(Color::White))),
        popup,
    );

    let items: Vec<ListItem> = FREE_MODELS.iter().map(|(_, name)| {
        ListItem::new(*name).style(Style::default().fg(Color::Gray))
    }).collect();

    f.render_stateful_widget(
        List::new(items)
            .highlight_style(Style::default().fg(Color::White).add_modifier(Modifier::BOLD))
            .highlight_symbol("> "),
        Rect { x: popup.x + 1, y: popup.y + 1, width: popup.width.saturating_sub(2), height: popup.height.saturating_sub(2) },
        &mut app.model_list_state,
    );
}

// ── helpers ────────────────────────────────────────────────────────────────────

fn rect_contains(r: Rect, col: u16, row: u16) -> bool {
    col >= r.x && col < r.x + r.width && row >= r.y && row < r.y + r.height
}

// ── main ───────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> io::Result<()> {
    dotenvy::dotenv().ok();

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.clear()?;

    let mut app = App::new();

    loop {
        app.frame_count += 1;
        terminal.draw(|f| render(f, &mut app))?;

        if let Ok(result) = app.rx.try_recv() {
            app.thinking = false;
            app.chat_scroll = 0;
            let content = match result {
                Ok(s) => s,
                Err(e) => format!("[error: {}]", e),
            };
            app.history.push(Message { role: "assistant".into(), content });
        }

        if event::poll(std::time::Duration::from_millis(50))? {
            match event::read()? {
                Event::Key(key) => {
                    if app.model_select_open {
                        match key.code {
                            KeyCode::Esc | KeyCode::Tab => app.model_select_open = false,
                            KeyCode::Up => {
                                let i = app.selected_model_idx.saturating_sub(1);
                                app.selected_model_idx = i;
                                app.model_list_state.select(Some(i));
                            }
                            KeyCode::Down => {
                                let i = (app.selected_model_idx + 1).min(FREE_MODELS.len() - 1);
                                app.selected_model_idx = i;
                                app.model_list_state.select(Some(i));
                            }
                            KeyCode::Enter => app.model_select_open = false,
                            _ => {}
                        }
                    } else {
                        match key.code {
                            KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => break,
                            KeyCode::Tab => {
                                app.model_select_open = true;
                                app.model_list_state.select(Some(app.selected_model_idx));
                            }
                            KeyCode::Enter => app.submit(),
                            KeyCode::Backspace => { app.input.pop(); }
                            KeyCode::Char(c) => app.input.push(c),
                            _ => {}
                        }
                    }
                }
                Event::Mouse(mouse) => {
                    let col = mouse.column;
                    let row = mouse.row;
                    match mouse.kind {
                        MouseEventKind::Down(MouseButton::Left) => {
                            if app.model_select_open {
                                let p = app.popup_rect;
                                if rect_contains(p, col, row) {
                                    let inner_row = row.saturating_sub(p.y + 1) as usize;
                                    let idx = inner_row + app.model_list_state.offset();
                                    if idx < FREE_MODELS.len() {
                                        app.selected_model_idx = idx;
                                        app.model_list_state.select(Some(idx));
                                    }
                                }
                                app.model_select_open = false;
                            } else if rect_contains(app.model_btn_rect, col, row) {
                                app.model_select_open = true;
                                app.model_list_state.select(Some(app.selected_model_idx));
                            }
                        }
                        MouseEventKind::ScrollUp => {
                            if app.model_select_open {
                                let i = app.selected_model_idx.saturating_sub(1);
                                app.selected_model_idx = i;
                                app.model_list_state.select(Some(i));
                            } else {
                                app.chat_scroll = app.chat_scroll.saturating_add(3)
                                    .min(app.total_chat_lines.saturating_sub(app.chat_view_height));
                            }
                        }
                        MouseEventKind::ScrollDown => {
                            if app.model_select_open {
                                let i = (app.selected_model_idx + 1).min(FREE_MODELS.len() - 1);
                                app.selected_model_idx = i;
                                app.model_list_state.select(Some(i));
                            } else {
                                app.chat_scroll = app.chat_scroll.saturating_sub(3);
                            }
                        }
                        _ => {}
                    }
                }
                Event::Resize(_, _) => {}
                _ => {}
            }
        }
    }

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen, DisableMouseCapture)?;
    Ok(())
}
