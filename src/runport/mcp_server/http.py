"""Runport Streamable HTTP (SSE) Transport for Model Context Protocol (MCP).

Specification: docs/GLOBAL_PRODUCT_READINESS_AUDIT.md Milestone 4 (Task 4.1 & 4.2).
Complies with MCP Streamable HTTP Specification:
- GET /sse: Initiates persistent Server-Sent Events stream, emits endpoint URI with session ID.
- POST /messages?sessionId=<id>: Ingests JSON-RPC 2.0 messages and routes to RunportMcpServer.
- Bearer token authentication via Authorization header.
- Strict invariant: prevent agents from approving their own spend (no self-approval tools).
"""

import asyncio
import hmac
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from runport.mcp_server.server import RunportMcpServer

logger = logging.getLogger(__name__)


class McpSessionManager:
    """Manages active SSE client sessions and message dispatch."""

    def __init__(self) -> None:
        self._sessions: Dict[str, asyncio.Queue[str]] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        async with self._lock:
            self._sessions[session_id] = asyncio.Queue()
        return session_id

    async def get_queue(self, session_id: str) -> Optional[asyncio.Queue[str]]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def send_event(self, session_id: str, event_type: str, data: str) -> bool:
        queue = await self.get_queue(session_id)
        if queue is not None:
            formatted = f"event: {event_type}\ndata: {data}\n\n"
            await queue.put(formatted)
            return True
        return False


def create_mcp_router(
    server: Optional[RunportMcpServer] = None,
    auth_token: Optional[str] = None,
    path_prefix: str = "",
) -> APIRouter:
    """Creates FastAPI APIRouter implementing the Streamable HTTP MCP transport."""
    router = APIRouter(tags=["mcp"])
    mcp_server = server or RunportMcpServer()
    session_mgr = McpSessionManager()

    def verify_auth(
        request: Request,
        authorization: Optional[str] = Header(None),
    ) -> None:
        # 1. Credential already verified by outer middleware
        if getattr(request.state, "api_credential", None) is not None:
            return

        expected = auth_token or os.environ.get("RUNPORT_API_TOKEN")
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        elif request.headers.get("X-Runport-Token"):
            token = request.headers.get("X-Runport-Token", "").strip()

        if token:
            if expected and hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
                request.state.api_credential = {"is_master": True, "project_id": None}
                return
            try:
                from runport.api.v1.auth import verify_api_credential
                from runport.api.v1.errors import UnauthorizedError

                cred = verify_api_credential(token)
                request.state.api_credential = cred
                return
            except UnauthorizedError:
                raise HTTPException(
                    status_code=401,
                    detail={"error": {"code": "unauthorized", "message": "Invalid Bearer token for MCP transport."}},
                )

        # 2. No token provided
        client_host = request.client.host if request.client else ""
        if client_host and client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "forbidden", "message": "Remote access requires valid API credentials."}},
            )

        if expected:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "unauthorized", "message": "Missing or invalid Bearer token for MCP transport."}},
            )

        # Local unauthenticated default to master context
        request.state.api_credential = {"is_master": True, "project_id": None}

    @router.get("/sse")
    async def sse_endpoint(
        request: Request,
        _auth: None = Depends(verify_auth),
    ) -> StreamingResponse:
        """Establishes persistent SSE stream and transmits session endpoint URL."""
        session_id = await session_mgr.create_session()
        base_messages_path = f"{path_prefix}/messages" if path_prefix else "/messages"
        endpoint_url = f"{base_messages_path}?sessionId={session_id}"

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                # 1. Emit initial endpoint event with messages path
                yield f"event: endpoint\ndata: {endpoint_url}\n\n"

                queue = await session_mgr.get_queue(session_id)
                if not queue:
                    return

                # 2. Stream server events or send keep-alive pings
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield message
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                await session_mgr.close_session(session_id)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/messages")
    async def messages_endpoint(
        request: Request,
        sessionId: Optional[str] = Query(None),
        _auth: None = Depends(verify_auth),
    ) -> Response:
        """Receives JSON-RPC 2.0 messages from the client and returns or streams responses."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_request", "message": "Invalid JSON body"}},
            )

        if not isinstance(body, dict):
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_request", "message": "JSON-RPC request must be an object"}},
            )

        # Execute JSON-RPC message against RunportMcpServer with authenticated caller context
        auth = getattr(request.state, "api_credential", None)
        response_dict = mcp_server.handle(body, auth=auth)

        # If a session is open and active, also mirror response as SSE message
        if sessionId and response_dict is not None:
            await session_mgr.send_event(sessionId, "message", json.dumps(response_dict))

        if response_dict is None:
            # Notification (no id in request)
            return Response(status_code=202)

        return JSONResponse(content=response_dict, status_code=200)

    return router
