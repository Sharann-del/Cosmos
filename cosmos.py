"""COSMOS — streaming terminal AI chat."""
from __future__ import annotations

import asyncio
import base64
import colorsys
import json
import math
import mimetypes
import os
import random
import re
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.style import Style
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalGroup,
    VerticalScroll,
)
from textual.events import Click, Enter, Leave, Resize
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.content import Content
from textual.widgets import (
    Button, Input, Label,
    ListItem, ListView, Markdown, Static, TextArea,
)
from textual.widgets._markdown import MarkdownFence
from textual.widgets.text_area import TextAreaTheme
from textual import work

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
SESSION_PATH = Path.home() / ".cosmos" / "session.json"
COSMOS_API_BASE = "https://cosmos-tui.app/api"

FOLDER_ICON_CLOSED = "▶"
FOLDER_ICON_OPEN = "▼"
CHAT_ICON = "·"
SIDEBAR_INDENT_COLS = 3

# Plain ASCII action labels (Buttons hid label text in some terminals)
LABEL_COPY = "copy"
LABEL_COPIED = "ok!"
LABEL_REGEN = "retry"

_GLITCH_CHARS = "▓▒░▄▀▌▐╬╪╫╋▕▔╱╲╳"
_PARTICLE_CHARS = "·∙⋆·∙·∙·"

_ACTION_LABEL_CSS = """
.action-label {
    width: auto;
    height: 1;
    color: #888888;
    background: transparent;
    text-style: bold;
    padding: 0 1;
}
.action-label:hover { color: #eeeeee; text-style: bold underline; pointer: default; }
"""


def _copy_to_clipboard(text: str) -> None:
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    except Exception:
        pass


def _flash_copy_label(label: Label) -> None:
    label.update(LABEL_COPIED)
    label.set_timer(1.5, lambda: label.update(LABEL_COPY))


MAX_ATTACH_TEXT_CHARS = 50_000
MAX_ATTACH_IMAGE_BYTES = 5_000_000

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".heif",
})

TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".xml", ".html", ".htm", ".css", ".scss", ".sql",
    ".py", ".pyw", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".go", ".rs", ".rb", ".php", ".swift", ".m",
    ".mm", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".fs", ".lua", ".r",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd", ".toml",
    ".ini", ".cfg", ".conf", ".env", ".log", ".tex", ".bib", ".dockerfile",
    ".makefile", ".gradle", ".svelte", ".vue", ".zig", ".v", ".asm",
    ".tf", ".hcl", ".nix", ".plist", ".rtf",
})

_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_CONTENT_JSON_PREFIX = '{"cosmos_content":'


@dataclass
class FileAttachment:
    path: Path
    kind: str
    text_excerpt: str = ""
    image_b64: str | None = None
    image_mime: str | None = None


