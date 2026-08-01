# Specify the production change set and acceptance criteria

Type: grilling
Status: resolved
Blocked by: 03

## Question

Given the chosen preset contract and compatibility prototype, what is the minimal production-ready change set across provider schema, trusted-endpoint handling, configuration persistence, CLI, both terminal interfaces, Web settings, bilingual documentation, examples, and automated tests? Define security and compatibility acceptance criteria, validation commands, release notes, and any separately scoped follow-up work clearly enough for implementation to proceed without unresolved design decisions.

## Answer

### Non-negotiable contract

- Add the first-class preset ID `openrouter`, label `OpenRouter`, canonical base
  URL `https://openrouter.ai/api/v1`, and deterministic default Model ID
  `openai/gpt-4o`.
- Use the existing generic static credential fields and environment variables:
  `llm.api_key`, `llm.api_keys`, `VULNCLAW_LLM_API_KEY`, and
  `VULNCLAW_LLM_API_KEYS`. Do not introduce an OpenRouter-specific secret name,
  accept a management key, or route a ChatGPT OAuth token to OpenRouter.
- Keep the existing OpenAI SDK transport. Omit optional attribution headers.
  Do not add first-class upstream routing, fallback, ZDR, or privacy controls.
- Preserve explicit model/base-URL overrides, custom providers, existing
  persisted configuration, and the current default provider.
- Document that OpenRouter is a Model Gateway whose default routing can use
  multiple upstreams and allow upstream data collection; do not claim
  end-to-end zero retention.

### Dependency-ordered production changes

#### 1. Preset, switching, and configuration

Change:

- `vulnclaw/config/schema.py`
  - Add `LLMProvider.OPENROUTER`.
  - Add the reviewed entry to `PROVIDER_PRESETS`.
  - Update `LLMConfig.provider` documentation without narrowing the persisted
    field from `str`; unknown/custom values must continue to load.
- `vulnclaw/config/settings.py`
  - Extend `apply_provider_preset()` so an explicit switch to `openrouter`
    selects the canonical URL, sets `auth_mode="static"`, and disables
    `chatgpt_auto_proxy` without deleting stored OAuth tokens or static keys.
  - Preserve a deliberately customized model under the existing compatibility
    rule; use `openai/gpt-4o` only for blank/previous-default selections.
  - Safely handle an unknown old provider when comparing old defaults.
- `vulnclaw/web/services/config_service.py`
  - Preserve the existing update order: apply the preset first, then allow
    explicit model/base-URL values in the same request to win.
  - Report `api_key_configured` from `llm.key_pool()`, not only the legacy
    single key.
- `vulnclaw/cli/main.py`
  - Keep `config provider` validation/listing driven by `LLMProvider` and
    `PROVIDER_PRESETS`; add no second provider registry.

Acceptance:

- A fresh switch produces exactly the decided tuple and static auth state.
- A deliberate model override survives a switch when current compatibility
  policy says it should.
- Existing `openai`, other built-ins, arbitrary provider strings, and `custom`
  configurations round-trip unchanged.
- Selecting OpenRouter never sends or deletes a ChatGPT OAuth token.

#### 2. Shared request policy and model discovery

Change:

- `vulnclaw/config/llm_utils.py`
  - In `build_chat_completion_kwargs()`, when and only when the explicit
    provider is `openrouter`, add
    `extra_body={"provider": {"require_parameters": True}}`.
  - Merge this fixed policy without dropping unrelated request extras and do not
    expose a setting that can silently disable the invariant.
  - Because every call path uses this builder/reuses its kwargs, initial,
    streaming, tool-result, helper, and reporting requests inherit one policy.
- `vulnclaw/config/settings.py`
  - Add a typed detailed discovery result while retaining
    `fetch_provider_models()` as a compatibility wrapper for current callers.
  - For explicit `openrouter`, use `httpx` (already a direct dependency) to send
    an authenticated `GET {normalized_base_url}/models/user`; do not infer
    OpenRouter behavior from the URL.
  - Disable cross-origin credentialed redirects and retain the existing
    ten-second timeout unless tests justify a smaller bound.
  - Bound the response body (2 MiB), source records, retained records (500), and
    Model ID length (160). Require a non-empty string ID, text output modality,
    and `tools`, `max_tokens`, and `temperature` in `supported_parameters`;
    reject explicitly expired records, ASCII control characters, malformed
    shapes, and duplicates. Put the default first when present, then sort
    deterministically.
  - Return distinct non-secret statuses for missing key, untrusted URL, auth,
    timeout, malformed/oversized response, and empty compatible catalog.
  - Keep generic SDK `models.list()` behavior unchanged for other providers and
    `custom`.
- `vulnclaw/web/schemas.py`
  - Extend `ProviderModelsResponse` with a stable status/error code while
    retaining `models`, `detail`, `base_url`, and `has_api_key`.
  - Keep provider/model length limits and `_validate_http_base_url()`;
    explicitly test credentials, query strings, and fragments are rejected.
