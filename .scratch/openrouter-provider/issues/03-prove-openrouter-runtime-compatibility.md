# Prove OpenRouter runtime compatibility

Type: prototype
Status: resolved
Blocked by: 02

## Question

Can VulnClaw's existing OpenAI SDK path satisfy the chosen OpenRouter preset contract for model discovery, ordinary completions, streaming, tool calls, key failover, and representative error handling without provider-specific runtime branching? Build the smallest disposable test harness or spike that answers this, using mocked protocol fixtures by default and no committed real credentials, then link the prototype and observed compatibility gaps in the resolution.

## Answer

See [OpenRouter runtime compatibility prototype](../assets/openrouter-runtime-prototype.md).
The existing transport supports static authentication, ordinary Chat
Completions, streaming text, streamed tool assembly, and tool-result follow-up,
but the chosen contract requires bounded provider-aware changes for
`require_parameters`, `/models/user` capability discovery, in-band error
normalization, and OpenRouter retry semantics.
