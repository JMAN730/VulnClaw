# Handoff Spec: Keyboard-navigable `/config` panel (LLM settings)

**Status:** Locked. This is the destination artifact of the `config-panel` wayfinder map. A separate
build effort implements the panel from this document alone — every decision here is already made and
adversarially verified against installed Textual 8.2.8; do not re-litigate without flagging.

**Scope:** LLM settings only (provider, base URL, API key, model). Language and MCP settings are
explicitly out of scope (separate future efforts). This spec replaces the Textual `/config` wizard;
it does **not** replace the classic-REPL `run_config_tui` editor (see §7).

Source decisions: tickets 01 (widget inventory), 02 (interaction model), 03 (dead-code disposition),
04 (prototype). Full detail lives in those tickets under `.scratch/config-panel/issues/`.

---

## 1. What ships

A new `config_panel` prompt type inside the Textual `SecondaryPopup` (a floating popup, **not** a
`ModalScreen`, **not** a full `Screen`). Invoked by `/config` (`/cfg`) in the Textual dashboard. One
in-place form — not a chain of sub-prompts. Reachable via `_SLASH_HANDLERS["config"]` in
`vulnclaw/cli/tui_textual.py`.

## 2. Layout — row order (top → bottom)

1. **Live summary line** — mirrors the `/scope` action_matrix summary. Composed in code from the row
   labels + current draft values:
   `provider <name>   url <preset|value>   key <mask|reveal>   model <name|(none — press Fetch)>`
   - key rendered as up-to-8 `•` when hidden, plaintext when revealed, `—` when empty.
   - model-none placeholder = `tui.config_panel_summary_model_none`.
2. **Header** — `tui.config_panel_header` (`Configure LLM`).
3. **provider** row — `Select`.
4. **base url** row — `Input` (plain). **Conditional: displayed only when provider == custom** (Q7).
5. **api key** row — `Input(password=True)`, masked, with reveal toggle.
6. **model** row — `Select(allow_blank=True)`.
7. (blank spacer)
8. **Action row** — `[ Fetch ]   [ Save ]   (Esc discards)`.
9. **Fetch-state hint line** — idle / loading / ok / fail (see §5).
10. **In-panel error Label** — validation/error surface (see §6). Empty when no error.

A single packed nav hint (`tui.config_panel_hint`) is rendered in the panel chrome, mirroring
`action_matrix_hint`: `Up/Down: move  Enter: edit  Ctrl+R: reveal key  Esc: discard`.

## 3. Widgets (reuse-vs-new per row)

| Row | Widget | Reuse / New |
|---|---|---|
| Provider | `Select([(p["label"], p["provider"]) for p in list_providers()], allow_blank=False)` | New widget; **reuse** `on_provider` body |
| Base URL (custom only) | `Input` (plain), `.display` toggled | **Reuse** `_show_input` + `on_baseurl` logic |
| API key | `Input(password=True, select_on_focus=False)`, reveal = flip `.password` reactive | **Reuse** Input mount; reveal is New |
| Model (deferred) | `Select(options=[], allow_blank=True)` + `set_options()` after fetch | New widget; **reuse** `fetch_provider_models` |
| Fetch | `Button#fetch-models` | New; **reuse** the thread + `app.call_later` scaffold |
| Save | `Button#save-config` (`variant="primary"`) | New; **reuse** `save_config` |

**Provider option values must be the provider-name strings, never the dicts.** `list_providers()`
returns `list[dict]` (`provider` / `label` / `base_url` / `default_model`), so `Select.from_values()` is
wrong here — it would hand `Select.Changed.value` a dict and blow up in the reused `on_provider` →
`apply_provider_preset(config, provider_name)` path, which calls `provider_name.lower()`. Build
`(label, provider)` option pairs explicitly as above: the user sees `label`, the handler receives the
`provider` string.

