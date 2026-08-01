# Handoff spec synthesis

Type: grilling
Status: resolved
Assignee: JMAN730
Blocked by: 03, 04

## Question

Synthesize everything into the **handoff spec** — the destination artifact (Q9). A separate build
effort must be able to implement the panel from this alone, no re-deciding. Assemble:

- Final field set + row order + labels (from prototype, ticket 04).
- The `config_panel` prompt-type contract in `SecondaryPopup`: how it's invoked from `/config`, its
  mode in the prompt state machine, entry/exit, and the save/discard semantics (Q4).
- Interaction model verbatim (ticket 02): provider selection, fetch action + feedback states, key
  masking + reveal toggle (Q8), conditional base URL row (Q7), up/down + Enter + Escape (Q6).
- Widget choices (ticket 01) with the reuse-vs-new call for each row.
- Delete/keep/reuse table + i18n key plan (ticket 03), including new `tui.*` keys and en/zh values.
- Acceptance criteria + validation/error behavior (graduated from Not-yet-specified).

Output: `.scratch/config-panel/spec.md` (the handoff spec). Resolving this ticket completes the map —
the way to the destination is clear and the build effort can start.

## Answer

**Resolved 2026-07-23.** Handoff spec written to [`.scratch/config-panel/spec.md`](../spec.md) — the
map's destination artifact. Synthesized tickets 01–04 into a single build-ready document; the separate
build effort can implement from it with no re-deciding.

Bulk of the spec is mechanical synthesis of already-locked decisions. This session's grilling resolved
the four remaining open items (the "Not yet specified" fog):

- **i18n key strategy** — fresh `tui.config_panel_*` key family; the 9 legacy wizard keys are orphaned
  once `_h_config` + `_cmd_config` are deleted (`run_config_tui` uses hardcoded English), so **delete
  all 9**; 3 shape-neutral legacy values (`api_key_configured`, `api_key_not_configured`, `config_saved`)
  lifted verbatim into new keys.
- **Full key inventory + en values** — 21 keys (labels, packed hint line, buttons, fetch-state copy,
  errors, summary placeholder). `{n}` interpolation on fetch-ok; summary line stays code-composed from
  row-label keys. Locked in spec §8.
- **zh values** — matched existing zh style (keeps `API Key`/`Base URL` English). Approved without
  native review → spec flags that a Chinese-reading reviewer should sanity-check before ship.
- **Acceptance criteria** — 9 pass/fail statements (spec §10), all lifted from locked decisions.

Spec sections: §1 what ships, §2 layout/row-order, §3 widgets (reuse-vs-new), §4 draft edit + save/discard,
§5 interaction model, §6 validation/errors, §7 removal plan (3 surfaces, panel replaces 1), §8 i18n key
plan (full en+zh table), §9 win32 discipline, §10 acceptance criteria, §11 assets.

No new tickets surfaced; no fog remains. **Map complete.**
