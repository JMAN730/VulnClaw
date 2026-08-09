# Keyboard-navigable config panel for the classic REPL

Date: 2026-08-09
Branch: `JMAN730/87-i18n-support` (PR #93)
Related: issue #87, PR #93

## Problem

PR #93 gave the Rust/ratatui TUI a keyboard-navigable `/config` panel for LLM settings. It
deliberately left the classic REPL alone, because issue #87 scoped the REPL editor out (story 30,
"Out of Scope"). That scoping is now reversed: the REPL `/config` surface is in scope, and unlike
the ratatui panel it must cover **every** section the current editor covers, not only LLM.

Today `/config` in the REPL (`vulnclaw/cli/main.py:229` → `vulnclaw/cli/tui.py:2571
run_config_tui`) is a section menu wrapping five prompt chains: `_edit_llm_config`,
`_edit_session_config`, `_edit_safety_config`, `_edit_recon_config`, `_edit_mcp_config`. Roughly
55 fields, asked one question at a time. Changing a single value means walking the whole chain for
that section. The same complaint issue #87 opened with, on a surface the issue never fixed.

## Goal

Replace the prompt chains with a single keyboard-navigable panel covering llm, session, safety,
recon and MCP — one draft, one Save, Escape discards.

Non-goal: expanding the field set. The panel exposes exactly the fields the wizard exposes today
(llm 11, session 18, safety 9, recon 13, MCP servers). The schema carries ~60 further session and
subagent knobs; those stay `vulnclaw config set` territory.

## Decisions

### Panel shape — collapsible section groups

One scrolling panel. Each of the five sections is a collapsible group; a collapsed group shows a
one-line summary derived from the draft. Up/down walks the visible rows across every expanded
group, so nothing needs a second screen.

```
▸ LLM        openai · gpt-4o · key ●●●●
▾ SESSION
    Output dir      ./out
    Engine          react
    Max rounds      30
  ...
▸ SAFETY     python exec on · safe
▸ RECON      6 keys set
▸ MCP        3 servers

[Save]  Esc discards
```

MCP nests one level deeper: expanding MCP lists each server as its own collapsible sub-group that
expands to its fields (enabled, priority, description, transport type/command/args/url/env/
timeouts), with `[+ Add server]` as an action row.

```
▾ MCP
    ▸ filesystem   stdio · enabled
    ▾ github       sse · enabled
        Enabled      yes
        Priority     1
        Transport    sse
        URL          https://…
        Env          2 vars
    [+ Add server]
```

### Rendering — prompt_toolkit `Application`, Rich draws the body

`prompt_toolkit` is already a hard dependency (`pyproject.toml:30`) and `_run_pt_tui`
(`tui.py:490`) already runs a full-screen `Application` whose body is Rich output piped through
`ANSI` into a `FormattedTextControl` (`tui.py:559`). The panel reuses that exact pattern, which
keeps the app's visual language (`C_PRIMARY`, `box.ROUNDED`, `_mask_secret`) and avoids
hand-rolling cross-platform key decoding.

Rejected: Rich `Live` plus a hand-written `msvcrt`/`termios` key reader (re-implements what
prompt_toolkit exists to provide). Rejected: Textual (retired on this branch, not in
`pyproject.toml`; too large a dependency for one editor).

### Structure — pure model, thin shell

Three pieces, so that behavior is testable without a TTY and `tui.py` does not grow past 3,000
lines.

**`vulnclaw/cli/config_panel.py`** — pure model. No prompt_toolkit, no Rich, no I/O.
`ConfigPanelModel(config)` deep-copies the config into a draft and owns the row tree, focus,
expansion and edit state.

Public surface:

