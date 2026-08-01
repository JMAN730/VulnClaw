# Textual widget inventory for in-panel field editing

Type: research
Status: resolved
Blocked by:

## Question

Which Textual 8.2.8 widgets/patterns best support **in-panel, keyboard-driven field editing**
inside a floating `SecondaryPopup`, and how do they behave? Feeds the interaction-model + prototype
tickets. Investigate and report facts (not opinions):

1. **Provider selection** — for a fixed enum choice (list of providers from `list_providers`):
   `Select`, `OptionList`, `RadioSet`, or the existing hand-rolled `ListView` `_show_choice`?
   For each: does it open/expand inline within a container, or need its own overlay? Keyboard nav
   (open, move, commit, cancel)? Focus behavior when embedded among other rows?
2. **Text fields** (base URL, API key) — `Input` widget: password/masked mode support, toggling
   masked<->plain at runtime (for the reveal toggle), and placeholder/value handling.
3. **Model field** — same enum-list question but the list is fetched at runtime (may be empty until
   fetched). Which widget tolerates "populate later"?
4. **Row focus model** — how to move focus up/down a vertical stack of heterogeneous rows
   (a Select, two Inputs, a fetch button, a save button) with a single up/down convention. Does
   Textual's default Tab focus chain conflict with a custom up/down handler? `can_focus`, focus order.
5. **In-panel async feedback** — showing a "fetching models…" state and an error state inside the
   panel without spawning a second popup (current code uses a separate loading prompt + bg thread).
   `Loading` indicator / reactive label patterns.
6. **Windows-specific** — any known Textual focus/rendering quirks on Windows terminals relevant to
   the above (this repo runs on win32).

Ground findings in the **actually installed 8.2.8 API**. Note where the existing `SecondaryPopup`
already uses a widget so the panel can reuse the pattern. Capture on a `research/config-panel-widgets`
branch or scratch note and link from the resolution.

## Answer

Full findings: [research/01-widget-inventory-findings.md](../research/01-widget-inventory-findings.md).
Produced by a 6-angle parallel research workflow + grounded synthesis against `tui_textual.py`.

**Verdict — build the panel as one in-place form inside the existing `SecondaryPopup` container, not a
new chain of sub-prompts.** Widget-per-row:

| Row | Widget | Reuse / New |
|---|---|---|
| Provider | `Select` (`allow_blank=False`, `from_values(list_providers())`) | New; reuse `on_provider` body |
| Base URL (custom only) | `Input` (plain), `.display` toggled | Reuse `_show_input` + `on_baseurl` |
| API key | `Input(password=True, select_on_focus=False)`, reveal via flipping `.password` reactive | Reuse Input mount; reveal New |
| Model (deferred) | `Select(options=[], allow_blank=True)` + `set_options()` after fetch | New; reuse `fetch_provider_models` |
| Fetch | `Button#fetch-models` | New; reuse thread + `app.call_later` scaffold |
| Save | `Button#save-config` (primary) | New; reuse `save_config` |

Key facts that shape the build:
- **Focus/nav is already solved** by the app's `priority=True` up/down bindings (`tui_textual.py:1011–1012`)
  — re-point `action_cursor_up/down` at `screen.focus_next/previous("#sec-popup *")` when the panel is open;
  focus order is geometric (top-to-bottom = tab order). Enter is per-row (each widget's own message), Escape
  stays **non-priority** so a `Select` overlay's own Escape closes the dropdown first, second Escape discards.
- **Reveal toggle** = flip `Input.password` reactive (auto-refresh, preserves cursor). Ctrl-R is binding-free
  but win32/conhost delivery is unreliable — ship a **visible 👁 toggle button** (or F2) as the robust path,
  Ctrl-R as a bonus.
- **Async fetch** = keep the existing thread + `app.call_later` marshaling (win32-proven); wrap the model
  `Select` in a `loading`-able sub-container for the spinner. Never mutate widgets from the thread.
- **Windows discipline**: create rows once and toggle `.display`/`.disabled` — never mount/remove per change
  (repo already documents win32 focus-loss from widget destroy/recreate, `tui_textual.py:481–487`).
- `Select.set_options()` **resets selection every call** — re-apply configured model afterward; keep
  `allow_blank=True` while empty and fall back to a plain `Input` when `fetch_provider_models` returns nothing.

**Handoff to ticket 02**: the findings' §7 lists 7 interaction decisions the widget layer can't make alone
(save/rollback boundary of `apply_provider_preset`, stale-model clearing, hidden-row focus treatment,
model re-selection after fetch, Tab scope vs ModalScreen, validation/error surface, in-flight fetch cancel).

**Caveat**: the dedicated Windows-quirks research agent returned a placeholder result; §6 was reconstructed
by the synthesizer from this repo's own win32 notes + Textual behavior. Re-verify the Ctrl-R conhost claim
on real hardware if it becomes load-bearing (the recommended visible toggle button sidesteps it entirely).
