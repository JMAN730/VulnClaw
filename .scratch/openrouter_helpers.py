OPENROUTER_MAX_TRANSIENT_ATTEMPTS = 4
OPENROUTER_MAX_RETRY_DELAY_SECONDS = 60.0
OPENROUTER_BASE_RETRY_DELAY_SECONDS = 1.0
OPENROUTER_MAX_DIAGNOSTIC_TEXT = 512
_SAFE_ERROR_IDENTIFIER = re.compile(r"[^A-Za-z0-9._:/-]+")
_MISSING = object()


class OpenRouterResponseError(RuntimeError):
    """Sanitized OpenRouter HTTP or in-band response failure."""

    def __init__(
        self,
        *,
        status_code: int | None = None,
        error_type: str = "",
        request_id: str = "",
        retry_after: float | None = None,
        partial_text: str = "",
        kind: str = "response",
    ) -> None:
        self.status_code = status_code
        self.error_type = _sanitize_error_identifier(error_type, 64)
        self.request_id = _sanitize_error_identifier(request_id, 128)
        self.retry_after = retry_after
        self.partial_text = partial_text[:OPENROUTER_MAX_DIAGNOSTIC_TEXT]
        self.kind = kind
        super().__init__(self._safe_message())

    def _safe_message(self) -> str:
        if self.status_code == 401:
            message = "OpenRouter authentication failed; check the configured inference key."
        elif self.status_code == 402:
            message = "OpenRouter credits or the inference-key spending limit are exhausted."
        elif self.status_code == 429:
            message = "OpenRouter rate limited the account."
        elif self.status_code == 503:
            message = "OpenRouter has no eligible upstream endpoint available."
        elif self.kind == "transport":
            message = "OpenRouter could not complete the network request."
        else:
            message = "OpenRouter returned an unsuccessful generation response."

        context = []
        if self.status_code is not None:
            context.append(f"HTTP {self.status_code}")
        if self.error_type:
            context.append(f"type={self.error_type}")
        if self.request_id:
            context.append(f"request_id={self.request_id}")
        return f"{message} ({'; '.join(context)})" if context else message


def _sanitize_error_identifier(value: Any, max_length: int) -> str:
    if not isinstance(value, (str, int)):
        return ""
    normalized = _SAFE_ERROR_IDENTIFIER.sub("_", str(value).strip())
    return normalized[:max_length]


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _provider_name(agent: Any) -> str:
    config = getattr(agent, "config", None)
    llm = getattr(config, "llm", None)
    return str(getattr(llm, "provider", "") or "").strip().lower()


def _status_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    try:
        value = headers.get(name)
        if value is None:
            value = headers.get(name.lower())
        return str(value or "")
    except (AttributeError, TypeError):
        return ""


