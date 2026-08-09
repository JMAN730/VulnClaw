---
name: hackerone
description: HackerOne bounty program scope-guard workflow — reads program scope, enforces scope and program rules, then hands each in-scope asset to pentest-flow
requires_target: false
---

# HackerOne Bounty Scope-Guard Skill

You are executing a HackerOne bug bounty workflow. This Skill is a
**scope-guard wrapper**: first parse and enforce the program scope and program
rules, then hand each **in-scope asset** to `pentest-flow` for the actual
security testing. **Never touch an out-of-scope asset at any stage.**

The launch argument is a HackerOne program link (`<SCOPE LINK>`), for example
`hackerone.com/<handle>` or `.../policy_scopes`. This Skill has no preset scan
target (`requires_target: false` in frontmatter); targets are discovered from
the program scope.

## Phase 1: Read scope

1. **Fetch the link first**
   - Use the fetch tool to access the supplied `<SCOPE LINK>`.
   - HackerOne is a JavaScript SPA: fetching `hackerone.com/*` usually returns
     only an **empty app shell**, without rendered scope rows. Scope data is
     loaded from `hackerone.com/graphql` or the authenticated
     `api.hackerone.com` API, so a naive fetch may not retrieve it.
   - **Detect an empty shell**: if the response contains no recognizable scope
     table or asset list and only includes a skeleton such as `<div id="app">`,
     treat the fetch as unsuccessful.

2. **Fallback: ask the user to paste the scope**
   - An empty fetch, login wall, or JavaScript-only response is normal rather
     than exceptional.
   - Ask the user to paste the in-scope and out-of-scope tables directly from
     the program page's **Scope** tab. Provide this example format:

     ```
     In scope:
     https://api.example.com        | URL       | Eligible for bounty
     *.example.com                  | WILDCARD  | Eligible for bounty
     app.example.com                | URL       | In scope, NOT bounty-eligible
     com.example.android            | GOOGLE_PLAY_APP_ID | Eligible for bounty

     Out of scope:
     blog.example.com               | URL
     *.corp.example.com             | WILDCARD
     ```

3. **Parse leniently**
   - Extract two lists from the pasted or fetched result: **in-scope** and
     **out-of-scope**.
   - Recognize asset types by human label or API enum:
     `URL`, `WILDCARD` (`*.x.com`), `CIDR`/IP, `SOURCE_CODE`,
     `GOOGLE_PLAY_APP_ID`/`APPLE_STORE_APP_ID`/`TESTFLIGHT`/`OTHER_APK`/`OTHER_IPA`,
     `HARDWARE`, `AI_MODEL`, `SMART_CONTRACT`, `OTHER`, and similar values.
   - Recognize **three eligibility states**. Submission eligibility and bounty
     eligibility are independent booleans:
     - `submission=true, bounty=true` → in scope, testable, bounty eligible.
     - `submission=true, bounty=false` → **in scope, testable, not bounty eligible**.
       Do not confuse this with out of scope.
     - `submission=false` → **out of scope; never test it**.
   - If parsing is uncertain, ask the user to confirm. **Never default an
     uncertain asset to in-scope.**

4. **Output the boundary**
   - List the in-scope assets with their type and eligibility.
   - Output an out-of-scope **deny-list** for enforcement throughout the run.

## Phase 2: Enforce boundaries

Before any testing begins, state and follow these **hard rules** throughout:

1. **Scope boundary**
   - Test only assets in the in-scope list.
   - Never touch an asset on the out-of-scope deny-list: do not fetch it, scan
     it, or send any payload to it.
   - `pentest-flow` may directly handle only `URL` and `WILDCARD` assets. Other
     types (mobile apps, source code, CIDR, hardware, and so on) are not
     automated; ask the user to confirm how they should be handled.

2. **Program rules** (in addition to VulnClaw's existing `BLOCKED_PATTERNS` and
   `RESERVED_IP_RANGES`)
   - **No DoS or availability impact**: prohibit stress tests, resource
     exhaustion, and high-volume concurrency.
   - **Respect rate and automation limits**: operate slowly and serially, and
     follow any program rule that prohibits automated scanning.
   - **No social engineering**: do not target or phish people.
   - **Minimal impact and no PII exfiltration**: stop once a vulnerability is
     verified; do not export real user data or perform destructive actions.

3. **Handle exceptions safely**
   - If any step could cross the scope boundary or violate a program rule,
     stop and ask the user.

## Phase 3: Enumerate and confirm

1. List every parsed in-scope asset with its number, type, and eligibility.
2. Ask which asset to start with, or whether to process all of them.
3. **Handle one asset at a time** and confirm each one separately. Avoid
   concurrency that could cross the scope boundary or trigger rate limits.

## Phase 4: Delegate to pentest-flow

For the user's selected **single in-scope asset**:

1. Pass the asset as the target to `pentest-flow` and run the full
   recon → vulnerability-discovery → exploitation workflow.
2. Stay within scope throughout. Exclude and report any newly discovered
   subdomain or endpoint that is outside the in-scope definition, especially
   one that does not match an in-scope `WILDCARD`.
3. Continue to enforce all Phase 2 program rules.

## Phase 5: Report in HackerOne format

For every confirmed finding, produce a report in **HackerOne submission format**:

1. **Title** — concise description of the vulnerability, including its type and
   affected asset.
2. **Asset** — the affected in-scope asset (URL or identifier).
3. **Severity (CVSS)** — CVSS vector and score (Critical/High/Medium/Low).
4. **Steps to Reproduce** — reproducible steps, including requests, responses,
   and payloads.
5. **Impact** — exploitability and business impact.
6. **Remediation** — recommended fix.

When there are multiple findings, keep each one in a separate section. Include
a parameterized Python PoC using `requests` when useful.
Remind the user that reports are for **manual submission** on HackerOne; this
Skill never submits reports automatically.

## References

- `references/hackerone-report-and-scope.md` — scope parsing reference (asset
  type ↔ API enum, three-state eligibility, pasted table shapes), mandatory
  program rules, and the HackerOne report template.
