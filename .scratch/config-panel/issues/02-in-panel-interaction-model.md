# In-panel interaction model: provider list + fetch feedback

Type: grilling
Status: resolved
Assignee: JMAN730
Blocked by: 01

## Question

Given the widget inventory (ticket 01), lock the **interaction model** for the two moments the panel
can't just be a static form:

1. **Provider selection mechanic** — when the user activates the provider row (Enter per Q6), how does
   the choice appear? Options: (a) inline expand/collapse list in place, (b) a nested sub-popup reusing
   the existing `_show_choice`, (c) cycle-in-place (left/right or repeated Enter). Decide the mechanic
   and how commit/cancel of that sub-interaction maps to the panel's own Enter/Escape (Q6 says Escape
   discards the whole panel — does Escape inside an open provider list cancel just the list, or the panel?).
2. **Model-fetch feedback** — the explicit fetch action (Q3) runs a background network call. Decide how
   the panel shows: idle ("model — press F to fetch" or similar), in-flight ("fetching…"), success
   (list populated + selectable), failure (error text + retry affordance). Must render **in-panel**,
   not as the current separate loading popup — confirm feasible from ticket 01 findings.
3. **Field interdependency** — fetch needs provider + base_url + api_key present. Decide behavior when
   the user triggers fetch with those unfilled: block + hint, or attempt + surface the resulting error.

Output: a precise interaction description the prototype (ticket 04) can be built against.

## Inputs from ticket 01 (widget inventory)

The research resolved the *widget* layer and handed up **7 interaction decisions** this ticket must make —
see §7 of [research/01-widget-inventory-findings.md](../research/01-widget-inventory-findings.md). Beyond the
three questions above, resolve these (several already partly constrained by Q1–Q9):

1. **Save/rollback boundary** — `apply_provider_preset` mutates `session["config"]` *before* save
   (`tui_textual.py:884`). Q4 says Escape discards; decide how a discard rolls back an already-applied preset.
2. **Stale model options** — clear the model `Select` when provider/base-URL/key change so it can't show
   models from a prior provider?
3. **Hidden base-URL row** — `.display=False` vs `.disabled` vs omit-from-focus-chain when provider ≠ custom
   (affects up/down wrap order; Q7).
4. **Model re-selection after fetch** — `Select.set_options()` resets selection; silently re-apply the
   configured model if present, or force re-pick?
5. **Tab scope** — confine Tab to the panel (override `tab`/`shift+tab`, reconcile with `palette_tab`) or host
   in a `ModalScreen`. Structural; coexists with `CommandPalette` + `#cmd-input`.
6. **Validation timing + error surface** — block Save on invalid URL / empty key vs save-and-warn; error in the
   `#status-bar` (auto-dismiss) vs an in-panel Label.
7. **In-flight fetch cancel** — does Escape abort a running fetch thread, or ignore the late result?

## Answer

**Resolved 2026-07-23.** Interaction model locked for the `config_panel`. Every decision below was
adversarially verified against the installed Textual 8.2.8 source + `tui_textual.py` by the workflow
`verify-config-panel-interaction-model` (9 claim-verifiers + a critic, sonnet agents). No decision was
refuted: 5 claims returned HOLDS (C1, C2, C3, C5, C9), 4 returned CAVEAT (C4, C6, C7, C8) whose extra
constraints are baked into the decisions below.

### Edit model (backbone) — C1 HOLDS
Panel edits a **draft**: `draft = copy.deepcopy(session["config"])` on open. Every row, and
`apply_provider_preset`, operates on the draft. **Save** commits the draft into `session["config"]` +
`save_config`; **Escape** drops it. Live config is untouched until Save. `apply_provider_preset`
(`vulnclaw/config/settings.py:355-393`) only mutates the passed-in object via attribute assignment on
read-only preset lookups, and `VulnClawConfig`/`LLMConfig` are plain pydantic models, so `deepcopy`
yields a fully independent tree with no shared mutable state.

### Rows + widgets (from research ticket 01)
provider `Select` → base URL `Input` (conditional) → API key `Input(password=True, select_on_focus=False)`
+ reveal → model `Select(allow_blank=True)` → Fetch `Button` → Save `Button(variant="primary")`.

### 1. Provider selection mechanic + Escape layering
Inline `Select` overlay. Enter/Down opens the overlay `OptionList`; type-to-search; Enter commits and
returns focus to the row. **Escape inside an open overlay closes just the overlay; a second Escape**
bubbles to the panel and discards it. The panel's Escape stays **non-priority** so the overlay's own
Escape wins first.

### 2. Model-fetch feedback states (in-panel, no second popup) — C7 CAVEAT folded in
- **idle**: model row shows a "press Fetch to load models" prompt; model `Select` empty (`allow_blank=True`).
- **in-flight**: set `loading=True` **on the model `Select` widget itself** (not just a wrapper container),
  and disable Fetch. *(C7: `App.focused` guard checks only the focused widget's own `.loading`, and Key
  events forward straight to `self.focused` — a wrapper-only cover lets a focused Select still eat
  Enter/Down and pop its overlay on the next frame. Loading the Select itself blocks Key forwarding
  regardless of prior focus.)*