Shared backend helpers — **reuse verbatim, all backend-agnostic**: `apply_provider_preset`,
`fetch_provider_models`, `list_providers`, `load_config`, `save_config` (from
`vulnclaw.config.settings`). Fields: `config.llm.provider / base_url / api_key / model`.

## 4. Edit model, save & discard (Q4)

- On open: `draft = copy.deepcopy(session["config"])`. Every row and `apply_provider_preset` operate on
  the **draft**. `deepcopy` is safe — `VulnClawConfig`/`LLMConfig` are plain pydantic models,
  `apply_provider_preset` only assigns attributes, so the tree is fully independent (no shared mutable
  state).
- **Save** (explicit): commit the draft into `session["config"]`, call `save_config`, close the panel.
- **Escape** (discard): drop the draft, close. Live config untouched until Save.

## 5. Interaction model (from ticket 02, verified vs Textual 8.2.8)

**Provider selection.** Inline `Select` overlay. Enter/Down opens the overlay `OptionList`;
type-to-search; Enter commits and returns focus to the row.

**Escape layering.** Escape inside an open overlay closes **just the overlay**; a second Escape bubbles
to the panel and discards it. Panel's Escape stays **non-priority** so the overlay's Escape wins first.

**Model-fetch feedback (in-panel, no second popup).** State line = `tui.config_panel_fetch_*`:
- **idle**: `tui.config_panel_fetch_idle`; model `Select` empty.
- **in-flight**: `tui.config_panel_fetch_loading`; set `loading=True` **on the model `Select` widget
  itself** (not just a wrapper container — a wrapper-only cover lets a focused Select still eat
  Enter/Down and pop its overlay); disable Fetch.
- **success**: `tui.config_panel_fetch_ok` (`{n}` interpolated); `set_options([(m,m) for m in models])`,
  then re-apply the draft's model (see below).
- **failure/empty**: `tui.config_panel_fetch_fail`; fall back to a plain `Input` for manual model entry;
  re-enable Fetch for retry.

**Fetch preconditions.** Fetch requires provider + (custom) base URL + API key. **Disable Fetch + show
the idle hint** until present; never fire a doomed call (`Button.press()` checks `self.disabled` before
posting `Pressed`, so the gate is real). Non-custom providers get `base_url` from the preset, so API key
is the only user-supplied gate there.

**Stale model options + re-select.** Clear the model `Select` (`set_options([])`) whenever provider /
base URL / API key changes. **Hard constraint: model `Select` MUST be `allow_blank=True`** —
`set_options([])` raises `EmptySelectError` when `allow_blank=False`. After a successful fetch,
`set_options` resets selection to NULL, so **silently re-apply the draft's configured model if it is in
the new list**; otherwise leave blank for the user to pick.

**Conditional base-URL row.** Created once, `.display=False` when provider != custom. A non-displayed
row is **automatically excluded from up/down nav** (focus_chain is built from displayed children;
toggling `.display` invalidates the cache; `focus_next/previous` self-heal). Toggle `.display`, **never
mount/remove** (win32 focus-loss discipline). Hidden value ignored (base_url comes from the preset).

**API key masking + reveal (Q8).** `Input(password=True, select_on_focus=False)`. Reveal = flip the
`inp.password` reactive (auto-refresh, preserves value + cursor). `select_on_focus=False` is
**required** — otherwise a blur/refocus on toggle clobbers the cursor with a full-text selection.
Reveal affordances: **visible 👁 toggle in the key row is the primary/always-available path**; **Ctrl+R
is an accelerator layered on top**. Ctrl+R delivery is unreliable on win32/conhost, so the toggle
guarantees a conhost user is never locked out of revealing.

**Nav backbone + Tab scope.** When the panel is open:
- **Up/Down**: re-point the app's existing `priority=True` `action_cursor_up/down` at
  `screen.focus_next/previous("#sec-popup *")`. The priority pass fires before the focused Select sees
  the key, so it beats the Select's own up/down; the `#sec-popup *` selector confines wrapping to the
  panel. **The existing ListView-index-based `action_cursor_up/down` bodies
  (`tui_textual.py:1056-1094`) must be replaced by the focus path when the panel is open — not left to
  coexist.**
