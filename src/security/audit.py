"""
Audit logging utilities for tracking administrative operations.

This module provides functionality to log all management operations for
security and compliance purposes.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

from src.models import AuditLog


class AuditLogger:
    """
    Audit logger for tracking administrative operations.
    
    This class provides methods to log various types of operations
    including create, update, delete, and read operations.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize audit logger.
        
        Args:
            db_session: Database session for storing audit logs
        """
        self.db_session = db_session
    
    def log(
        self,
        user: str,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an administrative operation.
        
        Args:
            user: Username or email of the user performing the action
            action: Action performed (e.g., "create", "update", "delete", "read")
            resource_type: Type of resource (e.g., "site", "contract", "alert")
            resource_id: ID of the resource (optional)
            details: Additional details about the operation (optional)
            ip_address: IP address of the user (optional)
            user_agent: User agent string (optional)
            
        Returns:
            Created AuditLog object
            
        Example:
            >>> logger = AuditLogger(db_session)
            >>> logger.log(
            ...     user="admin@example.com",
            ...     action="create",
            ...     resource_type="site",
            ...     resource_id=123,
            ...     details={"company_name": "Example Corp"}
            ... )
        """
        audit_log = AuditLog(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
        )
        
        self.db_session.add(audit_log)
        self.db_session.commit()
        
        return audit_log
    
    def log_create(
        self,
        user: str,
        resource_type: str,
        resource_id: int,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a create operation.
        
        Args:
            user: Username or email
            resource_type: Type of resource created
            resource_id: ID of created resource
            details: Additional details
            request: FastAPI request object (for IP and user agent)
            
        Returns:
            Created AuditLog object
        """
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        return self.log(
            user=user,
            action="create",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_update(
        self,
        user: str,
        resource_type: str,
        resource_id: int,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log an update operation.
        
        Args:
            user: Username or email
            resource_type: Type of resource updated
            resource_id: ID of updated resource
            details: Additional details (e.g., changed fields)
            request: FastAPI request object
            
        Returns:
            Created AuditLog object
        """
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        return self.log(
            user=user,
            action="update",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_delete(
        self,
        user: str,
        resource_type: str,
        resource_id: int,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a delete operation.
        
        Args:
            user: Username or email
            resource_type: Type of resource deleted
            resource_id: ID of deleted resource
            details: Additional details
            request: FastAPI request object
            
        Returns:
            Created AuditLog object
        """
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        return self.log(
            user=user,
            action="delete",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_read(
        self,
        user: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a read operation (for sensitive resources).
        
        Args:
            user: Username or email
            resource_type: Type of resource read
            resource_id: ID of resource (optional for list operations)
            details: Additional details
            request: FastAPI request object
            
        Returns:
            Created AuditLog object
        """
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        return self.log(
            user=user,
            action="read",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def get_logs(
        self,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Query audit logs with filters.
        
        Args:
            user: Filter by user
            action: Filter by action
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of logs to return
            
        Returns:
            List of AuditLog objects
        """
        query = self.db_session.query(AuditLog)
        
        if user:
            query = query.filter(AuditLog.user == user)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if resource_id is not None:
            query = query.filter(AuditLog.resource_id == resource_id)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.limit(limit)
        
        return query.all()


def audit_operation(
    db_session: Session,
    user: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Convenience function to log an audit operation.
    
    Args:
        db_session: Database session
        user: Username or email
        action: Action performed
        resource_type: Type of resource
        resource_id: ID of resource (optional)
        details: Additional details (optional)
        request: FastAPI request object (optional)
        
    Returns:
        Created AuditLog object
        
    Example:
        >>> from src.security.audit import audit_operation
        >>> audit_operation(
        ...     db_session=session,
        ...     user="admin@example.com",
        ...     action="create",
        ...     resource_type="site",
        ...     resource_id=123
        ... )
    """
    logger = AuditLogger(db_session)
    
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    return logger.log(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
