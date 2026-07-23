# Choose the OpenRouter preset contract

Type: grilling
Status: resolved
Blocked by: 01

## Question

Given the verified OpenRouter contract and the agreed preset-parity scope, what exact contract should the first-class preset expose: canonical identifier and label, base URL, default Model ID or default-selection rule, model-list behavior, attribution metadata policy, and any provider-specific validation or documentation? Which choices preserve existing custom configuration and backward compatibility?

## Answer

Adopt this first-class, static-key-only LLM Provider Preset:

| Field | Contract |
|---|---|
| Preset/enum value | `openrouter` |
| Display label | `OpenRouter` |
| Canonical base URL | `https://openrouter.ai/api/v1` (no trailing slash) |
| Default Model ID | `openai/gpt-4o` |

`openai/gpt-4o` is a compatibility baseline, not a “best model”
recommendation. In the official
[OpenRouter catalog](https://openrouter.ai/api/v1/models) on 2026-07-22 it is
a current paid, text-output Model ID with no declared expiration; it advertises
`tools`, `max_tokens`, and `temperature`, and its 128,000-token context matches
VulnClaw's existing default context limit. It therefore supports the current
request shape without a dynamic router, free tier, reasoning-parameter
translation, or credentialed selection during preset application.

### Authentication and key semantics

- Require `auth_mode=static` and an ordinary OpenRouter inference key. Reuse
  `llm.api_key` / ordered `llm.api_keys` and
  `VULNCLAW_LLM_API_KEY` / `VULNCLAW_LLM_API_KEYS`; a non-empty key pool keeps
  its existing precedence over the single key.
- Selecting `openrouter` must set `auth_mode=static` and disable
  `chatgpt_auto_proxy`. Never send a stored ChatGPT OAuth token to OpenRouter.
  Do not delete the OAuth token store.
- Preserve an already saved static key, consistent with an explicit switch to
  a reviewed built-in endpoint, but tell the user that an OpenRouter key is
  required. Never assert that a prior provider's key is valid.
- Recommend a dedicated inference key with a spending cap and, when practical,
  an expiry. Never request or accept a management key. Never expose a key to the
  browser, logs, discovery results, or error text.
- For OpenRouter, an invalid/revoked key may advance to the next configured key.
  Treat `402` as an actionable credit/key-limit failure; honor `Retry-After` for
  `429`/`503` with bounded backoff instead of cycling keys.

### Tool and request compatibility

Keep the existing OpenAI Chat Completions SDK path. Every OpenRouter Chat
Completion request must add this fixed body:

```json
{"provider":{"require_parameters":true}}
```

This is an internal compatibility invariant, not a first-class routing
setting. It prevents an upstream endpoint from silently ignoring a parameter
VulnClaw sent. With the current generic request builder, a compatible model must
advertise all three required parameters: `tools`, `max_tokens`, and
`temperature`.

Apply the guard to initial, streamed, tool-result follow-up, structured-helper,
and report-generation calls whenever the explicit preset is `openrouter`.
Unsupported manual Model IDs must fail with an actionable compatibility error,
not silently drop parameters. OpenRouter-specific routing, fallback, privacy,
ZDR, data-collection, and reasoning settings remain outside the first-class
configuration surface. In-band and mid-stream error handling remains required
as established by
[Verify OpenRouter's compatibility and security contract](01-verify-openrouter-contract.md).

### Model discovery

Choose OpenRouter discovery only from explicit
`provider == "openrouter"`—never by guessing from the URL:

1. Send authenticated `GET {normalized_base_url}/models/user` with the current
   static inference key. For the preset this is
   `https://openrouter.ai/api/v1/models/user`. Do not fall back to `/models`,
   because that would discard the user's provider preferences, privacy
   settings, and guardrails.
2. Parse `{data: [...]}` and retain a record only when its trimmed `id` is
   non-empty and at most 160 characters,
   `architecture.output_modalities` contains `text`,
   `supported_parameters` contains `tools`, `max_tokens`, and `temperature`,
   and the record is not explicitly expired.
3. Treat retained IDs as opaque strings and deduplicate exact values. Put
   `openai/gpt-4o` first when present in the user-filtered catalog, then sort by
   case-folded ID with the original ID as a stable tiebreaker. Return at most
   500 IDs. Keep manual Model ID entry available for private/new IDs or entries
   beyond the display cap.
4. Missing credentials, `401`, timeout, malformed/oversized data, or an empty
   compatible set must return a distinct actionable, non-secret-bearing error.
   Do not disguise failure as a successful empty list.

Free variants and gateway-defined routes are not rejected by spelling. They
may appear when metadata passes the filter or be entered manually because
Model IDs remain opaque. Documentation must warn that `:free` variants have
lower limits/availability and dynamic routers trade deterministic model choice
for routing behavior; neither is the default.

Keep generic `client.models.list()` behavior unchanged for all other presets
and `custom`. If an explicit OpenRouter base-URL override is used, retain
OpenRouter's `/models/user` and compatibility semantics. The Web backend may
send the saved key only to the already-saved override or an exact reviewed
preset URL.

### Validation, overrides, and backward compatibility

- Normalize the preset ID to lowercase. For `openrouter`, trim the Model ID and
  reject empty values, values over 160 characters, and ASCII control
  characters. Do not impose an organization-prefix grammar or parse suffixes.
- The preset supplies the canonical HTTPS URL. Explicit overrides remain
  available through the existing base-URL field and generic safeguards:
  HTTP/S only, host required, and no embedded credentials, query, or fragment.
  Do not silently choose the EU domain or add it as another preset.
- On an explicit provider switch, replace the previous preset URL with the
  canonical OpenRouter URL. Apply the default model only when the current model
  is blank or still equals the previous preset default; preserve a deliberate
  custom model. Explicit model/base-URL values in the same update win.
- Do not migrate or reinterpret existing configurations. A `custom` or
  `openai` configuration already pointing at OpenRouter stays as authored;
  arbitrary provider strings/endpoints/models still load. Adding the enum
  member must not narrow persisted `llm.provider: str`.
- Future default changes affect only fresh/defaulted selections and never
  rewrite a saved Model ID. Provider-aware discovery and fixed
  `require_parameters` activate only for the explicit `openrouter` preset.
- Offline configuration remains valid. A structurally valid manual Model ID can
  be saved without a catalog call; inference then fails closed if no compatible
  upstream endpoint exists.

### Attribution, privacy, and documentation

Do not send `HTTP-Referer`, `X-OpenRouter-Title`/`X-Title`, or
`X-OpenRouter-Categories` initially. They are optional and can create public
attribution. Keep the existing fixed/overrideable `User-Agent`. Any later
attribution decision may use only fixed VulnClaw metadata—never a target,
prompt, user/local URL, credential, or runtime value.

CLI, TUI, Web settings, `.env.example`, and both READMEs must disclose near
provider selection that:

- OpenRouter is a Model Gateway that can route among upstream providers and
  perform pre-stream fallback;
- defaults can allow upstreams that retain data or use it for training;
  OpenRouter retains request metadata, and upstream policies are independent;
- this preset does not force `data_collection: "deny"` or `zdr: true` and
  provides no end-to-end zero-retention guarantee; users handling sensitive
  authorized-target data must configure and verify their OpenRouter account
  privacy/provider preferences first; and
- free/router Model IDs carry the reliability/determinism tradeoffs above.

No glossary change is needed: `LLM Provider Preset`, `Model Gateway`, `Upstream
Model Provider`, and opaque `Model ID` in `CONTEXT.md` remain sufficient.

### Handoff to the runtime prototype

[Prove OpenRouter runtime compatibility](03-prove-openrouter-runtime-compatibility.md)
should build only a disposable seam/probe for this contract. Verify the
canonical URL and default, static bearer-token isolation, `/models/user`
filter/order/cap, fixed `require_parameters`, non-streaming and streaming text,
streamed tools and tool-result follow-up, unsupported-model rejection, and
in-band/mid-stream errors. Use injected/fake credentials unless the user
separately supplies a test inference key.