- `vulnclaw/web/services/provider_service.py`
  - Pass the explicit provider into detailed discovery.
  - Preserve `_is_trusted_base_url()`: the saved key may go only to the saved
    normalized endpoint or an exact reviewed preset endpoint.
  - Map typed failures to actionable sanitized responses; never return a raw
    upstream body or credential.

Compatibility/preflight policy:

- Keep structurally valid manual Model IDs and offline configuration available.
- If a loaded catalog proves a selection incompatible, reject/warn before an
  autonomous run. If no catalog is available, the fixed
  `require_parameters=true` request is the authoritative fail-closed runtime
  guard; do not require a new network preflight on every run.
- Treat Model IDs as opaque: trim them, reject empty/over-160/control-character
  values, but do not require an organization prefix or parse suffixes.

#### 3. Response validation and retry semantics

Change `vulnclaw/agent/llm_client.py`:

- Add one provider-aware error model/normalizer used before any response is
  accepted by `_call_with_persistent_retries()`.
- Validate top-level response errors, error choices, top-level stream-chunk
  errors, and `finish_reason="error"` in:
  - `call_llm()` and `call_llm_auto()`;
  - `call_llm_stream()`;
  - the initial and tool-summary loops in `call_llm_auto_stream()`; and
  - tool-result summary responses.
- Preserve partial text only as diagnostic context; never return it as a
  successful assistant result after an error.
- For explicit `openrouter`:
  - `401`: rotate once through other configured static keys if available, then
    fail terminally and sanitise the message;
  - `402`: fail terminally with an actionable credit/key-limit message and no
    key cycling;
  - `429`: do not cycle keys for an account-global limit; retry within a named
    maximum attempt budget;
  - `503`: retry within that same bounded transient budget.
- Parse `Retry-After` as bounded delta-seconds or HTTP-date, reject malformed or
  negative values, cap it at a named maximum (60 seconds), and otherwise use
  bounded exponential backoff. Use named constants rather than magic numbers.
- Keep legacy retry/failover behavior unchanged for other providers unless a
  separately tested generic refactor is deliberately chosen.
- Cap error text/metadata, preserve only safe status/type/request identifiers,
  and never log authorization headers, full bodies, prompts, or keys.

`vulnclaw/agent/core.py` should continue constructing the shared client, with
regression coverage proving the OpenRouter preset can only use static
credentials and never enters the ChatGPT proxy branch.

#### 4. CLI, terminal UIs, Web UI, and localization

Most provider selectors already consume `list_providers()` or `/api/providers`;
keep that single source of truth.

Update:

- `vulnclaw/cli/tui.py` and `vulnclaw/cli/tui_textual.py`
  - Consume detailed discovery outcomes so missing credentials, auth failure,
    timeout, no compatible model, and malformed response are distinguishable.
  - Retain manual Model ID entry and never echo keys.
- `vulnclaw/web/app.py`, `vulnclaw/web/schemas.py`, and
  `vulnclaw/web/services/provider_service.py`
  - Preserve server-side validation and secret lookup for
    `/api/providers` and `/api/provider-models`; the browser submits no key.
- `frontend/src/types/api.ts`, `frontend/src/api/web.ts`, and
  `frontend/src/pages/SettingsPage.tsx`
  - Represent the stable discovery status, show actionable localized feedback,
    retain manual entry, and preserve provider/model/base-URL persistence.
  - Do not put a key or credential-derived cache identity in React state.
- `vulnclaw/i18n/en.json`, `vulnclaw/i18n/zh.json`,
  `frontend/src/i18n/en.json`, and `frontend/src/i18n/zh.json`
  - Add matching keys for discovery failures and the OpenRouter
    routing/privacy warning.
- `vulnclaw/config/cli_constants.py` and `vulnclaw/cli/manual.py`
  - Update examples/count wording where it is not generated dynamically.

No new authentication or authorization surface is introduced. Existing Web
deployment controls remain responsible for endpoint authorization; all provider
and trusted-destination decisions remain server-side.

#### 5. Documentation and release surface

Update:

- `.env.example` with the canonical URL/model example while continuing to use
  `VULNCLAW_LLM_API_KEY`;
- `README.md` and `README_EN.md` provider lists/tables/examples and every
  built-in count from 13 to 14;
- relevant CLI/TUI/Web copy with:
  - static inference-key guidance and spending-cap recommendation;
  - upstream routing/fallback disclosure;
  - metadata retention and independent upstream policy disclosure;
  - account privacy/ZDR guidance without a zero-retention promise; and
  - free/dynamic-router reliability and determinism trade-offs.

No dependency, database migration, new required environment variable, or
destructive config rewrite is needed.

### Tests

Keep behavior tests with the production slice they protect.

- `tests/test_config.py`
  - Enum/preset tuple, provider count, listing, switch/default behavior,
    static-auth/proxy isolation, custom override preservation, unknown old
    provider, key-pool persistence, and save/load round-trip.