- **Tab**: reuse the existing `tab → palette_tab` override pattern — conditional redirect to
  `focus_next("#sec-popup *")` when the popup is open, else fall through.
- **Shift+Tab**: currently unbound and leaks focus out of the panel. Add a companion
  `Binding("shift+tab", <new_action>, show=False)` mirroring the palette-tab open-check:
  `focus_previous("#sec-popup *")` when open, else `app.action_focus_previous()`.
- Panel stays a `SecondaryPopup` (Q5).

**In-flight fetch cancel.** Ignore-late-result guard, **no hard thread abort**. Requires three pieces:
1. Narrow the existing "loading cannot be cancelled" block (`tui_textual.py:696-698`) to permit
   cancelling a **model-fetch** loading state so Escape can close the panel.
2. A **generation counter** incremented on the main thread at fetch-start, **captured via closure
   before `Thread.start()`** (never read from a shared attribute inside the thread).
3. The generation + panel-open comparison must be the **first** statement in the `call_later`
   completion handler, **before** any dismiss / callback side effect.
   The generation counter must **also** be bumped when provider / base URL / API key change mid-fetch —
   not only on Escape — else a late result for the old provider repopulates the just-cleared list for
   the new one. `call_later` is main-thread-marshaled, so the abandoned thread's late message is a
   discarded no-op (wasted work only, no crash/correctness risk).

## 6. Validation & error surface (Q4 / ticket 02 §6)

- **Block Save** (disabled Save button, driven off `Input.Changed`) on **missing effective credential**
  and, when custom, empty base URL. Error copy: `tui.config_panel_err_empty_key`,
  `tui.config_panel_err_empty_baseurl`.
- **The credential gate is mode-aware — never a bare `not draft.llm.api_key` check.** `api_key` is only
  one of three supported credential sources, and the other two live outside this panel:
  - `auth_mode != "static"` (e.g. `"oauth"`): the panel supplies no credential at all — **no key gate**,
    Save stays enabled for provider/URL/model edits.
  - `auth_mode == "static"`: gate on the **key pool**, not the single field — `draft.llm.key_pool()`
    (`LLMConfig.key_pool()`, `config/schema.py`) prefers non-empty `llm.api_keys` and falls back to
    `llm.api_key`. A config carrying `api_keys` legitimately has an empty `api_key`.
  - So: block only when `auth_mode == "static"` **and** `not draft.llm.key_pool()`.
  The panel's key `Input` writes `llm.api_key` as always; it must not clear or shadow `llm.api_keys`.
- **Base-URL format** = **save-and-warn**, not a hard block: `validators=[URL()]`
  (`from textual.validation import URL`) + `validate_on=["submitted"]` — validates only on Enter, attaches
  to `Submitted.validation_result` **without rejecting keystrokes or mutating the value**. Warn copy:
  `tui.config_panel_warn_bad_url`.
- **Save must validate the base URL itself; `Submitted` is not a sufficient path.** Leaving the input via
  Up/Down or Tab and then activating Save never fires `Input.Submitted`, so a malformed URL would save
  with no warning. The Save handler (custom provider only) **re-runs the validator explicitly** on the
  current input value — `URL().validate(value)` / `input.validate(input.value)` — and renders
  `tui.config_panel_warn_bad_url` in the in-panel error Label **while still saving**. The `Submitted`
  path stays for immediate in-edit feedback; Save-time validation is the authoritative one.
- All errors render in the **in-panel error Label** (row 10), **not** the global `#status-bar`.

## 7. Removal plan (ticket 03) — what this effort deletes / keeps

`/config` has **three** surfaces. The panel replaces exactly one.

