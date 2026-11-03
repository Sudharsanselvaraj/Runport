"""Server-Sent Events (SSE) telemetry stream."""

import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from runport.observability.events import EventTail, default_events_path

router = APIRouter(prefix="/events", tags=["events"])


async def sse_event_stream() -> AsyncGenerator[str, None]:
    """Streams live RequestEvents from the local JSONL append-only log."""
    path = default_events_path()
    tail = EventTail(path)

    # Initial ping
    yield 'data: {"type": "connected", "message": "Runport SSE stream connected"}\n\n'

    try:
        while True:
            events = tail.poll()
            if events:
                for ev in events:
                    yield f"data: {ev.to_json_line()}\n\n"
            else:
                # Keep-alive comment
                yield ": keepalive\n\n"
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass


@router.get("", response_class=StreamingResponse)
async def get_live_events() -> StreamingResponse:
    """Subscribes to live execution telemetry events via SSE."""
    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
