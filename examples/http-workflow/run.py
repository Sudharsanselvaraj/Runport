#!/usr/bin/env python3
"""Offline HTTP workflow connector demonstration with local endpoint and schema extraction."""

import http.server
import json
import threading
from runport.connectors.http_workflow import HttpWorkflowConnector


class MockWorkflowServer(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "execution_id": "exec-9988",
            "status": "completed",
            "data": {
                "summary": f"HTTP processed: {body.get('text', '')}",
                "confidence": 0.98,
            },
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockWorkflowServer)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        connector = HttpWorkflowConnector(
            target_id="custom-http-workflow",
            name="Custom HTTP Service",
            url=f"http://127.0.0.1:{port}/analyze",
            payload_template={"text": "{query}"},
            output_path="data.summary",
            allow_localhost=True,
            timeout_seconds=5.0,
        )

        result = connector.execute({"query": "Check system logs"})
        print(f"Target ID: {result.target_id}")
        print(f"Status: {result.status.value}")
        print(f"Extracted Output: {result.output_text}")
        print(f"Latency: {result.latency_ms:.1f}ms")
        assert result.is_success
        print("\nHTTP workflow invocation completed successfully offline!")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