| Method | Behavior |
| --- | --- |
| `rows()` | flattened list of currently visible rows |
| `viewport(height)` | visible slice with the focused row kept on screen |
| `focus_next()` / `focus_prev()` | move focus among visible rows |
| `toggle_expand()` | expand/collapse the focused group |
| `collapse()` / `expand()` | left/right key semantics |
| `activate()` | Enter on the focused row: toggle bool, open dropdown, begin edit, or run action |
| `set_edit_text(str)` / `commit_edit()` / `cancel_edit()` | inline text editing |
| `select_option(delta)` / `commit_option()` / `cancel_option()` | dropdown navigation |
| `toggle_reveal()` | global secret reveal |
| `begin_fetch()` / `apply_fetch_result(generation, models, error)` | model fetch, thread-free in tests |
| `add_server()` / `delete_server()` | MCP list mutation |
| `validate()` | returns `list[str]` of blocking errors |
| `draft` | the edited `VulnClawConfig` |

**`vulnclaw/cli/config_panel_render.py`** — `render_panel(model) -> rich.console.Group`. Pure
function, no state. Separate from the model so a visual change cannot break behavior tests, and
snapshot-testable with a recording `Console`.

**`vulnclaw/cli/tui.py`** — `run_config_tui()` becomes a dispatcher:

```python
def run_config_tui() -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        _run_config_panel()
    else:
        _run_config_wizard()   # today's body, renamed
```

`_run_config_panel` builds the model, builds an `Application` whose `KeyBindings` map keys onto
model methods, renders `ANSI(render_panel(model))`, and on save calls `save_config(model.draft)`.

### Non-TTY fallback

The five `_edit_*_config` functions and the `_prompt_*_value` helpers stay exactly as they are and
become the non-TTY path, reached when stdin or stdout is not a TTY — the same check
`_read_config_prompt_raw` already makes at `tui.py:1950`. Piped and scripted use keeps working,
and the three existing tests
(`test_tui_llm_config_prompt_saves_provider_and_api_key`,
`test_config_tui_escape_exits_without_saving`,
`test_config_tui_llm_editor_shows_models_for_selected_provider`) keep passing unchanged.

Cost accepted: two code paths for the same editor.

### Row model

Three row kinds:

- **group** — a section, or an MCP server. Expandable. Renders a summary when collapsed.
- **field** — one config value. Carries a value kind.
- **action** — `[Fetch models]`, `[+ Add server]`, `[Delete server]`, `[Save]`.

Field value kinds and how Enter edits them:

| Kind | Fields | Enter behavior |
| --- | --- | --- |
| text | base_url, reasoning_effort, output_dir, fofa_email, dir_wordlist_path, MCP command/url/description | inline text buffer; `!clear` empties, blank keeps current (wizard parity) |
| secret | api_key, all six recon keys | inline text buffer starting empty; displayed via `_mask_secret` |
| secret list | api_keys | comma-separated buffer starting empty; displayed via `_mask_key_list` |
| bool | auto_save, show_thinking, enable_python_execute, … | toggles immediately, no buffer |
| choice | provider, auth_mode, report_format, poc_language, engine, language, python_execute_mode, transport type | inline dropdown: up/down moves, Enter commits, Esc cancels back to the prior value |
| int / float | max_tokens, max_rounds, http_timeout, ratios, timeouts | inline text buffer, parsed on commit |
| list | MCP args | comma-separated text buffer, split by `_split_csv_items` |
| env | MCP transport env | `KEY=value, KEY=value` buffer, same parser as `_prompt_env_value` |
| model | llm.model | dropdown when models have been fetched, otherwise text buffer |

Secrets are masked by default and revealed globally by `toggle_reveal()`. The six recon keys become
secret rows here; the wizard edits them as plain text (`tui.py:2409`) even though its summary masks
them (`tui.py:2218`). Treating them as secrets in the panel is a deliberate correction, not an
oversight.

### Key bindings

Mirrors the ratatui panel (`tui/src/app.rs:1149 config_panel_handle_key`) so the two surfaces feel
the same, plus the keys the tree needs.

| Key | Action |
| --- | --- |
| Up / Down | move focus |
| Tab / Shift+Tab | move focus (alias) |
| Left | collapse focused group, or jump to the parent group from a field |
| Right | expand focused group |
| Space | toggle group expansion; toggle a bool field; open a choice dropdown |
| Enter | activate focused row |
| Ctrl+R, or `V` when not editing | toggle secret reveal |
| Ctrl+S | save |
| Esc | cancel dropdown → else cancel edit → else discard and close |
| Ctrl+C | discard and close |

