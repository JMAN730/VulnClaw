# LLM-Config Panel — Consolidated Widget-Research Findings (Textual 8.2.8)

> Source: research ticket 01 (config-panel map). Produced by a 6-angle parallel research workflow +
> grounded synthesis against `vulnclaw/cli/tui_textual.py`. NOTE: the dedicated Windows-quirks agent
> returned a placeholder; §6 was reconstructed by the synthesizer from this repo's own win32 notes
> (`tui_textual.py:481–487`) + Textual 8.2.8 behavior — treat §6 as grounded-but-secondary, re-verify
> the Ctrl-R delivery claim on a real conhost if it becomes load-bearing.

## 1. Recommended overall approach

Build the LLM-config panel as a **single in-place form inside the existing `SecondaryPopup` container**
(`Vertical`, `can_focus=True`, `tui_textual.py:221–226`) rather than as today's chain of
one-widget-at-a-time sub-prompts (`_show_choice`/`_show_input`/`_show_loading`, driven by the
`on_provider → on_baseurl → on_apikey → loading → on_model_selected` callback ladder at
`tui_textual.py:881–934`). Compose the rows as ordinary focusable siblings — `Select` for provider, a
conditional `Input` for base URL, a `password=True` `Input` for the API key, a deferred-populated
`Select` for the model, and two `Button`s (Fetch / Save) — mounted below the persistent `#popup-desc`
`Static` (`tui_textual.py:246–247`). Keep the codebase's two proven mechanisms: **(a)** the app-level
`priority=True` up/down bindings (`tui_textual.py:1011–1012`) that already intercept arrow keys before
the focused widget, re-pointed from "move `lv.index`" to `screen.focus_next/previous` scoped to the
popup; and **(b)** the existing **thread + `app.call_later`** async marshaling
(`tui_textual.py:284–289, 545–553`) for the model fetch, updated to write into a `Select.set_options(...)`
instead of opening a new `choice` popup. This preserves every established pattern (`add_class("open")`,
`_clear_dynamic()`, `event.stop()` message filtering by `id`, Escape→`_cancel`) while collapsing five
sequential screens into one navigable panel.

## 2. Row → widget → reuse matrix

| Row | Recommended widget | Reuse existing pattern? (file:line) or New | Why |
|---|---|---|---|
| **Provider** (fixed enum) | `textual.widgets.Select` (`allow_blank=False`, seeded from `list_providers()`) | **New widget class**, replacing `_show_choice` `ListView` (`tui_textual.py:303–315`); reuse the `providers = [item["provider"]…]` data source (`tui_textual.py:878`) and `on_provider` logic (`tui_textual.py:881–894`) | Only `Select` gives the "activate → pick → auto-return to the row" round-trip needed for one row among siblings; the current `ListView` occupies N permanent rows and owns focus for the whole popup. `Select` is a single collapsed line. |
| **Base URL** (conditional, custom only) | `textual.widgets.Input` (plain, `compact=True`) | **Reuse** the `Input(value=…, id=…)` + mount + `focus()` pattern (`_show_input`, `tui_textual.py:291–301`); reuse `on_baseurl` (`tui_textual.py:896–901`) | Shown only when provider == `"custom"` (mirrors existing `if v == "custom"` branch at `tui_textual.py:887`). Toggle visibility via `.display` on provider change instead of a separate prompt step. |
| **API key** (masked + reveal) | `Input(password=True, select_on_focus=False, compact=True)` | **Reuse** `Input` mount pattern (`tui_textual.py:291–301`); reuse `on_apikey` (`tui_textual.py:903–914`). Reveal toggle is **New** | `password` is a plain reactive — flipping `input.password` re-renders with no manual `refresh()`. `select_on_focus=False` stops the whole key being pre-selected (and clobbered by the next keystroke) on refocus. |
| **Model** (deferred fetch) | `Select(options=[], allow_blank=True, prompt="…")`, later `set_options(...)` | **New widget**, replacing the post-fetch `_show_choice`/`on_models_loaded` popup (`tui_textual.py:916–920`); reuse `fetch_provider_models(base_url, api_key)` (`tui_textual.py:285`) | `Select` tolerates empty construction (when `allow_blank=True`), has a first-class `prompt` placeholder, and a single `set_options()` repopulate call — no async mount/remove. |
| **Fetch action** | `textual.widgets.Button` (id `#fetch-models`) | **New**; reuse the thread + `app.call_later` fetch scaffold (`tui_textual.py:284–289, 545–553`) | An explicit button makes the network call re-triggerable in place (today it only runs implicitly during the `loading` prompt). Handle via `Button.Pressed`. |
| **Save action** | `textual.widgets.Button(variant="primary")` (id `#save-config`) | **New**; reuse `save_config(session["config"])` + success `message` (`tui_textual.py:925–926`) | Replaces the implicit "save on final input submit" of `on_model_selected`/`on_model_input`. Explicit Save decouples editing from committing. |

