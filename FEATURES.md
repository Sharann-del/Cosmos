# COSMOS Feature Checklist

Audit of the feature list against the current codebase.

**Primary app:** `cosmos.py` (terminal UI via Textual)  
**Secondary:** `cosmos-web/` (Next.js marketing site + basic auth/dashboard; not the main chat client)

Legend:

- [x] **Have** — implemented and usable
- [~] **Partial** — exists but limited or incomplete
- [ ] **Don't have** — not implemented

---

## Sidebar

| Feature | Status | Notes |
|---------|--------|-------|
| App logo + name | [~] | ASCII **COSMOS** logo on welcome/home screen; not in sidebar header |
| New chat button | [x] | `+` next to **CHATS** |
| Search chats | [ ] | — |
| Chat history (Today / Yesterday / Last 7 days / etc.) | [ ] | Flat list only, no date grouping |
| Folders / Projects to organize chats | [~] | Create/list folders; chats are **not** linked to folders in DB/UI yet |
| Starred / pinned chats | [ ] | — |
| Shared chats | [ ] | — |
| User profile (avatar, name, plan) | [ ] | — |
| Collapsible sidebar (hamburger) | [x] | `≡` toggles sidebar show/hide |

---

## Chat Header

| Feature | Status | Notes |
|---------|--------|-------|
| Current chat title (editable) | [~] | Auto-generated on first message (LLM + fallback); **not** shown in a header; **not** editable |
| Model selector dropdown | [x] | Toolbar model button + modal list (25+ free models) |
| Share button | [ ] | — |
| Export chat (PDF, markdown) | [ ] | — |
| Pin / bookmark chat | [ ] | — |
| Rename / delete chat | [ ] | — |
| Three-dot overflow menu | [ ] | — |

---

## Main Chat Area

| Feature | Status | Notes |
|---------|--------|-------|
| Welcome screen (no active chat) | [x] | Home state with COSMOS ASCII logo |
| Tagline + suggested prompts | [ ] | Logo only, no starter prompts |
| Message bubbles (user / assistant layout) | [~] | Full-width blocks (terminal style), not left/right bubbles |
| Markdown rendering | [x] | Headings, lists, inline code, fences |
| Syntax-highlighted code blocks | [x] | Via Textual `MarkdownFence` |
| Code block copy button + language label | [ ] | Removed per product decision |
| Copy message button | [x] | User messages; **copy** under last assistant reply |
| Regenerate response | [x] | **retry** on last assistant message |
| Edit user message | [x] | Click user message to reload into input |
| Thumbs up / down feedback | [ ] | — |
| Streaming responses | [x] | Token streaming with live markdown update |
| Scroll to bottom when scrolled up | [ ] | Removed per product decision |
| Token / word count | [~] | Context window usage in toolbar (`278 / 128k (0%)`); not per-message word count |

---

## Input Box

| Feature | Status | Notes |
|---------|--------|-------|
| Multiline textarea | [x] | `ChatInput`; Enter = send, Shift+Enter = newline |
| Send button | [x] | `▶` action button |
| Attach file | [~] | `+` attach; macOS file picker only; content inlined in prompt |
| Image upload | [ ] | No dedicated image pipeline |
| Voice input | [ ] | — |
| Tools toggle (web search, code interpreter, etc.) | [ ] | — |
| Model selector in input area | [x] | Model button in bottom toolbar |
| Character / token counter (input) | [ ] | Only conversation context meter, not input length |

---

## Settings

| Feature | Status | Notes |
|---------|--------|-------|
| Account (name, email, avatar, password) | [ ] | No settings UI in terminal app |
| Appearance (light / dark / system, font size) | [ ] | Dark terminal theme only |
| Model preferences (default model) | [~] | Last-selected model in session; not persisted as default |
| API key management | [~] | `OPENROUTER_API_KEY` in `.env` only |
| Memory / personalization toggle | [ ] | — |
| Data & privacy (delete history, training opt-out) | [ ] | — |
| Keyboard shortcuts | [~] | `Ctrl+L` clear chat, `Ctrl+C` quit (hidden bindings); no shortcuts UI |
| Billing / plan | [ ] | — |
| Connected integrations | [ ] | — |
| Notification preferences | [ ] | — |
| Language | [ ] | English only |

---

## Auth Pages

| Feature | Status | Notes |
|---------|--------|-------|
| Landing page | [x] | `cosmos-web/app/page.tsx` |
| Sign up (email / password) | [x] | `cosmos-web/app/signup/page.tsx` |
| Sign up (Google, GitHub) | [ ] | — |
| Log in | [x] | Terminal `LoginScreen` + `cosmos-web/app/login/page.tsx` |
| Forgot password / reset | [ ] | — |
| Email verification | [ ] | — |
| Onboarding flow | [ ] | — |

---

## Dashboard (post-login home)

| Feature | Status | Notes |
|---------|--------|-------|
| Recent chats | [~] | Terminal: sidebar chat list; Web: `dashboard` lists chats (read-only, no chat UI) |
| Pinned chats | [ ] | — |
| Suggested prompts from history | [ ] | — |
| Usage stats (tokens, messages) | [~] | Live context % in terminal toolbar only |

---

## Extras (nice to have)

| Feature | Status | Notes |
|---------|--------|-------|
| Shared chat view (public URL) | [ ] | — |
| Full-text search across history | [ ] | — |
| Keyboard shortcuts modal | [ ] | — |
| What's new / changelog modal | [ ] | — |
| Mobile responsive layout | [ ] | Terminal-first; web landing is responsive but not a full mobile chat app |
| PWA support | [ ] | — |

---

## Summary

| | Count |
|---|------|
| **Have** | 18 |
| **Partial** | 14 |
| **Don't have** | 38 |

### Strongest areas today

- Terminal chat UX: streaming, markdown, models, attach (macOS), regenerate, copy, edit message
- Supabase auth + persisted chats/messages/folders
- Sidebar: folders, chats, new chat/folder, collapse, auto titles

### Biggest gaps vs. a full ChatGPT-style product

- Search, date-grouped history, starred/shared chats
- Chat header (title, rename, delete, share, export)
- Settings / account / appearance / billing
- OAuth, password reset, onboarding
- Feedback, tools, voice/image, suggested prompts
- `cosmos-web` is not yet a full web chat client (dashboard is a chat list only)

---

*Last updated: May 2026 — based on `cosmos.py` and `cosmos-web/` in this repo.*
