# OpenRouter compatibility and security contract

Research snapshot: 2026-07-22. Sources are current, first-party OpenRouter
documentation and API references. No credential or authenticated request was used.

## Conclusion

OpenRouter is wire-compatible with VulnClaw's synchronous OpenAI Chat Completions
path: use an ordinary OpenRouter API key as a Bearer token and set the OpenAI SDK
base URL to `https://openrouter.ai/api/v1`. A preset-only integration is therefore
feasible without a new SDK. It is not safely complete as only a new enum entry,
however. OpenRouter's heterogeneous catalog, default upstream routing, and
in-band error behavior require explicit model filtering, error handling, tests,
and user-facing privacy disclosure.

## Required API contract

| Area | Contract VulnClaw must support |
|---|---|
| Authentication | Send an ordinary OpenRouter inference API key as `Authorization: Bearer <key>`. The official Python example uses `OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`. OpenRouter recommends environment variables, never committing keys, and immediate key replacement after exposure. Keys can have credit limits. [Authentication](https://openrouter.ai/docs/api-reference/authentication) |
| Canonical endpoint | The normal preset base URL is `https://openrouter.ai/api/v1`; Chat Completions is `POST /chat/completions`. Enterprise EU in-region routing is a separately enabled product on the `eu.openrouter.ai` domain and must not replace the normal preset silently. [Authentication](https://openrouter.ai/docs/api-reference/authentication), [Provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging) |
| Chat Completions | OpenRouter accepts OpenAI-style `model`, `messages`, `max_tokens`/`max_completion_tokens`, `temperature`, and `tools`, and normalizes responses to the OpenAI Chat schema. Model IDs should be treated as opaque strings and normally include their organization prefix. Unsupported parameters are ignored by default. [API overview](https://openrouter.ai/docs/api-reference/overview), [Chat endpoint](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request) |
| Streaming | `stream: true` returns SSE Chat Completion chunks. Keepalive comment frames may occur and must be ignored. [Streaming](https://openrouter.ai/docs/api-reference/streaming) |
| Tool calling | OpenRouter uses standard OpenAI `tools`, `tool_calls`, tool-result messages, streaming tool-call deltas, `tool_choice`, and `parallel_tool_calls`. Capability varies by model and endpoint; the models catalog exposes `supported_parameters`, and OpenRouter documents `supported_parameters=tools` as the tool-capability filter. [Tool calling](https://openrouter.ai/docs/guides/features/tool-calling), [Models](https://openrouter.ai/docs/guides/overview/models) |
| Model listing | `GET /api/v1/models` returns `{data: [...]}` with OpenAI-compatible `id` fields plus OpenRouter metadata such as modalities and `supported_parameters`. `GET /api/v1/models/user` additionally filters by the authenticated user's provider preferences, privacy settings, and guardrails. [List models](https://openrouter.ai/docs/api/api-reference/models/get-models), [List models for user](https://openrouter.ai/docs/api/api-reference/models/list-models-user) |
| Attribution headers | `HTTP-Referer`, `X-OpenRouter-Title` (or `X-Title`), and `X-OpenRouter-Categories` are optional for inference. They identify and can publicly attribute the app; they are not authentication requirements. If enabled, values must be fixed VulnClaw project metadata, never a scan target, local URL, user URL, or other runtime-sensitive value. [API overview](https://openrouter.ai/docs/api-reference/overview), [App attribution](https://openrouter.ai/docs/app-attribution) |

## Routing and fallback semantics

- A model ID does not necessarily pin one upstream provider. Default routing
  favors healthy, lower-cost endpoints and uses remaining providers as fallbacks;
  `allow_fallbacks` defaults to `true`. A pre-stream failure may therefore cause
  one logical request to be sent to more than one eligible upstream. Once output
  has begun, OpenRouter cannot fail over without corrupting the partial response.
  [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection),
  [Errors and debugging](https://openrouter.ai/docs/api-reference/errors-and-debugging)
- When `tools` are present, OpenRouter makes a best effort to choose endpoints
  known to support them. Because `provider.require_parameters` defaults to
  `false`, an endpoint may otherwise ignore unsupported request parameters.
  VulnClaw depends on tool calls for core behavior, so compatibility cannot be
  inferred from a successful text response alone.
  [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- OpenRouter-specific routing, model fallback, ZDR, and provider-selection
  controls need not become first-class VulnClaw settings in the initial scope.
  The preset must nevertheless preserve the tool-use invariant. The next contract
  decision should choose either `provider.require_parameters: true` (and send
  only parameters the selected model supports) or an equally strict
  model/endpoint capability gate.

## Errors and limits

- Normal errors use `{ "error": { "code", "message", "metadata" } }`.
  Important statuses are `400` invalid request, `401` invalid/revoked key, `402`
  insufficient credits, `403` permissions/guardrail/moderation, `408` timeout,
  `429` rate limit, `502` unavailable/bad upstream response, and `503` no eligible
  provider. `error.metadata.error_type` is OpenRouter's stable Chat Completions
  classification when present. [Errors and debugging](https://openrouter.ai/docs/api-reference/errors-and-debugging)
- After generation starts, an error can arrive inside an HTTP `200` response.
  Streaming failures arrive as an SSE chunk with a top-level `error` and
  `choices[0].finish_reason == "error"`; the stream then ends. Non-streaming
  generation errors can also be in the response body. Clients must inspect the
  body/chunks rather than equating HTTP success or a non-empty `choices` array
  with generation success. [Errors and debugging](https://openrouter.ai/docs/api-reference/errors-and-debugging)
- A `429` or `503` may include `Retry-After`; honor it and use bounded exponential
  backoff. OpenRouter platform `429` responses carry `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `X-RateLimit-Reset`; successful inference responses
  do not. `GET /api/v1/key` reports credit usage and remaining per-key credit, but
  its `rate_limit` object is deprecated. [Limits](https://openrouter.ai/docs/api-reference/limits)
- OpenRouter governs capacity globally, so creating or rotating additional keys
  does not increase account rate limits. Free variants have materially lower
  request limits and availability than paid variants; they are unsuitable as a
  production preset default. [Limits](https://openrouter.ai/docs/api-reference/limits),
  [Free model router](https://openrouter.ai/docs/guides/routing/routers/free-router)

## Privacy, logging, and credential handling

- OpenRouter says it does not store prompt/response content by default. Private
  input/output logging and OpenRouter use of inputs/outputs are separate opt-ins.
  It does retain request metadata such as token counts and latency, and it samples
  a small number of prompts for anonymous categorization using a ZDR model.
  Documentation must not summarize this as "no data collection."
  [Data collection](https://openrouter.ai/docs/guides/privacy/data-collection),
  [Input/output logging](https://openrouter.ai/docs/guides/features/input-output-logging)
- Upstream providers have independent retention and training policies. By
  default, `provider.data_collection` is `allow`, which permits endpoints that
  may store data and train on it. Users can restrict account-wide routing or send
  `data_collection: "deny"`; `zdr: true` restricts a request to endpoints marked
  zero-retention. OpenRouter treats in-memory prompt caching as compatible with
  ZDR, so the UI/docs must avoid an unconditional end-to-end "zero retention"
  promise. [Provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging),
  [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection),
  [Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr)
- Because privacy-routing controls are outside the first preset-parity scope,
  initial documentation must disclose the upstream-routing/fallback behavior and
  direct users handling sensitive target data to OpenRouter account privacy/ZDR
  controls. Silently forcing `data_collection: "deny"` or `zdr: true` would be a
  separate availability-versus-privacy product decision.
- Use a dedicated, least-privilege inference key with a spending cap and, where
  practical, an expiry. Never request or accept an OpenRouter management key for
  inference. Keep the key server-side during model discovery and send it only to
  the saved endpoint or the reviewed canonical preset endpoint.
  [Create API key](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys),
  [Management keys](https://openrouter.ai/docs/guides/overview/auth/management-api-keys)

## Differences from VulnClaw's generic OpenAI-compatible path

1. `make_openai_client()` is already wire-compatible, and `client.models.list()`
   should parse `/models` IDs. No OpenRouter SDK is required.
2. Generic discovery currently discards capability metadata and returns every ID.
   For OpenRouter, use the authenticated `/models/user` catalog and retain only
   text-output models whose `supported_parameters` satisfy VulnClaw's actual
   request contract (at minimum `tools` and the token-limit parameter). Otherwise
   the UI can offer a model that silently cannot operate VulnClaw's tools.
3. VulnClaw currently sends `max_tokens`, `temperature`, and `tools` to every
   non-OpenAI provider. OpenRouter accepts those fields, but may ignore unsupported
   ones. Its unified reasoning control is not currently reached because
   VulnClaw's `reasoning_effort` branch is restricted to provider `openai`.
4. The streaming loop reads content and tool deltas but does not inspect a
   top-level chunk error or `finish_reason: "error"`. The non-streaming retry path
   treats any response with `choices` as success. Both paths need regression tests
   for OpenRouter's in-band errors so partial/empty output is never reported as a
   successful completion.
5. The generic persistent retry loop uses fixed five-second sleeps and treats
   `402` as key exhaustion. For OpenRouter, `402` requires credits or a key-limit
   change and should fail with an actionable message; `429`/`503` should honor
   `Retry-After`. Rotating keys is not a solution to OpenRouter's global capacity
   limit.
6. Adding the canonical preset URL to `PROVIDER_PRESETS` makes it an approved
   destination for the saved key in Web model discovery. Preserve the existing
   exact saved-or-reviewed endpoint trust boundary; never accept a browser-supplied
   arbitrary host for credentialed discovery.
7. There are pre-existing credential-display/storage risks to include in the
   production security acceptance criteria: `config list` serializes the full
   configuration (including keys), list-valued keys evade `config get`'s string
   redaction, and `save_config()` writes plaintext YAML without explicit
   permission hardening. OpenRouter's official environment-variable guidance
   should be the documented preferred path until those are addressed.
8. Optional attribution is not required for compatibility. For initial parity,
   omit it unless the project deliberately wants public OpenRouter attribution;
   if chosen, use only the fixed official VulnClaw homepage and title.

## Inputs for the next preset-contract decision

- Fixed facts: identifier `openrouter`, label `OpenRouter`, canonical base URL
  `https://openrouter.ai/api/v1`, ordinary static inference key, OpenAI SDK path,
  and opaque organization-prefixed Model IDs.
- Select an explicit, currently available, non-free default model only after
  verifying that its authenticated catalog metadata supports VulnClaw's full
  tool/request contract. Do not use a dynamic router or free variant as the
  production default without explicitly accepting nondeterminism or low limits.
- Model discovery should use the user-filtered catalog and filter capabilities
  client-side; a plain alphabetical dump of all OpenRouter models is not safe
  parity for a tool-dependent application.
- Omit optional attribution by default. Do not silently add privacy-routing
  controls in preset parity; clearly document OpenRouter's defaults and account
  controls.
- Runtime proof must cover non-streaming chat, streaming text, streamed tool
  calls, model discovery, pre-stream failures, in-band/mid-stream errors, `401`,
  `402`, `429` with `Retry-After`, and an unsupported-tool model rejection.
