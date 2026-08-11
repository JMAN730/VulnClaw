# Add OpenRouter as an LLM provider

**Date:** 2026-08-11
**Status:** Approved design

## Goal

Let users select **OpenRouter** as their LLM provider from the CLI, TUI, and Web
Settings UI, the same way they select OpenAI, Anthropic, DeepSeek, etc.

## Background

OpenRouter is an OpenAI-compatible aggregator:

- Base URL: `https://openrouter.ai/api/v1`
- Auth: `Authorization: Bearer <key>` (standard OpenAI SDK key handling)
- Model listing: `GET /v1/models` (works with existing `fetch_provider_models`)
- Model IDs are namespaced, e.g. `anthropic/claude-sonnet-5`, `openai/gpt-4o`

Every provider consumer in the codebase is **data-driven** off the
`LLMProvider` enum and the `PROVIDER_PRESETS` dict in
`vulnclaw/config/schema.py`:

- CLI `list_providers()` / `vulnclaw config provider` iterate the presets
- Web `get_provider_presets()` builds the Settings dropdown from the presets
- `apply_provider_preset()` auto-fills `base_url`/`model` from the preset
- `_is_trusted_base_url()` (web `provider_service.py`) auto-trusts any preset
  base URL, so server-side model listing works with no extra allow-listing

No hardcoded provider menus exist. Therefore adding a provider is one enum value
plus one preset entry — no client, no UI, no trust-list changes.

## Design

### Change 1 — `LLMProvider` enum (`vulnclaw/config/schema.py`)

Add:

```python
OPENROUTER = "openrouter"
```

### Change 2 — `PROVIDER_PRESETS` (`vulnclaw/config/schema.py`)

Add:

```python
LLMProvider.OPENROUTER: {
    "base_url": "https://openrouter.ai/api/v1",
    "default_model": "",
    "label": "OpenRouter",
},
```

**Design decisions:**

- **`default_model` is blank.** OpenRouter routes hundreds of models with no
  single obvious default; the user picks after selecting the provider. Matches
  the existing `CUSTOM` preset, which also ships blank and works (model listing
  populates the dropdown). `apply_provider_preset()` only overwrites the model
  when the preset supplies one, so a blank default leaves the user's model
  untouched on switch.
- **No ranking headers.** OpenRouter's optional `HTTP-Referer` / `X-Title`
  headers only affect its public leaderboard. Skipped — they require a
  per-provider header code path that `make_openai_client` does not have, and add
  no functional value.

### Change 3 (cosmetic, optional) — provider description string

`LLMConfig.provider` field description enumerates provider names. Append
`openrouter` for accuracy. Purely documentation; no behavior depends on it.

## Non-goals

- No changes to `make_openai_client`, `fetch_provider_models`, or any UI file.
- No per-provider header logic.
- No OAuth path (OpenRouter uses a static API key, already supported).

## Testing

In `tests/config/test_config.py`:

1. Extend `test_provider_presets` expected list with `"openrouter"` (or add a
   focused test) asserting `LLMProvider("openrouter") is LLMProvider.OPENROUTER`.
2. Add `test_openrouter_preset` mirroring the Ollama test:
   - `PROVIDER_PRESETS[LLMProvider.OPENROUTER]["base_url"] == "https://openrouter.ai/api/v1"`
   - `preset["default_model"] == ""`
   - `preset["label"]` is non-empty
3. Add `hasattr(LLMProvider, "OPENROUTER")` to `test_llm_provider_enum`.

## Manual verification

- `vulnclaw config provider --list` shows `openrouter`.
- `vulnclaw config provider openrouter` switches and sets base URL.
- Web Settings: OpenRouter appears in the dropdown; after saving an OpenRouter
  key, "list models" returns the OpenRouter catalog.
