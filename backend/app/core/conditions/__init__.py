# backend/core/conditions/routing_conditions.py
"""
LangGraph Routing Conditions for Contract Amendment Workflow

This module contains all the conditional routing logic that determines
how the workflow flows between different nodes in the LangGraph.
"""

from typing import Dict, Any, List, Optional
from ..graph_state import AmendmentWorkflowState, AmendmentStatus, PartyResponse


def should_route_to_parties(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should route to party review nodes
    
    Returns True when:
    - Workflow is newly initiated and parties need to be notified
    - Conflicts have been resolved and parties need to re-review
    - New changes have been proposed that require party input
    """
    
    # New workflow that hasn't collected party responses yet
    if state.status == AmendmentStatus.INITIATED:
        return True
    
    # Parties have been notified but haven't all responded
    if state.status == AmendmentStatus.PARTIES_NOTIFIED:
        return len(state.party_responses) < len(state.parties)
    
    # Conflicts resolved, need party re-confirmation
    if (state.status == AmendmentStatus.CONFLICT_RESOLUTION and 
        len(state.active_conflicts) == 0):
        return True
    
    # Some parties haven't responded yet
    pending_parties = state.get_pending_parties()
    if pending_parties and state.status == AmendmentStatus.UNDER_REVIEW:
        return True
    
    return False


def should_route_to_conflict_resolution(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should route to conflict resolution
    
    Returns True when:
    - Active conflicts are detected between party positions
    - High-severity conflicts need immediate attention
    - Previous conflict resolution failed and retry is needed
    """
    
    # Active conflicts exist
    if len(state.active_conflicts) > 0:
        return True
    
    # Conflicts were just detected
    if state.status == AmendmentStatus.CONFLICTS_DETECTED:
        return True
    
    # Check for implicit conflicts in party responses
    if len(state.party_responses) >= 2:
        conflicting_responses = _detect_response_conflicts(state)
        if conflicting_responses:
            return True
    
    # Legal review found compliance conflicts
    if (state.status == AmendmentStatus.LEGAL_REVIEW and 
        state.compliance_checks.get("compliance_status") == "non_compliant"):
        return True
    
    return False


def should_route_to_legal_review(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should route to legal review
    
    Returns True when:
    - All parties have reached consensus
    - Workflow configuration requires legal review
    - Significant changes need compliance validation
    - Complex multi-party agreements need legal validation
    """
    
    # Legal review is explicitly required in config
    if state.workflow_config.get("require_legal_review", False):
        # Only after consensus or conflict resolution
        if (state.is_consensus_reached() and 
            len(state.active_conflicts) == 0):
            return True
    
    # High-value or high-risk amendments need legal review
    if _requires_legal_review_by_content(state):
        if state.is_consensus_reached():
            return True
    
    # Multi-party agreements with complex changes
    if (len(state.parties) >= 3 and 
        len(state.proposed_changes) >= 3 and
        state.is_consensus_reached()):
        return True
    
    # Status specifically indicates legal review needed
    if state.status == AmendmentStatus.LEGAL_REVIEW:
        return True
    
    return False


def should_route_to_version_control(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should route to version control/document merging
    
    Returns True when:
    - Consensus reached and no active conflicts
    - Legal review passed (if required)
    - Ready to merge approved changes into final document
    """
    
    # Basic requirements: consensus + no conflicts
    basic_requirements = (
        state.is_consensus_reached() and 
        len(state.active_conflicts) == 0
    )
    
    if not basic_requirements:
        return False
    
    # If legal review is required, it must be completed successfully
    if state.workflow_config.get("require_legal_review", False):
        if state.legal_review_status != "approved":
            return False
    
    # Check that we have substantive changes to merge
    approved_changes = _get_approved_changes(state)
    if not approved_changes:
        return False
    
    # Status indicates consensus building is complete
    if state.status == AmendmentStatus.CONSENSUS_BUILDING:
        return True
    
    # Legal review just completed successfully
    if (state.status == AmendmentStatus.LEGAL_REVIEW and 
        state.legal_review_status == "approved"):
        return True
    
    return False


def should_complete_workflow(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should complete
    
    Returns True when:
    - Final document has been generated successfully
    - All parties have approved final version
    - All compliance checks passed
    - No outstanding issues or conflicts
    """
    
    # Must have final document
    if not state.final_document:
        return False
    
    # All parties must have approved
    if not state.is_consensus_reached():
        return False
    
    # No active conflicts
    if len(state.active_conflicts) > 0:
        return False
    
    # Legal review passed (if required)
    if state.workflow_config.get("require_legal_review", False):
        if state.legal_review_status != "approved":
            return False
    
    # Workflow status indicates readiness for completion
    completion_statuses = [
        AmendmentStatus.FINAL_APPROVAL,
        AmendmentStatus.APPROVED
    ]
    
    if state.status in completion_statuses:
        return True
    
    # Check for auto-completion conditions
    if _meets_auto_completion_criteria(state):
        return True
    
    return False


def should_retry_workflow(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should retry after failure
    
    Returns True when:
    - Transient errors occurred that might succeed on retry
    - Haven't exceeded maximum retry attempts
    - Error conditions are recoverable
    """
    
    # Check retry limits
    max_retries = state.workflow_config.get("max_retries", 3)
    if state.retry_count >= max_retries:
        return False
    
    # No errors means no need to retry
    if not state.errors:
        return False
    
    # Analyze recent errors for recoverability
    recent_errors = state.errors[-3:] if len(state.errors) >= 3 else state.errors
    recoverable_errors = 0
    
    for error in recent_errors:
        if _is_recoverable_error(error):
            recoverable_errors += 1
    
    # If majority of recent errors are recoverable, retry
    if recoverable_errors > len(recent_errors) / 2:
        return True
    
    # Specific retry conditions
    if state.status == AmendmentStatus.FAILED:
        # Check if failure was due to temporary issues
        latest_error = state.errors[-1] if state.errors else {}
        error_type = latest_error.get("error", "").lower()
        
        temporary_error_keywords = [
            "timeout", "connection", "rate limit", "temporary", 
            "unavailable", "retry", "network"
        ]
        
        if any(keyword in error_type for keyword in temporary_error_keywords):
            return True
    
    return False


def should_route_back_to_coordinator(state: AmendmentWorkflowState) -> bool:
    """
    Determine if workflow should route back to coordinator for re-evaluation
    
    Returns True when:
    - Current node cannot determine next step
    - Workflow state is ambiguous  
    - Need central coordination to resolve routing
    """
    
    # Ambiguous state that needs coordinator evaluation
    ambiguous_conditions = [
        # Partial party responses with unclear next steps
        (0 < len(state.party_responses) < len(state.parties) and 
         state.status == AmendmentStatus.UNDER_REVIEW),
        
        # Conflicts partially resolved but status unclear
        (len(state.conflicts) > len(state.active_conflicts) and
         len(state.active_conflicts) > 0),
        
        # Legal review has comments but not clear approve/reject
        (state.legal_review_status not in ["approved", "rejected"] and
         state.status == AmendmentStatus.LEGAL_REVIEW)
    ]
    
    return any(ambiguous_conditions)


def get_next_node_from_state(state: AmendmentWorkflowState) -> str:
    """
    Centralized routing logic to determine next node
    
    This function encapsulates the main routing decision tree
    """
    
    # Error handling - always check first
    if state.errors and should_retry_workflow(state):
        return "error_handler"
    
    # Completion check
    if should_complete_workflow(state):
        return "completion"
    
    # Priority routing based on current status and conditions
    if should_route_to_conflict_resolution(state):
        return "conflict_resolution"
    
    if should_route_to_legal_review(state):
        return "legal_review"
    
    if should_route_to_version_control(state):
        return "version_control"
    
    if should_route_to_parties(state):
        return "party_review"
    
    # Default back to coordinator for re-evaluation
    if should_route_back_to_coordinator(state):
        return "coordinator"
    
    # Final fallback - should rarely happen
    return "coordinator"


# Helper functions for routing logic

def _detect_response_conflicts(state: AmendmentWorkflowState) -> List[Dict[str, Any]]:
    """Detect conflicts between party responses"""
    
    conflicts = []
    responses = list(state.party_responses.values())
    
    # Check for direct conflicts in status
    approve_count = sum(1 for r in responses if r.status == "approved")
    reject_count = sum(1 for r in responses if r.status == "rejected")
    
    if approve_count > 0 and reject_count > 0:
        conflicts.append({
            "type": "status_conflict",
            "description": f"{approve_count} parties approved, {reject_count} rejected"
        })
    
    # Check for conflicting proposed changes
    proposed_changes = [r.proposed_changes for r in responses if r.proposed_changes]
    if len(proposed_changes) > 1:
        # Simple conflict detection - would be more sophisticated in production
        conflicts.append({
            "type": "proposed_changes_conflict", 
            "description": "Multiple parties proposed different changes"
        })
    
    return conflicts


def _requires_legal_review_by_content(state: AmendmentWorkflowState) -> bool:
    """Determine if content requires legal review"""
    
    # Check for high-risk change keywords
    high_risk_keywords = [
        "liability", "indemnification", "termination", "intellectual property",
        "confidentiality", "non-compete", "arbitration", "governing law",
        "force majeure", "warranty", "damages"
    ]
    
    content_to_check = [
        str(state.proposed_changes),
        str([r.proposed_changes for r in state.party_responses.values() if r.proposed_changes])
    ]
    
    content_text = " ".join(content_to_check).lower()
    
    for keyword in high_risk_keywords:
        if keyword in content_text:
            return True
    
    # Check for financial thresholds
    if _contains_significant_financial_changes(state):
        return True
    
    return False


def _get_approved_changes(state: AmendmentWorkflowState) -> List[Dict[str, Any]]:
    """Get list of changes that have been approved"""
    
    approved_changes = []
    
    for party_id, response in state.party_responses.items():
        if response.status == "approved":
            if response.proposed_changes:
                approved_changes.append({
                    "party": party_id,
                    "changes": response.proposed_changes
                })
    
    return approved_changes


def _meets_auto_completion_criteria(state: AmendmentWorkflowState) -> bool:
    """Check if workflow meets criteria for auto-completion"""
    
    auto_approve_threshold = state.workflow_config.get("auto_approve_threshold", 1.0)
    
    if auto_approve_threshold < 1.0:
        # Calculate approval percentage
        total_parties = len(state.parties)
        approved_parties = sum(
            1 for response in state.party_responses.values() 
            if response.status == "approved"
        )
        
        approval_rate = approved_parties / total_parties if total_parties > 0 else 0
        
        if approval_rate >= auto_approve_threshold:
            return True
    
    return False


def _is_recoverable_error(error: Dict[str, Any]) -> bool:
    """Determine if an error is recoverable through retry"""
    
    error_message = error.get("error", "").lower()
    
    # Recoverable error patterns
    recoverable_patterns = [
        "timeout", "connection reset", "rate limit exceeded",
        "temporary unavailable", "service unavailable", 
        "network error", "connection error", "retry"
    ]
    
    return any(pattern in error_message for pattern in recoverable_patterns)


def _contains_significant_financial_changes(state: AmendmentWorkflowState) -> bool:
    """Check if changes involve significant financial amounts"""
    
    # This would parse financial amounts from proposed changes
    # Simplified implementation for demo
    
    financial_keywords = ["$", "dollar", "payment", "budget", "cost", "fee", "price"]
    content = str(state.proposed_changes).lower()
    
    return any(keyword in content for keyword in financial_keywords)


# Route mapping for easy access
ROUTING_CONDITIONS = {
    "parties": should_route_to_parties,
    "conflict_resolution": should_route_to_conflict_resolution,
    "legal_review": should_route_to_legal_review,
    "version_control": should_route_to_version_control,
    "completion": should_complete_workflow,
    "retry": should_retry_workflow,
    "coordinator": should_route_back_to_coordinator
}