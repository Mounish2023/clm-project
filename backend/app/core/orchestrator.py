# backend/core/orchestrator.py
"""
Main LangGraph Orchestrator for Contract Amendment Workflow

This module creates and manages the LangGraph workflow that orchestrates
the entire multi-party contract amendment process.
"""

from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
import asyncio
from datetime import datetime

from .graph_state import AmendmentWorkflowState, AmendmentStatus
from .nodes.coordinator_node import CoordinatorNode
from .nodes.party_node import PartyAgentNode


class ContractAmendmentOrchestrator:
    """
    Main orchestrator class that manages the LangGraph workflow
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
        self.memory = MemorySaver()
        self.workflow = None
        self.party_agents: Dict[str, PartyAgentNode] = {}
        self._build_workflow()
    
    def _build_workflow(self):
        """Build the LangGraph workflow"""
        
        # Create the StateGraph
        workflow = StateGraph(AmendmentWorkflowState)
        
        # Add nodes
        workflow.add_node("coordinator", self._coordinator_node)
        workflow.add_node("party_notified", self._party_notified_node)
        workflow.add_node("party_review", self._party_review_node)
        workflow.add_node("conflict_resolution", self._conflict_resolution_node)
        workflow.add_node("consensus_building", self._consensus_building_node)
        workflow.add_node("legal_review", self._legal_review_node)
        workflow.add_node("version_control", self._version_control_node)
        workflow.add_node("final_approval", self._final_approval_node)
        workflow.add_node("completion", self._completion_node)
        workflow.add_node("error_handler", self._error_handler_node)

        # Set entry point
        workflow.set_entry_point("coordinator")
        
        # Add conditional edges from coordinator
        workflow.add_conditional_edges(
            "coordinator",
            self._route_from_coordinator,
            {
                "party_notified": "party_notified",
                "party_review": "party_review",
                "conflict_resolution": "conflict_resolution", 
                "legal_review": "legal_review",
                "version_control": "version_control",
                "final_approval": "final_approval",
                "completion": "completion",
                "error": "error_handler"
            }
        )

        # Add conditional edges from party notified
        workflow.add_conditional_edges(
            "party_notified",
            self._route_from_party_notified,
            {
                "party_review": "party_review",
                "error": "error_handler"
            }
        )
        
        # Add conditional edges from party review
        workflow.add_conditional_edges(
            "party_review",
            self._route_from_party_review,
            {
                "coordinator": "coordinator",
                "conflict_resolution": "conflict_resolution",
                "version_control": "version_control",
                "error": "error_handler"
            }
        )
        
        # Add conditional edges from conflict resolution
        workflow.add_conditional_edges(
            "conflict_resolution",
            self._route_from_conflict_resolution,
            {
                "consensus_building": "consensus_building",
                "coordinator": "coordinator",
                "error": "error_handler"
            }
        )

        # Add edge from consensus building back to party review
        workflow.add_edge("consensus_building", "party_review")
        
        # Add conditional edges from legal review
        workflow.add_conditional_edges(
            "legal_review",
            self._route_from_legal_review, 
            {
                "version_control": "version_control",
                "conflict_resolution": "conflict_resolution",
                "coordinator": "coordinator",
                "error": "error_handler"
            }
        )
        
        # Add conditional edges from version control
        workflow.add_conditional_edges(
            "version_control",
            self._route_from_version_control,
            {
                "final_approval": "final_approval",
                "coordinator": "coordinator",
                "error": "error_handler"
            }
        )
        
        # Simple edges to completion or error handling
        workflow.add_edge("final_approval", "completion")
        workflow.add_edge("error_handler", END)
        workflow.add_edge("completion", END)

        # Compile the workflow
        self.workflow = workflow.compile(checkpointer=self.memory)
    
    async def initiate_amendment(self, 
                               contract_id: str,
                               parties: List[Dict[str, Any]],
                               proposed_changes: Dict[str, Any],
                               original_contract: Optional[str] = None,
                               workflow_config: Optional[Dict[str, Any]] = None) -> str:
        """
        Initiate a new contract amendment workflow
        
        Args:
            contract_id: ID of the contract being amended
            parties: List of party configurations [{"id": "party1", "organization": "Company A", "policies": {...}}]
            proposed_changes: Dictionary of proposed changes
            original_contract: Full text of original contract
            workflow_config: Workflow configuration overrides
            
        Returns:
            workflow_id: ID of the initiated workflow
        """
        
        # Create party agents
        for party_info in parties:
            party_id = party_info["id"]
            organization = party_info["organization"] 
            policies = party_info.get("policies", {})
            
            self.party_agents[party_id] = PartyAgentNode(party_id, organization, policies)
        
        # Create initial state
        initial_state = AmendmentWorkflowState(
            contract_id=contract_id,
            parties=[p["id"] for p in parties],
            proposed_changes=proposed_changes,
            original_contract=original_contract,
            status=AmendmentStatus.INITIATED
        )
        
        if workflow_config:
            initial_state.workflow_config.update(workflow_config)
        
        print(f"🚀 Initiating amendment workflow {initial_state.workflow_id}")
        print(f"   Contract: {contract_id}")
        print(f"   Parties: {[p['organization'] for p in parties]}")
        print(f"   Changes: {len(proposed_changes)} proposed changes")
        
        # Run the workflow
        config = {"configurable": {"thread_id": initial_state.workflow_id}}
        
        try:
            async for output in self.workflow.astream(initial_state.to_dict(), config):
                # Log intermediate outputs
                for node_name, node_output in output.items():
                    print(f"   ✅ {node_name}: {node_output.get('action', 'processed')}")
                    
                    # Update party responses if this was a party node
                    if node_name == "party_review" and "party_responses" in node_output:
                        for party_id, response in node_output["party_responses"].items():
                            initial_state.add_party_response(party_id, response)
        except Exception as e:
            print(f"   ❌ Workflow error: {str(e)}")
            raise
        
        return initial_state.workflow_id
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get current status of a workflow"""
        
        config = {"configurable": {"thread_id": workflow_id}}
        
        try:
            # Get the latest state
            state_snapshot = self.workflow.get_state(config)
            if state_snapshot and state_snapshot.values:
                current_state = AmendmentWorkflowState.from_dict(state_snapshot.values)
                
                return {
                    "workflow_id": workflow_id,
                    "status": current_state.status,
                    "progress": current_state.calculate_progress(),
                    "parties_status": {
                        party_id: response.status 
                        for party_id, response in current_state.party_responses.items()
                    },
                    "conflicts": len(current_state.active_conflicts),
                    "created_at": current_state.created_at.isoformat(),
                    "updated_at": current_state.updated_at.isoformat(),
                    "estimated_completion": current_state.metrics.estimated_completion.isoformat() if current_state.metrics.estimated_completion else None
                }
        except Exception as e:
            return {"error": str(e), "workflow_id": workflow_id}
        
        return {"error": "Workflow not found", "workflow_id": workflow_id}
    
    async def resume_workflow(self, workflow_id: str, updates: Optional[Dict[str, Any]] = None) -> bool:
        """Resume a paused or interrupted workflow"""
        
        config = {"configurable": {"thread_id": workflow_id}}
        
        try:
            # Get current state
            state_snapshot = self.workflow.get_state(config)
            if not state_snapshot or not state_snapshot.values:
                return False
            
            current_state = AmendmentWorkflowState.from_dict(state_snapshot.values)
            
            # Apply updates if provided
            if updates:
                for key, value in updates.items():
                    if hasattr(current_state, key):
                        setattr(current_state, key, value)
            
            # Resume workflow
            async for output in self.workflow.astream(None, config):
                for node_name, node_output in output.items():
                    print(f"   🔄 {node_name}: {node_output.get('action', 'processed')}")
            
            return True
            
        except Exception as e:
            print(f"Resume error: {str(e)}")
            return False
    
    # Node implementations
    async def _party_notified_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Party notified node implementation"""
        state.update_status(AmendmentStatus.UNDER_REVIEW, notes = "Party Agents have to review the Amendment Changes")
        return state

    async def _coordinator_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Coordinator node implementation"""
        coordinator = CoordinatorNode()
        result = await coordinator(state)
        
        # Update state based on coordinator output
        if "next_action" in result:
            state.next_steps = [result["next_action"]]
        
        return state

    # async def _wait_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
    #     pending = state.get_pending_parties() if hasattr(state, "get_pending_parties") else []
    #     print(f"⏸️ WAIT: Pending party responses: {pending if pending else 'unknown'}")
    #     # Do not change status; just return to halt execution (END edge will stop the graph run)
    #     return state
        
    async def _party_review_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Party review node - coordinates all party agents"""
        state.review_rounds += 1
        print(f"👥 PARTY REVIEW (Round {state.review_rounds}): Processing {len(state.parties)} parties")

        # Check if the number of review rounds has exceeded the maximum
        max_rounds = state.workflow_config.get("max_review_rounds", 5)
        if state.review_rounds > max_rounds:
            print(f"   ❌ ERROR: Maximum review rounds ({max_rounds}) exceeded.")
            state.errors.append({"node": "party_review", "error": "Maximum review rounds exceeded."})
            state.update_status(AmendmentStatus.FAILED, notes="Consensus could not be reached within the allowed number of rounds.")
            return state

        pending_parties = state.get_pending_parties() if hasattr(state, "get_pending_parties") else state.parties
        print(f"   Pending parties: {pending_parties}")
        # Run all party agents concurrently
        party_tasks = []
        for party_id in pending_parties:
            if party_id in self.party_agents:
                party_agent = self.party_agents[party_id]
                task = party_agent(state)
                party_tasks.append(task)
        
        if party_tasks:
            # Wait for all parties to respond
            party_results = await asyncio.gather(*party_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(party_results):
                if isinstance(result, Exception):
                    print(f"   ❌ Party {state.parties[i]} error: {str(result)}")
                else:
                    print(f"   ✅ Party {result.get('organization', 'Unknown')}: {result.get('decision', 'No decision')}")
        
        # Update status based on responses
        if len(state.party_responses) == len(state.parties):
            if state.has_active_conflicts():
                state.update_status(AmendmentStatus.CONFLICTS_DETECTED)
            elif state.is_consensus_reached():
                state.update_status(AmendmentStatus.CONSENSUS_BUILDING)
            else:
                state.update_status(AmendmentStatus.UNDER_REVIEW)
        
        return state
    
    async def _conflict_resolution_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Conflict resolution node"""
        print(f"⚡ CONFLICT RESOLUTION: Resolving {len(state.active_conflicts)} conflicts")
        
        # In a full implementation, this would use sophisticated AI mediation
        conflict_resolution_prompt = f"""
        You are an AI mediator resolving contract amendment conflicts.
        
        Active Conflicts:
        {[c.description for c in state.conflicts if c.resolution_status == 'unresolved']}
        
        Party Positions:
        {[(p.organization, p.status, p.comments) for p in state.party_responses.values()]}
        
        Based on the conflicts and party positions, generate a new set of proposed changes as a JSON object that merges the positions and resolves the conflicts. The JSON output should be in the same format as the original 'proposed_changes'.
        
        Return ONLY the JSON object of the new proposed changes.
        Example format: {{"clause_1.1": "New text for clause 1.1..."}}
        """
        
        # Use LLM to generate resolution suggestions
        from langchain.schema import HumanMessage, SystemMessage
        import json

        messages = [
            SystemMessage(content="You are an expert contract mediator specializing in multi-party negotiations. Your task is to generate a revised set of contract changes to build consensus."),
            HumanMessage(content=conflict_resolution_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            # The LLM should return a JSON string of the new proposed changes
            new_changes = json.loads(response.content)
            # Store the new changes in a temporary field in the state
            state.node_outputs["consensus_proposal"] = new_changes
            print(f"   AI Mediator proposed new changes: {new_changes}")
        except json.JSONDecodeError:
            print("   Error: AI mediator did not return valid JSON for new changes.")
            state.errors.append({"node": "conflict_resolution", "error": "Failed to parse new changes from LLM."})

        state.update_status(AmendmentStatus.CONSENSUS_BUILDING)
        
        return state

    async def _consensus_building_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Applies the AI-mediated proposal and sends it back for review."""
        print("🤝 CONSENSUS BUILDING: Applying AI-mediated changes and preparing for re-review.")

        new_changes = state.node_outputs.get("consensus_proposal")

        if new_changes:
            # Update the main proposed changes with the mediator's solution
            state.proposed_changes = new_changes

            # Reset party responses to 'pending' to trigger a new review round
            for party_id in state.parties:
                if party_id in state.party_responses:
                    state.party_responses[party_id].status = "pending"
            
            # Clear approvals and conflicts as we are starting a new review round
            state.received_approvals = []
            state.active_conflicts = []
            state.conflicts = [] # Optionally clear old conflicts

            # Set status to trigger re-review
            state.update_status(AmendmentStatus.UNDER_REVIEW, notes="Re-evaluating proposal after AI-mediated resolution.")
            print("   New proposal sent to parties for re-evaluation.")
        else:
            print("   Skipping consensus building as no new proposal was generated.")
            # If no new changes, we might need an alternative path, like manual intervention
            state.errors.append({"node": "consensus_building", "error": "No consensus proposal found to apply."})

        return state
    
    async def _legal_review_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Legal compliance review node"""
        print("⚖️  LEGAL REVIEW: Checking compliance and legal requirements")
        
        # Use compliance checking tool
        from .tools.contract_tools import CONTRACT_TOOLS
        compliance_tool = CONTRACT_TOOLS["check_compliance"]
        
        # Perform compliance check
        compliance_result = compliance_tool._run(
            contract_content=state.original_contract or "",
            jurisdiction="US", # This would come from contract metadata
            contract_type="service_agreement", # This would be detected
            regulations=["GDPR", "SOX"] # This would be determined based on parties
        )
        
        state.compliance_checks = compliance_result
        
        if compliance_result.get("compliance_status") == "compliant":
            state.legal_review_status = "approved"
            state.update_status(AmendmentStatus.FINAL_APPROVAL)
        else:
            state.legal_review_status = "requires_changes"
            # Would typically route back to conflict resolution or party review
        
        return state
    
    async def _version_control_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Version control and document merging node"""
        print("📝 VERSION CONTROL: Merging approved changes")
        
        # Collect all approved changes
        approved_changes = []
        for party_id, response in state.party_responses.items():
            if response.status == "approved":
                if response.proposed_changes:
                    approved_changes.append({
                        "party": party_id,
                        "changes": response.proposed_changes
                    })
        
        if approved_changes:
            # Use amendment merging tool
            from .tools.contract_tools import CONTRACT_TOOLS
            merge_tool = CONTRACT_TOOLS["merge_amendments"]
            
            merge_result = merge_tool._run(
                base_contract=state.original_contract or "",
                approved_changes=approved_changes,
                merge_strategy="balanced"
            )
            
            # Create new document version
            from .graph_state import DocumentVersion
            import hashlib
            
            merged_content = merge_result.get("merged_contract", "")
            version = DocumentVersion(
                content=merged_content,
                content_hash=hashlib.md5(merged_content.encode()).hexdigest(),
                author="system_merge",
                changes_summary=f"Merged {len(approved_changes)} approved amendments"
            )
            
            state.add_document_version(version)
            state.final_document = merged_content
        
        state.update_status(AmendmentStatus.FINAL_APPROVAL)
        return state
    
    async def _final_approval_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Final approval node"""
        print("✅ FINAL APPROVAL: Completing amendment process")
        
        # Perform final validation
        if (state.is_consensus_reached() and 
            not state.has_active_conflicts() and 
            state.legal_review_status == "approved" and
            state.final_document):
            
            state.update_status(AmendmentStatus.APPROVED)
            state.completed_at = datetime.utcnow()
        else:
            # Return to coordinator for further processing
            state.update_status(AmendmentStatus.UNDER_REVIEW)
        
        return state
    
    async def _completion_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Workflow completion node"""
        print(f"🎉 COMPLETION: Amendment workflow {state.workflow_id} completed successfully")
        
        state.update_status(AmendmentStatus.COMPLETED)
        state.completed_at = datetime.utcnow()
        
        # Calculate final metrics
        state.metrics.current_duration = (
            state.completed_at - state.metrics.start_time
        ).total_seconds()
        state.metrics.progress_percentage = 100.0
        
        return state
    
    async def _error_handler_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Error handling node"""
        print(f"❌ ERROR HANDLER: Processing errors for workflow {state.workflow_id}")
        
        state.update_status(AmendmentStatus.FAILED)
        
        # Log error details
        error_summary = {
            "error_count": len(state.errors),
            "latest_errors": state.errors[-3:] if state.errors else [],
            "failed_at": datetime.utcnow().isoformat()
        }
        
        state.node_outputs["error_summary"] = error_summary
        
        return state
    
    # Routing conditions
    def _route_from_coordinator(self, state: AmendmentWorkflowState) -> str:
        """Route from coordinator based on state"""

        if state.status == AmendmentStatus.PARTIES_NOTIFIED:
            return "party_notified"
        elif state.status == AmendmentStatus.UNDER_REVIEW:
            return "party_review"
        elif state.status == AmendmentStatus.CONFLICTS_DETECTED:
            return "conflict_resolution"
        elif state.status == AmendmentStatus.LEGAL_REVIEW:
            return "legal_review"
        elif state.status == AmendmentStatus.CONSENSUS_BUILDING:
            return "version_control"
        elif state.status == AmendmentStatus.FINAL_APPROVAL:
            return "final_approval"
        elif state.status in [AmendmentStatus.APPROVED, AmendmentStatus.COMPLETED]:
            return "completion"
        elif state.errors:
            return "error"
        else:
            return "party_review"

    def _route_from_party_notified(self, state: AmendmentWorkflowState) -> str:
        """Route from party notified based on responses"""
        if state.status == AmendmentStatus.UNDER_REVIEW:
            return "party_review"
        elif state.errors:
            return "error"
        else:
            return "coordinator"

    def _route_from_party_review(self, state: AmendmentWorkflowState) -> str:
        """Route from party review based on responses"""
        pending_parties = state.get_pending_parties()

        if state.has_active_conflicts():
            return "conflict_resolution"
        elif state.is_consensus_reached():
            return "version_control"
        elif pending_parties:
            return END
        elif state.errors:
            return "error"
        else:
            return "coordinator"

    def _route_from_conflict_resolution(self, state: AmendmentWorkflowState) -> str:
        """Route from conflict resolution"""
        if state.errors:
            return "error"
        if state.status == AmendmentStatus.CONSENSUS_BUILDING:
            return "consensus_building"
        else:
            # This case should ideally not be hit if the node works correctly
            return "coordinator"
    
    def _route_from_legal_review(self, state: AmendmentWorkflowState) -> str:
        """Route from legal review"""
        
        if state.legal_review_status == "approved":
            return "version_control"
        elif state.legal_review_status == "requires_changes":
            return "conflict_resolution"
        elif state.errors:
            return "error"
        else:
            return "coordinator"
    
    def _route_from_version_control(self, state: AmendmentWorkflowState) -> str:
        """Route from version control"""
        
        if state.final_document and state.is_consensus_reached():
            return "final_approval"
        elif state.errors:
            return "error"
        else:
            return "coordinator"


# Global orchestrator instance
orchestrator = ContractAmendmentOrchestrator()


async def initiate_contract_amendment(
    contract_id: str,
    parties: List[Dict[str, Any]], 
    proposed_changes: Dict[str, Any],
    original_contract: Optional[str] = None,
    workflow_config: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to initiate contract amendment"""
    
    return await orchestrator.initiate_amendment(
        contract_id=contract_id,
        parties=parties,
        proposed_changes=proposed_changes,
        original_contract=original_contract,
        workflow_config=workflow_config
    )


async def get_amendment_status(workflow_id: str) -> Dict[str, Any]:
    """Convenience function to get amendment status"""
    
    return await orchestrator.get_workflow_status(workflow_id)