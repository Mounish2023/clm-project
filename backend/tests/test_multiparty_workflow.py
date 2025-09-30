# tests/integration/test_multi_party_workflow.py
"""
Integration tests for the complete multi-party contract amendment workflow

These tests validate the entire LangGraph workflow from initiation to completion
using realistic multi-party scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from backend.core.orchestrator import ContractAmendmentOrchestrator
from backend.core.graph_state import AmendmentWorkflowState, AmendmentStatus


class TestMultiPartyWorkflow:
    """Test complete multi-party amendment workflows"""
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator instance for testing"""
        return ContractAmendmentOrchestrator()
    
    @pytest.fixture
    def sample_contract(self) -> str:
        """Sample contract for testing"""
        return """
        SERVICE AGREEMENT
        
        This Service Agreement ("Agreement") is entered into between Company A ("Client") 
        and Company B ("Provider") and Company C ("Subcontractor").
        
        1. SERVICES
        Provider shall deliver software development services as specified in Exhibit A.
        
        2. PAYMENT TERMS
        Client shall pay Provider $100,000 upon completion of milestones.
        Payment terms: Net 30 days.
        
        3. TERM
        This Agreement shall commence on January 1, 2024 and terminate on December 31, 2024.
        
        4. TERMINATION
        Either party may terminate this Agreement with 30 days written notice.
        
        5. INTELLECTUAL PROPERTY
        All work product shall be owned by Client upon full payment.
        """
    
    @pytest.fixture
    def three_party_config(self) -> List[Dict[str, Any]]:
        """Configuration for three-party scenario"""
        return [
            {
                "id": "company_a",
                "organization": "Company A",
                "policies": {
                    "risk_tolerance": "low",
                    "budget_limit": 150000,
                    "approval_threshold": 25000,
                    "required_clauses": ["termination_protection", "ip_ownership"]
                }
            },
            {
                "id": "company_b", 
                "organization": "Company B",
                "policies": {
                    "risk_tolerance": "medium",
                    "budget_limit": 200000,
                    "approval_threshold": 50000,
                    "preferred_terms": {"payment_terms": "Net 15"}
                }
            },
            {
                "id": "company_c",
                "organization": "Company C", 
                "policies": {
                    "risk_tolerance": "high",
                    "budget_limit": 75000,
                    "approval_threshold": 10000,
                    "constraints": {"no_exclusivity_clauses": True}
                }
            }
        ]
    
    @pytest.mark.asyncio
    async def test_successful_three_party_amendment(self, orchestrator, sample_contract, three_party_config):
        """Test successful three-party amendment with consensus"""
        
        proposed_changes = {
            "payment_terms": {
                "old_value": "$100,000 upon completion",
                "new_value": "$120,000 in three installments: $40,000 at 33%, $40,000 at 66%, $40,000 at completion"
            },
            "timeline": {
                "old_value": "December 31, 2024",
                "new_value": "March 31, 2025"
            },
            "additional_clause": {
                "section": "6. PERFORMANCE METRICS", 
                "content": "Provider must maintain 99.5% uptime and respond to issues within 4 hours."
            }
        }
        
        workflow_id = await orchestrator.initiate_amendment(
            contract_id="test_contract_001",
            parties=three_party_config,
            proposed_changes=proposed_changes,
            original_contract=sample_contract,
            workflow_config={"timeout_minutes": 60}
        )
        
        # Wait for workflow to complete (with timeout)
        max_wait_time = 120  # 2 minutes max
        start_time = datetime.utcnow()
        
        final_status = None
        while (datetime.utcnow() - start_time).seconds < max_wait_time:
            status = await orchestrator.get_workflow_status(workflow_id)
            final_status = status.get("status")
            
            if final_status in ["completed", "failed", "approved"]:
                break
                
            await asyncio.sleep(5)
        
        # Validate results
        assert final_status in ["completed", "approved"], f"Workflow failed with status: {final_status}"
        
        final_state = await self._get_final_workflow_state(orchestrator, workflow_id)
        
        # Check that all parties responded
        assert len(final_state.party_responses) == 3
        
        # Check that consensus was reached or conflicts resolved
        if final_state.conflicts:
            assert len(final_state.active_conflicts) == 0, "Unresolved conflicts remain"
        
        # Validate final document was generated
        assert final_state.final_document is not None, "Final document not generated"
        
        print(f"✅ Three-party amendment completed successfully")
        print(f"   Workflow ID: {workflow_id}")
        print(f"   Final Status: {final_status}")
        print(f"   Duration: {(datetime.utcnow() - start_time).seconds} seconds")
    
    @pytest.mark.asyncio
    async def test_conflicting_amendments_resolution(self, orchestrator, sample_contract, three_party_config):
        """Test amendment workflow with conflicting party requirements"""
        
        # Create conflicting changes that will require resolution
        proposed_changes = {
            "payment_terms": {
                "old_value": "Net 30 days",
                "new_value": "Net 15 days"  # This will conflict with Company A's conservative approach
            },
            "termination_clause": {
                "old_value": "30 days written notice",
                "new_value": "90 days written notice"  # This might conflict with Company C's flexibility needs
            },
            "liability_cap": {
                "section": "7. LIABILITY",
                "content": "Provider's liability shall be capped at 50% of contract value"  # Risk tolerance conflicts
            }
        }
        
        workflow_id = await orchestrator.initiate_amendment(
            contract_id="test_contract_002", 
            parties=three_party_config,
            proposed_changes=proposed_changes,
            original_contract=sample_contract,
            workflow_config={"enable_ai_mediation": True}
        )
        
        # Monitor workflow progress
        max_iterations = 24  # 2 minutes with 5-second intervals
        iteration = 0
        conflict_detected = False
        conflicts_resolved = False
        
        while iteration < max_iterations:
            status = await orchestrator.get_workflow_status(workflow_id)
            current_status = status.get("status")
            
            if current_status == "conflicts_detected":
                conflict_detected = True
                print(f"🔥 Conflicts detected as expected: {status.get('conflicts', 0)} conflicts")
            
            elif current_status == "consensus_building" and conflict_detected:
                conflicts_resolved = True
                print(f"🤝 Conflicts resolved, building consensus")
            
            elif current_status in ["completed", "approved"]:
                break
                
            await asyncio.sleep(5)
            iteration += 1
        
        # Validate that conflicts were detected and resolved
        assert conflict_detected, "Expected conflicts were not detected"
        assert conflicts_resolved, "Conflicts were not resolved"
        
        final_state = await self._get_final_workflow_state(orchestrator, workflow_id)
        
        # Ensure all conflicts were resolved
        assert len(final_state.active_conflicts) == 0, f"Unresolved conflicts: {final_state.active_conflicts}"
        
        print(f"✅ Conflict resolution workflow completed successfully")
        print(f"   Conflicts detected: {len(final_state.conflicts)}")
        print(f"   Conflicts resolved: {len(final_state.resolved_conflicts)}")
    
    @pytest.mark.asyncio 
    async def test_complex_multi_clause_amendment(self, orchestrator, sample_contract, three_party_config):
        """Test complex amendment affecting multiple contract sections"""
        
        complex_changes = {
            "scope_expansion": {
                "section": "1. SERVICES",
                "old_value": "software development services as specified in Exhibit A",
                "new_value": "software development, testing, deployment, and 6-month maintenance services as specified in Exhibits A, B, and C"
            },
            "payment_restructure": {
                "section": "2. PAYMENT TERMS", 
                "changes": [
                    {
                        "clause": "base_amount",
                        "old_value": "$100,000",
                        "new_value": "$150,000"
                    },
                    {
                        "clause": "payment_schedule",
                        "old_value": "upon completion",
                        "new_value": "25% upfront, 25% at 50% completion, 25% at delivery, 25% after 30-day warranty"
                    },
                    {
                        "clause": "penalty_clause",
                        "content": "Late delivery penalty: 1% of remaining payment per week delayed"
                    }
                ]
            },
            "term_extension": {
                "section": "3. TERM",
                "old_value": "December 31, 2024",
                "new_value": "June 30, 2025 for development, plus 6-month maintenance period ending December 31, 2025"
            },
            "new_governance": {
                "section": "8. PROJECT GOVERNANCE",
                "content": """
                8.1 Steering Committee: Monthly meetings with representatives from all parties
                8.2 Change Control: All scope changes require written approval from steering committee
                8.3 Reporting: Weekly status reports and monthly executive summaries
                8.4 Escalation: Issues escalated to steering committee within 48 hours
                """
            },
            "compliance_requirements": {
                "section": "9. COMPLIANCE",
                "content": """
                9.1 All parties must maintain SOC 2 Type II certification
                9.2 GDPR compliance required for all data handling
                9.3 Annual security audits with shared results
                """
            }
        }
        
        # Add a more risk-averse party to create interesting dynamics
        enhanced_config = three_party_config.copy()
        enhanced_config[0]["policies"]["risk_tolerance"] = "very_low"
        enhanced_config[0]["policies"]["required_clauses"].extend([
            "penalty_caps", "change_control", "compliance_certification"
        ])
        
        workflow_id = await orchestrator.initiate_amendment(
            contract_id="test_contract_003",
            parties=enhanced_config,
            proposed_changes=complex_changes,
            original_contract=sample_contract,
            workflow_config={
                "timeout_minutes": 120,
                "require_legal_review": True,
                "enable_ai_mediation": True
            }
        )
        
        # Monitor for complex workflow patterns
        workflow_events = []
        max_iterations = 48  # 4 minutes
        iteration = 0
        
        while iteration < max_iterations:
            status = await orchestrator.get_workflow_status(workflow_id)
            current_status = status.get("status")
            
            # Track significant events
            if current_status not in [e.get("status") for e in workflow_events[-3:]]:
                workflow_events.append({
                    "status": current_status,
                    "timestamp": datetime.utcnow(),
                    "conflicts": status.get("conflicts", 0),
                    "progress": status.get("progress", 0)
                })
                print(f"📊 Workflow progress: {current_status} ({status.get('progress', 0):.1f}%)")
            
            if current_status in ["completed", "approved", "failed"]:
                break
                
            await asyncio.sleep(5)
            iteration += 1
        
        final_state = await self._get_final_workflow_state(orchestrator, workflow_id)
        
        # Validate complex workflow completion
        assert final_state.status in [AmendmentStatus.COMPLETED, AmendmentStatus.APPROVED]
        assert final_state.legal_review_status == "approved", "Legal review should be completed"
        
        # Check that all major workflow stages were hit
        statuses_seen = [e["status"] for e in workflow_events]
        expected_stages = ["initiated", "under_review", "legal_review"]
        
        for stage in expected_stages:
            assert stage in statuses_seen, f"Missing expected workflow stage: {stage}"
        
        # Validate final document complexity
        assert final_state.final_document is not None
        assert len(final_state.final_document) > len(sample_contract), "Final document should be more comprehensive"
        
        print(f"✅ Complex multi-clause amendment completed")
        print(f"   Workflow stages: {len(workflow_events)}")
        print(f"   Final document length: {len(final_state.final_document)} characters")
        print(f"   Execution history: {len(final_state.execution_history)} steps")
    
    @pytest.mark.asyncio
    async def test_workflow_error_recovery(self, orchestrator, sample_contract, three_party_config):
        """Test workflow error handling and recovery mechanisms"""
        
        # Create a scenario likely to cause errors (invalid changes)
        problematic_changes = {
            "invalid_section": {
                "section": "999. NONEXISTENT",
                "content": "This section doesn't exist"
            },
            "contradictory_terms": {
                "section": "2. PAYMENT TERMS",
                "old_value": "Net 30 days", 
                "new_value": "Immediate payment AND Net 60 days"  # Contradiction
            }
        }
        
        # Add a party with impossible constraints
        error_prone_config = three_party_config.copy()
        error_prone_config.append({
            "id": "company_d",
            "organization": "Company D",
            "policies": {
                "risk_tolerance": "none",  # Invalid value
                "budget_limit": -1000,     # Impossible constraint
                "prohibited_clauses": ["all_clauses"],  # Impossible constraint
                "required_clauses": ["contradictory_clause_a", "contradictory_clause_b"]
            }
        })
        
        workflow_id = await orchestrator.initiate_amendment(
            contract_id="test_contract_004",
            parties=error_prone_config, 
            proposed_changes=problematic_changes,
            original_contract=sample_contract,
            workflow_config={"max_retries": 3}
        )
        
        # Monitor for error handling
        max_iterations = 20
        iteration = 0
        errors_encountered = False
        recovery_attempted = False
        
        while iteration < max_iterations:
            status = await orchestrator.get_workflow_status(workflow_id)
            current_status = status.get("status")
            
            if current_status == "failed":
                errors_encountered = True
                print(f"💥 Expected failure encountered")
                break
            elif "error" in status:
                errors_encountered = True
                recovery_attempted = True
                print(f"🔄 Error recovery in progress")
            
            await asyncio.sleep(5)
            iteration += 1
        
        # Validate error handling
        assert errors_encountered, "Expected errors were not encountered"
        
        final_state = await self._get_final_workflow_state(orchestrator, workflow_id)
        
        # Check that errors were properly logged
        assert len(final_state.errors) > 0, "Errors should be logged in state"
        
        # Validate retry attempts
        assert final_state.retry_count > 0, "Retry mechanism should have been triggered"
        
        print(f"✅ Error handling workflow completed")
        print(f"   Errors logged: {len(final_state.errors)}")
        print(f"   Retry attempts: {final_state.retry_count}")
    
    async def _get_final_workflow_state(self, orchestrator, workflow_id: str) -> AmendmentWorkflowState:
        """Helper to get final workflow state"""
        config = {"configurable": {"thread_id": workflow_id}}
        
        try:
            state_snapshot = orchestrator.workflow.get_state(config)
            if state_snapshot and state_snapshot.values:
                return AmendmentWorkflowState.from_dict(state_snapshot.values)
        except Exception as e:
            print(f"Warning: Could not retrieve final state: {str(e)}")
        
        # Return minimal state if retrieval fails
        return AmendmentWorkflowState(
            workflow_id=workflow_id,
            contract_id="unknown",
            status=AmendmentStatus.FAILED
        )


# Test runner convenience
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])