- `tests/test_agent.py`
  - OpenRouter request kwargs include the fixed `extra_body` guard for ordinary
    calls and retain current OpenAI/other-provider kwargs unchanged.
  - AgentCore constructs the canonical static client and cannot select the
    ChatGPT proxy for the OpenRouter preset.
- Add focused `tests/test_provider_models.py`
  - Authenticated `/models/user`, deterministic filter/order/cap, default-first
    behavior, manual/opaque IDs, text/tool/parameter requirements, expired and
    duplicate records, missing/wrong types, control characters, 2 MiB/record
    bounds, wrong content type, timeout, 401, redirect handling, and sanitized
    failures.
- `tests/test_web.py`
  - Preset metadata, stable discovery statuses, missing key, saved URL, reviewed
    preset URL, attacker URL/credential/query/fragment rejection, redirect
    exfiltration resistance, raw-error/secret redaction, config update
    precedence, and `api_key_configured` for key pools.
- `tests/test_llm_client_streaming.py`
  - Valid text and split tool deltas remain green.
  - Partial-then-error, empty error, `finish_reason="error"`, and tool-summary
    errors fail in every stream loop without reporting success.
- `tests/test_llm_failover.py`
  - OpenRouter `401` bounded key rotation, terminal `402`, no key cycling on
    `429`/`503`, delta-seconds/HTTP-date/malformed/negative/over-60
    `Retry-After`, and bounded attempts; retain other-provider behavior.
- `tests/test_cli.py`
  - CLI listing/switch, prompt-toolkit and Textual selection, discovery error
    feedback, manual entry, and English/Chinese output without key exposure.
- `tests/test_agent_runtime_i18n_catalog.py`
  - Backend catalog key/placeholder parity; add equivalent frontend catalog
    parity coverage in `tests/test_web.py` if no dedicated frontend test runner
    is introduced.
- Frontend
  - Do not add a test framework solely for this feature. Keep the existing
    Python source-contract tests where useful and require the TypeScript/Vite
    production build.

Security/abuse fixtures must use fake keys and assert they never appear in
logs, exceptions, HTTP responses, snapshots, cache keys, or frontend sources.
No live OpenRouter credential belongs in CI.

### Conventional commit slices

1. `feat: add openrouter provider preset`
   - schema, switching/auth isolation, config/Web metadata, and their tests.
2. `feat: validate openrouter model discovery`
   - typed `/models/user` discovery, trusted-destination integration, UI/TUI
     status handling, and abuse tests.
3. `fix: enforce openrouter request and error semantics`
   - fixed request guard, in-band validation, bounded retry/failover behavior,
     and regression tests.
4. `docs: document openrouter provider behavior`
   - bilingual docs, examples, i18n, provider counts, and release notes.

Each commit must pass its relevant tests and must not weaken existing assertions.

### Validation

Run the repository's checked-in commands:

```powershell
python -m pytest
python -m ruff check .
python -m build
npm --prefix frontend ci
npm --prefix frontend run build
python scripts/release_preflight.py --build
```

The frontend has no checked-in lint, typecheck, or test scripts; `npm run build`
already runs `tsc -b` before Vite and is the required frontend type/build gate.

Manual verification uses a local fake OpenAI-compatible server and a test-only
saved base-URL override. Capture requests and prove:

- authenticated `/models/user` uses only the fake key and refuses an arbitrary
  browser-supplied destination/redirect;
- every chat/tool/summary request contains `require_parameters=true`;
- normal, streaming, and tool-follow-up behavior works;
- HTTP and in-band `401`/`402`/`429`/`503` cases follow the bounded policy;
- attribution headers are absent; and
- fake secrets are absent from output and logs.

### Deployment, rollback, and residual risks

- Deployment only needs an OpenRouter inference key supplied through the
  existing generic secret mechanism and outbound HTTPS access to
  `openrouter.ai`; deploy backend and built frontend together because the
  discovery response contract changes.
- Rollback is code-only. A rolled-back release may read the persisted
  `openrouter` string as an unknown/custom provider; do not delete or rewrite
  it. Users can temporarily use the existing custom OpenAI-compatible endpoint
  path.
- Remaining risks are external catalog/model drift, upstream routing/pricing
  and privacy-policy changes, time-of-check/time-of-use catalog drift, and the
  existing risk of explicitly saved custom endpoints. Mitigate with bounded
  caching/validation, runtime fail-closed parameter enforcement, clear
  disclosure, and the preserved trusted-destination boundary.
- OpenRouter-specific routing/privacy settings, OAuth/delegated keys, EU-only
  routing, cost display, and dynamic capability/pricing UX remain separately
  scoped follow-ups, not hidden requirements for this preset.

### Definition of done

All configuration, CLI, prompt-toolkit, Textual, Web backend, and React surfaces
select and persist the same preset contract; static credentials remain
server-side and isolated; compatible models are discoverable with actionable
safe failures; incompatible requests fail closed; all non-streaming, streaming,
tool, and summary paths normalize in-band errors; retry/key behavior matches
the decided semantics; bilingual docs and counts are correct; the fake-server
security check passes; and the complete Python lint/test/build, frontend build,
and release preflight are green.
