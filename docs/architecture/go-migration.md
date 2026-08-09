# Incremental Go migration

The repository remains Python-first. The first migration slice is the opt-in
`vulnclaw-edge` process in `cmd/vulnclaw-edge/`:

```text
browser ──> Go edge :7789 ── /api/* ──> Python web API :7788
                 │
                 └──────── static SPA files
```

Go owns delivery concerns that do not need Python state or the agent runtime:
static files, SPA fallback, and API forwarding. Python continues to own
authentication decisions, authorization, task execution, target state,
reports, provider credentials, and MCP lifecycle.

## Run locally

Build the frontend first, start the existing Python API on port `7788`, then:

```sh
go run ./cmd/vulnclaw-edge \
  -listen 127.0.0.1:7789 \
  -backend http://127.0.0.1:7788 \
  -static-dir frontend/dist
```

The edge is opt-in and does not replace `vulnclaw web` yet. The default bind is
loopback. Remote exposure requires `-allow-remote`, an explicit deployment
decision, and the Python API's existing authentication behavior.

## Security boundary

- Only `GET` and `HEAD` are served from the static directory.
- Static paths are symlink-resolved before they are served; paths outside the
  configured root fall back to `index.html` and cannot read files.
- The backend URL accepts only `http` or `https` and rejects embedded
  credentials, preventing accidental credential leakage through configuration.
- API requests retain `Authorization` and session-cookie headers. The Python
  middleware remains authoritative for authentication and authorization.
- The edge has bounded header, request, and idle timeouts. Write timeout is
  intentionally unset because task event streams are long-lived.

## Migration sequence

1. Validate the edge against the current Python API in development.
2. Add integration coverage for the proxy boundary and deployment health.
3. Move additional stateless web concerns behind this boundary.
4. Migrate stateful services only after their contracts and authorization tests
   have language-independent coverage.
