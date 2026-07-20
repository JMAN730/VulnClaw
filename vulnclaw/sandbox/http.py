"""httpx transports that execute the network hop inside a boundary."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx

from .boundary import ExecutionBoundary

_HTTP_RUNNER = r'''
import base64, json, ssl, sys, urllib.error, urllib.request
payload = json.loads(sys.stdin.read())
body = base64.b64decode(payload["body"]) if payload.get("has_body") else None
request = urllib.request.Request(
    payload["url"], data=body, headers=dict(payload.get("headers") or []), method=payload["method"]
)
context = None if payload.get("verify", True) else ssl._create_unverified_context()
try:
    response = urllib.request.urlopen(request, timeout=payload["timeout"], context=context)
except urllib.error.HTTPError as exc:
    response = exc
except Exception as exc:
    print(json.dumps({"error": str(exc)}), file=sys.stderr)
    raise SystemExit(2)
with response:
    result = {
        "status": response.status,
        "headers": list(response.headers.items()),
        "body": base64.b64encode(response.read()).decode("ascii"),
        "reason": getattr(response, "reason", "") or "",
        "url": response.geturl(),
    }
print(json.dumps(result))
'''.strip()


class _BoundaryHTTPMixin:
    def __init__(
        self, boundary: ExecutionBoundary, *, verify: bool = True, timeout: float = 30.0
    ) -> None:
        self._boundary = boundary
        self._verify = verify
        self._timeout = timeout
        self.evidence_refs = []

    def _send(self, request: httpx.Request, content: bytes) -> httpx.Response:
        payload = {
            "method": request.method,
            "url": str(request.url),
            "headers": list(request.headers.multi_items()),
            "body": base64.b64encode(content).decode("ascii"),
            "has_body": bool(content),
            "verify": self._verify,
            "timeout": self._timeout,
        }
        result = self._boundary.run(
            [self._boundary.python_executable, "-c", _HTTP_RUNNER],
            timeout=max(1, int(self._timeout) + 5),
            label=f"http_{request.method.lower()}",
            stdin_text=json.dumps(payload),
        )
        if result.bundle_ref is not None:
            self.evidence_refs.append(result.bundle_ref)
        if result.timed_out:
            raise httpx.ReadTimeout("Sandboxed HTTP request timed out", request=request)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown transport error"
            raise httpx.ConnectError(
                f"Sandboxed HTTP request failed: {detail[:1000]}", request=request
            )
        try:
            response_data: dict[str, Any] = json.loads(result.stdout.strip())
            body = base64.b64decode(str(response_data.get("body", "")))
            headers = [(str(k), str(v)) for k, v in response_data.get("headers", [])]
            return httpx.Response(
                int(response_data["status"]),
                headers=headers,
                content=body,
                request=request,
                extensions={
                    "reason_phrase": str(response_data.get("reason", "")).encode(
                        "ascii", "replace"
                    )
                },
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise httpx.ProtocolError(
                "Sandboxed HTTP helper returned an invalid response", request=request
            ) from exc


class BoundaryHTTPTransport(_BoundaryHTTPMixin, httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self._send(request, request.read())


class AsyncBoundaryHTTPTransport(_BoundaryHTTPMixin, httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        content = await request.aread()
        return await asyncio.to_thread(self._send, request, content)


__all__ = ["AsyncBoundaryHTTPTransport", "BoundaryHTTPTransport"]