| Symbol | File:line | Disposition |
|---|---|---|
| `_h_config` + inner `on_provider/on_baseurl/on_apikey/on_models_loaded/on_model_selected/on_model_input` | `tui_textual.py:874-935` | **REPLACE + delete** — the wizard the panel supersedes. |
| `"loading"` prompt type + `_show_loading` / `complete_loading` / `_finish_model_fetch` / `_bg_fetch` | `tui_textual.py:275-289, 490-553, 696` | **RETIRE the loading-prompt UI; REUSE the raw thread + `call_later` mechanic.** `_h_config` (line 914) is the only setter of `"loading"`; fetch feedback moves onto the model `Select` (§5). |
| `_cmd_config` + inner `_on_provider/_on_baseurl/_on_apikey/_on_model_selected/_on_model_input` | `tui.py:1407-1467` | **DELETE** — dead (only reachable via caller-less `_run_pt_tui`). Removes the `"config"/"cfg"` entry from `tui.py._SLASH_HANDLERS`; no production path and no test reads it. |
| `_run_pt_tui` + `_dispatch_slash` + `tui.py._SLASH_HANDLERS` registry | `tui.py:451, 1145, 1160` | **LEAVE UNTOUCHED** (out of scope). `_dispatch_slash`/registry still exercised by tests; deleting them is a separate cleanup. |
| `run_config_tui` + `_edit_llm_config` / `_edit_session_config` / `_edit_safety_config` / `_edit_recon_config` / `_edit_mcp_config` / `_render_config_summary` | `tui.py:2499` + editors | **LEAVE UNTOUCHED.** Live classic-REPL Rich editor (all config sections, reached via `main.py _run_repl_command("config")`). Broader than LLM-only, out of scope. **The panel does NOT replace it — two `/config` surfaces coexist.** |
| `apply_provider_preset`, `fetch_provider_models`, `list_providers`, `load_config`, `save_config` | `vulnclaw.config.settings` | **REUSE** — backend-agnostic. |

## 8. i18n key plan

New `tui.config_panel_*` family. The **9 legacy keys** the old wizard owned
(`prompt_select_provider`, `prompt_enter_baseurl`, `api_key_configured`, `api_key_not_configured`,
`prompt_enter_apikey`, `prompt_enter_model_fallback`, `fetching_models`, `prompt_select_model`,
`config_saved`) become **orphaned** once `_h_config` + `_cmd_config` are deleted (`run_config_tui` uses
hardcoded English, not these keys) — **delete all 9** from `en.json` and `zh.json`. Three of their
values are lifted verbatim into new keys (marked ⤵).

| Key | English (`en.json`) | Chinese (`zh.json`) |
|---|---|---|
| `tui.config_panel_header` | `Configure LLM` | `配置 LLM` |
| `tui.config_panel_hint` | `Up/Down: move  Enter: edit  Ctrl+R: reveal key  Esc: discard` | `上/下: 移动  回车: 编辑  Ctrl+R: 显示密钥  Esc: 放弃` |
| `tui.config_panel_label_provider` | `provider` | `提供商` |
| `tui.config_panel_label_baseurl` | `base url` | `Base URL` |
| `tui.config_panel_label_apikey` | `api key` | `API Key` |
| `tui.config_panel_label_model` | `model` | `模型` |
| `tui.config_panel_btn_fetch` | `Fetch` | `获取` |
| `tui.config_panel_btn_save` | `Save` | `保存` |
| `tui.config_panel_esc_discards` | `Esc discards` | `Esc 放弃` |
| `tui.config_panel_reveal_hint` | `Ctrl+R / 👁 reveal` | `Ctrl+R / 👁 显示` |
| `tui.config_panel_fetch_idle` | `press Fetch to load models` | `点击"获取"加载模型列表` |
| `tui.config_panel_fetch_loading` | `⠿ fetching models…` | `⠿ 正在获取模型…` |
| `tui.config_panel_fetch_ok` | `✓ {n} models loaded` | `✓ 已加载 {n} 个模型` |
| `tui.config_panel_fetch_fail` | `✗ fetch failed — type model manually` | `✗ 获取失败 — 请手动输入模型` |
| `tui.config_panel_summary_model_none` | `(none — press Fetch)` | `(无 — 点击"获取")` |
| `tui.config_panel_apikey_configured` ⤵ | `Configured, leave empty to keep` | `已配置，留空保持不变` |
| `tui.config_panel_apikey_not_configured` ⤵ | `Not configured` | `未配置` |
| `tui.config_panel_saved` ⤵ | `Model/API configuration saved` | `模型/API 配置已保存` |
| `tui.config_panel_err_empty_key` | `API key required` | `需要 API Key` |
| `tui.config_panel_err_empty_baseurl` | `Base URL required for custom provider` | `自定义提供商需要 Base URL` |
| `tui.config_panel_warn_bad_url` | `URL looks malformed — saved anyway` | `URL 格式可能有误 — 已保存` |

