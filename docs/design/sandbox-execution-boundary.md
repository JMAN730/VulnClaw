# Sandboxed execution boundary — design

Design for issue #38 (PRD: per-run Docker sandbox, `/workspace` ingress, sandbox
evidence bundles). Provenance: Wayfinder "Strix-Inspired VulnClaw Roadmap" (#18),
sandboxed execution boundary (#23). Persistence foundation (#35) has landed, so this
work is unblocked — it writes into the run directory that `run_context.py` already
provides.

## 1. Goal and scope

Give Tier A active tools a disposable, isolated execution boundary. By default they run
inside a **per-run Docker container** that is destroyed at run end; sandboxed commands
cannot write to the host target (though the target may be read-only mounted, and evidence
is written to the host). Target material enters at `/workspace`. Every sandboxed command
leaves an **evidence bundle** under `evidence/sandbox/` that findings can reference by
`EvidenceRef{kind: "sandbox_output", path: ...}`.

`--trusted-local` preserves today's host execution. The boundary is **opt-out, not
opt-in**.

**In scope:** the boundary abstraction; routing `python_execute`, PoC execution
(`verifier.py`), and the other Tier A subprocess/active-HTTP tools through it; copy and
read-only-mount ingress; the evidence-bundle writer; a VulnClaw-maintained sandbox
Dockerfile; Docker-absent fail-loud.

**Out of scope (map Fog / other PRDs):** writable-mount / autofix; Tier B MCP-in-sandbox
sidecars; the traffic/browser capture that runs *inside* the container (separate traffic
PRD — this PRD only provides the container it runs in); run-directory / `evidence/` tree
creation (owned by #35, already done).

## 2. Current state (seams this plugs into)

Four host call sites execute code or fire active network traffic today:

| Seam | Location | Mechanism |
|------|----------|-----------|
| `execute_python` | `vulnclaw/agent/builtin_tools.py:1157` | tempfile + `subprocess.run([sys.executable, tmp], cwd=tempdir, env=…)` in an executor |
| `execute_nmap` | `builtin_tools.py:877` | `subprocess.run(cmd)` against the host `nmap` binary |
| active-HTTP tools | `execute_brute_force` (`:1311` httpx), `traffic_repeat` (`:191`), recon tools (`:239`) | real network requests from the host |
| PoC execution | `vulnclaw/report/verifier.py:461` | tempfile + `subprocess.run([sys.executable, tmp])`, output kept in-memory only |

Supporting facts:

- **Run directory / evidence tree** — `RunContext` (`run_context.py:39`) creates and
  reserves `evidence/` (`_create_run_layout` `:465`, validated at `:218`). It exposes
  `state_dir` / `state_path` / `snapshot_path` / `target_json_path` / `append_event` and
  the atomic writers `atomic_write_json` / `atomic_write_text` — **but no evidence-path
  accessor**. Tool code reaches the tree today via `session.evidence_dir` / `session.run_dir`
  (see `builtin_tools.resolve_traffic_store` `:118`). The traffic store already assumes the
  `<run>/evidence/` layout (`traffic/paths.py:3`).
- **Target model** — `Target` (`vulnclaw/targets.py:27`) already carries
  `ingress_mode: Literal["copy","mount"]` (`:35`). It is persisted and round-tripped but
  **has no behavioral consumer** — the mount decision lands here.
- **EvidenceRef** — `domain_models.py:56` defines `EvidenceKind` with `"sandbox_output"`
  already reserved ("refs land under `evidence/sandbox/`"). `EvidenceRef` (`:59`) has
  `kind` / `path` (relative to `evidence/`) / `request_id`. Findings hold
  `evidence_refs: list[EvidenceRef]` (`:99`); the verifier currently stamps only the
  legacy free-text `evidence` string (`verifier.py:680`) and emits no ref.
- **Config** — execution knobs live on `SafetyConfig` (`config/schema.py:230`), e.g.
  `python_execute_mode` (`:241`). CLI flags thread Typer option →
  `_run_context_kwargs` (`cli/main.py:852`) → `run_agent_task` → `build_targets`,
  exactly as `--mount` does today (`:1015`).
- **Docker** — repo-level `Dockerfile` / `docker-compose.yml` exist for *running
  VulnClaw itself*. There is **no programmatic Docker** in the Python package; forward
  comments already name this boundary (`traffic/mitm_addon.py:3`).

## 3. The boundary abstraction

Introduce `vulnclaw/sandbox/`. The core is a small interface so call sites depend on the
boundary, not on Docker:

```python
# vulnclaw/sandbox/boundary.py
class ExecResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str
    bundle_ref: EvidenceRef | None   # None in trusted-local

class ExecutionBoundary(Protocol):
    def run(self, argv: list[str], *, stdin_file: Path | None,
            workspace: Path | None, timeout: int, label: str) -> ExecResult: ...
    def close(self) -> None: ...       # tears the boundary down
```

Two implementations:

- **`DockerBoundary`** — default. Owns one container for the whole run (per-run, not
  per-command; see §4). `run()` executes `argv` inside it, captures streams, writes an
  evidence bundle, returns an `ExecResult` with a `bundle_ref`.
- **`LocalBoundary`** — `--trusted-local`. Runs `subprocess.run` on the host exactly as
  today, `bundle_ref=None`. This is the current behavior refactored behind the interface,
  so existing `verifier.py` / `test_trusted_local_allows_basic_code` semantics are
  preserved.

The boundary is created once per run, carried on the session (alongside `run_dir` /
`evidence_dir`, the seam tool code already reads), and `close()`d in `run_agent_task`'s
teardown unconditionally — on success, interruption, exceptions, and cancellation — via
a cancellation-safe cleanup mechanism (e.g. `try/finally` or equivalent). If container
removal fails, the failure is logged best-effort; it does not change run status or trigger
additional retry/cleanup handlers. This mirrors the checkpoint/summary funnel #35 added.

### Call-site changes

Each of the four seams stops calling `subprocess.run` / host httpx directly and calls
`boundary.run(...)` instead. Concretely:

- `execute_python`: build the tempfile as now, then copy or mount it into
  `/workspace/.tmp/x.py` in the container and invoke the image-owned Python interpreter
  (not host `sys.executable`):
  `boundary.run(["/usr/bin/python3", "/workspace/.tmp/x.py"], workspace=…, timeout=…, label="python_execute")`.
  Mode gating (`_resolve_python_execute_mode`, blocklists) is unchanged — it runs
  *before* dispatch and is orthogonal to where the code executes.
- `verifier.VerifierExecutor.execute_poc`: same shape (generate tempfile, copy/mount to
  `/workspace/.tmp/x.py`, invoke image-owned interpreter); additionally stamp an
  `EvidenceRef(kind="sandbox_output", path=bundle_ref.path)` onto the finding's
  `evidence_refs` (closing the `:680` gap).
- `execute_nmap` / active-HTTP tools: route the subprocess/request through the container.
  (Active HTTP inside the container is what gives network egress a chokepoint later; for
  this PRD it is enough that they run in-sandbox and leave a bundle.)

## 4. Sandbox lifecycle

**Per-run container, not per-command.** Container startup dominates latency; a pentest
issues many Tier A calls. Create one container when the run's first Tier A tool fires
(lazy) or at run start (eager) — lazy chosen, so passive-only runs never pay for Docker.

`/workspace` ingress is isolated per `local_repo` target, since `ingress_mode` is
target-specific. The container boundary is either scoped per-target (one container per
local_repo target), or `/workspace` is cleared/namespaced before switching targets,
ensuring copy-mode files cannot leak across targets and mount-based targets remain safe.

```text
run start ──▶ (first Tier A tool) ──▶ DockerBoundary.ensure_container()
                                          docker run -d --name vulnclaw-<run_id>
                                          --network <policy> --workspace ingress (§5)
   … many boundary.run() calls, each: docker exec + bundle write …
run end / interrupt ──▶ boundary.close() ──▶ docker rm -f  (idempotent)
```

Naming: `vulnclaw-sandbox-<run_id>` so an orphan from a hard crash is greppable and
cleanable. `close()` is idempotent and best-effort loud (logs if `docker rm` fails).

**Docker client.** Prefer the `docker` SDK if present; else shell out to the `docker`
CLI via `subprocess`. Keep it behind `sandbox/docker_client.py` so the boundary code
does not care which. No new hard dependency on `docker-py` if the CLI path is acceptable
— decide in review (open question §9).

**Docker-absent → fail loud.** If Docker is unreachable and the boundary is active
(not `--trusted-local`), abort with a clear diagnostic ("Docker required for the sandbox
execution boundary; re-run with --trusted-local to execute on the host"). **Never**
silently fall back to host execution — that would defeat the boundary. Docker-requiring
tests gate behind an availability probe.

## 5. Ingress — `/workspace`

Target material is placed at `/workspace` inside the container, driven by
`Target.ingress_mode` (already on the model, `targets.py:35`):

- **`copy` (default)** — copy the target tree into the container's `/workspace`
  (`docker cp` or a build-time `COPY` into a per-run layer). Container writes stay
  in-container and die with it; the host source is untouched.
- **`mount` (`--mount`, for large repos)** — bind-mount the target **read-only** at
  `/workspace` (`-v host:/workspace:ro`). A write attempt inside `/workspace` must fail.
  Chosen for monorepos to avoid copy cost.

Writable mounts / autofix are out of scope (needs a future `--autofix`). The
scratch area for tool tempfiles (e.g. the `python_execute` script) is a separate
writable in-container path (`/workspace/.tmp` on copy; a container-local `tmpfs` on
mount, since `/workspace` is RO).

Only `local_repo` targets have material to ingress; `web_url` / `domain` / `ip` targets
run tools that reach out over the network and need no `/workspace` population.

## 6. Evidence bundles

Each `boundary.run()` writes a bundle under `evidence/sandbox/<bundle_id>/`:

```text
evidence/sandbox/<bundle_id>/
  meta.json     # label, argv, workspace ingress mode, exit code, started/ended, timeout hit?
  stdout.txt
  stderr.txt
  artifacts/    # files the command produced under a designated out dir, copied out
```

**Evidence controls:**
- **Redaction**: `stdout.txt`, `stderr.txt`, and copied artifacts are written as-is;
  credential scrubbing or other redaction is out of scope for this PRD.
- **Access controls**: Evidence bundles inherit the run directory's filesystem permissions;
  no additional access control layer is introduced.
- **Size limits**: Per-stream (`stdout.txt`, `stderr.txt`) and per-artifact file writes are
  capped at a configurable limit (default 10 MB per file); exceeding files are truncated
  and truncation is noted in `meta.json`.
- **Retention**: Evidence bundles under `evidence/sandbox/<bundle_id>` persist for the
  lifetime of the run directory; cleanup follows the run directory retention policy (out
  of scope for this PRD, owned by persistence foundation #35).

- `<bundle_id>` = `<label>-<NNNN>` (monotonic per run) so bundles sort by call order and
  never collide. Allocation is atomic across concurrent Tier A calls via a run-level lock
  or atomic counter, preventing duplicate IDs and directory overwrites while preserving
  deterministic ordering. No timestamps in the id (deterministic; `run_context` forbids
  wall-clock in ids, matching #35 style).
- Written with the existing atomic writers (`atomic_write_json` / `atomic_write_text`)
  via a new `RunContext.evidence_dir(*subdirs)` accessor — the one missing helper (§2).
  `evidence_dir("sandbox", bundle_id)` returns the path and `mkdir -p`s it.
- The bundle `path` on `EvidenceRef` is **relative to `evidence/`**
  (`evidence/sandbox/<bundle_id>` → ref `path="sandbox/<bundle_id>"`), matching the
  `EvidenceRef.path` contract (`domain_models.py:69`).

## 7. Configuration & flags

New knobs on `SafetyConfig` (mirroring `python_execute_mode`):

```python
sandbox_mode: str = Field(default="docker",
    description="Execution boundary for Tier A tools: docker | trusted-local")
sandbox_image: str = Field(default="vulnclaw/sandbox@sha256:<digest>",
    description="Image for the per-run sandbox container")
sandbox_network: str = Field(default="none",
    description="Container network policy: none | bridge | host. Default 'none' (fail-closed); "
                "bridge enables HTTP/nmap with enforcement of private/loopback/metadata "
                "(169.254.169.254) blocks, DNS restrictions, and IPv6 policy; host grants "
                "full network access (unsafe, requires explicit opt-in)")
```

CLI: add `--trusted-local` (Typer flag, default off) threaded like `--mount`
(Typer option → `_run_context_kwargs` → `run_agent_task`). `--trusted-local` sets
`sandbox_mode="trusted-local"` for the run. `--mount` continues to set
`Target.ingress_mode="mount"`; the sandbox is its first real consumer.

Precedence: explicit `--trusted-local` > config `sandbox_mode`. Docker-absent with an
active boundary is an error, never an implicit downgrade.

## 8. Testing strategy

Drive the execution seam, assert observable outcomes (PRD testing decisions). Gate
Docker-requiring tests behind an availability probe.

- **Lifecycle** — run a Tier A tool with the boundary active → container created, command
  runs, container `rm`'d at run end; host filesystem untouched (assert no tempfile leaks
  on host, container gone).
- **Ingress** — `copy` places target at `/workspace`; `--mount` bind-mounts read-only
  (a write inside `/workspace` fails).
- **Evidence bundle** — a sandboxed command yields `evidence/sandbox/<id>/` with
  `meta.json` (argv/stdout/stderr/exit), and the path resolves as an `EvidenceRef`
  stamped on the finding.
- **`--trusted-local`** — no container created; `execute_python` /
  `VerifierExecutor.execute_poc` run on host; existing `test_verifier.py` and
  `test_trusted_local_allows_basic_code` still pass unchanged.
- **Docker-absent** — active boundary + no Docker → nonzero, clear diagnostic, **no**
  host fallback.

Unit-test the boundary via a `FakeBoundary` for call-site wiring (that `execute_python` /
`execute_poc` call `boundary.run` with the right argv and stamp the ref) so most tests
need no real Docker; keep a thin Docker-gated integration test for the real container.

Out of test scope: real exploit payloads against live targets.

## 9. Open questions (resolve in review)

1. **Docker access** — `docker-py` dependency vs shelling out to the `docker` CLI?
   CLI avoids a new dep and matches how the repo Dockerfile world already works; SDK is
   cleaner for stream capture. Lean CLI.
2. **Network policy** — default container network for active-HTTP tools: host-net,
   bridge, or none-by-default-with-opt-in? Affects whether `nmap` / recon reach targets
   out of the box. Needs a security call; default should not be silently permissive.
3. **Lazy vs eager container** — lazy (first Tier A tool) proposed; confirm no ordering
   assumption in the orchestrator breaks from deferring creation.
4. **Interpreter parity** — `python_execute` uses `sys.executable` on host; in-container
   the generated tempfile must be copied or mounted into `/workspace/.tmp/x.py` and the
   image-owned Python interpreter (e.g. `/usr/bin/python3`) must be invoked, not host
   `sys.executable`. Pin the image Python to the supported matrix so PoC behavior matches
   host runs. (See §3 call-site contracts for full ingress and interpreter selection.)
5. **Bundle artifact capture** — which in-container dir is the "artifacts" out-dir, and
   how large before we truncate/skip? Define a cap and log truncation (no silent drop).

## 10. Phasing

1. **Boundary skeleton** — `sandbox/` package, `ExecutionBoundary` protocol,
   `LocalBoundary` (pure refactor of today's host path), `RunContext.evidence_dir()`
   accessor, `EvidenceRef` stamping on findings. No Docker yet; behavior identical to
   today. Fully unit-testable.
2. **DockerBoundary + lifecycle** — container create/exec/teardown, Docker-absent
   fail-loud, config knobs, `--trusted-local` flag. Docker-gated integration test.
3. **Ingress** — copy + read-only mount off `Target.ingress_mode`; RO-write-fails test.
4. **Evidence bundles** — full bundle writer + artifact capture; wire `verifier.py` PoC
   output into bundles (closes the in-memory-only gap).
5. **Reconcile remaining Tier A tools** — route `nmap` / active-HTTP / recon through the
   boundary once network policy (§9.2) is decided.

The VulnClaw-maintained sandbox `Dockerfile` (no Strix runtime vendoring) is authored in
phase 2; the image is pinned to an immutable digest (see §7 `sandbox_image` default) once
stable.