def _truncate_text(text: str, limit: int = MAX_ATTACH_TEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[... truncated ...]"


def _read_text_bytes(raw: bytes) -> str:
    if b"\x00" in raw[:8192]:
        raise ValueError("Binary file cannot be read as text")
    return raw.decode("utf-8", errors="replace")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None  # type: ignore[misc, assignment]
    if PdfReader is not None:
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    raise ValueError(
        "Could not extract PDF text (install pypdf: pip install pypdf)"
    )


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid DOCX: {path.name}") from exc
    root = ET.fromstring(xml_bytes)
    tag = f"{{{_DOCX_NS['w']}}}t"
    chunks: list[str] = []
    for node in root.iter(tag):
        if node.text:
            chunks.append(node.text)
        if node.tail:
            chunks.append(node.tail)
    text = "".join(chunks).strip()
    if not text:
        raise ValueError(f"No text found in {path.name}")
    return text


def _image_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("image/"):
        return mime
    ext = path.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "svg":
        return "image/svg+xml"
    return f"image/{ext or 'png'}"


def extract_file_attachment(path: Path) -> FileAttachment:
    """Read file content for chat: text/code, PDF, DOCX, or base64 image."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        raw = path.read_bytes()
        if len(raw) > MAX_ATTACH_IMAGE_BYTES:
            raise ValueError(
                f"Image too large (max {MAX_ATTACH_IMAGE_BYTES // 1_000_000} MB)"
            )
        mime = _image_mime(path)
        return FileAttachment(
            path=path,
            kind="image",
            text_excerpt=f"[Image: {path.name}]",
            image_b64=base64.standard_b64encode(raw).decode("ascii"),
            image_mime=mime,
        )

    if suffix == ".pdf":
        text = _truncate_text(_extract_pdf_text(path))
        return FileAttachment(path=path, kind="text", text_excerpt=text)

    if suffix == ".docx":
        text = _truncate_text(_extract_docx_text(path))
        return FileAttachment(path=path, kind="text", text_excerpt=text)

    if suffix in TEXT_EXTENSIONS or not suffix:
        text = _truncate_text(_read_text_bytes(path.read_bytes()))
        return FileAttachment(path=path, kind="text", text_excerpt=text)

    raw = path.read_bytes()
    if suffix in (".doc", ".xls", ".xlsx", ".ppt", ".pptx"):
        raise ValueError(
            f"Unsupported format {suffix} (try PDF, DOCX, or plain text)"
        )
    try:
        text = _truncate_text(_read_text_bytes(raw))
    except ValueError as exc:
        raise ValueError(
            f"Unsupported file type: {path.name}"
        ) from exc
    return FileAttachment(path=path, kind="text", text_excerpt=text)


def attachment_display_text(user_text: str, att: FileAttachment | None) -> str:
    if not att:
        return user_text
    label = (
        f"[Attached image: {att.path.name}]"
        if att.kind == "image"
        else f"[Attached file: {att.path.name}]"
    )
    if user_text.strip():
        return f"{label}\n\n{user_text}"
    return label


def build_user_message_content(
    user_text: str,
    att: FileAttachment | None,
) -> str | list[dict]:
    if not att:
        return user_text

    if att.kind == "image" and att.image_b64 and att.image_mime:
        parts: list[dict] = []
        prompt = user_text.strip() or (
            f"Describe and analyze this image ({att.path.name})."
        )
        parts.append({"type": "text", "text": prompt})
        parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{att.image_mime};base64,{att.image_b64}",
            },
        })
        return parts

    file_block = (
        f"[Attached file: {att.path.name}]\n```\n{att.text_excerpt}\n```"
    )
    body = f"{file_block}\n\n{user_text}" if user_text.strip() else file_block
    return body


def serialize_message_content(content: str | list[dict]) -> str:
    if isinstance(content, list):
        return json.dumps({"cosmos_content": content}, ensure_ascii=False)
    return content


def deserialize_message_content(raw: str) -> str | list[dict]:
    if raw.startswith(_CONTENT_JSON_PREFIX):
        try:
            obj = json.loads(raw)
            parts = obj.get("cosmos_content")
            if isinstance(parts, list):
                return parts
        except json.JSONDecodeError:
            pass
    return raw


def message_content_for_display(content: str | list[dict]) -> str:
    if isinstance(content, str):
        content = deserialize_message_content(content)
    if isinstance(content, str):
        return content
    lines: list[str] = []
    for part in content:
        if part.get("type") == "text":
            lines.append(part.get("text", ""))
        elif part.get("type") == "image_url":
            lines.append("[Image attached]")
    return "\n".join(lines).strip()


FREE_MODELS: list[tuple[str, str]] = [
    ("openrouter/free",                                    "Auto (Best Free)"),
    ("openrouter/owl-alpha",                               "Owl Alpha"),
    ("cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "Dolphin Mistral 24B"),
    ("liquid/lfm-2.5-1.2b-instruct:free",                 "LFM 2.5 1.2B"),
    ("nvidia/nemotron-3-nano-30b-a3b:free",               "Nemotron 3 Nano 30B"),
    ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free","Nemotron 3 Nano Omni 30B"),
    ("nvidia/nemotron-3-super-120b-a12b:free",            "Nemotron 3 Super 120B"),
    ("nvidia/nemotron-nano-12b-v2-vl:free",               "Nemotron Nano 12B VL"),
    ("nvidia/nemotron-nano-9b-v2:free",                   "Nemotron Nano 9B"),
    ("poolside/laguna-m.1:free",                          "Laguna M.1"),
    ("poolside/laguna-xs.2:free",                         "Laguna XS.2"),
]

DEFAULT_CONTEXT_TOKENS = 128_000
MODEL_CONTEXT_TOKENS: dict[str, int] = {
    "openrouter/free":                                     200_000,
    "openrouter/owl-alpha":                                1_000_000,
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": 33_000,
    "liquid/lfm-2.5-1.2b-instruct:free":                  33_000,
    "nvidia/nemotron-3-nano-30b-a3b:free":                 256_000,
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free":  256_000,
    "nvidia/nemotron-3-super-120b-a12b:free":              1_000_000,
    "nvidia/nemotron-nano-12b-v2-vl:free":                 128_000,
    "nvidia/nemotron-nano-9b-v2:free":                     128_000,
    "poolside/laguna-m.1:free":                            262_000,
    "poolside/laguna-xs.2:free":                           262_000,
}


def _format_token_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


MAX_CHAT_TITLE_LEN = 40
MAX_CHAT_TITLE_WORDS = 6


def _normalize_generated_title(
    raw: str,
    max_len: int = MAX_CHAT_TITLE_LEN,
    max_words: int = MAX_CHAT_TITLE_WORDS,
) -> str:
    title = raw.strip().strip("\"'").split("\n")[0].strip()
    title = " ".join(title.split())
    title = title.rstrip(".,!?;:")
    if not title:
        return "New chat"
    words = title.split()
    if len(words) > max_words:
        title = " ".join(words[:max_words])
    if len(title) <= max_len:
        return title
    cut = title[:max_len].rsplit(" ", 1)[0].strip()
    return cut or title[:max_len].strip()


_TITLE_SKIP_WORDS = frozenset({
    "a", "an", "the", "i", "me", "my", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "can", "may", "might",
    "what", "how", "why", "when", "where", "who", "which", "please", "help",
    "explain", "tell", "give", "show", "write", "create", "make", "describe", "define",
    "around", "about", "words", "word", "need", "want", "like", "just", "also",
})

_TITLE_MODELS = [
    "openrouter/free",
    "nvidia/nemotron-nano-9b-v2:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "poolside/laguna-xs.2:free",
]


def _title_from_message(text: str) -> str:
    """Local fallback: extract topic words, not the raw prompt."""
    line = text.strip().split("\n")[0]
    lower = line.lower()
    for marker in (" about ", " on ", " regarding ", " for "):
        if marker in lower:
            line = line[lower.index(marker) + len(marker) :].strip()
            break

    words: list[str] = []
    for word in line.split():
        clean = word.strip(".,!?;:\"'").lower()
        if clean.isdigit():
            continue
        if clean in _TITLE_SKIP_WORDS:
            continue
        words.append(word.strip(".,!?;:\"'"))

    if not words:
        words = [w.strip(".,!?;:\"'") for w in line.split() if w.strip(".,!?;:\"'")]

    return _normalize_generated_title(" ".join(words[:MAX_CHAT_TITLE_WORDS]))


def _fetch_title_from_llm(message: str) -> str | None:
    """Ask the model for a short descriptive chat title."""
    if not API_KEY:
        return None
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Generate a short chat title (1-6 words) summarizing the user's "
                    "message. Output only the title, no quotes or punctuation."
                ),
            },
            {"role": "user", "content": message[:800]},
        ],
        "max_tokens": 16,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30) as client:
            for model_id in _TITLE_MODELS:
                try:
                    resp = client.post(
                        API_URL,
                        headers=headers,
                        json={**payload, "model": model_id},
                    )
                    if resp.status_code in (429, 503):
                        continue
                    resp.raise_for_status()
                    raw = resp.json()["choices"][0]["message"]["content"]
                    if raw and raw.strip():
                        return _normalize_generated_title(raw)
                except Exception:
                    continue
    except Exception:
        pass
    return None


# ── session ─────────────────────────────────────────────────────────────────────

def _load_session() -> dict:
    try:
        return json.loads(SESSION_PATH.read_text())
    except Exception:
        return {}


def _save_session(data: dict) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(data, indent=2))


# ── login screen ───────────────────────────────────────────────────────────────

class LoginScreen(ModalScreen):
    CSS = """
    LoginScreen {
        align: center middle;
    }
    #login-box {
        width: 46;
        height: auto;
        background: #000000;
        padding: 3 4;
    }
    #login-title {
        color: #cccccc;
        text-style: bold;
        content-align: center middle;
        width: 100%;
        margin-bottom: 3;
    }
    #login-email, #login-password {
        background: #111111;
        color: #d0d0d0;
        border: none;
        width: 100%;
        height: 3;
        margin-bottom: 2;
        padding: 1 1;
        scrollbar-size-horizontal: 0;
        scrollbar-size-vertical: 0;
    }
    #login-email:focus, #login-password:focus {
        background: #161616;
        border: none;
    }
    #login-btn {
        background: #1e1e1e;
        color: #888888;
        border: none;
        width: 100%;
        height: 3;
        margin-top: 1;
        content-align: center middle;
    }
    #login-btn { pointer: default; }
    #login-btn:hover { color: #eeeeee; background: #2a2a2a; }
    #login-error {
        color: #884444;
        width: 100%;
        height: 1;
        content-align: center middle;
        margin-top: 1;
    }

    /* light mode */
    LoginScreen:light #login-box            { background: #ffffff; border: solid #dddddd; }
    LoginScreen:light #login-title          { color: #333333; }
    LoginScreen:light #login-email,
    LoginScreen:light #login-password       { background: #ffffff; color: #1a1a1a; }
    LoginScreen:light #login-email:focus,
    LoginScreen:light #login-password:focus { background: #f8f8f8; border: none; }
    LoginScreen:light #login-btn            { background: #e0e0e0; color: #444444; border: none; }
    LoginScreen:light #login-btn:hover      { background: #cccccc; color: #111111; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Label("COSMOS", id="login-title")
            yield Input(placeholder="email", id="login-email")
            yield Input(placeholder="password", password=True, id="login-password")
            yield Button("sign in", id="login-btn")
            yield Label("", id="login-error")

    def on_mount(self) -> None:
        is_dark = "dark" in self.app.pseudo_classes
        self.styles.background = "#111111" if is_dark else "#f0f0f0"
        self.query_one("#login-email", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login-btn":
            self._do_login()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._do_login()

    def _do_login(self) -> None:
        email = self.query_one("#login-email", Input).value.strip()
        password = self.query_one("#login-password", Input).value
        if not email or not password:
            return
        btn = self.query_one("#login-btn", Button)
        btn.disabled = True
        btn.label = "signing in…"
        self._login_worker(email, password)

    @work(thread=True)
    def _login_worker(self, email: str, password: str) -> None:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{COSMOS_API_BASE}/auth/login",
                    json={"email": email, "password": password},
                )
                if resp.status_code == 401:
                    raise Exception("Invalid email or password.")
                resp.raise_for_status()
                data = resp.json()
            session = {
                "token": data["token"],
                "user": data["user"],
            }
            _save_session(session)
            self.app.call_from_thread(self.dismiss, session)
        except Exception as exc:
            def _show_err():
                try:
                    self.query_one("#login-error", Label).update(str(exc)[:60])
                    b = self.query_one("#login-btn", Button)
                    b.disabled = False
                    b.label = "sign in"
                except Exception:
                    pass
            self.app.call_from_thread(_show_err)


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

    def __init__(self, models: list[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._models = models

    def compose(self) -> ComposeResult:
        with Vertical():
            with ListView(id="model-list"):
                for model_id, name in self._models:
                    item = ListItem(Label(name))
                    if model_id == "ollama:---":
                        item.disabled = True
                    yield item

    def on_mount(self) -> None:
        self.styles.background = "rgba(0,0,0,0)"
        lv = self.query_one(ListView)
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        try:
            label_text = str(event.item.query_one(Label).renderable)
            for i, (mid, name) in enumerate(self._models):
                if mid == "ollama:---":
                    continue
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


class SidebarFloatingMenu(Vertical):
    """Compact context menu mounted on the app overlay at the ⋮ button."""

    def __init__(
        self,
        entry_type: str,
        anchor_x: int,
        anchor_y: int,
        row: "SidebarEntryRow",
        **kwargs,
    ) -> None:
        super().__init__(id="sidebar-floating-menu", **kwargs)
        self.entry_type = entry_type
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._row = row

    DEFAULT_CSS = """
    SidebarFloatingMenu {
        width: 22;
        height: auto;
        background: #141414;
        border: solid #2a2a2a;
        layer: overlay;
        padding: 0;
    }
    SidebarFloatingMenu .sidebar-menu-act {
        height: 1;
        width: 100%;
        padding: 0 1;
        color: #d0d0d0;
        background: transparent;
        content-align: left middle;
    }
    SidebarFloatingMenu .sidebar-menu-act:hover {
        background: #2a2a2a;
        color: #ffffff;
    }
    SidebarFloatingMenu .sidebar-menu-act.-danger {
        color: #c08080;
    }
    SidebarFloatingMenu .sidebar-menu-act.-danger:hover {
        color: #ffaaaa;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Rename", id="act-rename", classes="sidebar-menu-act")
        if self.entry_type == "folder":
            yield Label("New subfolder", id="act-subfolder", classes="sidebar-menu-act")
        if self.entry_type == "chat":
            yield Label("Move to folder", id="act-move", classes="sidebar-menu-act")
        yield Label("Delete", id="act-delete", classes="sidebar-menu-act -danger")

    def on_mount(self) -> None:
        self.styles.offset = (self._anchor_x, self._anchor_y)

    def on_click(self, event: Click) -> None:
        app = self.app
        if not isinstance(app, CosmosApp):
            return
        tid = getattr(event.widget, "id", None)
        if tid == "act-rename":
            event.stop()
            app._close_floating_menu()
            if self.entry_type == "chat":
                app._rename_chat_entry(self._row)
            else:
                app._rename_folder_entry(self._row)
        elif tid == "act-subfolder":
            event.stop()
            app._close_floating_menu()
            app._new_subfolder(self._row.entry_id)
        elif tid == "act-move":
            event.stop()
            app._schedule_folder_picker(self._row)
        elif tid == "act-delete":
            event.stop()
            app._close_floating_menu()
            if self.entry_type == "chat":
                app._delete_chat(self._row.entry_id)
            else:
                app._delete_folder(self._row.entry_id)


class SidebarFolderFloatingMenu(Vertical):
    """Folder picker floating at the same ⋮ anchor."""

    def __init__(
        self,
        folder_entries: list[tuple[str | None, str, int]],
        anchor_x: int,
        anchor_y: int,
        row: "SidebarEntryRow",
        **kwargs,
    ) -> None:
        super().__init__(id="sidebar-folder-menu", **kwargs)
        self._folder_entries = folder_entries
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._row = row

    DEFAULT_CSS = """
    SidebarFolderFloatingMenu {
        width: 22;
        height: auto;
        max-height: 10;
        background: #141414;
        border: solid #2a2a2a;
        layer: overlay;
        padding: 0;
        overflow-y: auto;
    }
    SidebarFolderFloatingMenu .sidebar-menu-act {
        height: 1;
        width: 100%;
        padding: 0 1;
        color: #d0d0d0;
        background: transparent;
        content-align: left middle;
    }
    SidebarFolderFloatingMenu .sidebar-menu-act:hover {
        background: #2a2a2a;
        color: #ffffff;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Move to folder", classes="sidebar-menu-act")
        for fid, label, _depth in self._folder_entries:
            lid = "folder-none" if fid is None else f"folder-{fid}"
            yield Label(label[:22], id=lid, classes="sidebar-menu-act")

    def on_mount(self) -> None:
        self.styles.offset = (self._anchor_x, self._anchor_y)

    def on_click(self, event: Click) -> None:
        app = self.app
        if not isinstance(app, CosmosApp):
            return
        tid = getattr(event.widget, "id", None)
        if tid == "folder-none":
            event.stop()
            app._close_floating_menu()
            app._move_chat_to_folder(self._row.entry_id, None)
        elif tid and tid.startswith("folder-"):
            event.stop()
            app._close_floating_menu()
            app._move_chat_to_folder(
                self._row.entry_id,
                tid.removeprefix("folder-"),
            )


class NamePromptScreen(ModalScreen[str | None]):
    """Small modal to name a new folder (or other sidebar item)."""

    def __init__(
        self,
        heading: str,
        placeholder: str = "",
        confirm_label: str = "Create",
        *,
        initial_value: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._heading = heading
        self._placeholder = placeholder
        self._confirm_label = confirm_label
        self._initial_value = initial_value

    CSS = """
    NamePromptScreen {
        background: #000000 60%;
        align: center middle;
    }
    #name-prompt-box {
        width: 44;
        height: auto;
        background: #0e0e0e;
        border: solid #2a2a2a;
        padding: 2 3;
    }
    #name-prompt-title {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    #name-prompt-input {
        background: #1a1a1a;
        color: #d0d0d0;
        border: none;
        width: 100%;
        margin-bottom: 1;
    }
    #name-prompt-input:focus { background: #222222; border: none; }
    #name-prompt-actions {
        width: 100%;
        height: 1;
        background: transparent;
    }
    #name-prompt-create {
        background: #1a1a1a;
        color: #888888;
        border: none;
        width: 1fr;
        margin-right: 1;
    }
    #name-prompt-create, #name-prompt-cancel { pointer: default; }
    #name-prompt-create:hover { color: #eeeeee; background: #252525; }
    #name-prompt-cancel {
        background: #1a1a1a;
        color: #555555;
        border: none;
        width: auto;
        min-width: 10;
    }
    #name-prompt-cancel:hover { color: #aaaaaa; background: #252525; }
    #name-prompt-error {
        color: #884444;
        width: 100%;
        height: 1;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="name-prompt-box"):
            yield Label(self._heading, id="name-prompt-title")
            yield Input(placeholder=self._placeholder, id="name-prompt-input")
            with Horizontal(id="name-prompt-actions"):
                yield Button(self._confirm_label, id="name-prompt-create")
                yield Button("Cancel", id="name-prompt-cancel")
            yield Label("", id="name-prompt-error")

    def on_mount(self) -> None:
        inp = self.query_one("#name-prompt-input", Input)
        if self._initial_value:
            inp.value = self._initial_value
        inp.focus()
        if self._initial_value:
            try:
                inp.action_select_all()
            except Exception:
                pass

    def _submit(self) -> None:
        name = self.query_one("#name-prompt-input", Input).value.strip()
        if not name:
            self.query_one("#name-prompt-error", Label).update("Enter a name.")
            return
        self.dismiss(name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "name-prompt-create":
            self._submit()
        elif event.button.id == "name-prompt-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "name-prompt-input":
            self._submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ── api key setup screen ───────────────────────────────────────────────────────

class ApiKeyScreen(ModalScreen[str | None]):
    """Modal shown when no OpenRouter API key is configured."""

    CSS = """
    ApiKeyScreen {
        background: #000000 60%;
        align: center middle;
    }
    #apikey-box {
        width: 52;
        height: auto;
        background: #0e0e0e;
        border: solid #2a2a2a;
        padding: 2 3;
    }
    #apikey-title {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    #apikey-sub {
        color: #555555;
        width: 100%;
        margin-bottom: 1;
    }
    #apikey-input {
        background: #1a1a1a;
        color: #d0d0d0;
        border: none;
        width: 100%;
        margin-bottom: 1;
    }
    #apikey-input:focus { background: #222222; border: none; }
    #apikey-actions {
        width: 100%;
        height: 1;
        background: transparent;
    }
    #apikey-save {
        background: #1a1a1a;
        color: #888888;
        border: none;
        width: 1fr;
        margin-right: 1;
    }
    #apikey-save, #apikey-cancel { pointer: default; }
    #apikey-save:hover { color: #eeeeee; background: #252525; }
    #apikey-cancel {
        background: #1a1a1a;
        color: #555555;
        border: none;
        width: auto;
        min-width: 10;
    }
    #apikey-cancel:hover { color: #aaaaaa; background: #252525; }
    #apikey-error {
        color: #884444;
        width: 100%;
        height: 1;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="apikey-box"):
            yield Label("OpenRouter API Key", id="apikey-title")
            yield Label("Get your free key at openrouter.ai/keys", id="apikey-sub")
            yield Input(placeholder="sk-or-...", password=True, id="apikey-input")
            with Horizontal(id="apikey-actions"):
                yield Button("Save", id="apikey-save")
                yield Button("Cancel", id="apikey-cancel")
            yield Label("", id="apikey-error")

    def on_mount(self) -> None:
        self.query_one("#apikey-input", Input).focus()

    def _submit(self) -> None:
        key = self.query_one("#apikey-input", Input).value.strip()
        if not key:
            self.query_one("#apikey-error", Label).update("Enter your API key.")
            return
        if not key.startswith("sk-"):
            self.query_one("#apikey-error", Label).update("Key should start with sk-")
            return
        self.dismiss(key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apikey-save":
            self._submit()
        elif event.button.id == "apikey-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "apikey-input":
            self._submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ── message widgets ────────────────────────────────────────────────────────────

class UserMessage(Vertical):
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
    UserMessage Static { color: #cccccc; background: transparent; height: auto; }
    UserMessage .action-label { dock: right; }
    """ + _ACTION_LABEL_CSS

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._msg_text = text

    def compose(self) -> ComposeResult:
        yield Static(self._msg_text)
        yield Label(LABEL_COPY, id="user-copy-btn", classes="action-label")

    def on_click(self, event: Click) -> None:
        if event.widget.id == "user-copy-btn":
            event.stop()
            _copy_to_clipboard(self._msg_text)
            _flash_copy_label(event.widget)
            return
        self.post_message(self.EditRequested(self, self._msg_text))


def _parse_mermaid_node(part: str) -> tuple[str, str] | None:
    part = part.strip()
    # node[label], node(label), node{label}, node((label))
    m = re.match(r"^(\w+)\s*[\[\(\{]+([^\]\)\}]+)[\]\)\}]+\s*$", part)
    if m:
        return m.group(1), m.group(2).strip()
    m = re.match(r"^(\w+)\s*$", part)
    if m:
        return m.group(1), m.group(1)
    return None


def _node_box(label: str, max_w: int = 28) -> str:
    text = label if len(label) <= max_w else label[:max_w - 1] + "…"
    w = len(text) + 2
    return f"╭{'─' * w}╮\n│ {text} │\n╰{'─' * w}╯"


def _mermaid_flowchart_ascii(src: str) -> str:
    """Render Mermaid flowchart/graph as terminal ASCII, supporting branching."""
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []  # (from, to, label)

    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        low = line.lower()
        if low.startswith(("flowchart ", "graph ", "style ", "class ", "classdef ", "subgraph", "end")):
            continue
        # edge with label: A -->|label| B  or  A -- label --> B
        m = re.match(r"^(.+?)\s*--\s*([^->]+?)\s*-->\s*(.+)$", line)
        if m:
            a = _parse_mermaid_node(m.group(1).strip())
            b = _parse_mermaid_node(m.group(3).strip())
            lbl = m.group(2).strip()
            if a and b:
                if a[0] not in nodes: nodes[a[0]] = a[1]
                if b[0] not in nodes: nodes[b[0]] = b[1]
                edges.append((a[0], b[0], lbl))
            continue
        m = re.match(r"^(.+?)\s*-->\|([^|]*)\|\s*(.+)$", line)
        if m:
            a = _parse_mermaid_node(m.group(1).strip())
            b = _parse_mermaid_node(m.group(3).strip())
            lbl = m.group(2).strip()
            if a and b:
                if a[0] not in nodes: nodes[a[0]] = a[1]
                if b[0] not in nodes: nodes[b[0]] = b[1]
                edges.append((a[0], b[0], lbl))
            continue
        if "-->" not in line:
            continue
        parts = re.split(r"\s*-->\s*", line)
        for left, right in zip(parts[:-1], parts[1:]):
            a = _parse_mermaid_node(left)
            b = _parse_mermaid_node(right)
            if a and b:
                if a[0] not in nodes: nodes[a[0]] = a[1]
                if b[0] not in nodes: nodes[b[0]] = b[1]
                edges.append((a[0], b[0], ""))

    if not edges:
        return src.strip()

    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: set[str] = set()
    for a, b, lbl in edges:
        outgoing[a].append((b, lbl))
        incoming.add(b)

    starts = [n for n in nodes if n not in incoming]
    root = starts[0] if starts else edges[0][0]

    out: list[str] = []

    def _render(node_id: str, visited: set[str], indent: int = 0) -> None:
        pad = "  " * indent
        label = nodes.get(node_id, node_id)
        for line in _node_box(label).splitlines():
            out.append(pad + line)
        if node_id in visited:
            out.append(pad + "  ↺ (loop)")
            return
        visited = visited | {node_id}
        children = outgoing.get(node_id, [])
        if not children:
            return
        if len(children) == 1:
            child_id, lbl = children[0]
            connector = f"  │  {lbl}" if lbl else "  │"
            out.append(pad + connector)
            out.append(pad + "  ↓")
            _render(child_id, visited, indent)
        else:
            for i, (child_id, lbl) in enumerate(children):
                branch_marker = "  ├─" if i < len(children) - 1 else "  └─"
                arrow = f"{branch_marker} {lbl} ─→" if lbl else f"{branch_marker}──→"
                out.append(pad + arrow)
                _render(child_id, visited, indent + 2)
                if i < len(children) - 1:
                    out.append("")

    _render(root, set())
    return "\n".join(out)


def _mermaid_sequence_ascii(src: str) -> str:
    """Render a Mermaid sequenceDiagram as terminal ASCII."""
    actors: list[str] = []
    aliases: dict[str, str] = {}
    messages: list[tuple[str, str, str, str]] = []  # (from, to, arrow, text)
    notes: list[tuple[int, str, str]] = []  # (msg_index, actor, text)

    for line in src.splitlines():
        line = line.strip()
        if not line or line.startswith("%%") or line.lower().startswith("sequencediagram"):
            continue
        m = re.match(r"(?:participant|actor)\s+(\w[\w\s]*?)\s+as\s+(.+)", line, re.IGNORECASE)
        if m:
            key = m.group(1).strip()
            aliases[key] = m.group(2).strip()
            if key not in actors:
                actors.append(key)
            continue
        m = re.match(r"(?:participant|actor)\s+(\w[\w\s]*)", line, re.IGNORECASE)
        if m:
            key = m.group(1).strip()
            if key not in actors:
                actors.append(key)
            continue
        m = re.match(r"Note\s+(?:over|left of|right of)\s+(\w[\w\s,]*)\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            notes.append((len(messages), m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.match(r"(\w[\w\s]*?)\s*(->>|-->>|->|-->|-x|--x)\s*(\w[\w\s]*?)\s*:\s*(.+)", line)
        if m:
            frm = m.group(1).strip()
            arr = m.group(2)
            to = m.group(3).strip()
            text = m.group(4).strip()
            for actor in (frm, to):
                if actor not in actors:
                    actors.append(actor)
            messages.append((frm, to, arr, text))

    if not messages:
        return src.strip()

    col_w = 14
    def _actor_display(a: str) -> str:
        name = aliases.get(a, a)
        return name[:col_w - 2]

    header_parts = []
    for a in actors:
        name = _actor_display(a)
        pad = col_w - len(name)
        header_parts.append(name + " " * pad)
    header = "".join(header_parts).rstrip()

    sep = ("─" * (col_w - 1) + "┬").join([""] * (len(actors) + 1))
    lines_out: list[str] = [header, "─" * len(header)]

    actor_col = {a: i * col_w + col_w // 2 for i, a in enumerate(actors)}
    total_w = len(actors) * col_w

    def _lifeline_row(highlight: set[int] | None = None) -> str:
        row = [" "] * total_w
        for i, a in enumerate(actors):
            c = actor_col[a]
            if c < total_w:
                row[c] = "│"
        if highlight:
            for c in highlight:
                if 0 <= c < total_w:
                    row[c] = "│"
        return "".join(row).rstrip()

    note_map: dict[int, tuple[str, str]] = {idx: (a, t) for idx, a, t in notes}
    max_msg_w = 24

    for i, (frm, to, arr, text) in enumerate(messages):
        if i in note_map:
            _, note_text = note_map[i]
            lines_out.append(_lifeline_row())
            lines_out.append(f"  ┌─ {note_text[:max_msg_w]} ─┐")

        lines_out.append(_lifeline_row())
        fc = actor_col.get(frm, 0)
        tc = actor_col.get(to, 0)
        dashed = arr.startswith("--")
        label = text[:max_msg_w]
        if frm == to:
            row = list(_lifeline_row())
            if fc < total_w - 2:
                row[fc] = "├"
                for j in range(fc + 1, min(fc + 5, total_w)):
                    row[j] = "─"
            lines_out.append("".join(row).rstrip() + f" {label}")
        elif fc < tc:
            dash = "─" if not dashed else "╌"
            span = tc - fc - 1
            mid = label[:span - 2].center(span - 2, dash) if span > 2 else dash * span
            row = list(_lifeline_row())
            row[fc] = "├"
            for j in range(fc + 1, tc):
                row[j] = dash
            row[tc] = "►"
            prefix = "".join(row[:tc + 1]).rstrip()
            lines_out.append(prefix)
            label_row = list(" " * total_w)
            start = fc + 1
            for j, ch in enumerate(label[:tc - fc - 1]):
                if start + j < total_w:
                    label_row[start + j] = ch
            lines_out.append("".join(label_row).rstrip())
        else:
            dash = "─" if not dashed else "╌"
            row = list(_lifeline_row())
            row[tc] = "◄"
            for j in range(tc + 1, fc):
                row[j] = dash
            row[fc] = "┤"
            lines_out.append("".join(row).rstrip())
            label_row = list(" " * total_w)
            start = tc + 1
            for j, ch in enumerate(label[:fc - tc - 1]):
                if start + j < total_w:
                    label_row[start + j] = ch
            lines_out.append("".join(label_row).rstrip())

    lines_out.append(_lifeline_row())
    return "\n".join(lines_out)


def _render_bar_chart(src: str) -> str:
    """Render a simple bar chart from 'label: value' lines."""
    entries: list[tuple[str, float]] = []
    for line in src.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        m = re.match(r"^(.+?)\s*[:=]\s*([\d.]+)\s*$", line)
        if m:
            entries.append((m.group(1).strip(), float(m.group(2))))
    if not entries:
        return src.strip()

    max_val = max(v for _, v in entries) or 1
    max_label = min(max(len(l) for l, _ in entries), 20)
    bar_w = 32
    out: list[str] = []
    for label, val in entries:
        filled = round(val / max_val * bar_w)
        bar = "█" * filled + "░" * (bar_w - filled)
        label_padded = label[:max_label].ljust(max_label)
        val_str = f"{val:g}"
        out.append(f"  {label_padded}  {bar}  {val_str}")
    return "\n".join(out)


_CHART_LANGS = frozenset({"chart", "bar", "barchart", "histogram"})


class CosmosMarkdownFence(MarkdownFence):
    """Code fences with rich diagram rendering: Mermaid, bar charts."""

    def __init__(self, markdown: Markdown, token, code: str) -> None:
        lang = (token.info or "").strip().split()[0].lower() if token.info else ""
        rendered: str | None = None
        if lang == "mermaid":
            first = next((l.strip().lower() for l in code.splitlines() if l.strip()), "")
            if first.startswith("sequencediagram"):
                rendered = _mermaid_sequence_ascii(code)
            else:
                rendered = _mermaid_flowchart_ascii(code)
        elif lang in _CHART_LANGS:
            rendered = _render_bar_chart(code)
        if rendered is not None:
            super().__init__(markdown, token, rendered)
            self.lexer = "text"
            self._highlighted_code = Content(rendered)
            self.set_content(self._highlighted_code)
        else:
            super().__init__(markdown, token, code)


class CosmosMarkdown(Markdown):
    BLOCKS = {
        **Markdown.BLOCKS,
        "fence": CosmosMarkdownFence,
        "code_block": CosmosMarkdownFence,
    }


class CosmosMessage(Vertical):
    """COSMOS response box with an inline pulsing dot next to the label."""

    DEFAULT_CSS = """
    CosmosMessage {
        background: #111111;
        padding: 1 3;
        margin: 0 0 1 0;
        height: auto;
    }
    CosmosMessage #cosmos-header {
        height: 1;
        background: #111111;
        margin-bottom: 1;
    }
    CosmosMessage #cosmos-name {
        color: #383838;
        background: #111111;
        text-style: bold;
        width: auto;
    }
    CosmosMessage #cosmos-dot {
        color: #1c1c1c;
        background: #111111;
        width: auto;
        margin-left: 1;
    }
    CosmosMessage #cosmos-dot.pulse-bright { color: #999999; }
    CosmosMessage #cosmos-dot.pulse-dim    { color: #222222; }
    CosmosMessage #cosmos-dot.done         { color: #ffffff; }

    CosmosMessage Markdown                { background: #111111; margin: 0; padding: 0; }
    CosmosMessage MarkdownParagraph       { background: #111111; color: #c8c8c8; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH1              { background: #111111; color: #ffffff;  text-style: bold underline; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH2              { background: #111111; color: #f0f0f0;  text-style: bold; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH3              { background: #111111; color: #d8d8d8;  text-style: bold; margin: 0; padding: 0; }
    CosmosMessage MarkdownCode  { background: #1e1e1e; }
    CosmosMessage MarkdownFence {
        background: #1c1c1c;
        margin: 0 0 1 0;
        padding: 0 1;
        overflow: hidden;
        scrollbar-size-horizontal: 0;
        scrollbar-size-vertical: 0;
    }
    CosmosMessage MarkdownBulletListItem,
    CosmosMessage MarkdownOrderedListItem { background: #111111; color: #c8c8c8; }
    CosmosMessage MarkdownHorizontalRule  { background: #111111; color: #2a2a2a; }
    CosmosMessage MarkdownH4              { background: #111111; color: #c0c0c0; text-style: bold; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownH5,
    CosmosMessage MarkdownH6              { background: #111111; color: #a8a8a8; text-style: italic; margin: 0 0 1 0; padding: 0; }
    CosmosMessage MarkdownBlockQuote {
        background: #0d0d0d;
        border-left: thick #2e2e2e;
        padding: 0 2;
        margin: 0 0 1 2;
        color: #888888;
    }
    CosmosMessage MarkdownTable {
        background: #111111;
        margin: 0 0 1 0;
        height: auto;
    }
    CosmosMessage MarkdownTableHead {
        background: #1a1a1a;
        color: #e0e0e0;
        text-style: bold;
    }
    CosmosMessage MarkdownTableBody { background: #111111; }
    CosmosMessage MarkdownTableRow  { height: 1; color: #c8c8c8; background: #111111; }
    CosmosMessage MarkdownTH {
        color: #e8e8e8;
        text-style: bold;
        background: #1a1a1a;
        padding: 0 2;
    }
    CosmosMessage MarkdownTD {
        color: #c0c0c0;
        background: transparent;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="cosmos-header"):
            yield Label("COSMOS", id="cosmos-name")
            yield Label("●", id="cosmos-dot")
        yield CosmosMarkdown("", id="stream-md")

    async def stream_append(self, full_text: str) -> None:
        try:
            await self.query_one("#stream-md", CosmosMarkdown).update(full_text)
        except Exception:
            pass

    async def set_content(self, text: str) -> None:
        try:
            await self.query_one("#stream-md", CosmosMarkdown).update(text)
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


class RegenerateBar(Horizontal):
    """Action row shown below the last AI reply: copy + regenerate."""

    class Requested(Message):
        pass

    DEFAULT_CSS = """
    RegenerateBar {
        height: 1;
        background: #111111;
        align: right middle;
        padding: 0 4;
        margin-bottom: 1;
    }
    """ + _ACTION_LABEL_CSS + """
    RegenerateBar #regen-copy-btn { margin-right: 1; }
    """

    def __init__(self, copy_text: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._copy_text = copy_text

    def compose(self) -> ComposeResult:
        yield Label(LABEL_COPY, id="regen-copy-btn", classes="action-label")
        yield Label(LABEL_REGEN, id="regen-btn", classes="action-label")

    def on_click(self, event: Click) -> None:
        event.stop()
        if event.widget.id == "regen-copy-btn":
            _copy_to_clipboard(self._copy_text)
            _flash_copy_label(event.widget)
        elif event.widget.id == "regen-btn":
            self.post_message(self.Requested())


LOGO = """\
 ██████  ██████  ███████ ███    ███  ██████  ███████
██      ██    ██ ██      ████  ████ ██    ██ ██
██      ██    ██ ███████ ██ ████ ██ ██    ██ ███████
██      ██    ██      ██ ██  ██  ██ ██    ██      ██
 ██████  ██████  ███████ ██      ██  ██████  ███████"""


class AnimatedLogo(Widget):
    """COSMOS wordmark — greyscale glitch animation."""

    DEFAULT_CSS = """
    AnimatedLogo {
        background: transparent;
        content-align: center middle;
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame = 0
        self._glitch_frames = 0
        self._glitch_map: dict[tuple[int, int], str] = {}

    def on_mount(self) -> None:
        self.set_interval(1 / 20, self._tick)

    def _tick(self) -> None:
        self._frame += 1
        if self._glitch_frames > 0:
            self._glitch_frames -= 1
            if self._glitch_frames == 0:
                self._glitch_map.clear()
        elif random.random() < 0.035:
            self._trigger_glitch()
        self.refresh()

    def _trigger_glitch(self) -> None:
        lines = LOGO.split("\n")
        self._glitch_map.clear()
        for i, line in enumerate(lines):
            for j, ch in enumerate(line):
                if ch != " " and random.random() < 0.38:
                    self._glitch_map[(i, j)] = random.choice(_GLITCH_CHARS)
        self._glitch_frames = random.randint(2, 5)

    def render(self):
        from rich.text import Text

        lines = LOGO.split("\n")
        result = Text(justify="center")

        for i, line in enumerate(lines):
            for j, char in enumerate(line):
                if char == " ":
                    result.append(" ")
                    continue

                display_char = self._glitch_map.get((i, j), char)
                is_dark = "dark" in self.app.pseudo_classes
                bg = "#111111" if is_dark else "#f5f5f5"
                if (i, j) in self._glitch_map:
                    if is_dark:
                        v = random.randint(80, 200)
                        fg = f"#{v:02x}{v:02x}{v:02x}"
                    else:
                        v = random.randint(60, 160)
                        fg = f"#{v:02x}{v:02x}{v:02x}"
                    result.append(display_char, style=f"{fg} on {bg}")
                else:
                    fg = "#ffffff" if is_dark else "#333333"
                    result.append(display_char, style=f"{fg} on {bg}")

            if i < len(lines) - 1:
                result.append("\n")

        return result

_COSMOS_THEME = TextAreaTheme(
    name="cosmos-input",
    base_style=Style(color="#d0d0d0", bgcolor="#1a1a1a"),
    cursor_style=Style(color="#1a1a1a", bgcolor="#d0d0d0"),
    cursor_line_style=Style(bgcolor="#1a1a1a"),
    selection_style=Style(bgcolor="#2a2a2a"),
)

_COSMOS_THEME_LIGHT = TextAreaTheme(
    name="cosmos-input-light",
    base_style=Style(color="#1a1a1a", bgcolor="#ffffff"),
    cursor_style=Style(color="#ffffff", bgcolor="#1a1a1a"),
    cursor_line_style=Style(bgcolor="#ffffff"),
    selection_style=Style(bgcolor="#cccccc"),
)

CHAT_PLACEHOLDER_PROMPTS = (
    "What's on your mind?...",
    "Ask anything...",
    "What are you building today?...",
    "Describe what you need...",
    "Where should we start?...",
    "What would you like to explore?...",
    "Tell me what you're stuck on...",
    "Paste code or ask a question...",
    "Summarize, draft, or debug...",
    "What's the goal?...",
    "Need ideas or a second opinion?...",
    "What should we tackle first?...",
    "How can I help right now?...",
    "Walk me through the problem...",
    "What are you curious about?...",
)


class ChatInput(TextArea):
    """Multiline chat input: Enter submits, Shift+Enter inserts newline."""

    PLACEHOLDER_TYPE_S = 0.055
    PLACEHOLDER_DELETE_S = 0.035
    PLACEHOLDER_HOLD_S = 1.75
    PLACEHOLDER_GAP_S = 0.4

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
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    ChatInput:focus { background: #1a1a1a; border: none; }
    ChatInput.-focus { background: #1a1a1a; border: none; }
    ChatInput .text-area--placeholder { color: #505050; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder="",
            show_line_numbers=False,
            highlight_cursor_line=False,
            **kwargs,
        )
        self._ph_timer = None
        self._ph_phase = ""
        self._ph_shown = ""
        self._ph_target = ""

    def on_mount(self) -> None:
        self.register_theme(_COSMOS_THEME)
        self.register_theme(_COSMOS_THEME_LIGHT)
        self.theme = "cosmos-input"
        self._start_placeholder_animation()

    def _placeholder_anim_active(self) -> bool:
        return not self.text and not self.disabled

    def _cancel_placeholder_timer(self) -> None:
        if self._ph_timer is not None:
            self._ph_timer.stop()
            self._ph_timer = None

    def _arm_placeholder_timer(self, delay_s: float) -> None:
        self._cancel_placeholder_timer()
        self._ph_timer = self.set_timer(delay_s, self._placeholder_anim_step)

    def _pick_next_prompt(self) -> str:
        pool = CHAT_PLACEHOLDER_PROMPTS
        choices = [p for p in pool if p != self._ph_target] or list(pool)
        return random.choice(choices)

    def _start_placeholder_animation(self) -> None:
        if not self._placeholder_anim_active():
            return
        self._ph_target = self._pick_next_prompt()
        self._ph_shown = ""
        self._ph_phase = "type"
        self.placeholder = ""
        self._placeholder_anim_step()

    def _stop_placeholder_animation(self, *, clear: bool = True) -> None:
        self._cancel_placeholder_timer()
        self._ph_phase = ""
        if clear:
            self.placeholder = ""

    def _placeholder_anim_step(self) -> None:
        if not self._placeholder_anim_active():
            self._stop_placeholder_animation()
            return

        if self._ph_phase == "type":
            if len(self._ph_shown) < len(self._ph_target):
                self._ph_shown = self._ph_target[: len(self._ph_shown) + 1]
                self.placeholder = self._ph_shown
                self._arm_placeholder_timer(self.PLACEHOLDER_TYPE_S)
            else:
                self._ph_phase = "hold"
                self._arm_placeholder_timer(self.PLACEHOLDER_HOLD_S)
        elif self._ph_phase == "hold":
            self._ph_phase = "delete"
            self._placeholder_anim_step()
        elif self._ph_phase == "delete":
            if self._ph_shown:
                self._ph_shown = self._ph_shown[:-1]
                self.placeholder = self._ph_shown
                self._arm_placeholder_timer(self.PLACEHOLDER_DELETE_S)
            else:
                self._ph_phase = "gap"
                self._arm_placeholder_timer(self.PLACEHOLDER_GAP_S)
        elif self._ph_phase == "gap":
            self._ph_target = self._pick_next_prompt()
            self._ph_phase = "type"
            self._placeholder_anim_step()

    def watch_text(self, text: str) -> None:
        if text:
            self._stop_placeholder_animation()
        elif not self.disabled:
            self._start_placeholder_animation()

    def watch_disabled(self, disabled: bool) -> None:
        if disabled:
            self._stop_placeholder_animation()
        elif not self.text:
            self._start_placeholder_animation()

    def _on_key(self, event) -> None:
        if event.key == "enter":
            event.prevent_default()
            self.post_message(self.Submitted(self, self.text))
        elif event.key == "shift+enter":
            event.prevent_default()
            self.insert("\n")


class SidebarEntryRow(Horizontal):
    """Single-line sidebar row; folders expand/collapse; ⋯ opens floating menu."""

    def __init__(
        self,
        title: str,
        entry_type: str,
        entry_id: str | None = None,
        index: int = 0,
        *,
        empty: bool = False,
        indent: int = 0,
        folder_expanded: bool = False,
        icon: str = "",
        creating: bool = False,
        create_parent_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.entry_type = entry_type
        self.entry_id = entry_id
        self.row_index = index
        self._title = title
        self._empty = empty
        self.indent = indent
        self.folder_expanded = folder_expanded
        self._icon = icon
        self._creating = creating
        self.create_parent_id = create_parent_id
        self._display_title = self._format_display_title(title, indent)

    @staticmethod
    def _format_display_title(title: str, indent: int) -> str:
        del indent
        return (title or "")[:20]

    DEFAULT_CSS = """
    SidebarEntryRow {
        height: 1;
        width: 100%;
        background: transparent;
        padding: 0;
    }
    SidebarEntryRow.-hovered {
        background: #2a2a2a;
    }
    SidebarEntryRow #entry-indent {
        width: 0;
        min-width: 0;
        height: 1;
        background: transparent;
    }
    SidebarEntryRow #entry-chat-marker {
        width: 2;
        height: 1;
        color: #555555;
        background: transparent;
        content-align: center middle;
    }
    SidebarEntryRow #entry-chevron {
        width: 2;
        height: 1;
        color: #888888;
        background: transparent;
        content-align: center middle;
    }
    SidebarEntryRow.-folder-open #entry-chevron {
        color: #cccccc;
    }
    SidebarEntryRow #entry-title {
        width: 1fr;
        height: 1;
        padding: 0 1;
        color: #909090;
        background: transparent;
        text-overflow: ellipsis;
        content-align: left middle;
    }
    SidebarEntryRow.-folder #entry-title {
        color: #a0a0a0;
    }
    SidebarEntryRow.-hovered #entry-title {
        color: #e8e8e8;
    }
    SidebarEntryRow.-empty #entry-title {
        color: #606060;
    }
    SidebarEntryRow #entry-menu-btn {
        width: 3;
        height: 1;
        color: #888888;
        background: transparent;
        content-align: center middle;
        visibility: hidden;
    }
    SidebarEntryRow.-hovered #entry-menu-btn {
        visibility: visible;
    }
    SidebarEntryRow #entry-menu-btn:hover {
        color: #eeeeee;
    }
    SidebarEntryRow #entry-rename {
        display: none;
        width: 1fr;
        min-width: 0;
        height: 1;
        padding: 0 1;
        border: none;
        background: #1a1a1a;
        color: #eeeeee;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
        scrollbar-size-vertical: 0;
    }
    SidebarEntryRow #entry-rename:focus {
        background: #252525;
        border: none;
    }
    SidebarEntryRow.-renaming {
        overflow-x: hidden;
    }
    SidebarEntryRow.-renaming #entry-title {
        display: none;
    }
    SidebarEntryRow.-renaming #entry-rename {
        display: block;
    }
    SidebarEntryRow.-renaming #entry-chevron,
    SidebarEntryRow.-renaming #entry-chat-marker {
        display: none;
    }
    SidebarEntryRow.-renaming #entry-menu-btn {
        visibility: hidden;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="entry-indent")
        if self.entry_type == "chat" and self._icon:
            yield Label(self._icon, id="entry-chat-marker")
        elif self.entry_type == "folder" and self._icon:
            yield Label(self._icon, id="entry-chevron")
        yield Label(self._display_title, id="entry-title")
        yield Input(
            self._title,
            id="entry-rename",
            placeholder="Folder name" if self._creating else "",
        )
        if not self._empty and not self._creating:
            yield Label("⋮", id="entry-menu-btn")

    def on_mount(self) -> None:
        self.set_class(self.entry_type == "folder", "-folder")
        self.set_class(self.entry_type == "chat", "-chat")
        self.set_class(self.folder_expanded, "-folder-open")
        if self._empty:
            self.add_class("-empty")
        self._apply_indent_spacer()
        if self._creating:
            self.call_after_refresh(self.begin_inline_create)

    def on_enter(self, event: Enter) -> None:
        event.stop()
        if not self._empty and not self._creating:
            self.add_class("-hovered")

    def on_leave(self, event: Leave) -> None:
        event.stop()
        self.remove_class("-hovered")

    def _apply_indent_spacer(self) -> None:
        """Fixed-width spacer so nested folders/chats visibly indent."""
        try:
            spacer = self.query_one("#entry-indent", Static)
            cols = self.indent * SIDEBAR_INDENT_COLS
            if cols > 0:
                spacer.styles.width = cols
                spacer.update(" " * cols)
                spacer.display = True
            else:
                spacer.styles.width = 0
                spacer.update("")
                spacer.display = False
        except Exception:
            pass

    def begin_inline_create(self) -> None:
        if not self._creating:
            return
        self.add_class("-renaming")
        self._apply_indent_spacer()
        inp = self.query_one("#entry-rename", Input)
        inp.value = ""
        inp.focus()

    def begin_inline_rename(self) -> None:
        if self._empty or not self.entry_id or self._creating:
            return
        self.add_class("-renaming")
        self._apply_indent_spacer()
        inp = self.query_one("#entry-rename", Input)
        inp.value = self._title
        inp.focus()
        try:
            inp.action_select_all()
        except Exception:
            pass

    def cancel_inline_rename(self) -> None:
        self.remove_class("-renaming")
        try:
            self.query_one("#entry-rename", Input).value = self._title
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "entry-rename" or not self.has_class("-renaming"):
            return
        event.stop()
        app = self.app
        if not isinstance(app, CosmosApp):
            return
        if self._creating:
            app._commit_inline_new_folder(self, event.value)
            return
        self.cancel_inline_rename()
        app._commit_inline_rename(self, event.value)

    def on_key(self, event) -> None:
        if self.has_class("-renaming") and event.key == "escape":
            event.stop()
            app = self.app
            if not isinstance(app, CosmosApp):
                return
            if self._creating:
                app._cancel_inline_new_folder(self)
            else:
                app._cancel_inline_rename(self)

    def on_click(self, event: Click) -> None:
        if self._empty or self.has_class("-renaming") or self._creating:
            return
        tid = getattr(event.widget, "id", None)
        app = self.app
        if not isinstance(app, CosmosApp):
            return
        if tid == "entry-menu-btn":
            event.stop()
            app._open_sidebar_entry_menu(self, event.screen_x, event.screen_y)
            return
        if tid in ("entry-title", "entry-chevron", "entry-chat-marker"):
            event.stop()
            if self.entry_type == "folder" and self.entry_id:
                app._toggle_folder_expand(self.entry_id)
            elif self.entry_type == "chat" and self.entry_id:
                app._open_chat_by_id(self.entry_id)


