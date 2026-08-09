# config_panel prototype: lock layout + feel

Type: prototype
Status: closed
Assignee: JMAN730
Blocked by: 02

## Question

Build a **throwaway** `config_panel` prototype (via `/prototype`) to lock the last "how it looks /
feels" questions that only settle by reacting to a concrete artifact. Not production code — a rough
Textual panel to click through and judge:

- Row order + labels for: provider, base URL (conditional, custom only — Q7), API key (masked +
  reveal toggle — Q8), model, fetch action (Q3), save action (Q4).
- The provider-selection mechanic + fetch-feedback states chosen in ticket 02, made real.
- The masked/reveal interaction (Q8) — pick + feel out the binding (Ctrl-R candidate).
- Up/down row nav + Enter-activates + Escape-discards (Q6), and the top live summary line
  (mirroring the `/scope` action_matrix summary).
- Conditional appearance/disappearance of the base URL row as provider changes (Q7).

Resolution records: what layout/interaction won, screenshots or a recording linked as an asset, and
the concrete details (row order, bindings, state copy) the handoff spec must encode. Graduate the
relevant **Not yet specified** items (row order, reveal binding, error rendering) as they get pinned.

## Resolution

Built throwaway prototype (`prototype/config_panel_prototype.py`, one-command run, in-memory only,
fake fetch). Three structurally-different layouts flipped via a switcher bar. Assets:
`prototype/variant-A.svg`, `variant-B.svg`, `variant-C.svg`.

Variant A carries the Q6 nav model itself: a row cursor (Up/Down over the *visible* rows, so the
conditional base-URL row drops out of nav exactly as a hidden row drops out of `focus_chain`),
Enter-activates-the-focused-row, and Esc-discards. Its text edits are faked (Enter toggles a canned
value) — the prototype settles row order/nav feel, while the widget-level guarantees
(`focus_next/previous("#sec-popup *")`, Select-overlay Escape layering) were verified against Textual
8.2.8 source in ticket 02, not inferred from the prototype.

**Winner: Variant A — stacked labeled rows** (the `/scope action_matrix` shape). Rationale (user pick):
maximal consistency with the existing panel precedent, least widget machinery, live summary on top.
Variant B (two-column widget grid) and C (collapsible groups) discarded — kept only as prototype assets.

### Locked details for the handoff spec (ticket 05)

- **Row order (top → bottom):**
  1. Live summary line — mirrors action_matrix summary: `provider  url <preset|value>  key <mask|reveal>  model <name|(none — press Fetch)>`.
  2. Header: `Configure LLM`.
  3. `provider` row.
  4. `base url` row — **conditional, custom-only** (Q7), dropped from layout + nav when hidden.
  5. `api key` row — masked, with reveal state indicator + chord hint.
  6. `model` row.
  7. (blank spacer)
  8. Action row: `[ Fetch ]   [ Save ]   (Esc discards)`.
  9. Fetch-state hint line (idle / loading / ok / fail — see below).
- **Labels (working):** `provider`, `base url`, `api key`, `model`; header `Configure LLM`.
- **Reveal chord: Ctrl+R** — the accelerator. Ticket 01/02 flagged Ctrl+R unreliable on conhost, so the
  **visible 👁 toggle in the key row stays the primary/always-available affordance** (ticket 02 mechanism:
  flip `Input.password`, `select_on_focus=False`); Ctrl+R is the keyboard shortcut layered on top, not the
  sole path. Spec must state the fallback so a conhost user is never locked out of revealing.
- **Fetch-state hint copy (rendering locked, exact i18n strings still graduate):**
  idle `press Fetch to load models` · loading `⠿ fetching models…` · ok `✓ N models loaded` ·
  fail `✗ fetch failed — type model manually`.
- **Summary-line masking:** key shown as up-to-8 `•`/`*` when hidden, plaintext when revealed, `—` when empty.

### Graduated from "Not yet specified"

- Final row order + label wording → **pinned** (above).
- Reveal chord (Ctrl+R vs F2 vs other) → **pinned** = Ctrl+R accelerator + visible toggle primary.
- Error/hint copy: *rendering* pinned (in-panel hint line, states above); *exact i18n strings/keys* still
  open → carried into ticket 05 (handoff spec) + i18n key plan.
