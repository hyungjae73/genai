"""
Tests for audit logging functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Index
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.types import JSON

from src.security.audit import AuditLogger, audit_operation


# Create a test-specific Base and AuditLog model for SQLite compatibility
class TestBase(DeclarativeBase):
    """Base class for test models."""
    pass


class TestAuditLog(TestBase):
    """Test version of AuditLog that uses JSON instead of JSONB for SQLite compatibility."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Use JSON instead of JSONB for SQLite
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_audit_user', 'user'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_timestamp', 'timestamp'),
    )


@pytest.fixture
def db_session(monkeypatch):
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Monkey patch the AuditLog import in the audit module to use our test version
    import src.security.audit
    monkeypatch.setattr(src.security.audit, 'AuditLog', TestAuditLog)
    
    yield session
    session.close()


@pytest.fixture
def audit_logger(db_session):
    """Create an AuditLogger instance."""
    return AuditLogger(db_session)


def test_log_basic(audit_logger, db_session):
    """Test basic audit logging."""
    log = audit_logger.log(
        user="admin@example.com",
        action="create",
        resource_type="site",
        resource_id=123,
        details={"company_name": "Example Corp"},
    )
    
    assert log.id is not None
    assert log.user == "admin@example.com"
    assert log.action == "create"
    assert log.resource_type == "site"
    assert log.resource_id == 123
    assert log.details == {"company_name": "Example Corp"}
    assert log.timestamp is not None
    
    # Verify it's in the database
    stored_log = db_session.query(TestAuditLog).filter_by(id=log.id).first()
    assert stored_log is not None
    assert stored_log.user == "admin@example.com"


def test_log_without_resource_id(audit_logger):
    """Test logging without resource ID."""
    log = audit_logger.log(
        user="user@example.com",
        action="list",
        resource_type="sites",
    )
    
    assert log.resource_id is None
    assert log.action == "list"


def test_log_with_ip_and_user_agent(audit_logger):
    """Test logging with IP address and user agent."""
    log = audit_logger.log(
        user="admin@example.com",
        action="update",
        resource_type="contract",
        resource_id=456,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
    )
    
    assert log.ip_address == "192.168.1.1"
    assert log.user_agent == "Mozilla/5.0"


def test_log_create(audit_logger):
    """Test log_create convenience method."""
    log = audit_logger.log_create(
        user="admin@example.com",
        resource_type="site",
        resource_id=789,
        details={"domain": "example.com"},
    )
    
    assert log.action == "create"
    assert log.resource_type == "site"
    assert log.resource_id == 789


def test_log_create_with_request(audit_logger):
    """Test log_create with FastAPI request object."""
    # Mock FastAPI request
    mock_request = MagicMock()
    mock_request.client.host = "10.0.0.1"
    mock_request.headers.get.return_value = "TestAgent/1.0"
    
    log = audit_logger.log_create(
        user="admin@example.com",
        resource_type="site",
        resource_id=100,
        request=mock_request,
    )
    
    assert log.ip_address == "10.0.0.1"
    assert log.user_agent == "TestAgent/1.0"


def test_log_update(audit_logger):
    """Test log_update convenience method."""
    log = audit_logger.log_update(
        user="admin@example.com",
        resource_type="contract",
        resource_id=200,
        details={"changed_fields": ["price", "payment_methods"]},
    )
    
    assert log.action == "update"
    assert log.resource_type == "contract"
    assert log.resource_id == 200


def test_log_delete(audit_logger):
    """Test log_delete convenience method."""
    log = audit_logger.log_delete(
        user="admin@example.com",
        resource_type="site",
        resource_id=300,
        details={"reason": "Decommissioned"},
    )
    
    assert log.action == "delete"
    assert log.resource_type == "site"
    assert log.resource_id == 300


def test_log_read(audit_logger):
    """Test log_read convenience method."""
    log = audit_logger.log_read(
        user="user@example.com",
        resource_type="contract",
        resource_id=400,
    )
    
    assert log.action == "read"
    assert log.resource_type == "contract"
    assert log.resource_id == 400


def test_get_logs_no_filters(audit_logger):
    """Test getting logs without filters."""
    # Create multiple logs
    audit_logger.log("user1", "create", "site", 1)
    audit_logger.log("user2", "update", "contract", 2)
    audit_logger.log("user3", "delete", "alert", 3)
    
    logs = audit_logger.get_logs()
    
    assert len(logs) == 3