## 3. Per-angle implementation detail

### Angle A — Provider (fixed-enum) → `Select`
- **Class/ctor** (`textual/widgets/_select.py:401`): `Select(options, *, prompt="Select", allow_blank=True, value=Select.NULL, type_to_search=True, name, id, classes, disabled, tooltip, compact=False)`. Shorthand `Select.from_values(values, …)` when label == value (fits `providers` which are bare strings). Set `allow_blank=False` so a real provider is always selected (auto-picks `options[0]` unless you pass `value=cur`).
- **Reactives**: `value` (`Select.NULL` sentinel when unset — never assign `None`; unknown value raises `InvalidSelectValueError`), `expanded`, `prompt`, `compact`. Property `.selection` returns the value or `None`.
- **Message**: `Select.Changed(select, value)` → `on_select_changed` / `@on(Select.Changed)`; attrs `.value`, `.control`. Drive the existing `on_provider` body from here, including `apply_provider_preset` + custom base-URL show/hide.
- **Keyboard**: BINDINGS `Binding("enter,down,space,up","show_overlay")` (`_select.py:292`, non-priority). Open with enter/down/space/up; overlay (`SelectOverlay`, an `OptionList`) takes focus; `type_to_search=True` jumps on printable keys; **enter** commits (posts `Select.Changed`, calls `self.focus()`, `expanded=False` — focus returns to the row); **escape** dismisses and re-focuses the Select. Focus never leaves the Select subtree, so a focus-loss-dismiss popup will not close when the dropdown opens.
- **Fallback**: `RadioSet` if the provider list should stay permanently visible (single Tab stop via `can_focus_children=False`, arrows move, enter/space → `RadioSet.Changed`), at the cost of one row per provider.

### Angle B — Base URL & API key → `Input` (masked + runtime reveal)
- **Class/ctor** (`textual/widgets/_input.py:354`): `Input(value=None, placeholder="", highlighter=None, password=False, *, restrict=None, type="text", max_length=0, suggester=None, validators=None, validate_on=None, valid_empty=False, select_on_focus=True, …, compact=False)`.
- **Masking**: `password = reactive(False)` (`_input.py:270`). Mask char hardcoded `U+2022` (`_input.py:685`) — not configurable in 8.2.8. In password mode, word-motion/word-delete collapse to home/end/delete-all to avoid leaking word boundaries.
- **Runtime reveal**: assign `inp.password = not inp.password` — reactive auto-refreshes; do **not** also call `.refresh()`. Toggling mid-edit preserves value and cursor. Bind the toggle on the **panel**, not the Input:
  ```python
  def action_reveal_key(self) -> None:
      inp = self.query_one("#apikey", Input)
      inp.password = not inp.password
  ```
- **Messages** (expose `.input`/`.value`/`.validation_result`, `.control` alias): `Input.Submitted` (`:309`, Enter → commit), `Input.Changed` (`:287`, live — use to enable/disable Save), `Input.Blurred` (`:331`). Filter by `event.input.id` exactly as the existing `on_input_submitted` (`tui_textual.py:646–648`).
- **URL validation**: `validators=[URL()]` + `validate_on=["submitted"]` shows `-invalid` CSS on Enter without blocking keystrokes; or `restrict=` regex (rejected edits ring `app.bell()` via `restricted()` — override to silence).
- **Keyboard**: standard editing keys; note **`ctrl+a` is Home, not select-all** (select-all is `ctrl+shift+a`). No built-in Escape — the panel supplies it. `Input.check_consume_key` (`_input.py:498`) consumes only printable chars, so up/down/enter/escape bubble to the panel's bindings.

### Angle C — Model (deferred fetch) → `Select` + `set_options`
- **Empty construction**: `Select(options=[], allow_blank=True, prompt=_("tui.fetching_models"))` — legal only while `allow_blank=True`; `allow_blank=False` with no options raises `EmptySelectError`.
- **Repopulate after fetch**: `select.set_options([(m, m) for m in models])` — THE populate-later method; rebuilds legal values and the overlay. **It resets the current selection every call** — re-apply the previously configured `config.llm.model` afterward if it is in the new list. Guard empty results: `set_options([])` under `allow_blank=False` raises; keep `allow_blank=True` until data exists, and fall back to a plain `Input` (mirroring the existing `on_model_input` fallback, `tui_textual.py:920`) when `fetch_provider_models` returns empty.
- **Message/keyboard**: same `Select.Changed` and overlay keys as Angle A.
- **Alternative**: `OptionList` if the model list should stay inline/visible — fully synchronous `set_options/add_options/clear_options`, and a disabled `Option("Fetching…", disabled=True)` sentinel as placeholder. Avoid `ListView` here — items are child widgets, so every repopulate is an async `AwaitMount/AwaitRemove` with no bulk string API.

