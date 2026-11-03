#!/usr/bin/env python3
"""Offline Dify workflow connector demonstration using a local mock HTTP server."""

import http.server
import json
import threading
from runport.connectors.dify import DifyConnector


class MockDifyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer app-"):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "Unauthorized"}')
            return

        length = int(self.headers.get("Content-Length", 0))
        req_data = json.loads(self.rfile.read(length).decode("utf-8"))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "workflow_run_id": "run-mock-12345",
            "data": {
                "id": "wf-exec-001",
                "status": "succeeded",
                "outputs": {"result": f"Mock processed: {req_data.get('inputs', {}).get('query', 'done')}"},
                "total_tokens": 42,
            },
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress console log


def main():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockDifyHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        connector = DifyConnector(
            target_id="dify-mock-workflow",
            name="Mock Dify Workflow",
            api_key="app-synthetic-dify-secret-key-123",
            base_url=f"http://127.0.0.1:{port}",
            app_type="workflow",
            response_mode="blocking",
            allow_localhost=True,
            timeout_seconds=5.0,
        )

        result = connector.execute({"query": "Synthesize revenue report"})
        print(f"Target ID: {result.target_id}")
        print(f"Status: {result.status.value}")
        print(f"Output: {result.output_text}")
        print(f"Latency: {result.latency_ms:.1f}ms")
        assert result.is_success
        print("\nDify workflow invocation succeeded offline!")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