All strings resolved through `_()`. **The zh values were approved without a native-speaker review — a
Chinese-reading reviewer should sanity-check them before ship.**

## 9. Windows discipline (win32)

- Create every row once at panel build; toggle `.display` / `.disabled` — **never mount/remove per
  change** (repo documents win32 focus-loss from widget destroy/recreate, `tui_textual.py:481-487`).
- Keep the existing `threading.Thread` + `app.call_later` marshaling for fetch (win32-proven). **Never
  mutate widgets from the thread.**
- Ctrl+R conhost unreliability is sidestepped by the primary 👁 toggle (§5).

## 10. Acceptance criteria

1. `/config` (Textual) opens the `config_panel` in `SecondaryPopup`; old `_h_config` prompt-chain +
   `"loading"` prompt type + `_cmd_config` deleted; `run_config_tui` classic-REPL editor untouched and
   still reachable from the REPL.
2. Panel edits a `deepcopy` draft: **Save** commits into `session["config"]` + `save_config` + closes;
   **Escape** discards, live config untouched.
3. Rows render in the §2 order; base-URL row displayed only when provider == custom, auto-dropped from
   nav when hidden (`.display` toggle, never mount/remove).
4. Up/Down moves between rows (priority bindings re-pointed to `focus_next/previous("#sec-popup *")`);
   Tab **and** Shift+Tab confined to the panel; Enter edits focused row; Escape layered (open Select
   overlay closes first, second Escape discards panel).
5. API key masked (`Input(password=True, select_on_focus=False)`); reveal via visible 👁 toggle
   (primary) + Ctrl+R accelerator; toggle works even where conhost eats Ctrl+R.
6. Fetch disabled + idle hint until provider + (custom) base URL + key present; in-flight sets `loading`
   on the model `Select` itself; success populates + re-applies the draft's model if present; failure
   falls back to manual `Input`; stale results discarded via generation-counter guard (bumped on Escape
   **and** provider/URL/key change).
7. Model `Select(allow_blank=True)` cleared on provider/URL/key change.
8. Save blocked (disabled button) on missing effective credential — `auth_mode == "static"` **and**
   empty `key_pool()` (an `api_keys`-only or `auth_mode="oauth"` config must still be able to save
   provider/model edits) — and on empty custom base URL; malformed base URL = save-and-warn (not
   block), validated **in the Save handler**, not only on `Input.Submitted`; all errors in an in-panel
   Label, not `#status-bar`.
9. Every string via `_()` using the new `tui.config_panel_*` keys; en + zh both present; the 9 legacy
   keys removed.

## 11. Assets

- Interaction model (verified): `.scratch/config-panel/issues/02-in-panel-interaction-model.md`
- Widget findings: `.scratch/config-panel/research/01-widget-inventory-findings.md`
- Removal table: `.scratch/config-panel/issues/03-wizard-deadcode-disposition.md`
- Prototype (throwaway, Variant A winner) + variant SVGs:
  `.scratch/config-panel/prototype/config_panel_prototype.py`, `variant-{A,B,C}.svg`
