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
from datetime import datetime, timedelta, timezone

from .graph_state import AmendmentWorkflowState, AmendmentStatus
from .nodes.party_node import PartyAgentNode
from langchain_core.messages import SystemMessage, HumanMessage
import json
from .nodes.conflict_resolution_node import ConflictResolutionNode

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
        workflow.add_node("initiator", self._initiator_node)
        workflow.add_node("party_notified", self._party_notified_node)
        workflow.add_node("party_review", self._party_review_node)
        workflow.add_node("conflict_resolution", self._conflict_resolution_node)
        # workflow.add_node("consensus_building", self._consensus_building_node)
        workflow.add_node("legal_review", self._legal_review_node)
        workflow.add_node("version_control", self._version_control_node)
        workflow.add_node("final_approval", self._final_approval_node)
        workflow.add_node("completion", self._completion_node)
        workflow.add_node("error_handler", self._error_handler_node)

        # Set entry point
        workflow.set_entry_point("initiator")
        
        # Add edges from initiator
        workflow.add_edge("initiator", "party_notified")
        workflow.add_edge("party_notified", "party_review")
        workflow.add_edge("party_review", "conflict_resolution")
        # workflow.add_edge("conflict_resolution", "consensus_building")
        workflow.add_edge("conflict_resolution", "legal_review")
        workflow.add_edge("legal_review", "version_control")
        workflow.add_edge("version_control", "final_approval")
        workflow.add_edge("final_approval", "completion")
        workflow.add_edge("completion", END)
        workflow.add_edge("error_handler", END)
        
        # Compile the workflow
        self.workflow = workflow.compile(checkpointer=self.memory)
    
    async def initiate_amendment(self, 
                               workflow_id: str,
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
            workflow_id=workflow_id,
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
                    "parties_status": {
                        party_id: response.status 
                        for party_id, response in current_state.party_responses.items()
                    },
                    "conflicts": len(current_state.active_conflicts),
                    "created_at": current_state.created_at.isoformat(),
                    "updated_at": current_state.updated_at.isoformat(),
                    # "estimated_completion": current_state.metrics.estimated_completion.isoformat() if current_state.metrics.estimated_completion else None
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
        state.current_step = "party_notified"
        state.update_status(AmendmentStatus.UNDER_REVIEW, notes = "Party Agents have to review the Amendment Changes")
        return state

    async def _initiator_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:

        """Handle workflow initiation"""
        print("📋 Handling workflow initiation...")
        
        # Validate that we have all required information
        if not state.parties:
            return {"error": "No parties specified for amendment"}
        
        if not state.proposed_changes:
            return {"error": "No proposed changes specified"}
        
        # Analyze the original contract if provided
        if state.original_contract:
            analysis_result = await self._analyze_contract_context(state)
            state.node_outputs["contract_analysis"] = analysis_result
        
        # Set up party notification requirements
        state.required_approvals = state.parties.copy()
        
        # Update status and determine next step
        state.update_status(AmendmentStatus.PARTIES_NOTIFIED, "Workflow initiated, moving to party notification")
        
        return state

    # def _calculate_estimated_duration(self, complexity: float, party_count: int) -> int:
    #     """Calculate estimated duration in minutes"""
    #     base_duration = 120  # 2 hours base
    #     complexity_factor = complexity * 480  # Up to 8 hours for max complexity
    #     party_factor = (party_count - 2) * 60  # 1 hour per additional party beyond 2
        
    #     return int(base_duration + complexity_factor + party_factor)
    
    async def _analyze_contract_context(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Analyze the original contract to understand context"""
        analysis_prompt = f"""
        Analyze this contract to understand the context for proposed amendments:
        
        Original Contract:
        {state.original_contract[:2000]}...
        
        Proposed Changes:
        {json.dumps(state.proposed_changes, indent=2)}
        
        Parties Involved:
        {state.parties}
        
        Provide analysis in JSON format:
        {{
            "contract_type": "type of contract",
            "complexity_indicators": ["factors that make this complex"],
            "amendment_areas": ["areas being modified"],
            "potential_risks": ["risks to watch for"],
            "stakeholder_impact": {{
                "party": "impact description"
            }},
            "recommended_review_time": "estimated time needed"
        }}
        """
        
        messages = [
            SystemMessage(content="You are an expert contract analyst."),
            HumanMessage(content=analysis_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_analysis": response.content}
    
    # async def _assess_workflow_complexity(self, state: AmendmentWorkflowState) -> float:
    #     """Assess the complexity of the amendment workflow"""
    #     complexity_factors = {
    #         "party_count": len(state.parties) * 0.2,
    #         "change_count": len(state.proposed_changes) * 0.15,
    #         "contract_length": len(state.original_contract or "") / 10000 * 0.1,
    #         "regulatory_complexity": 0.3 if state.workflow_config.get("require_legal_review") else 0.1
    #     }
        
    #     base_complexity = sum(complexity_factors.values())
        
    #     # Analyze proposed changes for complexity
    #     if state.proposed_changes:
    #         complexity_prompt = f"""
    #         Rate the complexity of these contract amendments on a scale of 1-10:
    #         {json.dumps(state.proposed_changes, indent=2)}
            
    #         Consider:
    #         - Legal complexity
    #         - Business impact
    #         - Implementation difficulty
    #         - Risk level
            
    #         Return only a number from 1-10.
    #         """
            
    #         messages = [
    #             SystemMessage(content="You are an expert contract analyst."),
    #             HumanMessage(content=complexity_prompt)
    #         ]
            
    #         try:
    #             response = await self.llm.ainvoke(messages)
    #             llm_complexity = float(response.content.strip()) / 10
    #             base_complexity += llm_complexity * 0.3
    #         except Exception as e:
    #             print(f"Error analyzing complexity: {e}")
    #             base_complexity += 0.5  # Default moderate complexity
        
    #     return min(base_complexity, 1.0)  # Cap at 1.0

        
    async def _party_review_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Party review node - coordinates all party agents"""
        state.review_rounds += 1
        print(f"👥 PARTY REVIEW (Round {state.review_rounds}): Processing {len(state.parties)} parties")

        # Check if the number of review rounds has exceeded the maximum
        max_rounds = state.workflow_config.get("max_review_rounds", 2)
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
        
        # # Update status based on responses
        # if len(state.party_responses) == len(state.parties):
        #     if state.has_active_conflicts():
        #         state.update_status(AmendmentStatus.CONFLICTS_DETECTED)
        #     elif state.is_consensus_reached():
        #         state.update_status(AmendmentStatus.CONSENSUS_BUILDING)
        #     else:
        #         state.update_status(AmendmentStatus.UNDER_REVIEW)
        
        return state
    
    async def _conflict_resolution_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Conflict resolution node"""
        print(f"⚡ CONFLICT RESOLUTION: Resolving {len(state.active_conflicts)} conflicts")
        
        # In a full implementation, this would use sophisticated AI mediation
        conflict_resolution_node = ConflictResolutionNode()
        result = await conflict_resolution_node(state)
        # result = {
        #         "conflicts_processed": len(resolution_results),
        #         "conflicts_resolved": sum(1 for r in resolution_results if r.get("status") == "resolved"),
        #         "remaining_conflicts": len(state.active_conflicts),
        #         "resolution_details": resolution_results
        #     }
        print(result)
        state.update_status(AmendmentStatus.CONSENSUS_BUILDING)
        
        return state

    # async def _consensus_building_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
    #     """Applies the AI-mediated proposal and sends it back for review."""
    #     print("🤝 CONSENSUS BUILDING: Applying AI-mediated changes and preparing for re-review.")

    #     new_changes = state.node_outputs.get("consensus_proposal")

    #     if new_changes:
    #         # Update the main proposed changes with the mediator's solution
    #         state.proposed_changes = new_changes

    #         # Reset party responses to 'pending' to trigger a new review round
    #         for party_id in state.parties:
    #             if party_id in state.party_responses:
    #                 state.party_responses[party_id].status = "pending"
            
    #         # Clear approvals and conflicts as we are starting a new review round
    #         state.received_approvals = []
    #         state.active_conflicts = []
    #         state.conflicts = [] # Optionally clear old conflicts

    #         # Set status to trigger re-review
    #         state.update_status(AmendmentStatus.UNDER_REVIEW, notes="Re-evaluating proposal after AI-mediated resolution.")
    #         print("   New proposal sent to parties for re-evaluation.")
    #     else:
    #         print("   Skipping consensus building as no new proposal was generated.")
    #         # If no new changes, we might need an alternative path, like manual intervention
    #         state.errors.append({"node": "consensus_building", "error": "No consensus proposal found to apply."})

    #     return state
    
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
            state.completed_at = datetime.now(timezone.utc)
        else:
            # Return to coordinator for further processing
            state.update_status(AmendmentStatus.UNDER_REVIEW)
        
        return state
    
    async def _completion_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Workflow completion node"""
        print(f"🎉 COMPLETION: Amendment workflow {state.workflow_id} completed successfully")
        
        state.update_status(AmendmentStatus.COMPLETED)
        state.completed_at = datetime.now(timezone.utc)
        
        return state
    
    async def _error_handler_node(self, state: AmendmentWorkflowState) -> AmendmentWorkflowState:
        """Error handling node"""
        print(f"❌ ERROR HANDLER: Processing errors for workflow {state.workflow_id}")
        
        state.update_status(AmendmentStatus.FAILED)
        
        # Log error details
        error_summary = {
            "error_count": len(state.errors),
            "latest_errors": state.errors[-3:] if state.errors else [],
            "failed_at": datetime.now(timezone.utc).isoformat()
        }
        
        state.node_outputs["error_summary"] = error_summary
        
        return state
    
# Global orchestrator instance
orchestrator = ContractAmendmentOrchestrator()


async def initiate_contract_amendment(
    workflow_id: str,
    contract_id: str,
    parties: List[Dict[str, Any]], 
    proposed_changes: Dict[str, Any],
    original_contract: Optional[str] = None,
    workflow_config: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to initiate contract amendment"""
    
    return await orchestrator.initiate_amendment(
        workflow_id=workflow_id,
        contract_id=contract_id,
        parties=parties,
        proposed_changes=proposed_changes,
        original_contract=original_contract,
        workflow_config=workflow_config
    )


async def get_amendment_status(workflow_id: str) -> Dict[str, Any]:
    """Convenience function to get amendment status"""
    
    return await orchestrator.get_workflow_status(workflow_id)