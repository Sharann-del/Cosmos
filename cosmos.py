"""COSMOS — streaming terminal AI chat."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.style import Style
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Label,
    ListItem, ListView, Markdown, Static, TextArea,
)
from textual.widgets.text_area import TextAreaTheme
from textual import work

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODELS: list[tuple[str, str]] = [
    ("openrouter/free",                                    "Auto (Best Free)"),
    ("arcee-ai/trinity-large-thinking:free",               "Trinity Large Thinking"),
    ("baidu/cobuddy:free",                                 "CoBuddy"),
    ("deepseek/deepseek-v4-flash:free",                    "DeepSeek V4 Flash"),
    ("google/gemma-4-26b-it:free",                         "Gemma 4 26B"),
    ("google/gemma-4-31b-it:free",                         "Gemma 4 31B"),
    ("liquid/lfm-2.5-1.2b-instruct:free",                  "LFM 2.5 1.2B"),
    ("liquid/lfm-2.5-1.2b-thinking:free",                  "LFM 2.5 1.2B Thinking"),
    ("meta-llama/llama-3.2-3b-instruct:free",              "Llama 3.2 3B"),
    ("meta-llama/llama-3.3-70b-instruct:free",             "Llama 3.3 70B"),
    ("minimax/minimax-m2.5:free",                          "MiniMax M2.5"),
    ("nousresearch/hermes-3-llama-3.1-405b:free",          "Hermes 3 405B"),
    ("nvidia/nemotron-3-nano-30b-a3b:free",                "Nemotron 3 Nano 30B"),
    ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "Nemotron 3 Nano Omni 30B"),
    ("nvidia/nemotron-3-super-120b-a12b:free",             "Nemotron 3 Super 120B"),
    ("nvidia/nemotron-nano-12b-v2-vl:free",                "Nemotron Nano 12B VL"),
    ("nvidia/nemotron-nano-9b-v2:free",                    "Nemotron Nano 9B"),
    ("openai/gpt-oss-120b:free",                           "GPT OSS 120B"),
    ("openai/gpt-oss-20b:free",                            "GPT OSS 20B"),
    ("poolside/laguna-m.1:free",                           "Laguna M.1"),
    ("poolside/laguna-xs.2:free",                          "Laguna XS.2"),
    ("qwen/qwen3-coder:free",                              "Qwen3 Coder"),
    ("qwen/qwen3-next-80b-a3b-instruct:free",              "Qwen3 Next 80B"),
    ("venice/uncensored:free",                             "Venice Uncensored"),
    ("z-ai/glm-4.5-air:free",                              "GLM 4.5 Air"),
]

# ── modals ─────────────────────────────────────────────────────────────────────

class ModelDropdown(ModalScreen[int | None]):
    """Compact dropdown anchored above the model button (bottom-right)."""
    CSS = """
    ModelDropdown {
        background: rgba(0,0,0,0);
        align: right bottom;
    }
    ModelDropdown > Vertical {
        width: 36;
        height: auto;
        background: #111111;
        border: solid #2a2a2a;
        margin: 0 4 5 0;
    }
    ModelDropdown ListView {
        background: #111111;
        border: none;
        padding: 0;
        height: auto;
        scrollbar-color: #111111;
        scrollbar-background: #111111;
        scrollbar-color-hover: #111111;
        scrollbar-color-active: #111111;
    }
    ModelDropdown ListItem {
        background: #111111;
        padding: 0 2;
        height: 1;
    }
    ModelDropdown ListView > ListItem.--highlight {
        background: #1e1e1e;
    }
    ModelDropdown ListItem Label {
        background: transparent;
        color: #707070;
        width: 100%;
    }
    ModelDropdown ListView > ListItem.--highlight Label {
        color: #e8e8e8;
        background: transparent;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            with ListView(id="model-list"):
                for _, name in FREE_MODELS:
                    yield ListItem(Label(name))

    def on_mount(self) -> None:
        lv = self.query_one(ListView)
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            label_text = str(event.item.query_one(Label).renderable)
            for i, (_, name) in enumerate(FREE_MODELS):
                if name == label_text:
                    self.dismiss(i)
                    return
        except Exception:
            pass
        self.dismiss(event.list_view.index)

    def on_click(self, event) -> None:
        try:
            container = self.query_one(Vertical)
            if not container.region.contains(event.screen_x, event.screen_y):
                self.dismiss(None)
        except Exception:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ── message widgets ────────────────────────────────────────────────────────────

class UserMessage(Static):
    class EditRequested(Message):
        def __init__(self, widget: "UserMessage", text: str) -> None:
            super().__init__()
            self.widget = widget
            self.text = text

    DEFAULT_CSS = """
    UserMessage {
        background: #1a1a1a;
        color: #cccccc;
        padding: 1 3;
        margin: 0 0 1 0;
        height: auto;
    }
    UserMessage:hover { background: #212121; }
    """

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self._msg_text = text

    def on_click(self) -> None:
        self.post_message(self.EditRequested(self, self._msg_text))


class CosmosMessage(Vertical):
    """COSMOS response box with an inline pulsing dot next to the label."""

    DEFAULT_CSS = """
    CosmosMessage {
        background: #0e0e0e;
        padding: 1 3;
        margin: 0 0 1 0;
        height: auto;
    }
    CosmosMessage #cosmos-header {
        height: 1;
        background: #0e0e0e;
        margin-bottom: 1;
    }
    CosmosMessage #cosmos-name {
        color: #383838;
        background: #0e0e0e;
        text-style: bold;
        width: auto;
    }
    CosmosMessage #cosmos-dot {
        color: #1c1c1c;
        background: #0e0e0e;
        width: auto;
        margin-left: 1;
    }
    CosmosMessage #cosmos-dot.pulse-bright { color: #999999; }
    CosmosMessage #cosmos-dot.pulse-dim    { color: #222222; }
    CosmosMessage #cosmos-dot.done         { color: #ffffff; }

    CosmosMessage Markdown                { background: #0e0e0e; margin: 0; padding: 0; }
    CosmosMessage MarkdownParagraph       { background: #0e0e0e; color: #c8c8c8; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH1              { background: #0e0e0e; color: #ffffff;  text-style: bold underline; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH2              { background: #0e0e0e; color: #f0f0f0;  text-style: bold; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH3              { background: #0e0e0e; color: #d8d8d8;  text-style: bold; margin: 0; padding: 0; }
    CosmosMessage MarkdownCode            { background: #1e1e1e; color: #9ecfb0; }
    CosmosMessage MarkdownFence           { background: #111111; margin: 0 0 1 0; padding: 0 1; }
    CosmosMessage MarkdownBulletListItem,
    CosmosMessage MarkdownOrderedListItem { background: #0e0e0e; color: #c8c8c8; }
    CosmosMessage MarkdownHorizontalRule  { background: #0e0e0e; color: #2a2a2a; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="cosmos-header"):
            yield Label("COSMOS", id="cosmos-name")
            yield Label("●", id="cosmos-dot")
        yield Markdown("")

    async def stream_append(self, full_text: str) -> None:
        try:
            await self.query_one(Markdown).update(full_text)
        except Exception:
            pass

    def start_dot(self) -> None:
        self.query_one("#cosmos-dot", Label).remove_class("done", "pulse-bright", "pulse-dim")

    def pulse_dot(self, bright: bool) -> None:
        dot = self.query_one("#cosmos-dot", Label)
        if bright:
            dot.add_class("pulse-bright")
            dot.remove_class("pulse-dim")
        else:
            dot.add_class("pulse-dim")
            dot.remove_class("pulse-bright")

    def finish_dot(self) -> None:
        dot = self.query_one("#cosmos-dot", Label)
        dot.remove_class("pulse-bright", "pulse-dim")
        dot.add_class("done")

    def idle_dot(self) -> None:
        try:
            self.query_one("#cosmos-dot", Label).remove_class("done", "pulse-bright", "pulse-dim")
        except Exception:
            pass


LOGO = """\
 ██████╗ ██████╗ ███████╗███╗   ███╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔════╝████╗ ████║██╔═══██╗██╔════╝
██║     ██║   ██║███████╗██╔████╔██║██║   ██║███████╗
██║     ██║   ██║╚════██║██║╚██╔╝██║██║   ██║╚════██║
╚██████╗╚██████╔╝███████║██║ ╚═╝ ██║╚██████╔╝███████║
 ╚═════╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝"""

_COSMOS_THEME = TextAreaTheme(
    name="cosmos-input",
    base_style=Style(color="#d0d0d0", bgcolor="#1a1a1a"),
    cursor_style=Style(color="#1a1a1a", bgcolor="#d0d0d0"),
    cursor_line_style=Style(bgcolor="#1a1a1a"),
    selection_style=Style(bgcolor="#2a2a2a"),
)


class ChatInput(TextArea):
    """Multiline chat input: Enter submits, Shift+Enter inserts newline."""

    class Submitted(Message):
        def __init__(self, input: "ChatInput", value: str) -> None:
            super().__init__()
            self.input = input
            self.value = value

    DEFAULT_CSS = """
    ChatInput {
        background: #1a1a1a;
        color: #d0d0d0;
        border: none;
        height: auto;
        min-height: 1;
        max-height: 10;
        padding: 0;
        scrollbar-background: #1a1a1a;
        scrollbar-color: #2a2a2a;
    }
    ChatInput:focus { background: #1a1a1a; border: none; }
    ChatInput.-focus { background: #1a1a1a; border: none; }
    ChatInput .text-area--placeholder { color: #505050; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder="What's on your mind?...",
            show_line_numbers=False,
            highlight_cursor_line=False,
            **kwargs,
        )

    def on_mount(self) -> None:
        self.register_theme(_COSMOS_THEME)
        self.theme = "cosmos-input"

    def _on_key(self, event) -> None:
        if event.key == "enter":
            event.prevent_default()
            self.post_message(self.Submitted(self, self.text))
        elif event.key == "shift+enter":
            event.prevent_default()
            self.insert("\n")


# ── main app ───────────────────────────────────────────────────────────────────

class CosmosApp(App):
    CSS = """
    Screen {
        background: #000000;
        layers: base overlay;
    }

    /* scroll */
    #scroll {
        background: #000000;
        height: 1fr;
        scrollbar-background: #000000;
        scrollbar-color: #2a2a2a;
        scrollbar-color-hover: #555555;
        scrollbar-color-active: #777777;
    }

    /* messages */
    #messages {
        background: #000000;
        height: auto;
        min-height: 100%;
        padding: 2 4 1 4;
    }

    /* home */
    #home-state {
        background: #000000;
        height: 100%;
        align: center middle;
    }
    #home-logo {
        color: #ffffff;
        background: #000000;
        content-align: center middle;
        width: 100%;
    }

    /* input section */
    #input-section {
        background: #000000;
        height: auto;
        padding: 0 0 1 0;
    }
    #input-box {
        background: #1a1a1a;
        height: auto;
        padding: 1 2 1 2;
    }
    ChatInput {
        background: #1a1a1a;
        border: none;
        padding: 0;
    }

    /* toolbar */
    #toolbar {
        background: #1a1a1a;
        height: 1;
        margin-top: 1;
    }
    #attach-btn {
        background: #1a1a1a;
        color: #505050;
        border: none;
        height: 1;
        min-width: 2;
        width: auto;
        padding: 0 1 0 0;
    }
    #attach-btn:hover { color: #aaaaaa; background: #1a1a1a; }
    #attach-btn:focus { border: none;   background: #1a1a1a; }

    #attach-label {
        color: #606060;
        background: #1a1a1a;
        width: auto;
        height: 1;
    }
    #right-controls {
        dock: right;
        width: auto;
        height: 1;
        background: #1a1a1a;
    }
    #model-btn {
        background: #1a1a1a;
        color: #505050;
        border: none;
        height: 1;
        width: auto;
        padding: 0 2 0 0;
    }
    #model-btn:hover { color: #aaaaaa; background: #1a1a1a; }
    #model-btn:focus { border: none;   background: #1a1a1a; }
    #action-btn {
        background: #1a1a1a;
        color: #303030;
        border: none;
        height: 1;
        width: auto;
        min-width: 1;
        padding: 0;
    }
    #action-btn.can-send  { color: #888888; }
    #action-btn.thinking  { color: #666666; }
    #action-btn:hover     { background: #1a1a1a; }
    #action-btn:focus     { border: none; background: #1a1a1a; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit",       show=False),
        Binding("ctrl+l", "clear_chat", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.conversation: list[dict] = []
        self.model_idx: int = 0
        self.attachment_path: Path | None = None
        self.attachment_content: str = ""
        self.is_thinking: bool = False
        self._dot_timer = None
        self._dot_bright: bool = False
        self._active_cosmos: CosmosMessage | None = None
        self._stream_worker = None

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="scroll"):
            with Vertical(id="messages"):
                with Vertical(id="home-state"):
                    yield Static(LOGO, id="home-logo", markup=False)
        with Vertical(id="input-section"):
            with Vertical(id="input-box"):
                yield ChatInput(id="main-input")
                with Horizontal(id="toolbar"):
                    yield Button("+", id="attach-btn")
                    yield Label("", id="attach-label")
                    with Horizontal(id="right-controls"):
                        yield Button(FREE_MODELS[0][1], id="model-btn")
                        yield Button("▶", id="action-btn")

    def on_mount(self) -> None:
        self.query_one("#main-input", ChatInput).focus()

    # ── send ──────────────────────────────────────────────────────────────────

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        text = event.value.strip()
        if not text or self.is_thinking:
            return
        event.input.clear()
        self._send(text)

    def on_user_message_edit_requested(self, event: UserMessage.EditRequested) -> None:
        if self.is_thinking:
            return
        messages = self.query_one("#messages", Vertical)
        msg_widgets = [c for c in messages.children if c.id != "home-state"]
        try:
            idx = msg_widgets.index(event.widget)
        except ValueError:
            return
        for w in msg_widgets[idx:]:
            w.remove()
        self.conversation = self.conversation[:idx]
        if not self.conversation:
            try:
                self.query_one("#home-state").display = True
            except Exception:
                pass
        inp = self.query_one("#main-input", ChatInput)
        inp.load_text(event.text)
        inp.move_cursor(inp.document.end)
        inp.focus()
        self._update_action_btn()

    def _send(self, text: str) -> None:
        messages = self.query_one("#messages", Vertical)

        try:
            self.query_one("#home-state").display = False
        except Exception:
            pass

        messages.mount(UserMessage(text))

        content = text
        if self.attachment_path and self.attachment_content:
            content = (
                f"[Attached file: {self.attachment_path.name}]\n"
                f"```\n{self.attachment_content}\n```\n\n"
                f"{text}"
            )
            self._clear_attachment()

        self.conversation.append({"role": "user", "content": content})

        cosmos = CosmosMessage()
        messages.mount(cosmos)
        self._active_cosmos = cosmos

        self.is_thinking = True
        self.query_one("#main-input", ChatInput).disabled = True
        self._update_action_btn()
        self._start_dot(cosmos)
        self._scroll_end()
        self._stream_worker = self._stream(cosmos)

    # ── streaming ─────────────────────────────────────────────────────────────

    @work
    async def _stream(self, cosmos: CosmosMessage) -> None:
        # Build fallback chain: selected → GPT OSS 120B → rest of free models
        primary = FREE_MODELS[self.model_idx]
        gpt_oss = next((m for m in FREE_MODELS if m[0] == "openai/gpt-oss-120b:free"), None)
        seen: set[str] = {primary[0]}
        model_queue = [primary]
        if gpt_oss and gpt_oss[0] not in seen:
            model_queue.append(gpt_oss)
            seen.add(gpt_oss[0])
        for m in FREE_MODELS:
            if m[0] not in seen:
                model_queue.append(m)
                seen.add(m[0])

        accumulated = ""
        streaming = True

        async def _render_loop() -> None:
            last = ""
            while streaming or accumulated != last:
                if accumulated != last:
                    last = accumulated
                    await cosmos.stream_append(last)
                    self._scroll_end()
                await asyncio.sleep(0.08)

        render_task = asyncio.create_task(_render_loop())

        for i, (model_id, model_name) in enumerate(model_queue):
            if i > 0:
                accumulated = f"Switching to {model_name}…"

            accumulated = ""

            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST", API_URL,
                        headers={
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_id,
                            "messages": self.conversation,
                            "stream": True,
                        },
                    ) as response:
                        if response.status_code != 200:
                            continue
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            payload = line[6:]
                            if payload == "[DONE]":
                                break
                            try:
                                obj = json.loads(payload)
                                if "error" in obj:
                                    break
                                token = obj["choices"][0]["delta"].get("content") or ""
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                            if token:
                                accumulated += token
            except Exception:
                continue

            if accumulated:
                break  # got a response — stop trying models

        streaming = False
        await render_task  # let the render loop flush the final state

        if not accumulated:
            accumulated = "[All models failed. Please try again later.]"
            await cosmos.stream_append(accumulated)

        self.conversation.append({"role": "assistant", "content": accumulated})

        self.is_thinking = False
        self._stream_worker = None
        self._stop_dot(cosmos)
        self._active_cosmos = None
        inp = self.query_one("#main-input", ChatInput)
        inp.disabled = False
        inp.focus()
        self._update_action_btn()
        self._scroll_end()

    # ── dot (inside CosmosMessage) ────────────────────────────────────────────

    def _start_dot(self, cosmos: CosmosMessage) -> None:
        self._dot_bright = False
        cosmos.start_dot()
        self._dot_timer = self.set_interval(0.5, lambda: self._pulse_dot(cosmos))

    def _pulse_dot(self, cosmos: CosmosMessage) -> None:
        self._dot_bright = not self._dot_bright
        try:
            cosmos.pulse_dot(self._dot_bright)
        except Exception:
            pass

    def _stop_dot(self, cosmos: CosmosMessage) -> None:
        if self._dot_timer:
            self._dot_timer.stop()
            self._dot_timer = None
        try:
            cosmos.finish_dot()
            self.set_timer(1.5, cosmos.idle_dot)
        except Exception:
            pass

    # ── buttons ───────────────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._update_action_btn()

    def _update_action_btn(self) -> None:
        try:
            btn = self.query_one("#action-btn", Button)
            if self.is_thinking:
                btn.label = "■"
                btn.remove_class("can-send")
                btn.add_class("thinking")
            else:
                btn.label = "▶"
                btn.remove_class("thinking")
                inp = self.query_one("#main-input", ChatInput)
                if inp.text.strip():
                    btn.add_class("can-send")
                else:
                    btn.remove_class("can-send")
        except Exception:
            pass

    def _cancel_stream(self) -> None:
        if self._stream_worker:
            self._stream_worker.cancel()
            self._stream_worker = None
        self.is_thinking = False
        if self._dot_timer:
            self._dot_timer.stop()
            self._dot_timer = None
        if self._active_cosmos:
            try:
                self._active_cosmos.finish_dot()
                self.set_timer(1.5, self._active_cosmos.idle_dot)
            except Exception:
                pass
            self._active_cosmos = None
        inp = self.query_one("#main-input", ChatInput)
        inp.disabled = False
        inp.focus()
        self._update_action_btn()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "attach-btn":
            event.stop()
            if self.attachment_path:
                self._clear_attachment()
            else:
                self._pick_file()
        elif btn_id == "model-btn":
            event.stop()
            self.push_screen(ModelDropdown(), self._on_model_selected)
        elif btn_id == "action-btn":
            event.stop()
            if self.is_thinking:
                self._cancel_stream()
            else:
                inp = self.query_one("#main-input", ChatInput)
                text = inp.text.strip()
                if text:
                    inp.clear()
                    self._send(text)

    @work
    async def _pick_file(self) -> None:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", "POSIX path of (choose file)"],
            capture_output=True,
            text=True,
        )
        path_str = result.stdout.strip()
        if path_str:
            self._on_file_selected(Path(path_str))

    # ── attach ────────────────────────────────────────────────────────────────

    def _on_file_selected(self, path: Path | None) -> None:
        if path is None:
            return
        try:
            content = path.read_text(errors="replace")
            if len(content) > 50_000:
                content = content[:50_000] + "\n[... truncated ...]"
            self.attachment_path = path
            self.attachment_content = content
            self.query_one("#attach-label", Label).update(f" {path.name}")
            self.query_one("#attach-btn", Button).label = "✕"
        except Exception as exc:
            self.query_one("#attach-label", Label).update(f" [!] {exc}")

    def _clear_attachment(self) -> None:
        self.attachment_path = None
        self.attachment_content = ""
        self.query_one("#attach-btn", Button).label = "+"
        self.query_one("#attach-label", Label).update("")

    # ── model ─────────────────────────────────────────────────────────────────

    def _on_model_selected(self, idx: int | None) -> None:
        if idx is None:
            return
        self.model_idx = idx
        self.query_one("#model-btn", Button).label = FREE_MODELS[idx][1]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scroll_end(self) -> None:
        def do_scroll() -> None:
            try:
                scroll = self.query_one("#scroll", ScrollableContainer)
                gap = scroll.max_scroll_y - scroll.scroll_y
                if gap <= scroll.size.height // 2:
                    scroll.scroll_end(animate=False)
            except Exception:
                pass
        self.call_after_refresh(do_scroll)

    def action_clear_chat(self) -> None:
        self.conversation.clear()
        self.is_thinking = False
        if self._dot_timer:
            self._dot_timer.stop()
            self._dot_timer = None
        self._active_cosmos = None
        messages = self.query_one("#messages", Vertical)
        for child in list(messages.children):
            if child.id != "home-state":
                child.remove()
        try:
            self.query_one("#home-state").display = True
        except Exception:
            pass
        self._clear_attachment()


if __name__ == "__main__":
    CosmosApp().run()
