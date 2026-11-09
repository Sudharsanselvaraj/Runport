"""Client wrappers for standard LLM SDKs (OpenAI, Anthropic).

Automatically intercepts model invocations and generates canonical SpanKind.LLM spans
with prompt/completion tokens, latency, and sanitized outputs.

Usage:
    import openai
    from runport.instrumentation import wrap_openai

    client = wrap_openai(openai.OpenAI())
    # All client.chat.completions.create() calls are now automatically recorded as canonical spans!
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Dict, Optional

from runport.instrumentation.tracer import get_current_span, get_current_trace, start_span
from runport.providers.base import scrub_secrets
from runport.traces.domain import SpanKind, SpanStatus


def wrap_openai(client: Any) -> Any:
    """Instruments an OpenAI client instance to emit canonical SpanKind.LLM spans."""
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        return client

    original_create = client.chat.completions.create

    @functools.wraps(original_create)
    def wrapped_create(*args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown-model")
        messages = kwargs.get("messages", [])

        span_name = f"openai:chat:{model}"
        t0 = time.perf_counter()

        with start_span(
            name=span_name,
            kind=SpanKind.LLM,
            provider="openai",
            model=model,
            attributes={
                "model": model,
                "messages": scrub_secrets(messages),
                "temperature": kwargs.get("temperature"),
                "max_tokens": kwargs.get("max_tokens"),
            },
        ) as span:
            try:
                response = original_create(*args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                span.duration_ms = latency_ms

                # Extract token usage
                usage = getattr(response, "usage", None)
                if usage is not None:
                    span.prompt_tokens = getattr(usage, "prompt_tokens", None)
                    span.completion_tokens = getattr(usage, "completion_tokens", None)
                    span.total_tokens = getattr(usage, "total_tokens", None)

                # Extract output content
                choices = getattr(response, "choices", None)
                if choices and len(choices) > 0:
                    msg = getattr(choices[0], "message", None)
                    if msg:
                        content = getattr(msg, "content", None)
                        if content:
                            span.attributes["output"] = scrub_secrets(content)

                return response
            except Exception as e:
                span.status = SpanStatus.ERROR
                span.error = scrub_secrets(str(e))
                raise

    client.chat.completions.create = wrapped_create
    return client


def wrap_anthropic(client: Any) -> Any:
    """Instruments an Anthropic client instance to emit canonical SpanKind.LLM spans."""
    if not hasattr(client, "messages") or not hasattr(client.messages, "create"):
        return client

    original_create = client.messages.create

    @functools.wraps(original_create)
    def wrapped_create(*args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown-model")
        messages = kwargs.get("messages", [])
        system = kwargs.get("system", "")

        span_name = f"anthropic:messages:{model}"
        t0 = time.perf_counter()

        with start_span(
            name=span_name,
            kind=SpanKind.LLM,
            provider="anthropic",
            model=model,
            attributes={
                "model": model,
                "system": scrub_secrets(system),
                "messages": scrub_secrets(messages),
                "max_tokens": kwargs.get("max_tokens"),
            },
        ) as span:
            try:
                response = original_create(*args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                span.duration_ms = latency_ms

                # Extract token usage from Anthropic usage object
                usage = getattr(response, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "input_tokens", None)
                    output_tokens = getattr(usage, "output_tokens", None)
                    span.prompt_tokens = input_tokens
                    span.completion_tokens = output_tokens
                    if input_tokens is not None and output_tokens is not None:
                        span.total_tokens = input_tokens + output_tokens

                # Extract response text blocks
                content_blocks = getattr(response, "content", None)
                if content_blocks and isinstance(content_blocks, list):
                    texts = [getattr(b, "text", "") for b in content_blocks if hasattr(b, "text")]
                    if texts:
                        span.attributes["output"] = scrub_secrets(" ".join(texts))

                return response
            except Exception as e:
                span.status = SpanStatus.ERROR
                span.error = scrub_secrets(str(e))
                raise

    client.messages.create = wrapped_create
    return client
