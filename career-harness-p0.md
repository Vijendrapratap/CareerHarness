# CareerHarness P0 Foundation Plan

## Goal
Build the production-grade P0 foundation for CareerHarness: multi-tenant architecture with PostgreSQL RLS, BYOK Key Vault with envelope encryption, Redis Streams event outbox, the thin in-house agent harness core, and the P0 test contract suite (KY-01..05, IT-02, ST-03/04).

## Tasks
- [x] Task 1: Initialize Python project layout (`pyproject.toml`, directory hierarchy for `app/api`, `app/core`, `app/domain`, `app/harness`, `app/agents`, `app/workers`, `app/tests`) → Verify: `python3 -m pytest --version` and directory tree verification.
- [x] Task 2: Implement BYOK Key Vault with envelope encryption, DEK derivation, masking, and memory-only decryption (`app/core/keyvault.py`) → Verify: Tests for `KY-01` (ciphertext-at-rest), `KY-02` (masked output), and `KY-05` (key purge).
- [x] Task 3: Implement multi-tenant data models and PostgreSQL RLS session manager (`app/core/database.py`, `app/domain/models.py`) → Verify: Tests for `IT-02` proving Tenant A cannot access Tenant B records.
- [x] Task 4: Implement transactional outbox event publisher and Redis Streams dispatcher (`app/core/outbox.py`) → Verify: Tests for `ST-03` proving reliable event emission within DB transactions.
- [x] Task 5: Implement BYOK Model Router with tier mapping, key validation probe, and 402/429 error pause handlers (`app/core/model_router.py`) → Verify: Tests for `KY-03` (zero-downtime rotation) and `KY-04` (402 injection pauses runs without fallback).
- [x] Task 6: Implement Harness Tool Registry and tenant-budgeted Memory Tools (`app/harness/registry.py`, `app/domain/memory.py`) → Verify: Unit tests verifying tool execution permissions and fail-closed tenant scoping.
- [x] Task 7: Implement Harness Loop and HITL Approval Gate middleware (`app/harness/loop.py`, `app/harness/gate.py`) → Verify: Tests proving external tools convert actions into `awaiting_approval` and park the Run.
- [x] Task 8: Implement PostgreSQL Checkpointer and crash-resume engine (`app/harness/checkpointer.py`) → Verify: Unit test verifying state restoration and idempotency after simulated crash.
- [x] Task 9: Implement FastAPI service layer (`app/api/`) and worker task lanes (`app/workers/`) with lane priority routing (`ST-04`) → Verify: FastAPI test client passes `/health` and key vault endpoints; Celery routing config verified.
- [x] Task 10: Run full P0 Consolidated Test Suite (`KY-01..05`, `IT-02`, `ST-03/04`) → Verify: `pytest app/tests/` passes with all tests green.

## Done When
- [x] All 10 tasks completed and checked.
- [x] P0 test suites (`KY-01..05`, `IT-02`, `ST-03/04`) pass in CI/pytest.
- [x] Zero plaintext API keys in database, logs, or responses.
- [x] Full directory structure conforms to the Solution Architecture Document.

## Notes
- Envelope encryption uses AES-256-GCM with a pluggable `KeyVaultKMSProvider`.
- RLS uses Postgres `SET LOCAL app.current_tenant_id` per connection/transaction.
- Celery worker lanes: `fast` (webhooks, probes), `agent_loop` (harness iterations), `batch` (bulk actions).
