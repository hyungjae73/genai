# Implementation Plan: testcontainers-migration

## Overview

Migrate backend test infrastructure from SQLite in-memory databases to testcontainers-python (PostgreSQL 15). This involves rewriting conftest.py, restoring JSONB types in models.py, creating an Alembic migration, unifying test files to use shared fixtures, updating CI workflow, and updating dependencies.

## Tasks

- [x] 1. Update dependencies and models
  - [x] 1.1 Add testcontainers[postgres] to requirements.txt
    - Add `testcontainers[postgres]>=4.0.0` to the Testing section of `genai/requirements.txt`
    - Verify `psycopg2-binary==2.9.9` is already present (no change needed)
    - _Requirements: 6.1, 6.3_

  - [x] 1.2 Restore JSONB types in models.py
    - In `genai/src/models.py`, change `MonitoringSite.pre_capture_script` from `JSON` to `JSONB`
    - Change `MonitoringSite.plugin_config` from `JSON` to `JSONB`
    - Change `VerificationResult.structured_data` from `JSON` to `JSONB`
    - Change `VerificationResult.structured_data_violations` from `JSON` to `JSONB`
    - All 4 fields must use `sqlalchemy.dialects.postgresql.JSONB` (already imported in models.py)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

  - [x] 1.3 Create Alembic migration for JSON→JSONB conversion
    - Create a new migration file in `genai/alembic/versions/` for converting the 4 fields from JSON to JSONB
    - Implement `upgrade()` with `op.alter_column()` using `postgresql.JSONB` as the new type
    - Implement `downgrade()` reversing JSONB back to JSON
    - _Requirements: 7.1, 7.3_

- [x] 2. Rewrite conftest.py with testcontainers fixtures
  - [x] 2.1 Implement Docker availability detection and PostgresContainer fixture
    - Rewrite `genai/tests/conftest.py` completely
    - Implement `_is_docker_available()` using `subprocess.run(["docker", "info"])` with 5s timeout
    - Create `requires_docker` skip marker
    - Create session-scoped `postgres_container` fixture using `PostgresContainer("postgres:15-alpine")`
    - Create session-scoped `engine` fixture from container connection URL
    - Create session-scoped `tables` fixture calling `Base.metadata.create_all()`
    - Keep existing Hypothesis profile configuration
    - Remove SQLite fallback logic, asyncpg references, and `event_loop` fixture
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.1, 9.2, 9.3_

  - [x] 2.2 Implement transaction rollback db_session and client fixtures
    - Create function-scoped `db_session` fixture with connection.begin() + transaction rollback pattern
    - Add SAVEPOINT support via `@event.listens_for(session, "after_transaction_end")` handler
    - Create function-scoped `client` fixture that overrides FastAPI `get_db` dependency with `db_session`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3_

  - [x] 2.3 Write property test: Transaction rollback data isolation (Property 1)
    - **Property 1: Transaction rollback data isolation**
    - Generate random model data, insert within transaction, rollback, verify data does not exist
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 2.4 Write property test: Nested transaction SAVEPOINT support (Property 2)
    - **Property 2: Nested transaction (SAVEPOINT) support**
    - Create nested transaction, commit inner, rollback outer, verify all data reverted
    - **Validates: Requirements 2.4**

- [x] 3. Checkpoint - Verify core fixtures work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Unify test files to use shared conftest fixtures
  - [x] 4.1 Migrate test_e2e.py to shared fixtures
    - Remove local `db_session` fixture with `create_engine("sqlite:///:memory:")`
    - Update test functions to use the shared `db_session` fixture from conftest.py
    - _Requirements: 4.4, 4.5_

  - [x] 4.2 Migrate test_audit.py to shared fixtures
    - Remove local `db_session` fixture with SQLite in-memory engine
    - Remove local `TestBase` if present; use shared `Base` from models
    - Update test functions to use shared `db_session` fixture
    - _Requirements: 4.4, 4.5_

  - [x] 4.3 Migrate test_extracted_data_api.py to shared fixtures
    - Remove local `_engine` with `create_engine("sqlite:///:memory:", ...)` and `StaticPool`
    - Remove local session/override setup; use shared `client` and `db_session` fixtures
    - _Requirements: 4.4, 4.5_

  - [x] 4.4 Migrate test_backend_integration.py to shared fixtures
    - Remove local `_engine` with `create_engine("sqlite:///:memory:", ...)` and `StaticPool`
    - Remove local session/override setup; use shared `client` and `db_session` fixtures
    - _Requirements: 4.4, 4.5_

  - [x] 4.5 Migrate test_visual_confirmation_api.py to shared fixtures
    - Remove local `_engine` with `create_engine("sqlite:///:memory:", ...)` and `StaticPool`
    - Remove local session/override setup; use shared `client` and `db_session` fixtures
    - _Requirements: 4.4, 4.5_

  - [x] 4.6 Migrate test_verification_model.py to shared fixtures
    - Remove local `engine` fixture with `create_engine("sqlite:///:memory:")` and JSONB→JSON compilation hack
    - Update to use shared `db_session` fixture (JSONB works natively on PostgreSQL)
    - _Requirements: 4.4, 4.5_

  - [x] 4.7 Migrate test_crawler.py and test_models_properties.py SQLite references
    - Remove `TEST_DATABASE_URL` SQLite fallback logic and `USE_SQLITE` references
    - Update to use shared PostgreSQL fixtures from conftest.py
    - _Requirements: 4.4, 4.5_

  - [x] 4.8 Migrate test_crawler_properties.py SQLite references
    - Remove `create_async_engine("sqlite+aiosqlite:///:memory:", ...)` usage
    - Update to use shared synchronous PostgreSQL fixtures
    - _Requirements: 4.4, 4.5_

- [x] 5. Checkpoint - Verify all test files migrated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update CI workflow
  - [x] 6.1 Remove PostgreSQL service from GitHub Actions
    - In `genai/.github/workflows/pr.yml`, remove the `postgres` service definition from `services` section (keep `redis`)
    - Remove `DATABASE_URL` environment variable from the pytest step
    - testcontainers will manage PostgreSQL container automatically
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 7. Property tests for PostgreSQL-specific behavior
  - [x] 7.1 Write property test: server_default correctness (Property 3)
    - **Property 3: server_default correctness**
    - Insert records without specifying server_default fields, verify PostgreSQL applies defaults correctly
    - **Validates: Requirements 10.3**

  - [x] 7.2 Write property test: Timestamp precision round-trip (Property 4)
    - **Property 4: Timestamp precision round-trip**
    - Generate random microsecond-precision datetimes, save to PostgreSQL, retrieve and verify precision preserved
    - **Validates: Requirements 10.4**

  - [x] 7.3 Write property test: JSONB data round-trip (Property 5)
    - **Property 5: JSONB data round-trip**
    - Generate random valid JSON structures (nested dicts, lists, strings, numbers, booleans, null), save to JSONB fields, retrieve and verify equivalence
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Verify all 446 backend tests pass on PostgreSQL
  - _Requirements: 10.1, 10.2, 8.1, 8.2, 8.3_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses Python throughout, so all implementation uses Python
- Test command: `cd genai && python -m pytest tests/ -v`
- Property tests go in `genai/tests/test_testcontainers_properties.py`
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
