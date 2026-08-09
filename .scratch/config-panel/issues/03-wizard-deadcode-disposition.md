# Wizard / dead-code disposition

Type: task
Status: closed
Assignee: wayfinder-session (claimed)
Blocked by:

## Question

Establish exactly what the new panel **replaces** and what gets deleted, so the spec (ticket 05) can
state the removal plan. This is a mapping/inventory task, not a build:

1. Enumerate every current `/config` code path:
   - Textual LIVE: `tui_textual.py` `_h_config` (line ~872) + its `_bg_fetch` / `_finish_model_fetch`
     / loading-prompt helpers. What exactly does the panel supersede here?
   - prompt_toolkit DEAD: `tui.py` `_cmd_config` (line ~1405) + `_on_provider`/`_on_baseurl`/
     `_on_apikey`/`_on_model_input` chain, and whether `_run_pt_tui` is truly unreachable.
2. Decide disposition for each: replaced-and-deleted, kept-as-fallback, or left-untouched. Recommended
   default: panel replaces `_h_config`; delete the dead prompt_toolkit config-wizard chain in the same
   change **only if** nothing else references it (grep-verify — report the callers).
3. Identify shared helpers the panel should reuse vs. retire (`apply_provider_preset`,
   `fetch_provider_models`, `list_providers`, `save_config`).
4. List i18n keys the current wizard owns (`tui.*`) that the panel inherits, renames, or orphans.

Output: a delete/keep/reuse table the spec can lift directly. No code changes — this only decides.

---

## Resolution

**Headline:** `/config` has **three** surfaces, not two. The map named Textual `_h_config` (LIVE) and
prompt_toolkit `_cmd_config` (DEAD). Reconnaissance surfaced a third — `run_config_tui` (LIVE,
classic-REPL Rich editor). The panel replaces only the first. The second is deleted. The third is left
untouched and must be called out in the spec so the build effort doesn't assume `/config` == the panel.

### The three surfaces

1. **Textual `_h_config`** — `tui_textual.py:874` (`@_register_handler("config"/"cfg")`). LIVE. Reached
   by the Textual dashboard: `run_tui()` (`tui.py:439`) bridges to `run_tui_textual()`, whose slash
   dispatch uses `tui_textual._SLASH_HANDLERS`. This is the wizard the panel replaces. Drives a
   choice→(custom)input→input→loading→choice/input prompt chain over `SecondaryPopup`.
2. **prompt_toolkit `_cmd_config`** — `tui.py:1407` (`@_register_handler("config"/"cfg")` into
   `tui.py._SLASH_HANDLERS`). **DEAD in production.** Only reachable via `_dispatch_slash("/config")`
   (`tui.py:1145`), whose sole production caller is `_run_pt_tui` (`tui.py:451`) — and `_run_pt_tui`
   has **zero callers** (grep: only its def + two comments). No test calls `_cmd_config` or
   `_dispatch_slash("/config")` (test 1912 calls `dispatch_repl_slash("/config")`, a different pure
   dispatcher that returns a `command` result and never touches this handler).
3. **`run_config_tui`** — `tui.py:2499`. **LIVE, separate.** Rich `Console`-based multi-section editor
   (llm / session / safety / recon / mcp / save / quit). Reached by the **classic REPL**:
   main.py `_run_repl_command("config")` (`main.py:234`) → `run_config_tui()`. Tested (test 1660).
   NOT the Textual popup, broader than LLM-only — **out of this map's scope**, coexists with the panel.

### Delete / keep / reuse table (spec lifts this directly)

| Symbol | File:line | Disposition | Why |
|---|---|---|---|
| `_h_config` + inner `on_provider/on_baseurl/on_apikey/on_models_loaded/on_model_selected/on_model_input` | `tui_textual.py:874-935` | **REPLACE + delete** | The prompt-chain wizard the `config_panel` supersedes. |
| `"loading"` prompt type + `_show_loading` / `complete_loading` / `_finish_model_fetch` / `_bg_fetch` | `tui_textual.py:275-289, 490-553, 696` | **RETIRE the loading-prompt UI; REUSE the raw thread+`call_later` mechanic** | `_h_config` (line 914) is the **only** setter of the `"loading"` prompt type. Ticket 02 moves fetch feedback onto the model `Select`, so the loading-prompt branches go unused; the panel reuses `threading.Thread` + `app.call_later` directly, not the `"loading"` prompt. |
| `_cmd_config` + inner `_on_provider/_on_baseurl/_on_apikey/_on_model_selected/_on_model_input` | `tui.py:1407-1467` | **DELETE** | Dead (only reachable via dead `_run_pt_tui`). Safe: removes the `"config"/"cfg"` entry from `tui.py._SLASH_HANDLERS`, which no production path and no test reads for config. |
| `_run_pt_tui` (whole pt dashboard loop) + `_dispatch_slash` + `tui.py._SLASH_HANDLERS` registry | `tui.py:451`, `tui.py:1145`, `tui.py:1160` | **LEAVE UNTOUCHED** (out of scope) | `_run_pt_tui` is dead too, but map Out-of-scope bars pt-backend changes "beyond deleting config-wizard code." `_dispatch_slash`/registry are still exercised by tests (936-1094 flag-skills, /ctf-web) — deleting them is a separate cleanup, not this map's. |
| `run_config_tui` + `_edit_llm_config` / `_edit_session_config` / `_edit_safety_config` / `_edit_recon_config` / `_edit_mcp_config` / `_render_config_summary` | `tui.py:2499` + editors | **LEAVE UNTOUCHED** | Live classic-REPL editor, all config sections, out of scope. Spec MUST note the panel does not replace it — two `/config` surfaces coexist. |
| `apply_provider_preset`, `fetch_provider_models`, `list_providers`, `load_config`, `save_config` (`vulnclaw.config.settings`) | — | **REUSE** | Backend-agnostic; the panel calls the same functions the wizard did. |

### i18n keys the wizard owns (`tui.*`)

Both `_h_config` and `_cmd_config` share the **same 9 keys** (en.json / zh.json). Deleting `_cmd_config`
orphans **none** — `_h_config` still uses all of them until the panel replaces it:

- `tui.prompt_select_provider` (en.json:267)
- `tui.prompt_enter_baseurl` (270)
- `tui.api_key_configured` / `tui.api_key_not_configured` (195/196)
- `tui.prompt_enter_apikey` (269)
- `tui.prompt_enter_model_fallback` (291)
- `tui.fetching_models` (292)
- `tui.prompt_select_model` (290)
- `tui.config_saved` (197)

**Panel inheritance:** the panel reuses these as static row labels / states where phrasing fits, but its
form shape differs from the prompt chain (labels not questions; a Fetch button, a reveal toggle, an idle
"press Fetch" hint, Save/discard — none keyed today). Exact rename/new-key plan is **Not-yet-specified**
and graduates from the prototype (ticket 04) + spec (ticket 05); this ticket only fixes ownership: 9
inherited keys, 0 orphaned by the delete. `run_config_tui` uses hardcoded English (not `tui.*` keys), so
it's unaffected either way.

**No code changed. No new tickets. Feeds ticket 05 (spec) the removal plan + the `run_config_tui`
coexistence callout.**