def test_get_logs_filter_by_user(audit_logger):
    """Test filtering logs by user."""
    audit_logger.log("user1", "create", "site", 1)
    audit_logger.log("user2", "update", "contract", 2)
    audit_logger.log("user1", "delete", "alert", 3)
    
    logs = audit_logger.get_logs(user="user1")
    
    assert len(logs) == 2
    assert all(log.user == "user1" for log in logs)


def test_get_logs_filter_by_action(audit_logger):
    """Test filtering logs by action."""
    audit_logger.log("user1", "create", "site", 1)
    audit_logger.log("user2", "create", "contract", 2)
    audit_logger.log("user3", "delete", "alert", 3)
    
    logs = audit_logger.get_logs(action="create")
    
    assert len(logs) == 2
    assert all(log.action == "create" for log in logs)


def test_get_logs_filter_by_resource_type(audit_logger):
    """Test filtering logs by resource type."""
    audit_logger.log("user1", "create", "site", 1)
    audit_logger.log("user2", "update", "site", 2)
    audit_logger.log("user3", "delete", "contract", 3)
    
    logs = audit_logger.get_logs(resource_type="site")
    
    assert len(logs) == 2
    assert all(log.resource_type == "site" for log in logs)


def test_get_logs_filter_by_resource_id(audit_logger):
    """Test filtering logs by resource ID."""
    audit_logger.log("user1", "create", "site", 100)
    audit_logger.log("user2", "update", "site", 100)
    audit_logger.log("user3", "delete", "site", 200)
    
    logs = audit_logger.get_logs(resource_id=100)
    
    assert len(logs) == 2
    assert all(log.resource_id == 100 for log in logs)


def test_get_logs_filter_by_date_range(audit_logger, db_session):
    """Test filtering logs by date range."""
    now = datetime.utcnow()
    
    # Create logs with different timestamps
    log1 = TestAuditLog(
        user="user1",
        action="create",
        resource_type="site",
        timestamp=now - timedelta(days=5)
    )
    log2 = TestAuditLog(
        user="user2",
        action="update",
        resource_type="site",
        timestamp=now - timedelta(days=2)
    )
    log3 = TestAuditLog(
        user="user3",
        action="delete",
        resource_type="site",
        timestamp=now
    )
    
    db_session.add_all([log1, log2, log3])
    db_session.commit()
    
    # Filter by date range
    start_date = now - timedelta(days=3)
    logs = audit_logger.get_logs(start_date=start_date)
    
    assert len(logs) == 2
    assert all(log.timestamp >= start_date for log in logs)


def test_get_logs_with_limit(audit_logger):
    """Test limiting number of returned logs."""
    # Create 10 logs
    for i in range(10):
        audit_logger.log(f"user{i}", "create", "site", i)
    
    logs = audit_logger.get_logs(limit=5)
    
    assert len(logs) == 5


def test_get_logs_ordered_by_timestamp(audit_logger, db_session):
    """Test that logs are ordered by timestamp descending."""
    now = datetime.utcnow()
    
    # Create logs with different timestamps
    log1 = TestAuditLog(
        user="user1",
        action="create",
        resource_type="site",
        timestamp=now - timedelta(hours=2)
    )
    log2 = TestAuditLog(
        user="user2",
        action="update",
        resource_type="site",
        timestamp=now - timedelta(hours=1)
    )
    log3 = TestAuditLog(
        user="user3",
        action="delete",
        resource_type="site",
        timestamp=now
    )
    
    db_session.add_all([log1, log2, log3])
    db_session.commit()
    
    logs = audit_logger.get_logs()
    
    # Should be ordered newest first
    assert logs[0].timestamp > logs[1].timestamp
    assert logs[1].timestamp > logs[2].timestamp


def test_audit_operation_convenience_function(db_session):
    """Test the audit_operation convenience function."""
    log = audit_operation(
        db_session=db_session,
        user="admin@example.com",
        action="create",
        resource_type="site",
        resource_id=999,
        details={"test": "data"},
    )
    
    assert log.user == "admin@example.com"
    assert log.action == "create"
    assert log.resource_type == "site"
    assert log.resource_id == 999
    
    # Verify it's in the database
    stored_log = db_session.query(TestAuditLog).filter_by(id=log.id).first()
    assert stored_log is not None


def test_audit_operation_with_request(db_session):
    """Test audit_operation with request object."""
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.100"
    mock_request.headers.get.return_value = "TestBrowser/1.0"
    
    log = audit_operation(
        db_session=db_session,
        user="admin@example.com",
        action="update",
        resource_type="contract",
        resource_id=500,
        request=mock_request,
    )
    
    assert log.ip_address == "192.168.1.100"
    assert log.user_agent == "TestBrowser/1.0"
