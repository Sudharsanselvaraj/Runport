---
name: Connector Request
about: Propose support for a new LLM provider, workflow engine, or API protocol
title: "[CONNECTOR] "
labels: ["connector", "enhancement"]
assignees: []
---

**Target System or Service**
- Name: [e.g. LangGraph Studio, vLLM, Bedrock, Mistral API]
- Documentation URL: 
- Protocol: [REST / SSE streaming / WebSocket / gRPC / Python library]

**Capabilities Supported**
- [ ] Non-streaming completion
- [ ] Server-Sent Events (SSE) streaming
- [ ] Token usage telemetry (prompt / completion tokens)
- [ ] Native cost reporting
- [ ] Logprobs / Confidence scores
- [ ] Structured JSON output schema enforcement

**Authentication & Network Security**
How are credentials provided? (e.g. Header `Authorization: Bearer $ENV_VAR`, query parameter).
Does the target service support local offline emulation or mock servers?

**Reference Implementation or API Snippet**
Provide a curl command or minimal Python snippet demonstrating request and response payloads.
