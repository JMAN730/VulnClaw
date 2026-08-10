---
name: vulnclaw-setup
description: >-
  Guide and run VulnClaw first-run setup (LLM, Chrome remote debugging +
  chrome-devtools MCP for Cloudflare-bypass recon, optional Burp MCP). Use when
  the user says setup VulnClaw, first-run wizard, /wizard, enable chrome-devtools,
  or Cloudflare 403s with fetch.
---

# VulnClaw first-run setup

## Prefer in-app `/wizard`

```text
vulnclaw Ready> /wizard
```

Native Python first-run wizard (LLM, Chrome/devtools MCP, optional Burp). Optional bash twin: `bash scripts/vulnclaw-setup-wizard.sh`.
