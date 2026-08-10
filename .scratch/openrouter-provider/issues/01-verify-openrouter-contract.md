# Verify OpenRouter's compatibility and security contract

Type: research
Status: resolved

## Question

Using current official OpenRouter documentation and primary sources, what exact contract must VulnClaw support for authentication, the canonical API base URL, Chat Completions, streaming, tool calls, model listing, error and rate-limit behavior, and optional or recommended attribution headers? Which documented privacy, data-routing, logging, or credential-handling facts must affect implementation or user-facing documentation, and where does OpenRouter differ from VulnClaw's current generic OpenAI-compatible path?

Record the sourced findings in `.scratch/openrouter-provider/assets/openrouter-contract.md`.

## Answer

See [OpenRouter compatibility and security contract](../assets/openrouter-contract.md).
The existing OpenAI SDK path is wire-compatible, but safe preset parity also
requires capability-aware model discovery, explicit handling of in-band errors,
and disclosure of OpenRouter's upstream routing and privacy defaults.