def _parse_retry_after(
    value: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    """Parse a bounded Retry-After delta or HTTP date."""
    if not value or not value.strip():
        return None
    normalized = value.strip()
    try:
        seconds = float(normalized)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(normalized)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        seconds = (retry_at - current).total_seconds()
    if seconds < 0:
        return None
    return min(seconds, OPENROUTER_MAX_RETRY_DELAY_SECONDS)


def _response_error_payload(response: Any) -> Any:
    top_level_error = _field(response, "error", _MISSING)
    if top_level_error is not _MISSING and top_level_error is not None:
        return top_level_error or {"type": "generation_error"}

    for choice in _field(response, "choices", None) or []:
        choice_error = _field(choice, "error", _MISSING)
        if choice_error is not _MISSING and choice_error is not None:
            return choice_error or {"type": "generation_error"}
        message_error = _field(
            _field(choice, "message"),
            "error",
            _MISSING,
        )
        if message_error is not _MISSING and message_error is not None:
            return message_error or {"type": "generation_error"}
        if str(_field(choice, "finish_reason", "") or "").lower() == "error":
            return {"type": "generation_error"}
    return None


def _openrouter_error_from_payload(
    payload: Any,
    *,
    response: Any = None,
    partial_text: str = "",
) -> OpenRouterResponseError:
    metadata = _field(payload, "metadata", {}) or {}
    headers = _field(response, "headers", {}) or {}
    status = _status_code(_field(payload, "code"))
    error_type = _field(metadata, "error_type") or _field(payload, "type") or ""
    request_id = (
        _field(metadata, "request_id")
        or _field(payload, "request_id")
        or _header(headers, "x-request-id")
    )
    return OpenRouterResponseError(
        status_code=status,
        error_type=error_type,
        request_id=request_id,
        retry_after=_parse_retry_after(_header(headers, "retry-after")),
        partial_text=partial_text,
    )


def _validate_provider_response(
    agent: Any,
    response: Any,
    *,
    partial_text: str = "",
    require_choices: bool = True,
) -> None:
    """Reject OpenRouter in-band errors before callers accept any output."""
    if _provider_name(agent) != "openrouter":
        return
    payload = _response_error_payload(response)
    if payload is not None:
        raise _openrouter_error_from_payload(
            payload,
            response=response,
            partial_text=partial_text,
        )
    if require_choices and not (_field(response, "choices", None) or []):
        raise OpenRouterResponseError(
            error_type="malformed_response",
            partial_text=partial_text,
        )


def _normalise_openrouter_exception(exc: Exception) -> OpenRouterResponseError:
    if isinstance(exc, OpenRouterResponseError):
        return exc

    response = getattr(exc, "response", None)
    status = _status_code(getattr(exc, "status_code", None))
    if status is None:
        status = _status_code(_field(response, "status_code"))
    headers = _field(response, "headers", {}) or {}
    body = getattr(exc, "body", None)
    payload = _field(body, "error", body) if body else {}
    metadata = _field(payload, "metadata", {}) or {}
    return OpenRouterResponseError(
        status_code=status,
        error_type=_field(metadata, "error_type") or _field(payload, "type") or "",
        request_id=(
            _field(metadata, "request_id")
            or _field(payload, "request_id")
            or _header(headers, "x-request-id")
        ),
        retry_after=_parse_retry_after(_header(headers, "retry-after")),
        kind="http" if status is not None else "transport",
    )


async def _call_openrouter_with_bounded_retries(
    agent: Any,
    request_fn: Any,
    stage_label: str,
    *,
    validate_response: bool = True,
) -> tuple[Any, int]:
    loop = asyncio.get_running_loop()
    retry_attempts = 0
    transient_attempts = 0
    pool_size = len(getattr(agent, "_key_pool", None) or [])
    can_rotate = pool_size > 1 and callable(getattr(agent, "rotate_api_key", None))
    remaining_key_rotations = max(pool_size - 1, 0)

    while True:
        try:
            maybe_response = loop.run_in_executor(None, request_fn)
            response = (
                await maybe_response
                if inspect.isawaitable(maybe_response)
                else maybe_response
            )
            if validate_response:
                _validate_provider_response(agent, response)
            return response, retry_attempts
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            error = _normalise_openrouter_exception(exc)

        if error.status_code == 401:
            if (
                can_rotate
                and remaining_key_rotations > 0
                and agent.rotate_api_key()
            ):
                remaining_key_rotations -= 1
                retry_attempts += 1
                continue
            raise error

        if error.status_code == 402:
            raise error

        is_transient = error.status_code in {429, 503} or error.kind == "transport"
        if not is_transient:
            raise error

        transient_attempts += 1
        if transient_attempts >= OPENROUTER_MAX_TRANSIENT_ATTEMPTS:
            raise error
        retry_attempts += 1
        delay = error.retry_after
        if delay is None:
            delay = min(
                OPENROUTER_BASE_RETRY_DELAY_SECONDS
                * (2 ** (transient_attempts - 1)),
                OPENROUTER_MAX_RETRY_DELAY_SECONDS,
            )
        print(
            f"[!] {stage_label} OpenRouter transient failure; "
            f"retry {retry_attempts}/{OPENROUTER_MAX_TRANSIENT_ATTEMPTS - 1} "
            f"in {delay:g}s.",
            file=sys.stdout,
            flush=True,
        )
        await asyncio.sleep(delay)


async def _create_stream_with_retries(
    agent: Any,
    kwargs: dict[str, Any],
    stage_label: str,
) -> Any:
    """Create a stream, applying OpenRouter retries only before consumption."""

    def request_fn() -> Any:
        return agent._get_client().chat.completions.create(
            **kwargs,
            stream=True,
        )
    if _provider_name(agent) == "openrouter":
        response, _ = await _call_openrouter_with_bounded_retries(
            agent,
            request_fn,
            stage_label,
            validate_response=False,
        )
        return response
    return request_fn()