class SidebarScroll(VerticalScroll):
    """Scrollable sidebar body (folders + chats)."""

    DEFAULT_CSS = """
    SidebarScroll {
        height: 1fr;
        width: 100%;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
    }
    """


def _system_prefers_dark() -> bool:
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout.strip().lower() == "dark"
        if sys.platform.startswith("linux"):
            r = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=2,
            )
            return "dark" in r.stdout.lower()
    except Exception:
        pass
    return True


# ── main app ───────────────────────────────────────────────────────────────────

class CosmosApp(App):
    CSS = """
    Screen {
        background: #000000;
        layers: base overlay;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
    }

    ScrollableContainer, ListView, TextArea, ChatInput {
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    ModelDropdown { background: rgba(0,0,0,0); }

    Button,
    #menu-btn,
    #chat-title-bar,
    #sidebar-logout-btn,
    .action-label,
    .sidebar-plus,
    SidebarEntryRow,
    #chats-list > SidebarEntryRow,
    #folders-list > SidebarEntryRow,
    ModelDropdown ListItem {
        pointer: default;
    }

    ChatInput, Input, SidebarEntryRow #entry-rename {
        pointer: text;
    }

    /* layout */
    #app-body {
        width: 100%;
        height: 1fr;
    }

    /* sidebar */
    #sidebar {
        width: 30;
        background: #222222;
        padding: 0;
        height: 1fr;
        layout: vertical;
        align: left top;
    }
    #sidebar.collapsed {
        display: none;
    }
    #sidebar-brand {
        width: 100%;
        height: 3;
        background: #222222;
        padding: 0;
        margin: 0;
        align: center middle;
    }
    #sidebar-brand-inner {
        width: auto;
        height: 1;
        background: transparent;
    }
    #sidebar-brand-dot {
        color: #ffffff;
        background: transparent;
        width: auto;
        height: 1;
        padding: 0;
    }
    #sidebar-brand-name {
        color: #cccccc;
        text-style: bold;
        background: transparent;
        width: auto;
        height: 1;
        padding: 0 0 0 1;
    }
    #sidebar-scroll {
        height: 1fr;
        width: 100%;
        min-height: 1;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
        scrollbar-background: #222222;
        scrollbar-color: #222222;
        scrollbar-color-hover: #222222;
        scrollbar-color-active: #222222;
    }
    #sidebar-content {
        width: 100%;
        height: auto;
        padding: 0;
        overflow: hidden hidden;
    }
    #sidebar-profile {
        width: 100%;
        height: 3;
        background: #222222;
        padding: 0 1;
        margin: 0;
        align: left middle;
    }
    #sidebar-profile-name {
        width: 1fr;
        height: 1;
        background: transparent;
        color: #888888;
        padding: 0 1;
        text-overflow: ellipsis;
        content-align: left middle;
    }
    #sidebar-logout-btn {
        color: #666666;
        background: transparent;
        height: 1;
        width: auto;
        min-width: 7;
        padding: 0 1;
        content-align: center middle;
    }
    #sidebar-logout-btn:hover {
        color: #eeeeee;
    }
    #chats-header, #folders-header {
        height: 3;
        width: 100%;
        background: #222222;
        margin: 0;
        padding: 0 1;
        align: left middle;
    }
    .sidebar-section-header-inner {
        width: 1fr;
        height: 1;
        background: transparent;
        align: left middle;
    }
    #sidebar-chats-label, #sidebar-folders-label {
        color: #cccccc;
        text-style: bold;
        background: transparent;
        height: 1;
        width: 1fr;
        padding: 0 0 0 2;
        content-align: left middle;
    }
    .sidebar-plus {
        color: #666666;
        background: transparent;
        height: 1;
        width: auto;
        min-width: 3;
        padding: 0 1;
        content-align: center middle;
    }
    .sidebar-plus:hover {
        color: #eeeeee;
    }
    #folders-panel, #chats-panel {
        background: #222222;
        height: auto;
        width: 100%;
        padding: 0 2;
        margin: 0;
        overflow-y: auto;
        overflow-x: hidden;
    }
    #folders-list, #chats-list {
        height: auto;
        width: 100%;
        padding: 0;
        overflow-y: auto;
        overflow-x: hidden;
        background: transparent;
    }
    /* main content */
    #main-content {
        width: 1fr;
        height: 100%;
        padding: 0;
        background: #111111;
    }
    #chat-title-bar {
        width: 100%;
        height: 3;
        background: #111111;
        padding: 0;
        margin: 0;
    }
    #menu-btn {
        width: 3;
        height: 3;
        background: #111111;
        color: #888888;
        padding: 0;
        margin: 0 0 0 2;
        content-align: center middle;
    }
    #menu-btn:hover {
        color: #eeeeee;
        background: #111111;
    }
    #chat-title {
        width: 1fr;
        height: 3;
        background: #111111;
        color: #888888;
        padding: 0;
        margin: 0;
        text-align: center;
        content-align: center middle;
        text-overflow: ellipsis;
    }
    /* scroll */
    #scroll {
        background: #111111;
        height: 1fr;
        scrollbar-background: #111111;
        scrollbar-color: #2a2a2a;
        scrollbar-color-hover: #555555;
        scrollbar-color-active: #777777;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    /* messages */
    #messages {
        background: #111111;
        height: auto;
        min-height: 100%;
        padding: 2 4 1 4;
    }

    /* home */
    #home-state {
        background: #111111;
        height: 100%;
        align: center middle;
    }
    #home-logo {
        background: transparent;
        content-align: center middle;
        width: 100%;
    }

    /* input section */
    #input-section {
        background: #111111;
        height: auto;
        padding: 0;
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
    #token-usage {
        color: #505050;
        background: #1a1a1a;
        width: auto;
        height: 1;
        padding: 0 2 0 0;
    }
    #token-usage.warn { color: #b0a050; }
    #token-usage.full { color: #c06060; }
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

    /* theme toggle */
    #theme-toggle {
        width: 3;
        height: 1;
        background: transparent;
        color: #555555;
        padding: 0 1;
        content-align: center middle;
    }
    #theme-toggle:hover { color: #eeeeee; }

    /* ── light mode ──────────────────────────────────────────────── */
    App:light Screen { background: #ebebeb; }

    App:light #sidebar,
    App:light #sidebar-brand,
    App:light #chats-header,
    App:light #folders-header,
    App:light #folders-panel,
    App:light #chats-panel,
    App:light #sidebar-profile { background: #eaeaea; }

    App:light #sidebar-scroll {
        scrollbar-background: #eaeaea;
        scrollbar-color: #eaeaea;
        scrollbar-color-hover: #eaeaea;
        scrollbar-color-active: #eaeaea;
    }
    App:light #sidebar-brand-dot  { color: #333333; }
    App:light #sidebar-brand-name { color: #444444; }
    App:light #sidebar-chats-label,
    App:light #sidebar-folders-label { color: #555555; }
    App:light .sidebar-plus        { color: #888888; }
    App:light .sidebar-plus:hover  { color: #111111; }
    App:light #sidebar-logout-btn       { color: #888888; }
    App:light #sidebar-logout-btn:hover { color: #111111; }
    App:light #sidebar-profile-name     { color: #777777; }
    App:light #theme-toggle       { color: #888888; }
    App:light #theme-toggle:hover { color: #111111; }

    App:light SidebarEntryRow #entry-title         { color: #444444; }
    App:light SidebarEntryRow.-folder #entry-title { color: #333333; }
    App:light SidebarEntryRow.-empty #entry-title  { color: #888888; }
    App:light SidebarEntryRow.-hovered             { background: #d8d8d8; }
    App:light SidebarEntryRow.-hovered #entry-title { color: #111111; }

    App:light #main-content,
    App:light #chat-title-bar,
    App:light #chat-title,
    App:light #scroll,
    App:light #messages,
    App:light #home-state,
    App:light #input-section { background: #f5f5f5; }

    App:light #scroll {
        scrollbar-background: #f5f5f5;
        scrollbar-color: #cccccc;
        scrollbar-color-hover: #aaaaaa;
        scrollbar-color-active: #888888;
    }
    App:light #menu-btn            { background: #f5f5f5; color: #777777; }
    App:light #menu-btn:hover      { background: #f5f5f5; color: #111111; }
    App:light #chat-title          { background: #f5f5f5; color: #777777; }

    App:light #input-box           { background: #ffffff; }
    App:light ChatInput            { background: #ffffff; color: #1a1a1a; scrollbar-background: #ffffff; scrollbar-color: #dddddd; }
    App:light ChatInput:focus      { background: #ffffff; }
    App:light ChatInput.-focus     { background: #ffffff; }
    App:light ChatInput .text-area--placeholder { color: #aaaaaa; }

    App:light #toolbar,
    App:light #right-controls,
    App:light #attach-label        { background: #ffffff; }
    App:light #attach-btn          { background: #ffffff; color: #aaaaaa; }
    App:light #attach-btn:hover    { background: #ffffff; color: #555555; }
    App:light #attach-btn:focus    { background: #ffffff; }
    App:light #token-usage         { background: #ffffff; color: #aaaaaa; }
    App:light #model-btn           { background: #ffffff; color: #888888; }
    App:light #model-btn:hover     { background: #ffffff; color: #333333; }
    App:light #model-btn:focus     { background: #ffffff; }
    App:light #action-btn          { background: #ffffff; color: #cccccc; }
    App:light #action-btn.can-send { color: #888888; }
    App:light #action-btn.thinking { color: #aaaaaa; }
    App:light #action-btn:hover    { background: #ffffff; }
    App:light #action-btn:focus    { background: #ffffff; }

    App:light UserMessage         { background: #eeeeee; color: #222222; }
    App:light UserMessage:hover   { background: #e4e4e4; }
    App:light UserMessage Static  { color: #222222; }

    App:light CosmosMessage,
    App:light CosmosMessage #cosmos-header { background: #f5f5f5; }
    App:light CosmosMessage #cosmos-name   { background: #f5f5f5; color: #cccccc; }
    App:light CosmosMessage #cosmos-dot    { background: #f5f5f5; color: #cccccc; }
    App:light CosmosMessage #cosmos-dot.done { color: #aaaaaa; }

    App:light CosmosMessage Markdown,
    App:light CosmosMessage MarkdownParagraph,
    App:light CosmosMessage MarkdownH1,
    App:light CosmosMessage MarkdownH2,
    App:light CosmosMessage MarkdownH3,
    App:light CosmosMessage MarkdownH4,
    App:light CosmosMessage MarkdownH5,
    App:light CosmosMessage MarkdownH6,
    App:light CosmosMessage MarkdownBulletListItem,
    App:light CosmosMessage MarkdownOrderedListItem,
    App:light CosmosMessage MarkdownHorizontalRule,
    App:light CosmosMessage MarkdownTable,
    App:light CosmosMessage MarkdownTableBody,
    App:light CosmosMessage MarkdownTableRow { background: #f5f5f5; }

    App:light CosmosMessage MarkdownParagraph        { color: #333333; }
    App:light CosmosMessage MarkdownH1               { color: #111111; }
    App:light CosmosMessage MarkdownH2               { color: #222222; }
    App:light CosmosMessage MarkdownH3               { color: #333333; }
    App:light CosmosMessage MarkdownH4               { color: #444444; }
    App:light CosmosMessage MarkdownH5,
    App:light CosmosMessage MarkdownH6               { color: #555555; }
    App:light CosmosMessage MarkdownBulletListItem,
    App:light CosmosMessage MarkdownOrderedListItem  { color: #333333; }
    App:light CosmosMessage MarkdownHorizontalRule   { color: #cccccc; }
    App:light CosmosMessage MarkdownTableRow         { color: #333333; }
    App:light CosmosMessage MarkdownCode             { background: #e8e8e8; }
    App:light CosmosMessage MarkdownFence            { background: #ececec; }
    App:light CosmosMessage MarkdownTableHead        { background: #e8e8e8; color: #222222; }
    App:light CosmosMessage MarkdownTH               { background: #e8e8e8; color: #222222; }
    App:light CosmosMessage MarkdownTD               { color: #333333; }
    App:light CosmosMessage MarkdownBlockQuote       { background: #ededed; color: #666666; border-left: thick #cccccc; }

    App:light RegenerateBar { background: #f5f5f5; }

    /* model dropdown */
    App:light ModelDropdown > Vertical        { background: #f0f0f0; border: solid #cccccc; }
    App:light ModelDropdown ListView          { background: #f0f0f0; scrollbar-color: #f0f0f0; scrollbar-background: #f0f0f0; scrollbar-color-hover: #f0f0f0; scrollbar-color-active: #f0f0f0; }
    App:light ModelDropdown ListItem          { background: #f0f0f0; }
    App:light ModelDropdown ListView > ListItem.--highlight { background: #e0e0e0; }
    App:light ModelDropdown ListItem Label    { color: #555555; }
    App:light ModelDropdown ListView > ListItem.--highlight Label { color: #111111; }

    /* rename / new-folder input */
    App:light SidebarEntryRow #entry-rename        { background: #f0f0f0; color: #222222; }
    App:light SidebarEntryRow #entry-rename:focus  { background: #e8e8e8; border: none; }

    /* context menus */
    App:light SidebarFloatingMenu,
    App:light SidebarFolderFloatingMenu             { background: #f0f0f0; border: solid #cccccc; }
    App:light SidebarFloatingMenu .sidebar-menu-act,
    App:light SidebarFolderFloatingMenu .sidebar-menu-act { color: #333333; background: transparent; }
    App:light SidebarFloatingMenu .sidebar-menu-act:hover,
    App:light SidebarFolderFloatingMenu .sidebar-menu-act:hover { background: #e0e0e0; color: #111111; }
    App:light SidebarFloatingMenu .sidebar-menu-act.-danger,
    App:light SidebarFolderFloatingMenu .sidebar-menu-act.-danger { color: #cc4444; }
    App:light SidebarFloatingMenu .sidebar-menu-act.-danger:hover,
    App:light SidebarFolderFloatingMenu .sidebar-menu-act.-danger:hover { color: #aa2222; background: #ead8d8; }

    /* suppress Textual's accent focus color on sidebar rows */
    App:light SidebarEntryRow:focus       { background: transparent; border: none; }
    App:light SidebarEntryRow.-hovered:focus { background: #d8d8d8; border: none; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit",       show=False),
        Binding("ctrl+l", "clear_chat", show=False),
        Binding("escape", "close_sidebar_menu", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.conversation: list[dict] = []
        self.model_idx: int = 0
        self.attachment: FileAttachment | None = None
        self.is_thinking: bool = False
        self._dot_timer = None
        self._dot_bright: bool = False
        self._active_cosmos: CosmosMessage | None = None
        self._stream_worker = None
        self._regen_bar: RegenerateBar | None = None
        self._last_usage_tokens: int | None = None
        self._ollama_models: list[tuple[str, str]] = []
        # auth / db
        self.user: dict | None = None
        self._access_token: str = ""
        self.current_chat_id: str | None = None
        self._chats: list[dict] = []
        self._folders: list[dict] = []
        self._folder_children: dict[str | None, list[dict]] = defaultdict(list)
        self._chats_by_folder: dict[str | None, list[dict]] = defaultdict(list)
        self._expanded_folder_ids: set[str] = set()
        self._sidebar_open: bool = True
        self._renaming_row: SidebarEntryRow | None = None
        self._creating_folder_row: SidebarEntryRow | None = None

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                with Horizontal(id="sidebar-brand"):
                    with Horizontal(id="sidebar-brand-inner"):
                        yield Label("●", id="sidebar-brand-dot")
                        yield Label("COSMOS", id="sidebar-brand-name")
                with SidebarScroll(id="sidebar-scroll"):
                    with VerticalGroup(id="sidebar-content"):
                        with Horizontal(id="folders-header"):
                            with Horizontal(classes="sidebar-section-header-inner"):
                                yield Label("FOLDERS", id="sidebar-folders-label")
                                yield Label("+", id="new-folder-btn", classes="sidebar-plus")
                        with VerticalGroup(id="folders-panel"):
                            with VerticalGroup(id="folders-list"):
                                yield SidebarEntryRow(
                                    "(no folders yet)", "folder", empty=True,
                                )
                        with Horizontal(id="chats-header"):
                            with Horizontal(classes="sidebar-section-header-inner"):
                                yield Label("CHATS", id="sidebar-chats-label")
                                yield Label("+", id="new-chat-btn", classes="sidebar-plus")
                        with VerticalGroup(id="chats-panel"):
                            with VerticalGroup(id="chats-list"):
                                yield SidebarEntryRow(
                                    "(no chats yet)", "chat", empty=True,
                                )
                with Horizontal(id="sidebar-profile"):
                    yield Label("", id="sidebar-profile-name")
                    yield Label("logout", id="sidebar-logout-btn")
                    yield Label("◑", id="theme-toggle")
            with Vertical(id="main-content"):
                with Horizontal(id="chat-title-bar"):
                    yield Static("☰", id="menu-btn", markup=False)
                    yield Label("", id="chat-title")
                with ScrollableContainer(id="scroll"):
                    with Vertical(id="messages"):
                        with Vertical(id="home-state"):
                            yield AnimatedLogo(id="home-logo")
                with Vertical(id="input-section"):
                    with Vertical(id="input-box"):
                        yield ChatInput(id="main-input")
                        with Horizontal(id="toolbar"):
                            yield Button("+", id="attach-btn")
                            yield Label("", id="attach-label")
                            yield Label("", id="token-usage")
                            with Horizontal(id="right-controls"):
                                yield Button(self._all_models()[0][1], id="model-btn")
                                yield Button("▶", id="action-btn")

    def on_mount(self) -> None:
        self.query_one("#main-input", ChatInput).focus()
        self._update_sidebar_profile()
        self._update_chat_title()
        self._update_token_usage()
        self._try_restore_session()
        self._fetch_ollama_models()
        if not _system_prefers_dark():
            self._toggle_theme()

    @work(thread=True)
    def _fetch_ollama_models(self) -> None:
        try:
            with httpx.Client(timeout=3) as client:
                resp = client.get("http://localhost:11434/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    self._ollama_models = [
                        (f"ollama:{m['name']}", f"⬡ {m['name'].split(':')[0]}")
                        for m in models
                    ]
                    if self._ollama_models:
                        self.call_from_thread(self._refresh_model_btn)
        except Exception:
            pass

    def _refresh_model_btn(self) -> None:
        try:
            all_models = self._all_models()
            idx = self.model_idx
            if 0 <= idx < len(all_models):
                self.query_one("#model-btn", Button).label = all_models[idx][1]
        except Exception:
            pass

    def _all_models(self) -> list[tuple[str, str]]:
        if self._ollama_models:
            return FREE_MODELS + [("ollama:---", "── Local ──")] + self._ollama_models
        return list(FREE_MODELS)

    # ── auth ──────────────────────────────────────────────────────────────────

    @work(thread=True)
    def _try_restore_session(self) -> None:
        session = _load_session()
        if not session.get("token") or not session.get("user"):
            self.app.call_from_thread(self._show_login)
            return
        try:
            # Refresh user profile (name, api key) on every startup
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{COSMOS_API_BASE}/auth/me",
                    headers={"Authorization": f"Bearer {session['token']}"},
                )
                resp.raise_for_status()
                session["user"] = resp.json()
                _save_session(session)
            self.app.call_from_thread(self._on_authenticated, session)
        except Exception:
            self.app.call_from_thread(self._show_login)

    def _show_login(self) -> None:
        self.push_screen(LoginScreen(), self._on_login_complete)

    def _on_login_complete(self, session: dict | None) -> None:
        if not session:
            return
        self._on_authenticated(session)

    def _profile_display_name(self) -> str:
        if not self.user:
            return ""
        full_name = (self.user.get("full_name") or "").strip()
        if full_name:
            return full_name
        email = (self.user.get("email") or "").strip()
        if "@" in email:
            return email.split("@", 1)[0]
        return email

    def _update_sidebar_profile(self) -> None:
        try:
            bar = self.query_one("#sidebar-profile", Horizontal)
            name_lbl = self.query_one("#sidebar-profile-name", Label)
            logout_lbl = self.query_one("#sidebar-logout-btn", Label)
            if self.user:
                name = self._profile_display_name()
                name_lbl.update(name[:22] if name else "User")
                bar.display = True
                logout_lbl.display = True
            else:
                name_lbl.update("")
                bar.display = False
                logout_lbl.display = False
        except Exception:
            pass

    def _logout(self) -> None:
        if self.is_thinking:
            self._cancel_stream()
        self._close_floating_menu()
        self._cancel_inline_rename()
        self._cancel_inline_new_folder()
        try:
            SESSION_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        self.user = None
        self._access_token = ""
        self.current_chat_id = None
        self._chats = []
        self._folders = []
        self._folder_children = defaultdict(list)
        self._chats_by_folder = defaultdict(list)
        self._expanded_folder_ids = set()
        self.conversation = []
        self._clear_chat_view()
        self._update_sidebar_profile()
        self._update_chat_title()
        self._refresh_sidebar_lists()
        self._show_login()

    def _chat_title_for_display(self) -> str:
        if not self.current_chat_id:
            return ""
        for chat in self._chats:
            if chat.get("id") == self.current_chat_id:
                return (chat.get("title") or "New chat")[:MAX_CHAT_TITLE_LEN]
        return "New chat"

    def _update_chat_title(self) -> None:
        try:
            self.query_one("#chat-title", Label).update(self._chat_title_for_display())
        except Exception:
            pass

    def _on_authenticated(self, session: dict) -> None:
        self.user = session["user"]
        self._access_token = session["token"]
        self._db_log(f"authenticated user={self.user['id']} token_prefix={self._access_token[:20]}")
        self._update_sidebar_profile()
        self.query_one("#main-input", ChatInput).focus()
        self._fetch_sidebar_data()
        if not (self.user or {}).get("openrouter_api_key"):
            self.push_screen(ApiKeyScreen(), self._on_apikey_entered)

    def _on_apikey_entered(self, key: str | None) -> None:
        if not key:
            return
        self._save_apikey_worker(key)

    @work(thread=True)
    def _save_apikey_worker(self, key: str) -> None:
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.patch(
                    f"{COSMOS_API_BASE}/auth/settings",
                    headers=self._api_headers(),
                    json={"openrouter_api_key": key},
                )
                resp.raise_for_status()
            def _apply() -> None:
                if self.user:
                    self.user["openrouter_api_key"] = key
                session = _load_session()
                if session.get("user"):
                    session["user"]["openrouter_api_key"] = key
                    _save_session(session)
            self.app.call_from_thread(_apply)
        except Exception:
            pass

    # ── API helpers ───────────────────────────────────────────────────────────

    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _api_get(self, path: str) -> list:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{COSMOS_API_BASE}{path}", headers=self._api_headers())
            resp.raise_for_status()
            return resp.json()

    def _api_post(self, path: str, data: dict) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{COSMOS_API_BASE}{path}", headers=self._api_headers(), json=data)
            resp.raise_for_status()
            return resp.json()

    def _api_patch(self, path: str, data: dict) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.patch(f"{COSMOS_API_BASE}{path}", headers=self._api_headers(), json=data)
            resp.raise_for_status()
            return resp.json()

    def _api_delete(self, path: str) -> None:
        with httpx.Client(timeout=30) as client:
            resp = client.delete(f"{COSMOS_API_BASE}{path}", headers=self._api_headers())
            resp.raise_for_status()

    # ── sidebar data ──────────────────────────────────────────────────────────

    @work(thread=True)
    def _fetch_sidebar_data(self) -> None:
        if not self.user or not self._access_token:
            return
        try:
            chats = self._api_get("/chats")
            try:
                folders = self._api_get("/folders")
            except Exception:
                folders = []

            def _apply() -> None:
                try:
                    self._populate_sidebar(chats, folders)
                except Exception as exc:
                    self._db_log(f"_populate_sidebar error: {exc}")

            self.call_from_thread(_apply)
        except Exception as exc:
            self._db_log(f"_fetch_sidebar_data error: {exc}")

    def _populate_sidebar(self, chats: list[dict], folders: list[dict]) -> None:
        for chat in chats:
            if "folder_id" not in chat:
                chat["folder_id"] = None
        for folder in folders:
            if "parent_id" not in folder:
                folder["parent_id"] = None
        self._chats = chats
        self._folders = folders
        self._rebuild_sidebar_indexes()
        self._db_log(f"sidebar loaded: {len(chats)} chats, {len(folders)} folders")
        self._sync_sidebar_ui()

    @staticmethod
    def _norm_folder_id(folder_id: str | None) -> str | None:
        if folder_id is None or folder_id == "":
            return None
        return str(folder_id)

    def _rebuild_sidebar_indexes(self) -> None:
        valid_folder_ids = {
            str(f["id"]) for f in self._folders if f.get("id")
        }
        self._folder_children = defaultdict(list)
        for folder in self._folders:
            parent_id = self._norm_folder_id(folder.get("parent_id"))
            if parent_id and parent_id not in valid_folder_ids:
                parent_id = None
            folder["parent_id"] = parent_id
            self._folder_children[parent_id].append(folder)
        for children in self._folder_children.values():
            children.sort(key=lambda f: (f.get("name") or "").lower())

        self._chats_by_folder = defaultdict(list)
        for chat in self._chats:
            fid = self._norm_folder_id(chat.get("folder_id"))
            self._chats_by_folder[fid].append(chat)
        for chats in self._chats_by_folder.values():
            chats.sort(
                key=lambda c: c.get("created_at") or "",
                reverse=True,
            )

    def _uncategorized_chats(self) -> list[dict]:
        return list(self._chats_by_folder.get(None, []))

    def _folder_descendant_ids(self, folder_id: str) -> set[str]:
        found: set[str] = set()
        stack = [folder_id]
        while stack:
            pid = stack.pop()
            if pid in found:
                continue
            found.add(pid)
            for child in self._folder_children.get(pid, []):
                cid = child.get("id")
                if cid:
                    stack.append(cid)
        return found

    def _folder_picker_entries(self) -> list[tuple[str | None, str, int]]:
        entries: list[tuple[str | None, str, int]] = [(None, "(none)", 0)]

        def walk(parent_id: str | None, depth: int) -> None:
            for folder in self._folder_children.get(parent_id, []):
                fid = folder.get("id")
                if not fid:
                    continue
                prefix = "  " * depth
                name = (folder.get("name") or "")[: max(1, 16 - depth * 2)]
                entries.append((fid, f"{prefix}{name}", depth))
                walk(fid, depth + 1)

        walk(None, 0)
        return entries

    def _toggle_folder_expand(self, folder_id: str) -> None:
        fid = self._norm_folder_id(folder_id)
        if not fid:
            return
        if fid in self._expanded_folder_ids:
            self._expanded_folder_ids.discard(fid)
        else:
            self._expanded_folder_ids.add(fid)
        self._apply_folder_expand_toggle(fid)

    def _find_folder_row(self, folder_id: str) -> SidebarEntryRow | None:
        fid = self._norm_folder_id(folder_id)
        try:
            fl = self.query_one("#folders-list", VerticalGroup)
        except Exception:
            return None
        for child in fl.children:
            if (
                isinstance(child, SidebarEntryRow)
                and child.entry_type == "folder"
                and child.entry_id == fid
            ):
                return child
        return None

    @work
    async def _apply_folder_expand_toggle(self, folder_id: str) -> None:
        """Expand/collapse in place — do not rebuild the whole sidebar."""
        fid = self._norm_folder_id(folder_id)
        if not fid:
            return
        row = self._find_folder_row(fid)
        if row is None:
            await self._sync_folders_ui_impl()
            return
        try:
            fl = self.query_one("#folders-list", VerticalGroup)
        except Exception:
            return
        expanded = fid in self._expanded_folder_ids
        depth = row.indent
        row.folder_expanded = expanded
        row.set_class(expanded, "-folder-open")
        try:
            row.query_one("#entry-chevron", Label).update(
                FOLDER_ICON_OPEN if expanded else FOLDER_ICON_CLOSED
            )
        except Exception:
            pass

        children = list(fl.children)
        try:
            idx = children.index(row)
        except ValueError:
            return

        if not expanded:
            for w in children[idx + 1:]:
                if not isinstance(w, SidebarEntryRow) or w.indent <= depth:
                    break
                w.remove()
            return

        for w in children[idx + 1:]:
            if not isinstance(w, SidebarEntryRow) or w.indent <= depth:
                break
            w.remove()

        anchor: Widget = row
        for chat in self._chats_by_folder.get(fid, []):
            title = (chat.get("title") or "New chat")[:MAX_CHAT_TITLE_LEN]
            cid = chat.get("id")
            chat_row = SidebarEntryRow(
                title,
                "chat",
                entry_id=cid,
                indent=depth + 1,
                icon=CHAT_ICON,
            )
            await fl.mount(chat_row, after=anchor)
            anchor = chat_row
        anchor = await self._mount_folder_branch_after(fl, anchor, fid, depth)

    async def _mount_folder_branch_after(
        self,
        container: VerticalGroup,
        after: Widget,
        parent_id: str,
        depth: int,
    ) -> Widget:
        """Mount child folders/chats after *after*; return last mounted row."""
        anchor = after
        norm_parent = self._norm_folder_id(parent_id)
        for folder in self._folder_children.get(norm_parent, []):
            child_id = folder.get("id")
            if not child_id:
                continue
            name = (folder.get("name") or "Folder")[:20]
            child_fid = self._norm_folder_id(child_id)
            child_expanded = str(child_fid) in self._expanded_folder_ids
            icon = FOLDER_ICON_OPEN if child_expanded else FOLDER_ICON_CLOSED
            folder_row = SidebarEntryRow(
                name,
                "folder",
                entry_id=child_fid,
                indent=depth + 1,
                folder_expanded=child_expanded,
                icon=icon,
            )
            await container.mount(folder_row, after=anchor)
            anchor = folder_row
            if child_expanded:
                for chat in self._chats_by_folder.get(child_fid, []):
                    title = (chat.get("title") or "New chat")[:MAX_CHAT_TITLE_LEN]
                    cid = chat.get("id")
                    chat_row = SidebarEntryRow(
                        title,
                        "chat",
                        entry_id=cid,
                        indent=depth + 2,
                        icon=CHAT_ICON,
                    )
                    await container.mount(chat_row, after=anchor)
                    anchor = chat_row
                anchor = await self._mount_folder_branch_after(
                    container, anchor, child_fid, depth + 1,
                )
        return anchor

    def _open_chat_by_id(self, chat_id: str) -> None:
        if self.is_thinking or not chat_id:
            return
        self._load_chat(chat_id)

    def _refresh_sidebar_lists(self) -> None:
        """Reload folder/chat tree so UI matches the database."""
        if self.user and self._access_token:
            self._fetch_sidebar_data()
            return
        self._sync_sidebar_ui()

    @work(group="sidebar-ui", exclusive=True)
    async def _sync_sidebar_ui(self) -> None:
        try:
            self._rebuild_sidebar_indexes()
            await self._sync_folders_ui_impl()
            await self._sync_chats_ui_impl()
        except Exception as exc:
            self._db_log(f"_sync_sidebar_ui: {exc}")

    async def _sync_folders_ui_impl(self) -> None:
        self._creating_folder_row = None
        fl = self.query_one("#folders-list", VerticalGroup)
        await fl.remove_children()
        if self._folders:
            await self._mount_folder_tree(fl, None, 0)
        else:
            await fl.mount(
                SidebarEntryRow(
                    "(no folders yet)", "folder", empty=True,
                )
            )

    async def _sync_chats_ui_impl(self) -> None:
        cl = self.query_one("#chats-list", VerticalGroup)
        await cl.remove_children()
        loose = self._uncategorized_chats()
        if loose:
            for i, chat in enumerate(loose):
                title = (chat.get("title") or "New chat")[:MAX_CHAT_TITLE_LEN]
                cid = chat.get("id")
                await cl.mount(
                    SidebarEntryRow(
                        title,
                        "chat",
                        entry_id=cid,
                        index=i,
                        icon=CHAT_ICON,
                    )
                )
        else:
            await cl.mount(
                SidebarEntryRow(
                    "(no chats yet)", "chat", empty=True,
                )
            )

    @work(group="sidebar-ui", exclusive=True)
    async def _sync_folders_ui(self) -> None:
        try:
            self._rebuild_sidebar_indexes()
            await self._sync_folders_ui_impl()
        except Exception as exc:
            self._db_log(f"_sync_folders_ui: {exc}")

    @work(group="sidebar-ui", exclusive=True)
    async def _sync_chats_ui(self) -> None:
        try:
            self._rebuild_sidebar_indexes()
            await self._sync_chats_ui_impl()
        except Exception as exc:
            self._db_log(f"_sync_chats_ui: {exc}")

    def _upsert_sidebar_chat(self, title: str, chat_id: str | None = None) -> None:
        title = (title or "New chat")[:MAX_CHAT_TITLE_LEN]
        if chat_id is not None:
            for chat in self._chats:
                if chat.get("id") == chat_id:
                    chat["title"] = title
                    self._refresh_sidebar_lists()
                    self._update_chat_title()
                    return
        if self._chats and self._chats[0].get("id") is None:
            self._chats[0]["title"] = title
            if chat_id is not None:
                self._chats[0]["id"] = chat_id
        else:
            self._chats.insert(0, {
                "id": chat_id,
                "title": title,
                "folder_id": None,
            })
        self._refresh_sidebar_lists()
        self._update_chat_title()

    async def _mount_folder_tree(
        self,
        container: VerticalGroup,
        parent_id: str | None,
        depth: int,
    ) -> None:
        for folder in self._folder_children.get(parent_id, []):
            fid = folder.get("id")
            if not fid:
                continue
            name = (folder.get("name") or "Folder")[:20]
            expanded = str(fid) in self._expanded_folder_ids
            icon = FOLDER_ICON_OPEN if expanded else FOLDER_ICON_CLOSED
            await container.mount(
                SidebarEntryRow(
                    name,
                    "folder",
                    entry_id=fid,
                    indent=depth,
                    folder_expanded=expanded,
                    icon=icon,
                )
            )
            if expanded:
                for chat in self._chats_by_folder.get(self._norm_folder_id(fid), []):
                    title = (chat.get("title") or "New chat")[:MAX_CHAT_TITLE_LEN]
                    cid = chat.get("id")
                    await container.mount(
                        SidebarEntryRow(
                            title,
                            "chat",
                            entry_id=cid,
                            indent=depth + 1,
                            icon=CHAT_ICON,
                        )
                    )
                await self._mount_folder_tree(
                    container, self._norm_folder_id(fid), depth + 1,
                )

    def _refresh_folders_list(self) -> None:
        self._sync_folders_ui()

    def _refresh_chats_list(self) -> None:
        self._sync_chats_ui()

    SIDEBAR_MENU_WIDTH = 22

    def _close_floating_menu(self) -> None:
        for node in self.query("#sidebar-floating-menu"):
            node.remove()
        for node in self.query("#sidebar-folder-menu"):
            node.remove()

    def _schedule_folder_picker(self, row: SidebarEntryRow) -> None:
        """Open folder picker after the action menu is removed (avoids DuplicateIds)."""
        anchor = getattr(self, "_floating_menu_anchor", None)

        def _show() -> None:
            if anchor is not None:
                x, y = anchor
            else:
                x, y = self._menu_anchor_from_row(row)
            self.mount(
                SidebarFolderFloatingMenu(
                    self._folder_picker_entries(), x, y, row,
                ),
            )

        self._close_floating_menu()
        self.call_later(_show)

    def _menu_anchor_from_row(
        self,
        row: SidebarEntryRow,
        screen_x: int | None = None,
        screen_y: int | None = None,
    ) -> tuple[int, int]:
        """Screen offset for the ⋮ button (menu appears on the dots)."""
        if screen_x is not None and screen_y is not None:
            x = max(0, screen_x - self.SIDEBAR_MENU_WIDTH + 3)
            return x, screen_y
        try:
            btn = row.query_one("#entry-menu-btn")
            offset = btn.absolute_offset
            if offset is not None:
                ox, oy = offset
                x = max(0, ox + btn.size.width - self.SIDEBAR_MENU_WIDTH)
                return x, oy
        except Exception:
            pass
        return 32, 4

    def _open_sidebar_entry_menu(
        self,
        row: SidebarEntryRow,
        screen_x: int,
        screen_y: int,
    ) -> None:
        self._close_floating_menu()
        x, y = self._menu_anchor_from_row(row, screen_x, screen_y)
        self._floating_menu_anchor = (x, y)
        self.mount(SidebarFloatingMenu(row.entry_type, x, y, row))

    def _entry_title_from_store(
        self, row: SidebarEntryRow,
    ) -> str:
        if row.entry_type == "folder" and row.entry_id:
            for folder in self._folders:
                if folder.get("id") == row.entry_id:
                    return folder.get("name") or row._title
        if row.entry_type == "chat" and row.entry_id:
            for chat in self._chats:
                if chat.get("id") == row.entry_id:
                    return chat.get("title") or row._title
        return row._title

    def _cancel_inline_rename(self, row: SidebarEntryRow | None = None) -> None:
        target = row or self._renaming_row
        if target is not None:
            target.cancel_inline_rename()
        if target is self._renaming_row:
            self._renaming_row = None

    def _begin_inline_rename(self, row: SidebarEntryRow) -> None:
        if not row.entry_id:
            return
        self._close_floating_menu()
        self._cancel_inline_new_folder()
        if self._renaming_row is not None and self._renaming_row is not row:
            self._cancel_inline_rename(self._renaming_row)
        row._title = self._entry_title_from_store(row)
        row._display_title = row._format_display_title(row._title, row.indent)
        try:
            row.query_one("#entry-title", Label).update(row._display_title)
        except Exception:
            pass
        self._renaming_row = row
        row.begin_inline_rename()

    def _commit_inline_rename(self, row: SidebarEntryRow, value: str) -> None:
        self._renaming_row = None
        if row.entry_type == "chat":
            self._on_chat_renamed(row.entry_id, value)
        else:
            self._on_folder_renamed(row.entry_id, value)

    def _rename_chat_entry(self, row: SidebarEntryRow) -> None:
        self.call_later(lambda: self._begin_inline_rename(row))

    def _rename_folder_entry(self, row: SidebarEntryRow) -> None:
        self.call_later(lambda: self._begin_inline_rename(row))

    def _on_chat_renamed(self, chat_id: str, name: str | None) -> None:
        if not name or not self._access_token:
            return
        title = name.strip()[:MAX_CHAT_TITLE_LEN]
        if not title:
            return
        try:
            self._api_patch(f"/chats/{chat_id}", {"title": title})
        except Exception as exc:
            self._db_log(f"rename chat: {exc}")
            return
        for chat in self._chats:
            if chat.get("id") == chat_id:
                chat["title"] = title
                break
        self._refresh_sidebar_lists()
        self._update_chat_title()

    def _on_folder_renamed(self, folder_id: str | None, name: str | None) -> None:
        if not name or not self._access_token:
            return
        label = name.strip()[:40]
        if not label:
            return
        try:
            self._api_patch(f"/folders/{folder_id}", {"name": label})
        except Exception as exc:
            self._db_log(f"rename folder: {exc}")
            self.notify(
                f"Could not rename folder: {exc}",
                severity="error",
                timeout=4,
            )
            return
        for folder in self._folders:
            if folder.get("id") == folder_id:
                folder["name"] = label
                break
        self._refresh_sidebar_lists()
        self.notify("Folder renamed", timeout=2)

    def _delete_chat(self, chat_id: str | None) -> None:
        if not chat_id or not self._access_token:
            return
        try:
            self._api_delete(f"/chats/{chat_id}")
        except Exception as exc:
            self._db_log(f"delete chat: {exc}")
            return
        self._chats = [c for c in self._chats if c.get("id") != chat_id]
        if self.current_chat_id == chat_id:
            self.current_chat_id = None
            self._clear_chat_view()
        self._refresh_sidebar_lists()
        self._update_chat_title()

    def _delete_folder(self, folder_id: str | None) -> None:
        if not folder_id or not self._access_token:
            return
        try:
            self._api_delete(f"/folders/{folder_id}")
        except Exception as exc:
            self._db_log(f"delete folder: {exc}")
            return
        removed = self._folder_descendant_ids(folder_id)
        self._folders = [
            f for f in self._folders if f.get("id") not in removed
        ]
        self._expanded_folder_ids -= removed
        for chat in self._chats:
            if chat.get("folder_id") in removed:
                chat["folder_id"] = None
        self._refresh_sidebar_lists()

    def _move_chat_to_folder(self, chat_id: str | None, folder_id: str | None) -> None:
        if not chat_id or not self._access_token:
            return
        folder_id = self._norm_folder_id(folder_id)
        try:
            self._api_patch(f"/chats/{chat_id}", {"folder_id": folder_id})
        except Exception as exc:
            self._db_log(f"move chat to folder: {exc}")
        for chat in self._chats:
            if chat.get("id") == chat_id:
                chat["folder_id"] = folder_id
                break
        if folder_id:
            self._expand_folder_branch(folder_id)
        self._refresh_sidebar_lists()

    def notify(self, message: str, *, title: str = "", severity="information", timeout: float | None = None, markup: bool = True) -> None:
        if message.startswith("Switched to ") and "theme" in message:
            return
        super().notify(message, title=title, severity=severity, timeout=timeout, markup=markup)

    def _toggle_theme(self) -> None:
        self.action_toggle_dark()
        is_dark = "dark" in self.pseudo_classes
        self.query_one("#theme-toggle", Label).update("◑" if is_dark else "◐")
        theme_name = "cosmos-input" if is_dark else "cosmos-input-light"
        for inp in self.query(ChatInput):
            inp.theme = theme_name

    def _toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        if sidebar.has_class("collapsed"):
            sidebar.remove_class("collapsed")
            self._sidebar_open = True
        else:
            sidebar.add_class("collapsed")
            self._sidebar_open = False

    def _clear_chat_view(self) -> None:
        self._remove_regen_bar()
        self.conversation.clear()
        self._last_usage_tokens = None
        self.is_thinking = False
        if self._dot_timer:
            self._dot_timer.stop()
            self._dot_timer = None
        self._active_cosmos = None
        self._stream_worker = None
        messages = self.query_one("#messages", Vertical)
        for child in list(messages.children):
            if child.id != "home-state":
                child.remove()
        try:
            self.query_one("#home-state").display = True
        except Exception:
            pass
        self._clear_attachment()
        try:
            self.query_one("#main-input", ChatInput).disabled = False
        except Exception:
            pass
        self._update_action_btn()
        self._update_token_usage()

    def _new_chat(self) -> None:
        if self.is_thinking:
            return
        self.current_chat_id = None
        self._clear_chat_view()
        self._upsert_sidebar_chat("New chat")
        self._update_chat_title()
        if self.user and self._access_token:
            self._create_chat_db()

    def _new_folder(self, parent_id: str | None = None) -> None:
        if self.is_thinking:
            return
        if not self.user or not self._access_token:
            return
        self._close_floating_menu()
        self._cancel_inline_rename()
        self._cancel_inline_new_folder()
        pid = self._norm_folder_id(parent_id)
        self.call_later(lambda: self._begin_inline_new_folder(pid))

    def _new_subfolder(self, parent_id: str | None) -> None:
        if not parent_id:
            return
        self._new_folder(parent_id=parent_id)

    def _folder_row_anchor_for_insert(
        self, parent_id: str | None,
    ) -> tuple[VerticalGroup, Widget | None, int]:
        """Return (list, mount-after widget, indent) for a new folder row."""
        fl = self.query_one("#folders-list", VerticalGroup)
        parent_id = self._norm_folder_id(parent_id)
        if not parent_id:
            anchor: Widget | None = None
            for child in fl.children:
                if (
                    isinstance(child, SidebarEntryRow)
                    and child.entry_type == "folder"
                    and child.indent == 0
                    and not child._creating
                    and not child._empty
                ):
                    anchor = child
            return fl, anchor, 0

        parent_row = self._find_folder_row(parent_id)
        if parent_row is None:
            return fl, None, 0
        depth = parent_row.indent + 1
        children = list(fl.children)
        idx = children.index(parent_row)
        anchor = parent_row
        for w in children[idx + 1:]:
            if isinstance(w, SidebarEntryRow) and w.indent > parent_row.indent:
                anchor = w
            elif isinstance(w, SidebarEntryRow):
                break
        return fl, anchor, depth

    @work
    async def _begin_inline_new_folder(self, parent_id: str | None = None) -> None:
        if not self.user or not self._access_token:
            return
        parent_id = self._norm_folder_id(parent_id)
        fl, anchor, depth = self._folder_row_anchor_for_insert(parent_id)

        for child in list(fl.children):
            if isinstance(child, SidebarEntryRow) and child._empty:
                child.remove()

        if parent_id:
            self._expand_folder_branch(parent_id)
            parent_row = self._find_folder_row(parent_id)
            if parent_row is not None:
                fid = parent_id
                if fid not in self._expanded_folder_ids:
                    self._expanded_folder_ids.add(fid)
                    await self._apply_folder_expand_toggle(fid)
                fl, anchor, depth = self._folder_row_anchor_for_insert(parent_id)

        row = SidebarEntryRow(
            "",
            "folder",
            indent=depth,
            icon=FOLDER_ICON_CLOSED,
            creating=True,
            create_parent_id=parent_id,
        )
        if anchor is not None:
            await fl.mount(row, after=anchor)
        else:
            await fl.mount(row)
        self._creating_folder_row = row

    def _cancel_inline_new_folder(
        self, row: SidebarEntryRow | None = None,
    ) -> None:
        target = row or self._creating_folder_row
        if target is not None:
            try:
                target.remove()
            except Exception:
                pass
        if target is self._creating_folder_row:
            self._creating_folder_row = None
        self.call_later(self._ensure_folders_empty_placeholder)

    def _ensure_folders_empty_placeholder(self) -> None:
        if self._folders or self._creating_folder_row is not None:
            return
        try:
            fl = self.query_one("#folders-list", VerticalGroup)
        except Exception:
            return
        if any(
            isinstance(c, SidebarEntryRow) and (c._empty or c._creating)
            for c in fl.children
        ):
            return
        if not list(fl.children):
            self.call_later(self._mount_folders_empty_placeholder)

    @work
    async def _mount_folders_empty_placeholder(self) -> None:
        fl = self.query_one("#folders-list", VerticalGroup)
        if self._folders:
            return
        if any(isinstance(c, SidebarEntryRow) for c in fl.children):
            return
        await fl.mount(
            SidebarEntryRow("(no folders yet)", "folder", empty=True),
        )

    def _commit_inline_new_folder(
        self, row: SidebarEntryRow, value: str,
    ) -> None:
        self._creating_folder_row = None
        name = (value or "").strip()
        parent_id = row.create_parent_id
        try:
            row.remove()
        except Exception:
            pass
        if not name:
            self.call_later(self._ensure_folders_empty_placeholder)
            return
        self._on_folder_named(name, parent_id)

    def _expand_folder_branch(self, folder_id: str | None) -> None:
        """Expand folder and all ancestors so nested items are visible."""
        fid = self._norm_folder_id(folder_id)
        while fid:
            self._expanded_folder_ids.add(fid)
            parent_id: str | None = None
            for folder in self._folders:
                if str(folder.get("id")) == fid:
                    parent_id = self._norm_folder_id(folder.get("parent_id"))
                    break
            fid = parent_id

    def _on_folder_named(
        self, name: str | None, parent_id: str | None = None,
    ) -> None:
        if not name:
            return
        parent_id = self._norm_folder_id(parent_id)
        self._create_folder_db(name, parent_id=parent_id)

    @work(thread=True)
    def _create_chat_db(self) -> None:
        if not self.user or not self._access_token:
            return
        try:
            row = self._api_post("/chats", {"title": "New chat"})
            chat_id = row.get("id")
            if not chat_id:
                return

            def _apply() -> None:
                self.current_chat_id = chat_id
                if self._chats and self._chats[0].get("id") is None:
                    self._chats[0]["id"] = chat_id
                elif not any(c.get("id") == chat_id for c in self._chats):
                    self._chats.insert(0, {
                        "id": chat_id,
                        "title": "New chat",
                        "folder_id": None,
                    })
                self._refresh_sidebar_lists()

            self.call_from_thread(_apply)
        except Exception as exc:
            self._db_log(f"_create_chat_db error: {exc}")

    @work(thread=True)
    def _create_folder_db(
        self, name: str, parent_id: str | None = None,
    ) -> None:
        if not self.user or not self._access_token:
            return
        parent_id = self._norm_folder_id(parent_id)
        payload: dict = {"name": name[:40]}
        if parent_id:
            payload["parent_id"] = parent_id
        try:
            row = self._api_post("/folders", payload)
            folder_id = row.get("id")
            if not folder_id:
                return
            saved_parent = self._norm_folder_id(row.get("parent_id")) or parent_id

            def _apply() -> None:
                self._folders.insert(0, {
                    "id": folder_id,
                    "name": (row.get("name") or name)[:40],
                    "parent_id": saved_parent,
                })
                if saved_parent:
                    self._expand_folder_branch(saved_parent)
                self._refresh_sidebar_lists()
                if saved_parent:
                    self.notify("Subfolder created", timeout=2)
                else:
                    self.notify("Folder created", timeout=2)

            self.call_from_thread(_apply)
        except Exception as exc:
            self._db_log(f"_create_folder_db error: {exc}")
            hint = str(exc)

            def _err() -> None:
                self.notify(
                    f"Could not create folder: {hint}",
                    severity="error",
                    timeout=5,
                )

            self.call_from_thread(_err)

    def _open_chat_at_index(self, idx: int | None) -> None:
        loose = self._uncategorized_chats()
        if self.is_thinking or idx is None:
            return
        if 0 <= idx < len(loose):
            chat_id = loose[idx].get("id")
            if chat_id:
                self._open_chat_by_id(chat_id)

    @work(thread=True)
    def _load_chat(self, chat_id: str) -> None:
        if not self._access_token:
            return
        try:
            messages = self._api_get(f"/messages/{chat_id}")
            self.app.call_from_thread(self._render_chat, chat_id, messages)
        except Exception as exc:
            self._db_log(f"_load_chat error: {exc}")

    def _render_chat(self, chat_id: str, messages: list[dict]) -> None:
        self.current_chat_id = chat_id
        self._update_chat_title()
        self.conversation = [
            {
                "role": m["role"],
                "content": deserialize_message_content(m["content"]),
            }
            for m in messages
        ]

        msgs_widget = self.query_one("#messages", Vertical)
        for child in list(msgs_widget.children):
            if child.id != "home-state":
                child.remove()

        self._last_usage_tokens = None

        if not messages:
            try:
                self.query_one("#home-state").display = True
            except Exception:
                pass
            self._update_token_usage()
            return

        try:
            self.query_one("#home-state").display = False
        except Exception:
            pass

        for msg in messages:
            if msg["role"] == "user":
                display = message_content_for_display(msg["content"])
                msgs_widget.mount(UserMessage(display))
            elif msg["role"] == "assistant":
                cm = CosmosMessage()
                msgs_widget.mount(cm)
                content = msg["content"]
                cm.finish_dot()
                self.set_timer(0.05, lambda c=cm, t=content: asyncio.create_task(c.set_content(t)))

        self._scroll_end()
        self._update_token_usage()

    # ── send ──────────────────────────────────────────────────────────────────

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        text = event.value.strip()
        if self.is_thinking:
            return
        if not text and not self.attachment:
            return
        event.input.clear()
        await self._send(text)

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

    async def _send(self, text: str) -> None:
        self._remove_regen_bar()
        messages = self.query_one("#messages", Vertical)

        try:
            self.query_one("#home-state").display = False
        except Exception:
            pass

        display = attachment_display_text(text, self.attachment)
        await messages.mount(UserMessage(display))

        content = build_user_message_content(text, self.attachment)
        self._clear_attachment()

        self.conversation.append({"role": "user", "content": content})

        if self.current_chat_id is None:
            self._upsert_sidebar_chat("New chat")

        cosmos = CosmosMessage()
        await messages.mount(cosmos)
        self._active_cosmos = cosmos

        self.is_thinking = True
        self.query_one("#main-input", ChatInput).disabled = True
        self._update_action_btn()
        self._start_dot(cosmos)
        self._last_usage_tokens = None
        self._scroll_end()
        self._update_token_usage()
        self._stream_worker = self._stream(cosmos)

        if self.user:
            self._persist_user_message(
                display,
                serialize_message_content(content),
            )

    # ── db persistence ────────────────────────────────────────────────────────

    def _db_log(self, msg: str) -> None:
        log_path = Path.home() / ".cosmos" / "db.log"
        try:
            with open(log_path, "a") as f:
                f.write(f"{msg}\n")
        except Exception:
            pass

    @work(thread=True)
    def _persist_user_message(self, display_text: str, content: str) -> None:
        if not self.user or not self._access_token:
            self._db_log("persist skipped: no user or token")
            return
        try:
            new_chat = self.current_chat_id is None
            if new_chat:
                row = self._api_post("/chats", {"title": "New chat"})
                self._db_log(f"chat insert ok: {row}")
                chat_id = row.get("id")
                if not chat_id:
                    self._db_log("chat insert returned no id")
                    return

                def _set_chat() -> None:
                    self.current_chat_id = chat_id
                    self._upsert_sidebar_chat("New chat", chat_id)

                self.app.call_from_thread(_set_chat)
            else:
                chat_id = self.current_chat_id

            row2 = self._api_post("/messages", {
                "chat_id": chat_id,
                "role": "user",
                "content": content,
            })
            self._db_log(f"user msg insert ok: {row2.get('id')}")

            if new_chat:
                title = _fetch_title_from_llm(display_text) or _title_from_message(display_text)
                self._db_log(f"chat title: {title!r}")
                try:
                    self._api_patch(f"/chats/{chat_id}", {"title": title})
                except Exception as exc:
                    self._db_log(f"chat title patch error: {exc}")

                def _apply_title() -> None:
                    self._upsert_sidebar_chat(title, chat_id)
                    self._update_chat_title()

                self.app.call_from_thread(_apply_title)
        except Exception as exc:
            self._db_log(f"_persist_user_message error: {exc}")

    @work(thread=True)
    def _db_save_message(self, chat_id: str, role: str, content: str) -> None:
        if not self._access_token:
            return
        try:
            row = self._api_post("/messages", {
                "chat_id": chat_id,
                "role": role,
                "content": content,
            })
            self._db_log(f"assistant msg insert ok: {row.get('id')}")
        except Exception as exc:
            self._db_log(f"_db_save_message error: {exc}")

    # ── streaming ─────────────────────────────────────────────────────────────

    @work
    async def _stream(self, cosmos: CosmosMessage) -> None:
        openrouter_key = (self.user or {}).get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_key:
            msg = "No OpenRouter API key found. Log out and log back in, or set OPENROUTER_API_KEY in your environment."
            await cosmos.stream_append(msg)
            self.conversation.append({"role": "assistant", "content": msg})
            self.is_thinking = False
            self._stream_worker = None
            self._stop_dot(cosmos)
            self._active_cosmos = None
            self.query_one("#main-input", ChatInput).disabled = False
            self.query_one("#main-input", ChatInput).focus()
            self._update_action_btn()
            self._show_regen_bar()
            return

        all_models = self._all_models()
        primary = all_models[self.model_idx] if self.model_idx < len(all_models) else FREE_MODELS[0]

        # Ollama model — single attempt, no fallback queue
        if primary[0].startswith("ollama:"):
            ollama_name = primary[0].split(":", 1)[1]
            model_queue = [(ollama_name, primary[1])]
            _is_ollama = True
        else:
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
            _is_ollama = False

        accumulated = ""
        streaming = True

        async def _render_loop() -> None:
            last = ""
            while streaming or accumulated != last:
                if accumulated != last:
                    last = accumulated
                    await cosmos.stream_append(last)
                    self._update_token_usage(extra_assistant=accumulated)
                    self._scroll_end()
                await asyncio.sleep(0.08)

        render_task = asyncio.create_task(_render_loop())

        for i, (model_id, model_name) in enumerate(model_queue):
            if i > 0:
                accumulated = f"Switching to {model_name}…"

            accumulated = ""

            try:
                if _is_ollama:
                    req_url = "http://localhost:11434/v1/chat/completions"
                    req_headers = {"Content-Type": "application/json"}
                else:
                    req_url = API_URL
                    req_headers = {
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                    }
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST", req_url,
                        headers=req_headers,
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
                                usage = obj.get("usage")
                                if usage:
                                    total = usage.get("total_tokens")
                                    if total is None:
                                        total = usage.get("prompt_tokens", 0) + usage.get(
                                            "completion_tokens", 0
                                        )
                                    if total:
                                        self._last_usage_tokens = int(total)
                                        self._update_token_usage()
                                token = obj["choices"][0]["delta"].get("content") or ""
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                            if token:
                                accumulated += token
            except Exception:
                continue

            if accumulated:
                break

        streaming = False
        await render_task

        if not accumulated:
            accumulated = "[All models failed. Please try again later.]"
            await cosmos.stream_append(accumulated)

        self.conversation.append({"role": "assistant", "content": accumulated})

        if self.user and self.current_chat_id:
            self._db_save_message(self.current_chat_id, "assistant", accumulated)

        self.is_thinking = False
        self._stream_worker = None
        self._stop_dot(cosmos)
        self._active_cosmos = None
        inp = self.query_one("#main-input", ChatInput)
        inp.disabled = False
        inp.focus()
        self._update_action_btn()
        self._show_regen_bar()
        self._update_token_usage()
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
                if inp.text.strip() or self.attachment:
                    btn.add_class("can-send")
                else:
                    btn.remove_class("can-send")
        except Exception:
            pass

    def _cancel_stream(self) -> None:
        self._remove_regen_bar()
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

    def on_click(self, event: Click) -> None:
        wid = event.widget.id
        if wid == "menu-btn":
            event.stop()
            self._toggle_sidebar()
        elif wid == "new-chat-btn":
            event.stop()
            self._new_chat()
        elif wid == "new-folder-btn":
            event.stop()
            self._new_folder()
        elif wid == "sidebar-logout-btn":
            event.stop()
            self._logout()
        elif wid == "theme-toggle":
            event.stop()
            self._toggle_theme()
        elif self.query("#sidebar-floating-menu") or self.query("#sidebar-folder-menu"):
            node = event.widget
            while node is not None:
                if isinstance(
                    node, (SidebarFloatingMenu, SidebarFolderFloatingMenu),
                ):
                    return
                node = node.parent
            self._close_floating_menu()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "attach-btn":
            event.stop()
            if self.attachment:
                self._clear_attachment()
            else:
                self._pick_file()
            self._update_action_btn()
        elif btn_id == "model-btn":
            event.stop()
            self.push_screen(ModelDropdown(self._all_models()), self._on_model_selected)
        elif btn_id == "action-btn":
            event.stop()
            if self.is_thinking:
                self._cancel_stream()
            else:
                inp = self.query_one("#main-input", ChatInput)
                text = inp.text.strip()
                if text or self.attachment:
                    inp.clear()
                    await self._send(text)

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
            self.attachment = extract_file_attachment(path)
            kind = "image" if self.attachment.kind == "image" else "file"
            self.query_one("#attach-label", Label).update(
                f" {kind}: {path.name}"
            )
            self.query_one("#attach-btn", Button).label = "✕"
            self._update_action_btn()
        except Exception as exc:
            self.attachment = None
            self.query_one("#attach-label", Label).update(f" [!] {exc}")
            self.query_one("#attach-btn", Button).label = "+"
            self._update_action_btn()

    def _clear_attachment(self) -> None:
        self.attachment = None
        self.query_one("#attach-btn", Button).label = "+"
        self.query_one("#attach-label", Label).update("")

    # ── model ─────────────────────────────────────────────────────────────────

    def _on_model_selected(self, idx: int | None) -> None:
        if idx is None:
            return
        all_models = self._all_models()
        if not (0 <= idx < len(all_models)):
            return
        model_id = all_models[idx][0]
        if model_id == "ollama:---":
            return
        self.model_idx = idx
        self.query_one("#model-btn", Button).label = all_models[idx][1]
        self._update_token_usage()

    # ── regenerate ────────────────────────────────────────────────────────────

    def _show_regen_bar(self) -> None:
        self._remove_regen_bar()
        if not self.conversation or self.conversation[-1]["role"] != "assistant":
            return
        try:
            text = self.conversation[-1]["content"]
            messages = self.query_one("#messages", Vertical)
            bar = RegenerateBar(copy_text=text)
            self._regen_bar = bar
            messages.mount(bar)
        except Exception:
            pass

    def _remove_regen_bar(self) -> None:
        if self._regen_bar:
            try:
                self._regen_bar.remove()
            except Exception:
                pass
            self._regen_bar = None

    def on_regenerate_bar_requested(self, event: RegenerateBar.Requested) -> None:
        self._do_regenerate()

    def _do_regenerate(self) -> None:
        if self.is_thinking:
            return
        self._remove_regen_bar()
        self._last_usage_tokens = None
        # Drop last assistant turn from conversation
        if self.conversation and self.conversation[-1]["role"] == "assistant":
            self.conversation.pop()
        # Remove the last CosmosMessage widget
        try:
            messages = self.query_one("#messages", Vertical)
            kids = [c for c in messages.children if c.id != "home-state"]
            if kids and isinstance(kids[-1], CosmosMessage):
                kids[-1].remove()
        except Exception:
            pass
        # Re-stream
        cosmos = CosmosMessage()
        try:
            self.query_one("#messages", Vertical).mount(cosmos)
        except Exception:
            return
        self._active_cosmos = cosmos
        self.is_thinking = True
        self.query_one("#main-input", ChatInput).disabled = True
        self._update_action_btn()
        self._start_dot(cosmos)
        self._scroll_end()
        self._stream_worker = self._stream(cosmos)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _context_limit(self) -> int:
        all_models = self._all_models()
        model_id = all_models[self.model_idx][0] if self.model_idx < len(all_models) else FREE_MODELS[0][0]
        return MODEL_CONTEXT_TOKENS.get(model_id, DEFAULT_CONTEXT_TOKENS)

    def _conversation_tokens(self, *, extra_assistant: str = "") -> int:
        if self._last_usage_tokens is not None and not extra_assistant:
            return self._last_usage_tokens
        total = 0
        for msg in self.conversation:
            total += _estimate_tokens(msg.get("content", "")) + 4
        if extra_assistant:
            total += _estimate_tokens(extra_assistant) + 4
        return total

    def _update_token_usage(self, *, extra_assistant: str = "") -> None:
        try:
            used = self._conversation_tokens(extra_assistant=extra_assistant)
            limit = self._context_limit()
            pct = (used / limit * 100) if limit else 0
            label = self.query_one("#token-usage", Label)
            label.update(
                f"{_format_token_count(used)} / {_format_token_count(limit)} ({pct:.0f}%)"
            )
            label.remove_class("warn", "full")
            if pct >= 95:
                label.add_class("full")
            elif pct >= 80:
                label.add_class("warn")
        except Exception:
            pass

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

    def action_close_sidebar_menu(self) -> None:
        self._close_floating_menu()
        self._floating_menu_anchor = None
        self._cancel_inline_rename()
        self._cancel_inline_new_folder()

    def action_cancel_inline_rename(self) -> None:
        self._cancel_inline_rename()
        self._cancel_inline_new_folder()

    def action_clear_chat(self) -> None:
        self.current_chat_id = None
        self._clear_chat_view()
        self._update_chat_title()


def main() -> None:
    CosmosApp().run()


if __name__ == "__main__":
    main()
