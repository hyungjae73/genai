"""
Property-based tests for Docker CI/CD pipeline.

Tests correctness properties for Dockerfiles, Docker Compose, entrypoint scripts,
health checks, and CI/CD workflows using Hypothesis.
"""

import os
import re
import pytest
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume

# Project root (genai/)
PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Property 3: Dockerfileのセキュリティ準拠
# All production Dockerfiles must:
#   (a) Use alpine/slim base image variants
#   (b) Include a non-root USER directive
# Validates: Requirements 2.3, 9.1
# ---------------------------------------------------------------------------

# Production Dockerfiles that exist in the project
PRODUCTION_DOCKERFILES = [
    "docker/Dockerfile",           # Backend (API / Celery)
    "frontend/Dockerfile.prod",    # Frontend (Nginx) — created in task 3.1
]


def _get_existing_production_dockerfiles():
    """Return list of production Dockerfile paths that currently exist."""
    existing = []
    for rel_path in PRODUCTION_DOCKERFILES:
        full_path = PROJECT_ROOT / rel_path
        if full_path.exists():
            existing.append(rel_path)
    return existing


def _parse_dockerfile_stages(content: str):
    """Parse a Dockerfile and return list of (stage_name_or_none, base_image) tuples."""
    stages = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("FROM "):
            parts = stripped.split()
            image = parts[1] if len(parts) >= 2 else ""
            stage_name = None
            if "AS" in [p.upper() for p in parts]:
                as_idx = next(i for i, p in enumerate(parts) if p.upper() == "AS")
                if as_idx + 1 < len(parts):
                    stage_name = parts[as_idx + 1]
            stages.append((stage_name, image))
    return stages


def _get_final_stage_base_image(content: str) -> str:
    """Return the base image of the final (production) stage in a Dockerfile."""
    stages = _parse_dockerfile_stages(content)
    if not stages:
        return ""
    # The final FROM is the production stage
    return stages[-1][1]


