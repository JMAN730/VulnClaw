# Map: Keyboard-navigable /config panel

Label: wayfinder:map
Tracker: local-markdown

## Destination

Replace the `/config` linear wizard with a single **keyboard-navigable settings panel** in the
Textual backend (`tui_textual.py` `SecondaryPopup`), covering LLM settings only: provider, base URL
(conditional), API key, model. Output of this map = a **locked handoff spec + a throwaway
prototype**; the production build is a separate effort, not part of this map.

## Notes

- **Domain**: VulnClaw TUI. Two backends exist — prompt_toolkit (`tui.py` `_cmd_config`/`_run_pt_tui`,
  DEAD) and Textual (`tui_textual.py`, LIVE via `run_tui()` -> `run_tui_textual()`). All panel work
  targets the Textual `SecondaryPopup` prompt state machine.
- **Precedent to model on**: `/scope` `action_matrix` widget (ListView rows, arrow nav, space-toggle,
  colored markers, live summary, `_persist_scope_state`). New panel is the same shape for config.
- **Env facts**: Textual 8.2.8 installed (pin `>=0.40.0`). Modern widget set available
  (Select, OptionList, Collapsible, Input, RadioSet, ListView).
- **Config plumbing**: `apply_provider_preset`, `fetch_provider_models`, `list_providers`,
  `load_config`, `save_config` from `vulnclaw.config.settings`; fields
  `config.llm.provider/base_url/api_key/model`. Model list needs provider + base_url + api_key,
  fetched on a background thread + loading prompt.
- **i18n**: user-facing strings live in `vulnclaw/i18n/en.json` + `zh.json`, keyed `tui.*`, via `_()`.
- **Style**: caveman output style active this effort (terse); code/commits/spec written normally.
- **Skills each session should consult**: `/grilling` + `/domain-modeling` for decision tickets,
  `/prototype` for the prototype ticket, `/research` for the widget-inventory ticket.

### Locked constraints (from destination-naming grilling, Q1–Q9)

These frame every downstream ticket — do not re-litigate without flagging:

- **Q1** Replace the wizard with a navigable config panel (not incremental wizard polish).
- **Q2** Scope = LLM settings only. Language panel + MCP panel are separate future efforts (Out of scope).
- **Q3** Model list fetched via an **explicit "fetch models" action**, never auto-fired on field focus.
- **Q4** **Explicit save** writes all fields + closes; **Escape discards** all edits.
- **Q5** New `config_panel` prompt type inside `SecondaryPopup` (floating popup, not a full Screen).
- **Q6** Nav: up/down between rows, Enter activates focused row, Escape discards.
- **Q7** Base URL row is **conditional** — shown only when provider == custom.
- **Q8** API key **masked with a reveal toggle** (e.g. Ctrl-R).
- **Q9** Deliver decisions + prototype, then hand the spec to a separate build effort.

## Decisions so far

<!-- one line per closed ticket; gist + link, detail lives in the ticket -->

- [Textual widget inventory](issues/01-textual-widget-inventory.md) — panel = one in-place form in the
  existing `SecondaryPopup` (not a sub-prompt chain): `Select` provider/model, `Input`(password) key,
  conditional `Input` base URL, Fetch/Save `Button`s. Nav reuses the app's `priority` up/down bindings
  re-pointed at `screen.focus_next("#sec-popup *")`; reveal = flip `Input.password` + a visible 👁 toggle
  (Ctrl-R unreliable on conhost); fetch keeps the thread + `app.call_later` pattern. Full detail +
  [findings doc](research/01-widget-inventory-findings.md). Surfaced 7 interaction Qs → fed to ticket 02.
