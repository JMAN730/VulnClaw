# OpenRouter runtime compatibility prototype

Prototype run: 2026-07-22

## Question

Can VulnClaw's existing OpenAI-compatible runtime satisfy the chosen OpenRouter
preset contract for client construction, request payloads, model discovery,
streaming, tool calls, in-band errors, and retry behavior without
provider-specific production changes?

## Method

A disposable Python logic prototype imported the current runtime functions and
drove them with local fake clients, fake streams, catalog records, and the
literal key `fake-openrouter-key`. It made no network request and used no real
credential.

The one-command run was:

```powershell
python .scratch/openrouter-provider/tmp_openrouter_runtime_prototype.py
```

The throwaway script was deleted after this result was captured.

## Observed state

```text
OPENROUTER RUNTIME PROTOTYPE
state: complete
PASS | static-client               | {'api_key': 'fake-openrouter-key', 'base_url': 'https://openrouter.ai/api/v1'}
PASS | basic-request               | max_tokens,messages,model,temperature,tools
GAP  | required-parameters         | provider.require_parameters is absent
GAP  | model-discovery             | calls=['models.list']; output=['a/model', 'z/model']; metadata discarded
PASS | streamed-tools              | split ID/name/arguments reconstructed into one valid tool call
PASS | tool-result-follow-up       | reuses validated chat kwargs with appended tool-result messages
PASS | streaming-text              | 'hello'
GAP  | in-band-stream-error        | returned='partial' without raising
GAP  | in-band-response-error      | accepted choices with error; retries=0
GAP  | openrouter-retry-semantics  | 401 hard-fails; 402/429 rotate keys; 503 retries; fixed 5s; no Retry-After
summary: PASS=5 GAP=5
```

## Scenario findings

| Scenario | Result | Evidence and implication |
|---|---|---|
| Static bearer-token isolation | Pass | [`AgentCore._get_client`](../../../vulnclaw/agent/core.py) passed only the configured fake key and canonical base URL to [`make_openai_client`](../../../vulnclaw/config/settings.py). The chosen static-key transport needs no new SDK. Preset selection must still force static auth and disable the ChatGPT proxy so an OAuth token cannot be routed to OpenRouter. |
| Basic non-streaming request shape | Pass | [`build_chat_completion_kwargs`](../../../vulnclaw/config/llm_utils.py) emitted `model`, `messages`, `max_tokens`, `temperature`, and `tools` for `provider=openrouter`. These fields match the verified OpenRouter Chat Completions contract. |
| Required-parameter enforcement | Gap | The same builder emitted neither an OpenRouter `provider` body nor `extra_body`, so `provider.require_parameters=true` is absent from initial calls and every path that reuses these kwargs. A provider-aware request policy is required. |
| User-filtered capability discovery | Gap | [`fetch_provider_models`](../../../vulnclaw/config/settings.py) called the generic SDK `models.list()`, retained only `id`, sorted all IDs, and swallowed every exception into an indistinguishable empty list. It cannot call `/models/user`, filter output modality and required parameters, cap/validate records, or return actionable failure detail. |
| Streamed tool-call assembly | Pass | [`_assemble_tool_calls`](../../../vulnclaw/agent/llm_client.py) reconstructed an ID, function name, and JSON arguments split across three chunks and validated the assembled call. |
| Tool-result follow-up | Pass with inherited guard gap | [`call_llm_auto`](../../../vulnclaw/agent/llm_client.py) appends assistant/tool messages and reuses the original kwargs for the summary request. Once the OpenRouter request guard is added centrally, the follow-up inherits it; today it inherits the missing guard. |
| Streaming text | Pass | [`call_llm_stream`](../../../vulnclaw/agent/llm_client.py) consumed synchronous fake SSE-like chunks through its async adapter and returned `hello`. The basic stream transport is compatible. |
| Mid-stream/in-band error | Gap | A stream containing `partial` followed by a top-level error and `finish_reason="error"` returned `partial` as successful output. Neither [`call_llm_stream`](../../../vulnclaw/agent/llm_client.py) nor [`call_llm_auto_stream`](../../../vulnclaw/agent/llm_client.py) checks top-level chunk errors or error finish reasons, including the tool-summary stream. |
| Non-streaming in-band error | Gap | [`_call_with_persistent_retries`](../../../vulnclaw/agent/llm_client.py) accepts any response with a non-empty `choices` collection. A response carrying an error choice was returned with zero retries. Response validation must precede success handling. |
| HTTP error and retry semantics | Gap | Current string classifiers hard-fail `401`, classify both `402` and `429` as key exhaustion, retry `503`, sleep a fixed five seconds, and never read `Retry-After`. For OpenRouter, `402` needs an actionable credit/key-limit failure, account-global `429` is not repaired by cycling keys, and `429`/`503` should honor bounded `Retry-After`. |
| Unsupported Model ID preflight | Gap | There is no provider-aware catalog capability record or request preflight, so an incompatible manually entered model reaches inference and may silently ignore required parameters unless OpenRouter rejects it. |

## Conclusion

The current OpenAI SDK transport is compatible with OpenRouter for static
authentication, ordinary Chat Completions, streaming text, streamed tool-call
assembly, and tool-result follow-up. No OpenRouter SDK or parallel runtime is
needed.

The chosen preset contract is **not** satisfied by a data-only enum/preset
addition. Production work needs four bounded provider-aware extensions:

1. add `provider.require_parameters=true` to every OpenRouter request through
   the shared request builder;
2. add authenticated `/models/user` discovery with strict record validation,
   capability filtering, deterministic ordering/capping, and actionable errors;
3. normalize and reject OpenRouter top-level/in-band errors before any
   non-streaming or streaming response is treated as success; and
4. classify `401`/`402`/`429`/`503` semantically, honor bounded `Retry-After`,
   and avoid using key rotation as a response to account-global limits.

## Inputs for the production plan

- Keep provider-specific behavior behind explicit
  `llm.provider == "openrouter"` checks; do not infer it from a user-controlled
  base URL.
- Centralize request policy so initial, streaming, tool follow-up, helper, and
  reporting calls cannot drift.
- Centralize response-error normalization and test all three streaming loops:
  first response, tool-result summary, and non-auto streaming.
- Preserve the Web backend's saved-or-reviewed endpoint trust boundary when
  adding credentialed `/models/user` discovery.
- Add regression fixtures for valid and oversized/malformed catalog responses,
  unsupported models, partial-then-error streams, non-streaming error choices,
  `401`, `402`, `429` with `Retry-After`, and `503`.
- Document that transport compatibility does not change OpenRouter's upstream
  routing, fallback, retention, or training-policy defaults.