- **success**: `set_options([(m, m) for m in models])`, then re-apply the draft's model (see §4).
- **failure/empty**: inline error Label + fall back to a plain `Input` for manual model entry; re-enable
  Fetch for retry.

### 3. Fetch preconditions — C9 HOLDS
Fetch requires provider + (custom) base URL + API key. **Disable Fetch + show a one-line hint** until
present; never fire a doomed call. `Button.press()` checks `self.disabled` before posting `Pressed`, so
the gate is a real block. Non-custom providers get `base_url` from the preset, so API key is the only
user-supplied gate there.

### 4. Stale model options + re-select after fetch — C3 HOLDS
Clear the model `Select` (`set_options([])`) whenever provider / base URL / API key changes, so it can
never show a prior provider's models. **Hard constraint: the model `Select` must be constructed
`allow_blank=True`** — `set_options([])` raises `EmptySelectError` when `allow_blank=False`, so both this
clear and the "leave blank" branch below depend on it. After a successful fetch, `set_options` has reset
the selection to NULL, so **silently re-apply the draft's configured model if it is in the new list**;
otherwise leave blank for the user to pick.

### 5. Conditional base-URL row — C2 HOLDS
Created once, `.display=False` when provider != custom. A non-displayed row is **automatically excluded
from up/down nav** (focus_chain is built from displayed children; toggling `.display` invalidates the
cache instantly; `focus_next/previous` self-heal if the focused row just left the chain). No separate
omit-from-focus handling. Hidden value is ignored (base_url comes from the preset). Toggle `.display`,
never mount/remove (win32 focus-loss discipline).

### 6. Validation + error surface — C9 HOLDS
- **Block Save** (disabled Save button, driven off `Input.Changed`) on empty API key and, when custom,
  empty base URL.
- Base-URL **format** = **save-and-warn**, not hard block: `validators=[URL()]`
  (`from textual.validation import URL`) + `validate_on=["submitted"]` validates only on Enter and attaches
  to `Submitted.validation_result` **without rejecting keystrokes or mutating the value**.
- Errors render in an **in-panel Label**, not the global `#status-bar`.

### 7. Nav backbone + Tab scope — C5 HOLDS, C6 CAVEAT folded in
- **Up/down**: re-point the app's existing `priority=True` `action_cursor_up/down` at
  `screen.focus_next/previous("#sec-popup *")` **when the panel is open**. The priority pass fires before
  the focused Select sees the key, so it beats the Select's own non-priority up/down; the `#sec-popup *`
  selector confines wrapping to the panel. **The existing ListView-index-based `action_cursor_up/down`
  bodies (`tui_textual.py:1056-1094`) must be replaced by the focus path when the panel is open — not left
  to coexist**, or up/down behaves inconsistently between Select rows and any ListView rows.
- Panel stays a `SecondaryPopup` (Q5-locked), **not** a `ModalScreen`.
- **Tab**: reuse the existing `tab → palette_tab` override pattern — conditional redirect to
  `focus_next("#sec-popup *")` when the popup is open, else fall through.
- **Shift+Tab is currently unbound and leaks focus out of the panel** via Screen's default
  `focus_previous`. Add a companion `Binding("shift+tab", <new_action>, show=False)` mirroring the
  palette-tab open-check: `focus_previous("#sec-popup *")` when open, else `app.action_focus_previous()`.

### 8. Key masking + reveal — C4 CAVEAT folded in
`Input(password=True, select_on_focus=False)`. Reveal = flip the `inp.password` reactive (auto-refresh,
preserves value + cursor). **`select_on_focus=False` is required** — otherwise a blur/refocus of the key
Input on toggle clobbers the cursor with a full-text selection (`_on_focus`, `_input.py:736`). The exact
reveal chord stays deferred to the prototype (ticket 04); a **visible toggle is the primary affordance**.

### 9. In-flight fetch cancel — C8 CAVEAT folded in
**Ignore-late-result guard**, no hard thread abort. Requires three pieces the code lacks today:
1. Narrow the existing "loading cannot be cancelled" block (`tui_textual.py:696-698`) to permit
   cancelling a **model-fetch** loading state (Escape closes the panel).
2. A **generation counter** incremented on the main thread at fetch-start, **captured via closure before
   `Thread.start()`** (never read from a shared attribute inside the thread).
3. The generation + panel-open comparison must be the **first** statement in the `call_later` completion
   handler, **before** `complete_loading` runs any dismiss / cb / on_done side effect.

The **same generation counter must also be bumped when provider / base URL / API key change mid-fetch**
— not only on Escape/close — else a late result for the *old* provider repopulates the just-cleared list
for the *new* one (critic gap). `call_later` is main-thread-marshaled, so the abandoned thread's late
message is discarded as a no-op — only wasted work, no crash/correctness risk.

### Handoff
This is the precise interaction description the prototype (ticket 04) builds against. It graduates the
"how errors render in-panel" fog (rendering location + timing decided here). Exact error **copy**, final
row order / label wording, and the exact reveal chord remain deferred to the prototype (ticket 04) and
spec (ticket 05).