## 4. Focus & key-routing plan

The codebase **already owns the correct mechanism**: `Binding("up","cursor_up",…,priority=True)` and
`Binding("down","cursor_down",…,priority=True)` on the app (`tui_textual.py:1011–1012`). Priority
bindings fire App→focused **before** the focused widget sees the key, which is why they beat a focused
`ListView` today — and why they beat a focused `Select`'s **non-priority** `up/down → show_overlay`
binding (`_select.py:292`). Because up/down/enter/escape are non-printable, `check_consume_key` returns
`False`, so ancestor bindings stay in the chain (`screen.py:426`).

**Change needed:** today `action_cursor_up/down` move a single ListView's `.index`
(`tui_textual.py:1056–1094`). For a heterogeneous row stack, re-point them (when the panel is open) at
Textual's focus API, scoped to the popup so movement wraps *inside* it:

```python
def action_cursor_down(self) -> None:
    popup = self.query_one(SecondaryPopup)
    if popup.has_class("open") and popup._ptype == "llm_config":
        self.screen.focus_next("#sec-popup *")   # wraps modulo the popup's focus_chain
        return
    # ...existing ListView / CommandPalette branches unchanged...
```

`Screen.focus_next(selector)/focus_previous(selector)` (`screen.py:897/914`) step ±1 through
`screen.focus_chain`, skipping non-matching nodes; selector `#sec-popup *` confines traversal to the
panel. Focus order is **geometric** (`Widget._focus_sort_key = (y, x)`, `widget.py:2377`) — lay rows
top-to-bottom and order follows; no tab-index in 8.2.8.

- **Enter = activate (context-sensitive, no global binding):** each row handles Enter itself; react to
  its message — `Input.Submitted` (base URL / API key), `Button.Pressed` (Fetch / Save), `Select`'s own
  enter→`show_overlay`. Mirrors the existing per-message handlers (`on_input_submitted` id-filter,
  `tui_textual.py:646`; `on_list_view_selected`, `:670`).
- **Escape = discard (NON-priority):** keep the existing `on_key`→`_cancel` path
  (`tui_textual.py:705–707`) or a `Binding("escape","cancel")` **without** `priority`. Non-priority is
  deliberate: when a `Select` overlay is open, `SelectOverlay`'s own non-priority `escape→dismiss`
  (`_select.py:48–51`) closes the overlay first; a second Escape bubbles to the panel to discard. A
  `priority=True` panel Escape would cancel the whole form while a dropdown is open. (App also binds
  `escape→palette_esc` at `tui_textual.py:1009` — the existing `event.stop()` in `on_key` guarantees the
  panel's Escape wins when open.)
- **Tab:** the Screen's built-in Tab/Shift+Tab (`screen.py:269–273`) traverse the *whole* screen chain.
  To confine Tab to the panel, override `tab`/`shift+tab` calling `focus_next/previous("#sec-popup *")`,
  or host the panel in a `ModalScreen`. The app rebinds `tab→palette_tab` (`tui_textual.py:1008`) — reconcile there.
- **Optional cleanliness:** subclass `Select` with `BINDINGS=[Binding("enter,space","show_overlay")]`
  to drop up/down; then a non-priority panel up/down suffices. Not required — existing priority bindings already win.

## 5. Async fetch-feedback plan

**Reuse the codebase's existing thread + `app.call_later` marshaling** (`tui_textual.py:284–289` starts
`threading.Thread(target=_bg_fetch)`; `_bg_fetch` calls
`self.app.call_later(lambda: self._finish_model_fetch(models))`, `:287`). The network call runs off-thread,
UI mutation happens back on the main thread via `call_later`. Adapt to write into the panel:

1. On Fetch `Button.Pressed`, set an in-panel busy state and spawn the thread. Lowest-effort spinner:
   `self.loading = True` on a sub-container wrapping the model `Select` (`widget.py:354` reactive
   `loading`; `widget.py:1055` `set_loading`) — Textual covers it with a `LoadingIndicator` and swallows
   its input events (desirable: the stale Select is non-interactive while fetching). Or keep the existing
   dot-animation `Static` (`_tick_loading`, `tui_textual.py:511–523`) for visual continuity.
2. In the thread body call `fetch_provider_models(base_url, api_key)`; **do not** touch widgets there.
3. Marshal completion with `self.app.call_later(...)` (as today) — or `self.post_message(ModelsFetched(models))`.
   Main-thread handler: clear `loading`; on success `query_one("#model", Select).set_options([(m,m) for m in models])`;
   on empty/error set an error `Static/Label.update(...)` and reveal the fallback `Input`.