- [In-panel interaction model](issues/02-in-panel-interaction-model.md) — locked the `config_panel`
  interaction model. Draft-deepcopy edit (Save commits + `save_config`, Escape drops, live config untouched);
  inline `Select` overlay + layered Escape (overlay first, then panel); fetch feedback in-panel via
  `loading` on the **model `Select` itself** (idle "press Fetch" / in-flight spinner+disable / success
  populate+re-apply / fail→manual `Input`); Fetch gated on required fields; model `Select(allow_blank=True)`
  cleared on provider/URL/key change, configured model re-applied after fetch; conditional base-URL row via
  `.display` (auto-dropped from nav); Save blocked on empty key/(custom) URL, URL-format save-and-warn,
  errors in in-panel Label; up/down re-point the priority bindings at `focus_next("#sec-popup *")`, Tab
  **and Shift+Tab** both confined, stays a `SecondaryPopup`; API-key `Input(password, select_on_focus=False)`
  reveal-flip; in-flight fetch cancel via a generation-counter guard (bumped on field-change too, not just
  Escape). All 10 calls adversarially verified vs installed Textual 8.2.8 — 5 HOLDS, 4 CAVEAT folded in.
- [Wizard / dead-code disposition](issues/03-wizard-deadcode-disposition.md) — `/config` has **three**
  surfaces: Textual `_h_config` (LIVE, **replace+delete** — the panel's target, incl. the `"loading"`
  prompt type whose only user it is; reuse the raw thread+`call_later` fetch mechanic), prompt_toolkit
  `_cmd_config` (**DELETE** — dead, only reachable via caller-less `_run_pt_tui`), and `run_config_tui`
  (LIVE classic-REPL Rich editor, all config sections — **leave untouched, out of scope, coexists**;
  spec must say the panel does not replace it). `_run_pt_tui`/`_dispatch_slash` left untouched (Out-of-scope
  bar + still tested). Shared helpers `apply_provider_preset`/`fetch_provider_models`/`list_providers`/
  `load_config`/`save_config` = **reuse**. 9 shared `tui.*` i18n keys, **0 orphaned** by the delete; panel
  rename/new-key plan stays Not-yet-specified. Delete/keep/reuse table + key list in the ticket, ready for ticket 05.
- [config_panel prototype](issues/04-config-panel-prototype.md) — **Variant A wins**: stacked labeled rows
  (the `/scope action_matrix` shape), live summary on top, least widget machinery. **Row order locked**:
  summary → header `Configure LLM` → provider → base url (conditional custom-only) → api key (masked) →
  model → action row `[Fetch] [Save] (Esc discards)` → fetch-state hint line. **Reveal = Ctrl+R accelerator +
  visible 👁 toggle primary** (toggle is the conhost-safe fallback so Ctrl+R unreliability never locks reveal).
  Fetch-state hint copy + summary masking rendering pinned; exact i18n strings still open → ticket 05.
  Variants B (widget grid) / C (collapsible groups) discarded, kept as prototype assets (`variant-*.svg`).
- [Handoff spec synthesis](issues/05-handoff-spec.md) — **map complete**. Destination artifact written to
  [spec.md](spec.md): a build-ready handoff the separate build effort implements with no re-deciding.
  Synthesized tickets 01–04 + resolved the last open fog: **i18n key plan** = fresh `tui.config_panel_*`
  family, delete the 9 orphaned legacy keys, lift 3 shape-neutral values verbatim; **full 21-key en+zh
  table** (labels, packed hint line, buttons, fetch-state copy, errors, summary placeholder; `{n}` on
  fetch-ok; zh flagged for native review); **9 acceptance criteria**. Spec §1–§11 cover ship/layout/widgets/
  draft-save-discard/interaction/validation/removal-plan/i18n/win32/acceptance/assets.

## Not yet specified

_(empty — no fog remains; the way to the destination is clear)_

## Out of scope

- **Language settings in the panel** (Q2-B) — separate future effort / its own map.
- **MCP settings in the panel** (Q2-C) — separate future effort / its own map.
- Production build of the panel (Q9) — a separate build effort consumes this map's spec + prototype.
- Any change to the dead prompt_toolkit backend beyond deleting config-wizard code (see disposition ticket).
