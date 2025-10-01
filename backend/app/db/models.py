# backend/db/models.py
"""
Database Models for Contract Amendment Orchestrator

This module defines all the SQLAlchemy models for persisting
workflow state, contracts, and audit information.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from sqlalchemy import Index

Base = declarative_base()


class Contract(Base):
    """Contract entity model"""
    
    __tablename__ = "contracts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True)  # For version tracking
    contract_type = Column(String(100), nullable=False, default="service_agreement")
    
    # Parties and stakeholders
    parties = Column(JSON, nullable=False)  # List of party information
    primary_contact = Column(String(255), nullable=True)
    
    # Status and lifecycle
    status = Column(String(50), default="active")  # active, amended, terminated, draft
    version = Column(Integer, default=1)
    parent_contract_id = Column(String, nullable=True)  # For amended versions
    
    # Financial information
    total_value = Column(Float, nullable=True)
    currency = Column(String(3), default="USD")
    
    # Dates
    effective_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    amendments = relationship("Amendment", back_populates="contract")
    versions = relationship("ContractVersion", back_populates="contract")
    
    def __repr__(self):
        return f"<Contract(id='{self.id}', title='{self.title}', status='{self.status}')>"


class Amendment(Base):
    """Amendment workflow model"""
    
    __tablename__ = "amendments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    
    # Amendment details
    proposed_changes = Column(JSON, nullable=False)
    parties_involved = Column(JSON, nullable=False)  # List of party IDs
    
    # Workflow state
    status = Column(String(50), default="initiated")

    # Party responses and approvals
    approvals = Column(JSON, nullable=True)  # Party ID -> response data
    conflicts = Column(JSON, nullable=True)  # List of conflict information
    
    # Legal and compliance
    legal_review_status = Column(String(50), default="pending")
    compliance_checks = Column(JSON, nullable=True)
    risk_assessment = Column(JSON, nullable=True)
    

    # Final outputs
    final_document = Column(Text, nullable=True)
    final_document_hash = Column(String(64), nullable=True)
    
    # Audit and history
    error_log = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Metadata
    workflow_config = Column(JSON, nullable=True)
 
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    contract = relationship("Contract", back_populates="amendments")
    workflow_events = relationship("WorkflowEvent", back_populates="amendment")
    
    def __repr__(self):
        return f"<Amendment(id='{self.id}', contract_id='{self.contract_id}', status='{self.status}')>"


class ContractVersion(Base):
    """Contract version tracking"""
    
    __tablename__ = "contract_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    amendment_id = Column(String, ForeignKey("amendments.id"), nullable=True)
    
    # Version information
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    
    # Change tracking
    changes_summary = Column(Text, nullable=True)
    diff_from_previous = Column(JSON, nullable=True)  # Structured diff information
    
    # Authorship
    author = Column(String(255), nullable=False)  # System user or agent
    author_type = Column(String(50), default="system")  # system, user, agent
    
    # Metadata
    tags = Column(JSON, nullable=True)  # Version tags like "approved", "draft"
    contract_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="versions")
    
    def __repr__(self):
        return f"<ContractVersion(id='{self.id}', contract_id='{self.contract_id}', version='{self.version_number}')>"


class WorkflowEvent(Base):
    """Workflow event audit log"""
    
    __tablename__ = "workflow_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    amendment_id = Column(String, ForeignKey("amendments.id"), nullable=False)
    
    # Event information
    event_type = Column(String(100), nullable=False)  # node_execution, status_change, error, etc.
    event_source = Column(String(100), nullable=False)  # node name or system component
    
    # Event data
    event_data = Column(JSON, nullable=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    # Status and timing
    status = Column(String(50), nullable=False)  # success, error, pending
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Context
    workflow_status_before = Column(String(50), nullable=True)
    workflow_status_after = Column(String(50), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    amendment = relationship("Amendment", back_populates="workflow_events")
    
    def __repr__(self):
        return f"<WorkflowEvent(id='{self.id}', type='{self.event_type}', status='{self.status}')>"


class Party(Base):
    """Party/Organization information"""
    
    __tablename__ = "parties"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Organization details
    organization_name = Column(String(255), nullable=False)
    organization_type = Column(String(100), nullable=True)  # corporation, llc, individual
    
    # Contact information
    primary_contact_name = Column(String(255), nullable=True)
    primary_contact_email = Column(String(255), nullable=True)
    primary_contact_phone = Column(String(50), nullable=True)
    
    # Policies and preferences
    policies = Column(JSON, nullable=True)  # Risk tolerance, approval thresholds, etc.
    preferences = Column(JSON, nullable=True)  # Notification preferences, etc.
    
    # Status
    status = Column(String(50), default="active")  # active, inactive, suspended
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Party(id='{self.id}', name='{self.organization_name}')>"


class NotificationLog(Base):
    """Notification delivery log"""
    
    __tablename__ = "notification_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    amendment_id = Column(String, ForeignKey("amendments.id"), nullable=True)
    
    # Notification details
    notification_type = Column(String(100), nullable=False)
    channel = Column(String(50), nullable=False)  # email, websocket, sms, etc.
    recipient_id = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=True)
    
    # Content
    subject = Column(String(500), nullable=True)
    message = Column(Text, nullable=True)
    
    # Delivery status
    status = Column(String(50), default="pending")  # pending, sent, delivered, failed
    delivery_attempts = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<NotificationLog(id='{self.id}', type='{self.notification_type}', status='{self.status}')>"


class APIAuditLog(Base):
    """API call audit log"""
    
    __tablename__ = "api_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Request information
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    endpoint = Column(String(500), nullable=False)
    user_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    
    # Request/Response data
    request_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=True)
    
    # Timing
    duration_ms = Column(Float, nullable=True)
    
    # Context
    amendment_id = Column(String, nullable=True)  # If related to specific workflow
    contract_id = Column(String, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<APIAuditLog(id='{self.id}', method='{self.method}', endpoint='{self.endpoint}')>"


class SystemMetrics(Base):
    """System performance and usage metrics"""
    
    __tablename__ = "system_metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Metric information
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    value = Column(Float, nullable=False)
    
    # Context
    labels = Column(JSON, nullable=True)  # Key-value pairs for metric labels
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemMetrics(name='{self.metric_name}', value='{self.value}')>"




# Contract indexes
Index('idx_contracts_status', Contract.status)
Index('idx_contracts_type', Contract.contract_type)
Index('idx_contracts_created_at', Contract.created_at)

# Amendment indexes
Index('idx_amendments_contract_id', Amendment.contract_id)
Index('idx_amendments_status', Amendment.status)
Index('idx_amendments_created_at', Amendment.created_at)

# Event indexes
Index('idx_workflow_events_amendment_id', WorkflowEvent.amendment_id)
Index('idx_workflow_events_timestamp', WorkflowEvent.timestamp)
Index('idx_workflow_events_type', WorkflowEvent.event_type)

# Notification indexes
Index('idx_notification_logs_amendment_id', NotificationLog.amendment_id)
Index('idx_notification_logs_status', NotificationLog.status)
Index('idx_notification_logs_created_at', NotificationLog.created_at)

# API audit indexes
Index('idx_api_audit_timestamp', APIAuditLog.timestamp)
Index('idx_api_audit_endpoint', APIAuditLog.endpoint)
Index('idx_api_audit_user_id', APIAuditLog.user_id)