### Draft and save

`copy.deepcopy(load_config())` on open. Every edit lands on the draft; the live config on disk is
untouched until Save. Save calls `save_config(draft)` once and closes. Esc discards.

Changing `llm.provider` applies `apply_provider_preset` to the draft (rewriting base_url and
model, matching `tui.py:2259`), clears any fetched model list, and bumps the fetch generation.

`llm.api_keys` (failover pool) and `llm.api_key` both stay as editable rows — unlike the ratatui
panel, which clears the pool on save because it has no row for it. When the pool is non-empty and
a single key is also set, the LLM group renders a note that the pool takes precedence, so the
precedence rule is visible instead of silently applied.

### Model fetch

`[Fetch models]` is an action row inside the LLM group. It runs `fetch_provider_models` on a
`threading.Thread`; the result is marshaled back with `loop.call_soon_threadsafe` plus
`app.invalidate()`. Widgets are never mutated from the thread.

A generation counter guards stale results, mirroring the ratatui implementation
(`tui/src/app.rs:1034`): incremented on the main thread at fetch start and on any change to
provider, base_url or api_key; captured by closure; compared as the first statement of the
completion handler. `apply_fetch_result(generation, models, error)` lives on the model, so tests
exercise stale-result handling with no thread at all.

Fetch is disabled with a hint until base_url and a usable key are present. Failure sets an inline
error and leaves the model row as a text buffer.

### Validation and errors

- Int/float commits that do not parse keep the edit open and set a row-level error.
- MCP server names may not be blank or duplicate. Servers in `BUILTIN_MCP_SERVERS` cannot be
  deleted (matching `tui.py:2561`).
- Save runs `VulnClawConfig.model_validate(draft.model_dump())`; the first pydantic error is shown
  inline and blocks the save.
- Save is blocked when `auth_mode == "static"` and both `api_key` and `api_keys` are empty.
- A base_url that does not start with `http://` or `https://` warns once and saves on a second
  Save, mirroring `url_warning_acknowledged` in the ratatui panel.
- Every error renders inside the panel. Nothing is written to disk on a blocked save.

### i18n

All panel strings go through `_()` under a new `tui.config_panel.*` key family: section names, row
labels, hints, action labels, fetch-state copy, validation messages. Added to both `en.json` and
`zh.json`. This closes issue #87 story 31 on the surface that can actually reach the Python
catalog — the ratatui panel still cannot, which PR #93 records as a known limitation.

The wizard's existing hardcoded English labels stay as they are on the fallback path.

## Testing

New `tests/cli/test_config_panel.py`, driving `ConfigPanelModel` directly — no TTY, no
prompt_toolkit:

- navigation skips rows inside collapsed groups, and reaches every row when expanded
- expand/collapse round-trips, including nested MCP servers
- edit/commit/cancel for each value kind; cancel restores the prior value
- `!clear` empties, blank input keeps current (wizard parity)
- secrets render masked; `toggle_reveal()` reveals; masking is restored on close
- provider change applies the preset, clears fetched models, bumps the generation
- `apply_fetch_result` with a stale generation is ignored; current generation populates the model dropdown
- validation blocks save for: empty credentials under static auth, unparseable numbers, blank or
  duplicate MCP server name; malformed base_url warns once then saves
- builtin MCP servers cannot be deleted
- Save calls `save_config` exactly once with the draft; Esc never calls it

Render tests: `render_panel` snapshotted through a recording `Console` for one collapsed and one
expanded state, asserting section summaries and the masked key.

Shell test: `run_config_tui` dispatches to the panel when `isatty` is True and to the wizard when
False, with `isatty` monkeypatched.

Regression: the three existing wizard tests must stay green untouched.

## Delivery

New commits on `JMAN730/87-i18n-support`, extending PR #93. The PR description gains a section
covering the REPL surface, and its "Risks and Follow-Up Items" note about the Textual/i18n
requirements is updated, since the REPL panel closes the i18n story.

Issue #87 story 30 and its Out-of-Scope entry ("the classic-REPL `run_config_tui` editor — left
untouched") are contradicted by this work and are corrected on the issue when the PR lands.
