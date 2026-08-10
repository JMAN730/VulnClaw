# VulnClaw

VulnClaw coordinates authorized security testing through an LLM-backed agent. This glossary distinguishes the model-access concepts that shape configuration and runtime behavior.

## Language

**LLM Provider Preset**:
A named, selectable configuration bundle for accessing an LLM API, including its endpoint identity and default model. A preset may represent either a model vendor or a model gateway.
_Avoid_: Provider, integration

**Model Gateway**:
An LLM API service that routes requests to models served by one or more upstream model providers. OpenRouter is a model gateway exposed to VulnClaw through an LLM Provider Preset.
_Avoid_: Model provider

**Upstream Model Provider**:
The vendor or operator that serves a model reached through a Model Gateway.
_Avoid_: Provider

**Model ID**:
The opaque identifier selected through an LLM Provider Preset to address a model or gateway-defined route.
_Avoid_: Model name