**Idiomatic 8.2.8 alternative** (if refactoring the thread away): `@work(thread=True, exclusive=True,
group="fetch-models")`, poll `get_current_worker().is_cancelled`, handle `Worker.StateChanged` in
`on_worker_state_changed` (`SUCCESS` → `set_options`; `ERROR` → error label; set `exit_on_error=False`).
Cleaner but adds the `textual.worker` import. **Recommendation: keep the thread pattern** for consistency
and its win32 track record; wrap the model Select in a `loading`-able sub-container for the spinner. Either
way: never call `set_options`/`.update()` from the thread body — route through `call_later`/`post_message`.

## 6. Windows caveats

*(Angle-6 agent returned a placeholder; below is grounded in this repo's win32 notes + Textual 8.2.8 behavior.)*

- **Widget destroy/recreate on Windows causes focus loss** — documented in-repo: `_show_chain` creates the
  `Input` once for the whole chain "to prevent focus-loss issues on Windows from widget destruction/recreation"
  (`tui_textual.py:481–487`). **Apply the same discipline:** create rows once, toggle `.display`/`.disabled`
  (e.g. the conditional base-URL row) rather than mount/remove per provider change. Also sidesteps the
  `DuplicateIds` race that forced the `app.call_later(on_done)` deferral in `_resolve` (`tui_textual.py:614–620`).
- **`app.call_later` required for cross-thread UI updates** — already the established safe path
  (`tui_textual.py:287`); direct widget mutation from the fetch thread is unsafe, especially under ConPTY.
- **`Ctrl+R` reveal toggle — usable but NOT the safest default.** Binding-free (neither `Input.BINDINGS`
  `_input.py:75–141` nor app BINDINGS `tui_textual.py:1006–1013` claim it; non-printable so it bubbles).
  **But** win32 delivery is terminal-dependent: modern Windows Terminal / ConPTY passes `ctrl+r`; legacy
  `conhost.exe` and some emulators historically intercept or fail to distinguish Ctrl-letter chords. This
  app targets Windows 10 conhost users, so don't make Ctrl+R the *only* reveal path.
  - **Recommended:** primary `Binding("ctrl+r","reveal_key",show=False)` **plus** a non-chord fallback: a
    focusable "👁 Reveal" `Button`/label toggle in the panel (discoverable, mouse+keyboard reachable, no
    chord), or `Binding("f2","reveal_key")`. Prefer the visible toggle button — most robust across every
    Windows terminal, no key-delivery assumptions.
- **Emoji/Unicode markers**: the matrix already relies on `✓/✗/·` and `●/○` (`tui_textual.py:383–393, 516`),
  so the panel can safely reuse themed Unicode; keep to the same glyph set the app already ships.

## 7. Open questions for the interaction-model ticket (02)

1. **Save semantics:** explicit Save button vs. save-on-Enter (today `on_model_selected`/`on_model_input`
   save immediately, `tui_textual.py:925–931`). Does Escape discard *all* edits including an already-applied
   `apply_provider_preset` (`tui_textual.py:884`, which mutates `session["config"]` before save)? Commit/rollback
   boundary is beyond the widget layer. *(Q4 locks explicit-save + Escape-discards; this flags the rollback of
   preset mutation as the real open detail.)*
2. **Fetch trigger:** *(Q3 locks explicit Fetch button.)* Remaining: does the model Select ever show stale options
   after provider/key change — clear it on change?
3. **Conditional base-URL row:** hide (`.display=False`) vs. disable vs. omit-from-focus-chain when provider ≠
   custom — affects up/down wrap order and whether a hidden row can hold invalid state.
4. **Re-applying a previously selected model** after `set_options` (which resets selection) — silent re-selection
   vs. force re-pick? Product decision.
5. **Tab scope:** confine Tab to the panel (override `tab`/`shift+tab`, reconciling with `palette_tab`
   `tui_textual.py:1008`) or adopt a `ModalScreen` — structural, given the panel coexists with `CommandPalette`
   and `#cmd-input` on one screen.
6. **Validation timing & error surfacing:** block Save on invalid URL/empty key, or save-and-warn? Where does
   the error live — reuse `#status-bar` auto-dismiss (`tui_textual.py:1096–1111`) vs. an in-panel error Label?
7. **Cancel during in-flight fetch:** should Escape/cancel abort a running fetch thread (the current `loading`
   prompt is explicitly non-cancellable — `on_key` swallows all keys, `tui_textual.py:696–698`)? Cooperative-cancel
   via worker, or ignore-late-result guard?
