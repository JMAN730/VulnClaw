# Add OpenRouter as a first-class provider preset

Label: wayfinder:map

## Notes

- Destination: users can select an `openrouter` LLM Provider Preset anywhere existing presets are supported, with the same configuration, model-discovery, documentation, and validation quality as current presets.
- Initial scope is preset parity only. OpenRouter-specific upstream routing, fallback, and privacy-policy controls are not first-class VulnClaw settings in this effort.
- Canonical language is defined in [`CONTEXT.md`](../../CONTEXT.md): OpenRouter is a Model Gateway exposed through an LLM Provider Preset; its model identifiers remain opaque Model IDs.
- Preserve the existing trust boundary: a saved API key may only be sent to the saved endpoint or a reviewed built-in preset endpoint. Never expose or log API keys.
- Research sessions should use the `research` skill and current official OpenRouter documentation. Decision sessions should use `grilling` and `domain-modeling`; prototype sessions should use `prototype`.
- Charting this map does not authorize implementation or a pull request.

## Decisions so far

- [Verify OpenRouter's compatibility and security contract](issues/01-verify-openrouter-contract.md) — OpenAI SDK compatibility is confirmed; safe preset parity additionally requires capability-aware model discovery, in-band error handling, and explicit routing/privacy disclosure.
- [Choose the OpenRouter preset contract](issues/02-choose-openrouter-preset-contract.md) — Use the canonical static-key preset with `openai/gpt-4o`, user-filtered capability discovery, fixed required-parameter enforcement, and explicit routing/privacy disclosure while preserving manual overrides.
- [Prove OpenRouter runtime compatibility](issues/03-prove-openrouter-runtime-compatibility.md) — The OpenAI transport and tool streams are compatible, but production needs provider-aware request guards, discovery, in-band error normalization, and retry handling.
- [Specify the production change set and acceptance criteria](issues/04-specify-production-change-set.md) — Implement OpenRouter through the shared provider stack in four tested slices: preset/auth, trusted capability discovery, request/error semantics, and bilingual release documentation.

## Fog
