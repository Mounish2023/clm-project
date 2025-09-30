# backend/core/graph_state.py
"""
LangGraph State Definitions for Contract Amendment Orchestration

This module defines the comprehensive state structure that flows through
the entire multi-party contract amendment workflow.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class AmendmentStatus(str, Enum):
    """Amendment workflow status enumeration"""
    INITIATED = "initiated"
    PARTIES_NOTIFIED = "parties_notified"
    UNDER_REVIEW = "under_review"
    CONFLICTS_DETECTED = "conflicts_detected"
    CONFLICT_RESOLUTION = "conflict_resolution"
    CONSENSUS_BUILDING = "consensus_building"
    LEGAL_REVIEW = "legal_review"
    FINAL_APPROVAL = "final_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class PartyResponse(BaseModel):
    """Individual party response to amendment proposal"""
    party_id: str
    organization: str
    status: str  # approved, rejected, requested_changes, pending
    comments: Optional[str] = None
    proposed_changes: Optional[Dict[str, Any]] = None
    conditions: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    risk_assessment: Optional[Dict[str, Any]] = None


class ConflictInfo(BaseModel):
    """Information about detected conflicts between parties"""
    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_type: str  # contradictory_terms, overlapping_sections, policy_violation
    description: str
    affected_parties: List[str]
    affected_clauses: List[str]
    severity: str  # high, medium, low
    resolution_suggestions: Optional[List[str]] = None
    resolution_status: str = "unresolved"  # unresolved, in_progress, resolved
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentVersion(BaseModel):
    """Document version information"""
    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    content_hash: str
    author: str
    changes_summary: str
    parent_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    document_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowMetrics(BaseModel):
    """Workflow performance and progress metrics"""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    current_duration: Optional[float] = None
    estimated_completion: Optional[datetime] = None
    progress_percentage: float = 0.0
    bottlenecks: List[str] = Field(default_factory=list)
    efficiency_score: Optional[float] = None


class AmendmentWorkflowState(BaseModel):
    """
    Complete state for multi-party contract amendment workflow
    This state flows through all LangGraph nodes and maintains the complete
    context of the amendment process.
    """
    # Core identifiers
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amendment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    
    # Workflow status and control
    status: AmendmentStatus = AmendmentStatus.INITIATED
    current_step: str = "initiation"
    review_rounds: int = 0
    next_steps: List[str] = Field(default_factory=list)
    
    # Parties and stakeholders
    parties: List[str] = Field(description="List of party IDs involved in amendment")
    party_responses: Dict[str, PartyResponse] = Field(default_factory=dict)
    required_approvals: List[str] = Field(default_factory=list)
    received_approvals: List[str] = Field(default_factory=list)
    
    # Amendment content
    original_contract: Optional[str] = None
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    consolidated_changes: Optional[Dict[str, Any]] = None
    final_document: Optional[str] = None
    
    # Conflict management
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    active_conflicts: List[str] = Field(default_factory=list)
    resolved_conflicts: List[str] = Field(default_factory=list)
    
    # Document versioning
    document_versions: List[DocumentVersion] = Field(default_factory=list)
    current_version: Optional[str] = None
    merge_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Communication and notifications
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    pending_notifications: List[Dict[str, Any]] = Field(default_factory=list)
    communication_log: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Legal and compliance
    compliance_checks: Dict[str, Any] = Field(default_factory=dict)
    legal_review_status: str = "pending"
    regulatory_requirements: List[str] = Field(default_factory=list)
    risk_assessment: Optional[Dict[str, Any]] = None
    
    # Workflow orchestration data
    node_outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs from individual nodes for debugging and tracking"
    )
    execution_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of node executions and state transitions"
    )
    
    # Performance and analytics
    metrics: WorkflowMetrics = Field(default_factory=WorkflowMetrics)
    
    # Error handling
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    # Configuration and preferences
    workflow_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "timeout_minutes": 1440,  # 24 hours default
            "auto_approve_threshold": 0.8,
            "conflict_resolution_timeout": 120,  # 2 hours
            "max_review_rounds": 2, # Max number of party review cycles
            "require_legal_review": True,
            "enable_ai_mediation": True
        }
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def add_party_response(self, party_id: str, response: PartyResponse) -> None:
        """Add or update a party's response"""
        self.party_responses[party_id] = response
        if response.status == "approved":
            if party_id not in self.received_approvals:
                self.received_approvals.append(party_id)
        elif party_id in self.received_approvals:
            self.received_approvals.remove(party_id)
        self.updated_at = datetime.utcnow()
    
    def add_conflict(self, conflict: ConflictInfo) -> None:
        """Add a new conflict to the workflow"""
        self.conflicts.append(conflict)
        if conflict.conflict_id not in self.active_conflicts:
            self.active_conflicts.append(conflict.conflict_id)
        self.updated_at = datetime.utcnow()
    
    def resolve_conflict(self, conflict_id: str, resolution_notes: str = "") -> bool:
        """Mark a conflict as resolved"""
        for conflict in self.conflicts:
            if conflict.conflict_id == conflict_id:
                conflict.resolution_status = "resolved"
                if conflict_id in self.active_conflicts:
                    self.active_conflicts.remove(conflict_id)
                if conflict_id not in self.resolved_conflicts:
                    self.resolved_conflicts.append(conflict_id)
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def add_document_version(self, version: DocumentVersion) -> None:
        """Add a new document version"""
        self.document_versions.append(version)
        self.current_version = version.version_id
        self.updated_at = datetime.utcnow()
    
    def log_execution(self, node_name: str, input_data: Any, output_data: Any, 
                     duration: float = 0.0, success: bool = True) -> None:
        """Log node execution for debugging and audit trail"""
        execution_record = {
            "node": node_name,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": duration,
            "success": success,
            "input_hash": hash(str(input_data)) if input_data else None,
            "output_hash": hash(str(output_data)) if output_data else None
        }
        self.execution_history.append(execution_record)
        
        # Store latest output for reference
        self.node_outputs[node_name] = {
            "timestamp": execution_record["timestamp"],
            "output": output_data,
            "success": success
        }
    
    def get_pending_parties(self) -> List[str]:
        """Get list of parties that haven't responded yet"""
        return [
            party for party in self.parties 
            if party not in self.party_responses or 
            self.party_responses[party].status == "pending"
        ]
    
    def is_consensus_reached(self) -> bool:
        """Check if consensus has been reached among all parties"""
        if not self.parties:
            return False
            
        for party in self.parties:
            if party not in self.party_responses:
                return False
            if self.party_responses[party].status not in ["approved"]:
                return False
                
        return True
    
    def has_active_conflicts(self) -> bool:
        """Check if there are any unresolved conflicts"""
        return len(self.active_conflicts) > 0
    
    def calculate_progress(self) -> float:
        """Calculate overall workflow progress percentage"""
        total_steps = 8  # Total workflow steps
        completed_steps = 0
        
        if self.status in [AmendmentStatus.PARTIES_NOTIFIED, AmendmentStatus.UNDER_REVIEW]:
            completed_steps = 1
        elif self.status == AmendmentStatus.UNDER_REVIEW:
            completed_steps = 2
        elif self.status == AmendmentStatus.CONFLICTS_DETECTED:
            completed_steps = 3
        elif self.status == AmendmentStatus.CONFLICT_RESOLUTION:
            completed_steps = 4
        elif self.status == AmendmentStatus.CONSENSUS_BUILDING:
            completed_steps = 5
        elif self.status == AmendmentStatus.LEGAL_REVIEW:
            completed_steps = 6
        elif self.status == AmendmentStatus.FINAL_APPROVAL:
            completed_steps = 7
        elif self.status in [AmendmentStatus.APPROVED, AmendmentStatus.COMPLETED]:
            completed_steps = 8
            
        progress = (completed_steps / total_steps) * 100
        self.metrics.progress_percentage = progress
        return progress
    
    def update_status(self, new_status: AmendmentStatus, notes: str = "") -> None:
        """Update workflow status and log the change"""
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        # Log status change
        status_change = {
            "from_status": old_status,
            "to_status": new_status,
            "timestamp": self.updated_at.isoformat(),
            "notes": notes
        }
        
        if "status_changes" not in self.node_outputs:
            self.node_outputs["status_changes"] = []
        self.node_outputs["status_changes"].append(status_change)
        
        # Update progress
        self.calculate_progress()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization"""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AmendmentWorkflowState':
        """Create state from dictionary"""
        return cls.model_validate(data)


# Type alias for LangGraph state
GraphState = AmendmentWorkflowState