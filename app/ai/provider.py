"""Single choke point for every LLM call: key check, circuit breaker, timeout, one retry on
429/5xx/network errors, and usage logging. Raises AiUnavailableError on any failure so callers degrade gracefully."""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from ..config import settings
from ..db import db

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-4o-mini"}


class AiUnavailableError(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def model_name() -> str:
    return settings.ai_model or DEFAULT_MODELS.get(settings.ai_provider, DEFAULT_MODELS["anthropic"])


def _api_key() -> str:
    return settings.openai_key if settings.ai_provider == "openai" else settings.anthropic_key


def ai_configured() -> bool:
    return bool(_api_key())


# ---- Circuit breaker: after N consecutive failures stop calling the API for a cooldown ----
class _Breaker:
    failures = 0
    open_until = 0.0


def breaker_open() -> bool:
    return time.monotonic() < _Breaker.open_until


def reset_breaker() -> None:
    _Breaker.failures, _Breaker.open_until = 0, 0.0


def _record_failure() -> None:
    _Breaker.failures += 1
    if _Breaker.failures >= settings.breaker_threshold:
        _Breaker.open_until = time.monotonic() + settings.breaker_cooldown_s


class HttpStatusError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


async def post_json(url: str, headers: dict, body: dict) -> dict:
    """The only place that touches the network (tests replace this function)."""
    async with httpx.AsyncClient(timeout=settings.ai_timeout_s) as client:
        res = await client.post(url, headers=headers, json=body)
    try:
        data = res.json()
    except ValueError:
        data = {}
    if res.status_code >= 400:
        msg = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None
        raise HttpStatusError(res.status_code, msg or f"HTTP {res.status_code}")
    return data


async def _call_anthropic(system, user, max_tokens, temperature) -> Completion:
    data = await post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": _api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {"model": model_name(), "max_tokens": max_tokens, "temperature": temperature, "system": system,
         "messages": [{"role": "user", "content": user}]},
    )
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage", {})
    return Completion(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0))


async def _call_openai(system, user, max_tokens, temperature) -> Completion:
    data = await post_json(
        "https://api.openai.com/v1/chat/completions",
        {"authorization": f"Bearer {_api_key()}", "content-type": "application/json"},
        {"model": model_name(), "max_tokens": max_tokens, "temperature": temperature,
         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
    )
    usage = data.get("usage", {})
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return Completion(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


def _log_call(ticket_id, kind, in_tok, out_tok, latency_ms, ok, error):
    db.run(
        "INSERT INTO ai_calls (ticket_id, kind, model, input_tokens, output_tokens, latency_ms, ok, error, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (ticket_id, kind, model_name(), in_tok, out_tok, latency_ms, int(ok), (error or "")[:300] or None,
         datetime.now(timezone.utc).isoformat()),
    )


async def complete(*, kind: str, system: str, user: str, ticket_id: int | None = None,
                   max_tokens: int = 300, temperature: float = 0) -> Completion:
    if not ai_configured():
        raise AiUnavailableError("AI API key not configured")
    if breaker_open():
        raise AiUnavailableError("AI circuit breaker open (recent repeated failures)")

    call = _call_openai if settings.ai_provider == "openai" else _call_anthropic
    started = time.monotonic()
    last: Exception | None = None

    for attempt in range(2):
        try:
            out = await call(system, user, max_tokens, temperature)
            _Breaker.failures, _Breaker.open_until = 0, 0.0
            _log_call(ticket_id, kind, out.input_tokens, out.output_tokens, int((time.monotonic() - started) * 1000), True, None)
            return out
        except Exception as e:  # noqa: BLE001 - classify below
            last = e
            status = getattr(e, "status", None)
            retryable = status is None or status == 429 or status >= 500  # timeouts/network/429/5xx
            if not retryable:
                break  # 4xx (bad key, bad request): retrying will not help
            if attempt == 0:
                await asyncio.sleep(0.7)

    _record_failure()
    message = "AI request timed out" if isinstance(last, httpx.TimeoutException) else (str(last) or "AI request failed")
    _log_call(ticket_id, kind, 0, 0, int((time.monotonic() - started) * 1000), False, message)
    raise AiUnavailableError(message)
