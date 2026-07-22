"""Agent-facing traffic tools (in-process builtins).

``traffic_list`` / ``traffic_view`` / ``traffic_repeat`` / ``traffic_sitemap``
read and write the in-sandbox store directly — no MCP round-trip. They return
agent-readable strings (like ``python_execute``), with ``request_id`` surfaced
so the model can chain list → view → repeat and cite a capture in a finding.
"""

from __future__ import annotations

from typing import Any

from vulnclaw.i18n import _
from vulnclaw.traffic.replay import ReplayError, replay_request
from vulnclaw.traffic.store import TrafficStore

TRAFFIC_TOOL_NAMES = frozenset(
    {"traffic_list", "traffic_view", "traffic_repeat", "traffic_sitemap"}
)

_MAX_BLOB_CHARS = 4000


def traffic_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "traffic_list",
                "description": _("traffic.schema.list.desc"),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": _("traffic.schema.list.method"),
                        },
                        "host": {
                            "type": "string",
                            "description": _("traffic.schema.list.host"),
                        },
                        "status": {
                            "type": "integer",
                            "description": _("traffic.schema.list.status"),
                        },
                        "source": {
                            "type": "string",
                            "description": _("traffic.schema.list.source"),
                        },
                        "limit": {
                            "type": "integer",
                            "description": _("traffic.schema.list.limit"),
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "traffic_view",
                "description": _("traffic.schema.view.desc"),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": _("traffic.schema.view.request_id"),
                        }
                    },
                    "required": ["request_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "traffic_repeat",
                "description": _("traffic.schema.repeat.desc"),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": _("traffic.schema.repeat.request_id"),
                        },
                        "method": {
                            "type": "string",
                            "description": _("traffic.schema.repeat.method"),
                        },
                        "url": {
                            "type": "string",
                            "description": _("traffic.schema.repeat.url"),
                        },
                        "headers": {
                            "type": "object",
                            "description": _("traffic.schema.repeat.headers"),
                        },
                        "body": {
                            "type": "string",
                            "description": _("traffic.schema.repeat.body"),
                        },
                    },
                    "required": ["request_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "traffic_sitemap",
                "description": _("traffic.schema.sitemap.desc"),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def traffic_list(
    store: TrafficStore,
    *,
    method: str | None = None,
    host: str | None = None,
    status: int | None = None,
    source: str | None = None,
    limit: int = 50,
) -> str:
    rows = store.entries()
    if method:
        rows = [r for r in rows if str(r.get("method", "")).upper() == method.upper()]
    if host:
        rows = [r for r in rows if host.lower() in str(r.get("host", "")).lower()]
    if status is not None:
        rows = [r for r in rows if int(r.get("status", 0)) == int(status)]
    if source:
        rows = [r for r in rows if str(r.get("source", "")) == source]

    total = len(rows)
    if limit and limit > 0:
        rows = rows[-limit:]
    if not rows:
        return _("traffic.list.empty")

    lines = [_("traffic.list.header", total=total, shown=len(rows))]
    for r in rows:
        lines.append(
            f"  {r.get('request_id')}  {r.get('method')} {r.get('url')} "
            f"-> {r.get('status')} [{r.get('source')}] {r.get('content_length')}B"
        )
    return "\n".join(lines)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_BLOB_CHARS:
        return text
    return text[:_MAX_BLOB_CHARS] + f"\n... [truncated {len(text) - _MAX_BLOB_CHARS} chars]"


def traffic_view(store: TrafficStore, request_id: str) -> str:
    view = store.view(request_id)
    if view is None:
        return _("traffic.view.not_found", request_id=request_id)
    parts = [
        f"[traffic] {request_id}  {view.get('method')} {view.get('url')} "
        f"-> {view.get('status')} [{view.get('source')}]",
        "── Request ──",
        _truncate(view.get("request_text", "")) or _("traffic.view.empty_body"),
    ]
    if view.get("response_text"):
        parts += ["── Response ──", _truncate(view["response_text"])]
    return "\n".join(parts)


def traffic_repeat(
    store: TrafficStore,
    request_id: str,
    overrides: dict[str, Any] | None = None,
    *,
    transport: Any | None = None,
) -> str:
    try:
        record = replay_request(store, request_id, overrides, transport=transport)
    except ReplayError as exc:
        return _("traffic.repeat.failed", error=exc)
    except Exception as exc:  # network / transport errors
        return _("traffic.repeat.error", error=exc)
    return _(
        "traffic.repeat.ok",
        request_id=request_id,
        new_id=record.request_id,
        method=record.method,
        url=record.url,
        status=record.status,
    )


def traffic_sitemap(store: TrafficStore) -> str:
    sitemap = store.sitemap()
    if not sitemap:
        return _("traffic.sitemap.empty")
    lines = [_("traffic.sitemap.header")]
    for host, paths in sitemap.items():
        lines.append(f"  {host}")
        for leaf in paths:
            methods = ",".join(leaf["methods"])
            lines.append(f"    [{methods}] {leaf['path']} (x{leaf['count']})")
    return "\n".join(lines)


def dispatch_traffic_tool(
    store: TrafficStore,
    tool_name: str,
    args: dict[str, Any],
    *,
    transport: Any | None = None,
) -> str:
    """Route a traffic tool call to its handler and return an agent string."""
    if tool_name == "traffic_list":
        status = args.get("status")
        return traffic_list(
            store,
            method=args.get("method"),
            host=args.get("host"),
            status=int(status) if status not in (None, "") else None,
            source=args.get("source"),
            limit=int(args.get("limit", 50) or 50),
        )
    if tool_name == "traffic_view":
        return traffic_view(store, str(args.get("request_id", "")))
    if tool_name == "traffic_repeat":
        overrides: dict[str, Any] = {}
        for key in ("method", "url", "headers", "body"):
            if key in args and args[key] is not None:
                overrides[key] = args[key]
        result = traffic_repeat(
            store,
            str(args.get("request_id", "")),
            overrides,
            transport=transport,
        )
        refs = getattr(transport, "evidence_refs", [])
        if refs:
            result += "\n" + "\n".join(f"[evidence] {ref.path}" for ref in refs)
        return result
    if tool_name == "traffic_sitemap":
        return traffic_sitemap(store)
    return _("traffic.unknown_tool", name=tool_name)
