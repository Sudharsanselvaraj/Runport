# Novatech Systems Synthetic Knowledge Base

This is a synthetic, offline knowledge base for benchmarking RAG pipelines in Runport. All organizations, metrics, parameters, and specifications are invented fixtures.

---

<!-- RECORD: KB-REC-001 -->
## KB-REC-001: NovaCompute Auto-Scaling and Memory Constraints
- **Product**: NovaCompute Serverless Container Engine
- **Memory Ceiling**: Each container instance supports a minimum of 256 MB up to a maximum of 64 GB RAM.
- **Scaling Threshold**: Auto-scaling triggers when average CPU utilization across active nodes exceeds 75% for 60 consecutive seconds.
- **Cold Start SLA**: Standard container warm-up latency is guaranteed under 450 ms in primary regions.
- **Reference**: Novatech Infrastructure Engineering Manual 2026, Section 3.1.

---

<!-- RECORD: KB-REC-002 -->
## KB-REC-002: NovaDB Replication Latency and Consistency Models
- **Product**: NovaDB Global Document Store
- **Replication SLA**: Cross-region replication latency is guaranteed under 120 ms under nominal network conditions.
- **Consistency Modes**: Supports Strong Consistency within a single availability zone and Bounded Staleness across global regions.
- **Default TTL**: Unindexed temporary documents are automatically purged after 30 days unless pinned.
- **Reference**: NovaDB Distributed Storage Specification 2026, Section 7.4.

---

<!-- RECORD: KB-REC-003 -->
## KB-REC-003: NovaAuth OAuth 2.0 PKCE and Token Lifespans
- **Product**: NovaAuth Identity Broker
- **Protocol**: Mandates OAuth 2.0 with Proof Key for Code Exchange (PKCE) for all public client single-page and mobile applications.
- **Access Token Lifespan**: Standard JWT access tokens expire after 15 minutes (900 seconds).
- **Refresh Token Rotation**: Refresh tokens have a maximum idle lifetime of 14 days and rotate upon each exchange.
- **Reference**: NovaAuth Security and Integration Standard 2026, Section 2.8.

---

<!-- RECORD: KB-REC-004 -->
## KB-REC-004: NovaQueue Dead-Letter Queue Policy
- **Product**: NovaQueue Distributed Event Stream
- **Dead-Letter Threshold**: Messages failing consumption 5 consecutive times are moved to the designated Dead-Letter Queue (DLQ).
- **Retention**: DLQ messages are retained for 14 days before automatic archiving.
- **Reference**: NovaQueue Operations Guide 2026, Section 4.2.

---

<!-- RECORD: KB-REC-005 -->
## KB-REC-005: NovaGateway Rate Limiting and SSL Policies
- **Product**: NovaGateway Edge Router
- **Rate Limit**: Default tier enforces 10,000 requests per minute per authenticated API key.
- **TLS Version**: Exclusively supports TLS 1.3 with forward secrecy ciphers.
- **Reference**: NovaGateway Edge Networking Reference 2026, Section 1.5.

