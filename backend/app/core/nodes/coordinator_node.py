# backend/core/nodes/coordinator_node.py
"""
Coordinator Node for LangGraph Amendment Workflow

The coordinator node orchestrates the entire multi-party amendment process,
making routing decisions and managing the overall workflow state.
"""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from datetime import datetime, timedelta
import json

from ..graph_state import AmendmentWorkflowState, AmendmentStatus
from ..tools.contract_tools import get_contract_tools


class CoordinatorNode:
    """
    Central coordinator node that manages the amendment workflow
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.2)
        self.tools = get_contract_tools()
        
    async def __call__(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """
        Main coordinator logic that determines next steps and routing
        """
        print(f"🎯 COORDINATOR: Processing workflow {state.workflow_id} - Status: {state.status}")
        
        start_time = datetime.utcnow()
        
        try:
            # Update workflow metrics
            if state.metrics.start_time:
                state.metrics.current_duration = (start_time - state.metrics.start_time).total_seconds()
            
            # Route based on current status
            if state.status == AmendmentStatus.INITIATED:
                result = await self._handle_initiation(state)
            elif state.status == AmendmentStatus.PARTIES_NOTIFIED:
                result = await self._handle_party_notification(state)
            elif state.status == AmendmentStatus.UNDER_REVIEW:
                result = await self._handle_review_coordination(state)
            elif state.status == AmendmentStatus.CONFLICTS_DETECTED:
                result = await self._handle_conflict_coordination(state)
            elif state.status == AmendmentStatus.CONSENSUS_BUILDING:
                result = await self._handle_consensus_coordination(state)
            else:
                result = await self._handle_default_coordination(state)
            
            # Log execution
            duration = (datetime.utcnow() - start_time).total_seconds()
            state.log_execution("coordinator", state.to_dict(), result, duration, True)
            
            return result
            
        except Exception as e:
            # Error handling
            error_info = {
                "node": "coordinator",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            state.errors.append(error_info)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            state.log_execution("coordinator", state.to_dict(), {"error": str(e)}, duration, False)
            
            return {
                "status": AmendmentStatus.FAILED,
                "error": str(e),
                "next_action": "error_handling"
            }
    
    async def _handle_initiation(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
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
        
        # Estimate workflow complexity and timeline
        complexity_score = await self._assess_workflow_complexity(state)
        estimated_duration = self._calculate_estimated_duration(complexity_score, len(state.parties))
        
        state.metrics.estimated_completion = datetime.utcnow() + timedelta(minutes=estimated_duration)
        
        # Set up party notification requirements
        state.required_approvals = state.parties.copy()
        
        # Update status and determine next step
        state.update_status(AmendmentStatus.PARTIES_NOTIFIED, "Workflow initiated, moving to party notification")
        
        return {
            "next_action": "notify_parties",
            "complexity_score": complexity_score,
            "estimated_duration_minutes": estimated_duration,
            "parties_to_notify": state.parties
        }
    
    async def _handle_party_notification(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Coordinate party notifications"""
        print(f"📢 Coordinating notifications to {len(state.parties)} parties...")
        
        state.update_status(AmendmentStatus.UNDER_REVIEW, "All parties notified, under review")
        
        return {
            "next_action": "party_review",
            "waiting_for_parties": state.parties,
            "review_deadline": (datetime.utcnow() + timedelta(hours=48)).isoformat()
        }
    
    async def _handle_review_coordination(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Coordinate the review process"""
        print("👥 Coordinating party reviews...")
        
        # All parties have responded, check for conflicts
        if await self._has_conflicts(state):
            state.update_status(AmendmentStatus.CONFLICTS_DETECTED, "Conflicts detected in party responses")
            return {
                "next_action": "conflict_resolution",
                "conflicts_found": len(state.conflicts)
            }
        elif state.is_consensus_reached():
            state.update_status(AmendmentStatus.CONSENSUS_BUILDING, "Consensus reached, building final agreement")
            return {
                "next_action": "build_consensus",
                "consensus_status": "achieved"
            }
        else:
            # Mixed responses, need negotiation
            return {
                "next_action": "facilitate_negotiation",
                "negotiation_required": True
            }
    
    async def _handle_conflict_coordination(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Coordinate conflict resolution"""
        print(f"⚠️  Coordinating resolution of {len(state.active_conflicts)} conflicts...")
        
        # Prioritize conflicts by severity
        high_priority_conflicts = [
            c for c in state.conflicts 
            if c.severity == "high" and c.resolution_status == "unresolved"
        ]
        
        if high_priority_conflicts:
            return {
                "next_action": "resolve_high_priority_conflicts",
                "high_priority_count": len(high_priority_conflicts),
                "requires_human_intervention": True
            }
        
        # Check if all conflicts are resolved
        if not state.has_active_conflicts():
            state.update_status(AmendmentStatus.CONSENSUS_BUILDING, "All conflicts resolved")
            return {
                "next_action": "build_consensus",
                "resolution_complete": True
            }
        
        return {
            "next_action": "continue_conflict_resolution",
            "remaining_conflicts": len(state.active_conflicts)
        }
    
    async def _handle_consensus_coordination(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Coordinate consensus building"""
        print("🤝 Building consensus...")
        
        # Check if we have true consensus
        if state.is_consensus_reached() and not state.has_active_conflicts():
            state.update_status(AmendmentStatus.LEGAL_REVIEW, "Consensus achieved, moving to legal review")
            return {
                "next_action": "legal_review",
                "consensus_achieved": True
            }
        
        return {
            "next_action": "continue_consensus_building",
            "consensus_percentage": self._calculate_consensus_percentage(state)
        }
    
    async def _handle_default_coordination(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Handle other coordination scenarios"""
        print(f"🔄 Default coordination for status: {state.status}")
        
        # Determine next action based on current state
        if state.status == AmendmentStatus.LEGAL_REVIEW:
            return {"next_action": "legal_compliance_check"}
        elif state.status == AmendmentStatus.FINAL_APPROVAL:
            return {"next_action": "final_document_generation"}
        elif state.status == AmendmentStatus.APPROVED:
            return {"next_action": "complete_workflow"}
        
        return {"next_action": "monitor_progress"}
    
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
    
    async def _assess_workflow_complexity(self, state: AmendmentWorkflowState) -> float:
        """Assess the complexity of the amendment workflow"""
        complexity_factors = {
            "party_count": len(state.parties) * 0.2,
            "change_count": len(state.proposed_changes) * 0.15,
            "contract_length": len(state.original_contract or "") / 10000 * 0.1,
            "regulatory_complexity": 0.3 if state.workflow_config.get("require_legal_review") else 0.1
        }
        
        base_complexity = sum(complexity_factors.values())
        
        # Analyze proposed changes for complexity
        if state.proposed_changes:
            complexity_prompt = f"""
            Rate the complexity of these contract amendments on a scale of 1-10:
            {json.dumps(state.proposed_changes, indent=2)}
            
            Consider:
            - Legal complexity
            - Business impact
            - Implementation difficulty
            - Risk level
            
            Return only a number from 1-10.
            """
            
            messages = [
                SystemMessage(content="You are an expert contract analyst."),
                HumanMessage(content=complexity_prompt)
            ]
            
            try:
                response = await self.llm.ainvoke(messages)
                llm_complexity = float(response.content.strip()) / 10
                base_complexity += llm_complexity * 0.3
            except Exception as e:
                print(f"Error analyzing complexity: {e}")
                base_complexity += 0.5  # Default moderate complexity
        
        return min(base_complexity, 1.0)  # Cap at 1.0
    
    def _calculate_estimated_duration(self, complexity: float, party_count: int) -> int:
        """Calculate estimated duration in minutes"""
        base_duration = 120  # 2 hours base
        complexity_factor = complexity * 480  # Up to 8 hours for max complexity
        party_factor = (party_count - 2) * 60  # 1 hour per additional party beyond 2
        
        return int(base_duration + complexity_factor + party_factor)
    
    async def _has_conflicts(self, state: AmendmentWorkflowState) -> bool:
        """Check if there are conflicts in party responses"""
        if len(state.party_responses) < 2:
            return False
        
        # Extract all party changes
        party_changes = []
        for party_id, response in state.party_responses.items():
            if response.proposed_changes:
                party_changes.append({
                    "party": party_id,
                    "changes": response.proposed_changes
                })
        
        if len(party_changes) < 2:
            return False
        
        # Use conflict detection tool
        from ..tools.contract_tools import CONTRACT_TOOLS
        conflict_tool = CONTRACT_TOOLS["detect_conflicts"]
        
        result = conflict_tool._run(
            original_contract=state.original_contract or "",
            proposed_changes=party_changes
        )
        
        # Add detected conflicts to state
        if result.get("conflicts"):
            from ..graph_state import ConflictInfo
            for conflict_data in result["conflicts"]:
                conflict = ConflictInfo(
                    conflict_type=conflict_data.get("type", "unknown"),
                    description=conflict_data.get("description", ""),
                    affected_parties=conflict_data.get("affected_parties", []),
                    affected_clauses=conflict_data.get("affected_clauses", []),
                    severity=conflict_data.get("severity", "medium"),
                    resolution_suggestions=conflict_data.get("resolution_suggestions", [])
                )
                state.add_conflict(conflict)
        
        return len(state.conflicts) > 0
    
    def _calculate_consensus_percentage(self, state: AmendmentWorkflowState) -> float:
        """Calculate consensus percentage"""
        if not state.parties:
            return 0.0
        
        approved_count = sum(
            1 for response in state.party_responses.values()
            if response.status == "approved"
        )
        
        return (approved_count / len(state.parties)) * 100
    
    def determine_next_node(self, state: AmendmentWorkflowState) -> str:
        """Determine which node should execute next"""
        
        if state.status == AmendmentStatus.PARTIES_NOTIFIED:
            return "party_agents"
        elif state.status == AmendmentStatus.CONFLICTS_DETECTED:
            return "conflict_resolution"
        elif state.status == AmendmentStatus.LEGAL_REVIEW:
            return "legal_compliance"
        elif state.status == AmendmentStatus.CONSENSUS_BUILDING:
            return "version_control"
        elif state.status == AmendmentStatus.FINAL_APPROVAL:
            return "final_approval"
        else:
            return "monitor"


def create_coordinator_node() -> CoordinatorNode:
    """Factory function to create coordinator node"""
    return CoordinatorNode()