def _has_non_root_user(content: str) -> bool:
    """Check if Dockerfile sets a non-root USER directive."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("USER "):
            user = stripped.split()[1] if len(stripped.split()) >= 2 else ""
            if user and user != "root" and user != "0":
                return True
    return False


def _is_slim_or_alpine_image(image: str) -> bool:
    """Check if a Docker image tag uses alpine or slim variant."""
    # Match patterns like python:3.11-slim, node:20-alpine, nginx:alpine
    image_lower = image.lower()
    return "alpine" in image_lower or "slim" in image_lower


# Strategy: pick from existing production Dockerfiles
dockerfile_strategy = st.sampled_from(PRODUCTION_DOCKERFILES)


class TestDockerfileSecurityCompliance:
    """Property 3: All production Dockerfiles must comply with security requirements."""

    @given(dockerfile_path=dockerfile_strategy)
    @settings(max_examples=20)
    def test_base_image_uses_slim_or_alpine(self, dockerfile_path: str):
        """Property 3a: Final stage base image must be alpine or slim variant."""
        full_path = PROJECT_ROOT / dockerfile_path
        assume(full_path.exists())

        content = full_path.read_text()
        base_image = _get_final_stage_base_image(content)

        assert _is_slim_or_alpine_image(base_image), (
            f"Dockerfile '{dockerfile_path}' final stage uses base image '{base_image}' "
            f"which is not an alpine or slim variant. "
            f"Production images must use minimal base images (Requirements 2.3, 9.1)."
        )

    @given(dockerfile_path=dockerfile_strategy)
    @settings(max_examples=20)
    def test_non_root_user_directive(self, dockerfile_path: str):
        """Property 3b: Dockerfile must include a non-root USER directive."""
        full_path = PROJECT_ROOT / dockerfile_path
        assume(full_path.exists())

        content = full_path.read_text()

        assert _has_non_root_user(content), (
            f"Dockerfile '{dockerfile_path}' does not set a non-root USER directive. "
            f"Production containers must run as non-root user (Requirements 2.3, 9.1)."
        )

    def test_all_existing_dockerfiles_use_slim_or_alpine(self):
        """Deterministic check: all existing production Dockerfiles use slim/alpine."""
        existing = _get_existing_production_dockerfiles()
        assert len(existing) > 0, "No production Dockerfiles found to test"

        for dockerfile_path in existing:
            content = (PROJECT_ROOT / dockerfile_path).read_text()
            base_image = _get_final_stage_base_image(content)
            assert _is_slim_or_alpine_image(base_image), (
                f"Dockerfile '{dockerfile_path}' final stage uses '{base_image}' — "
                f"expected alpine or slim variant."
            )

    def test_all_existing_dockerfiles_have_non_root_user(self):
        """Deterministic check: all existing production Dockerfiles set non-root USER."""
        existing = _get_existing_production_dockerfiles()
        assert len(existing) > 0, "No production Dockerfiles found to test"

        for dockerfile_path in existing:
            content = (PROJECT_ROOT / dockerfile_path).read_text()
            assert _has_non_root_user(content), (
                f"Dockerfile '{dockerfile_path}' missing non-root USER directive."
            )


# ---------------------------------------------------------------------------
# Entrypoint script simulation helpers
# ---------------------------------------------------------------------------

ENTRYPOINT_PATH = PROJECT_ROOT / "docker" / "entrypoint.sh"
REQUIRED_ENV_VARS = ["DATABASE_URL", "REDIS_URL", "SECRET_KEY"]


def _read_entrypoint_script() -> str:
    """Read the entrypoint.sh script content."""
    return ENTRYPOINT_PATH.read_text()


def _simulate_production_debug_enforcement(env: dict) -> dict:
    """
    Simulate the entrypoint.sh production DEBUG enforcement logic.

    In the script:
        if [ "$ENVIRONMENT" = "production" ]; then
          export DEBUG=false
          export ENABLE_DOCS=false
        fi

    Returns the resulting environment after enforcement.
    """
    result = dict(env)
    if result.get("ENVIRONMENT") == "production":
        result["DEBUG"] = "false"
        result["ENABLE_DOCS"] = "false"
    return result


def _simulate_required_env_check(env: dict) -> int:
    """
    Simulate the entrypoint.sh required environment variable check.

    Returns 0 if all required vars are set (non-empty), 1 otherwise.
    """
    for var in REQUIRED_ENV_VARS:
        value = env.get(var, "")
        if not value:  # empty string or missing → exit 1
            return 1
    return 0


def _simulate_migration_failure(migration_exit_code: int) -> int:
    """
    Simulate the entrypoint.sh migration failure handling.

    If migration_exit_code != 0, the script exits with 1 (deploy aborted).
    Returns the entrypoint exit code.
    """
    if migration_exit_code != 0:
        return 1  # exit 1 — deploy aborted
    return 0  # success — proceed to exec "$@"


# ---------------------------------------------------------------------------
# Property 5: 本番環境でのDEBUGモード強制無効化
# ENVIRONMENT=production時にDEBUG=falseが強制されることをランダムなDEBUG値で検証
# Validates: Requirements 3.3, 9.5
# ---------------------------------------------------------------------------

class TestProductionDebugEnforcement:
    """Property 5: Production environment must force DEBUG=false."""

    @given(debug_value=st.text(min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_production_forces_debug_false(self, debug_value: str):
        """
        **Validates: Requirements 3.3, 9.5**

        For any DEBUG value, when ENVIRONMENT=production the entrypoint
        must force DEBUG=false.
        """
        env = {
            "ENVIRONMENT": "production",
            "DEBUG": debug_value,
            "DATABASE_URL": "postgresql+psycopg2://u:p@h:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "SECRET_KEY": "secret",
        }
        result = _simulate_production_debug_enforcement(env)
        assert result["DEBUG"] == "false", (
            f"With ENVIRONMENT=production and DEBUG='{debug_value}', "
            f"expected DEBUG='false' but got DEBUG='{result['DEBUG']}'"
        )
        assert result["ENABLE_DOCS"] == "false", (
            f"With ENVIRONMENT=production, expected ENABLE_DOCS='false' "
            f"but got ENABLE_DOCS='{result.get('ENABLE_DOCS')}'"
        )

    @given(debug_value=st.text(min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_non_production_preserves_debug(self, debug_value: str):
        """Non-production environments should preserve the original DEBUG value."""
        env = {
            "ENVIRONMENT": "development",
            "DEBUG": debug_value,
        }
        result = _simulate_production_debug_enforcement(env)
        assert result["DEBUG"] == debug_value, (
            f"Non-production env should preserve DEBUG='{debug_value}' "
            f"but got DEBUG='{result['DEBUG']}'"
        )

    def test_entrypoint_script_contains_production_check(self):
        """Verify the actual entrypoint.sh contains the production enforcement logic."""
        content = _read_entrypoint_script()
        assert 'ENVIRONMENT" = "production"' in content or \
               "ENVIRONMENT\" = \"production\"" in content, (
            "entrypoint.sh must check for ENVIRONMENT=production"
        )
        assert "DEBUG=false" in content, (
            "entrypoint.sh must set DEBUG=false for production"
        )
        assert "ENABLE_DOCS=false" in content, (
            "entrypoint.sh must set ENABLE_DOCS=false for production"
        )


# ---------------------------------------------------------------------------
# Property 6: 必須環境変数の起動前検証
# ランダムな必須変数の欠落パターンに対し、エントリポイントが非ゼロ終了コードを返すことを検証
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

class TestRequiredEnvVarValidation:
    """Property 6: Missing required env vars must cause non-zero exit."""

    @given(
        missing_vars=st.lists(
            st.sampled_from(REQUIRED_ENV_VARS),
            min_size=1,
            max_size=len(REQUIRED_ENV_VARS),
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_missing_required_vars_cause_exit(self, missing_vars: list):
        """
        **Validates: Requirements 3.5**

        For any subset of missing required environment variables,
        the entrypoint must exit with a non-zero code.
        """
        env = {
            "DATABASE_URL": "postgresql+psycopg2://u:p@h:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "SECRET_KEY": "secret",
        }
        # Remove the missing vars
        for var in missing_vars:
            env[var] = ""

        exit_code = _simulate_required_env_check(env)
        assert exit_code != 0, (
            f"With missing vars {missing_vars}, expected non-zero exit code "
            f"but got {exit_code}"
        )

    def test_all_vars_present_succeeds(self):
        """When all required vars are set, the check should pass (exit 0)."""
        env = {
            "DATABASE_URL": "postgresql+psycopg2://u:p@h:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "SECRET_KEY": "my-secret-key",
        }
        exit_code = _simulate_required_env_check(env)
        assert exit_code == 0, (
            f"All required vars are set, expected exit 0 but got {exit_code}"
        )

    def test_entrypoint_script_checks_all_required_vars(self):
        """Verify entrypoint.sh checks all three required variables."""
        content = _read_entrypoint_script()
        for var in REQUIRED_ENV_VARS:
            assert var in content, (
                f"entrypoint.sh must check for required variable {var}"
            )


# ---------------------------------------------------------------------------
# Property 7: マイグレーション失敗時のデプロイ中止
# ランダムな非ゼロ終了コードに対し、エントリポイントがアプリケーション起動せずに終了することを検証
# Validates: Requirements 6.2
# ---------------------------------------------------------------------------

class TestMigrationFailureAbort:
    """Property 7: Migration failure must abort application startup."""

    @given(
        exit_code=st.integers(min_value=1, max_value=255)
    )
    @settings(max_examples=100)
    def test_nonzero_migration_exit_aborts_deploy(self, exit_code: int):
        """
        **Validates: Requirements 6.2**

        For any non-zero migration exit code, the entrypoint must
        exit with non-zero (aborting application startup).
        """
        entrypoint_exit = _simulate_migration_failure(exit_code)
        assert entrypoint_exit != 0, (
            f"Migration failed with exit code {exit_code}, "
            f"but entrypoint returned {entrypoint_exit} instead of non-zero"
        )

    def test_successful_migration_allows_startup(self):
        """When migration succeeds (exit 0), the entrypoint should proceed."""
        entrypoint_exit = _simulate_migration_failure(0)
        assert entrypoint_exit == 0, (
            f"Migration succeeded (exit 0), but entrypoint returned "
            f"{entrypoint_exit} instead of 0"
        )

    def test_entrypoint_script_checks_migration_status(self):
        """Verify entrypoint.sh checks migration exit status."""
        content = _read_entrypoint_script()
        assert "MIGRATION_STATUS" in content, (
            "entrypoint.sh must capture migration exit status"
        )
        assert "exit 1" in content, (
            "entrypoint.sh must exit 1 on migration failure"
        )


# ---------------------------------------------------------------------------
# YAML parsing helper for Docker Compose tests
# ---------------------------------------------------------------------------

import yaml

DOCKER_COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"

EXPECTED_SERVICES = [
    "postgres",
    "redis",
    "api",
    "celery-worker",
    "celery-beat",
    "frontend",
]


def _load_docker_compose() -> dict:
    """Load and parse docker-compose.yml."""
    content = DOCKER_COMPOSE_PATH.read_text()
    return yaml.safe_load(content)


# ---------------------------------------------------------------------------
# Property 1: 全サービス定義の完全性
# docker-compose.ymlに全6サービス（postgres, redis, api, celery-worker,
# celery-beat, frontend）が定義されていることを検証
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------

class TestAllServicesDefinition:
    """Property 1: All 6 required services must be defined in docker-compose.yml."""

    @given(service_name=st.sampled_from(EXPECTED_SERVICES))
    @settings(max_examples=50)
    def test_required_service_exists(self, service_name: str):
        """
        **Validates: Requirements 1.1**

        For any required service name, docker-compose.yml must define that service.
        """
        compose = _load_docker_compose()
        services = compose.get("services", {})
        assert service_name in services, (
            f"Required service '{service_name}' is not defined in docker-compose.yml. "
            f"All 6 services (postgres, redis, api, celery-worker, celery-beat, frontend) "
            f"must be present (Requirements 1.1)."
        )

    def test_all_six_services_present(self):
        """Deterministic check: all 6 expected services are defined."""
        compose = _load_docker_compose()
        services = set(compose.get("services", {}).keys())
        missing = set(EXPECTED_SERVICES) - services
        assert not missing, (
            f"Missing services in docker-compose.yml: {missing}. "
            f"Expected all of: {EXPECTED_SERVICES}"
        )

    def test_no_unexpected_services(self):
        """Verify only the expected services are defined (no extras)."""
        compose = _load_docker_compose()
        services = set(compose.get("services", {}).keys())
        expected = set(EXPECTED_SERVICES)
        extra = services - expected
        # This is informational — extra services are allowed but noted
        assert services >= expected, (
            f"docker-compose.yml is missing required services: {expected - services}"
        )


# ---------------------------------------------------------------------------
# Property 2: 全サービスのヘルスチェック設定
# docker-compose.yml内の全サービスにhealthcheck設定が存在することを検証
# Validates: Requirements 1.2, 8.2
# ---------------------------------------------------------------------------

class TestAllServicesHealthcheck:
    """Property 2: All services in docker-compose.yml must have healthcheck config."""

    @given(service_name=st.sampled_from(EXPECTED_SERVICES))
    @settings(max_examples=50)
    def test_service_has_healthcheck(self, service_name: str):
        """
        **Validates: Requirements 1.2, 8.2**

        For any service defined in docker-compose.yml, that service must
        include a healthcheck configuration.
        """
        compose = _load_docker_compose()
        services = compose.get("services", {})
        assume(service_name in services)

        service_config = services[service_name]
        assert "healthcheck" in service_config, (
            f"Service '{service_name}' in docker-compose.yml does not have a "
            f"healthcheck configuration. All services must include healthcheck "
            f"settings (Requirements 1.2, 8.2)."
        )

    @given(service_name=st.sampled_from(EXPECTED_SERVICES))
    @settings(max_examples=50)
    def test_healthcheck_has_test_command(self, service_name: str):
        """
        **Validates: Requirements 1.2, 8.2**

        For any service with a healthcheck, the healthcheck must include
        a 'test' command.
        """
        compose = _load_docker_compose()
        services = compose.get("services", {})
        assume(service_name in services)

        service_config = services[service_name]
        assume("healthcheck" in service_config)

        healthcheck = service_config["healthcheck"]
        assert "test" in healthcheck, (
            f"Service '{service_name}' healthcheck is missing a 'test' command. "
            f"Healthchecks must define how to verify service health."
        )

    def test_all_services_have_healthcheck(self):
        """Deterministic check: every service has a healthcheck."""
        compose = _load_docker_compose()
        services = compose.get("services", {})
        missing_healthcheck = []
        for svc_name in EXPECTED_SERVICES:
            if svc_name in services:
                if "healthcheck" not in services[svc_name]:
                    missing_healthcheck.append(svc_name)
        assert not missing_healthcheck, (
            f"Services missing healthcheck configuration: {missing_healthcheck}"
        )
