# backend/core/nodes/conflict_resolution_node.py
"""
Conflict Resolution Node for LangGraph Amendment Workflow

This node handles the detection, analysis, and resolution of conflicts
between different parties' proposed changes using AI mediation.
"""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from datetime import datetime
import json

from ..graph_state import AmendmentWorkflowState, ConflictInfo


class ConflictResolutionNode:
    """
    AI-powered conflict resolution node that mediates disputes between parties
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.4)  # Slightly higher temp for creativity
        # self.tools = get_contract_tools()
        self.mediation_strategies = [
            "compromise_based",
            "value_maximization", 
            "risk_minimization",
            "precedent_based",
            "win_win_optimization"
        ]
    
    async def __call__(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """
        Main conflict resolution logic
        """
        print(f"⚡ CONFLICT RESOLUTION: Processing amendment {state.amendment_id}")
        
        start_time = datetime.utcnow()
        
        try:
            # First, identify any new conflicts from party responses
            self._identify_conflicts(state)

            if not state.active_conflicts:
                print("   No active conflicts to resolve")
                return {"action": "no_conflicts", "message": "No active conflicts found"}
            
            print(f"   Found {len(state.active_conflicts)} active conflicts to resolve.")

            # Categorize conflicts by type and severity
            conflict_analysis = await self._analyze_conflicts(state)
            
            # Apply appropriate resolution strategy for each conflict
            resolution_results = []
            for conflict_id in state.active_conflicts.copy():
                conflict = next((c for c in state.conflicts if c.conflict_id == conflict_id), None)
                if conflict:
                    resolution = await self._resolve_conflict(state, conflict, conflict_analysis)
                    resolution_results.append(resolution)
                    
                    # If resolution successful, mark as resolved
                    if resolution.get("status") == "resolved":
                        state.resolve_conflict(conflict_id, resolution.get("resolution_notes", ""))
            
            # Update workflow status based on resolution results
            # if len(state.active_conflicts) == 0:
            #     state.update_status(AmendmentStatus.CONSENSUS_BUILDING, "All conflicts resolved")
            #     next_action = "build_consensus"
            # else:
            #     next_action = "escalate_conflicts"

            # Log execution
            duration = (datetime.utcnow() - start_time).total_seconds()
            result = {
                "conflicts_processed": len(resolution_results),
                "conflicts_resolved": sum(1 for r in resolution_results if r.get("status") == "resolved"),
                "remaining_conflicts": len(state.active_conflicts),
                "resolution_details": resolution_results
            }
            
            state.log_execution("conflict_resolution", state.to_dict(), result, duration, True)
            
            return result
            
        except Exception as e:
            error_info = {
                "node": "conflict_resolution",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            state.errors.append(error_info)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            state.log_execution("conflict_resolution", state.to_dict(), {"error": str(e)}, duration, False)
            
            return {"action": "error", "error": str(e)}
    
    async def _analyze_conflicts(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """Analyze all conflicts to understand patterns and relationships"""
        
        conflicts_data = []
        for conflict in state.conflicts:
            if conflict.conflict_id in state.active_conflicts:
                conflicts_data.append({
                    "id": conflict.conflict_id,
                    "type": conflict.conflict_type,
                    "description": conflict.description,
                    "severity": conflict.severity,
                    "affected_parties": conflict.affected_parties,
                    "affected_clauses": conflict.affected_clauses
                })
        
        analysis_prompt = f"""
        Analyze these contract amendment conflicts to understand patterns and relationships:
        
        Active Conflicts:
        {json.dumps(conflicts_data, indent=2)}
        
        Party Responses:
        {[(p.organization, p.status, p.comments) for p in state.party_responses.values()]}
        
        Original Proposed Changes:
        {json.dumps(state.proposed_changes, indent=2)}
        
        Provide analysis in JSON format:
        {{
            "conflict_patterns": ["patterns you identify"],
            "root_causes": ["underlying causes of conflicts"],
            "affected_relationships": ["which party relationships are strained"],
            "priority_order": ["conflict_ids in order of resolution priority"],
            "resolution_complexity": {{
                "conflict_id": "simple|moderate|complex"
            }},
            "recommended_strategy": "overall mediation approach",
            "quick_wins": ["conflicts that can be easily resolved"],
            "escalation_needed": ["conflicts requiring human intervention"]
        }}
        """
        
        messages = [
            SystemMessage(content="You are an expert contract mediator with deep understanding of multi-party negotiations."),
            HumanMessage(content=analysis_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_analysis": response.content, "parse_error": True}
    
    async def _resolve_conflict(self, state: AmendmentWorkflowState, conflict: ConflictInfo, 
                              analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a specific conflict using AI mediation"""
        
        print(f"   🤝 Resolving conflict: {conflict.description[:50]}...")
        
        # Select resolution strategy based on conflict complexity
        complexity = analysis.get("resolution_complexity", {}).get(conflict.conflict_id, "moderate")
        strategy = self._select_resolution_strategy(conflict, complexity)
        
        # Gather relevant context for this conflict
        context = await self._gather_conflict_context(state, conflict)
        
        resolution_prompt = f"""
        You are mediating a contract amendment conflict between multiple parties.
        
        Conflict Details:
        - Type: {conflict.conflict_type}
        - Description: {conflict.description}
        - Severity: {conflict.severity}
        - Affected Parties: {conflict.affected_parties}
        - Affected Clauses: {conflict.affected_clauses}
        
        Context:
        {json.dumps(context, indent=2)}
        
        Resolution Strategy: {strategy}
        
        Your task is to propose a specific resolution that:
        1. Addresses the core conflict fairly
        2. Considers each party's interests and constraints
        3. Maintains legal validity and business viability
        4. Provides clear, actionable next steps
        
        Provide your resolution in JSON format:
        {{
            "resolution_type": "compromise|alternative_approach|clarification|restructure",
            "proposed_solution": "detailed description of the solution",
            "specific_changes": [
                {{
                    "clause": "which clause to modify",
                    "current_conflict": "what's conflicting",
                    "proposed_text": "new proposed text",
                    "rationale": "why this resolves the conflict"
                }}
            ],
            "party_benefits": {{
                "party_id": "how this benefits each party"
            }},
            "implementation_steps": ["step 1", "step 2", "..."],
            "risk_mitigation": "how this reduces risks for all parties",
            "confidence_score": 0.85,
            "requires_party_approval": true,
            "alternative_options": ["other options if this is rejected"]
        }}
        """
        
        messages = [
            SystemMessage(content=f"You are an expert mediator using {strategy} strategy to resolve contract disputes."),
            HumanMessage(content=resolution_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            resolution_data = json.loads(response.content)
            
            # Validate the resolution
            validation_result = await self._validate_resolution(state, conflict, resolution_data)
            
            if validation_result["is_valid"]:
                # Apply the resolution
                application_result = await self._apply_resolution(state, conflict, resolution_data)
                
                return {
                    "conflict_id": conflict.conflict_id,
                    "status": "resolved" if application_result["success"] else "partially_resolved",
                    "resolution_data": resolution_data,
                    "validation": validation_result,
                    "application": application_result,
                    "resolution_notes": f"Applied {strategy} strategy: {resolution_data.get('proposed_solution', '')[:100]}"
                }
            else:
                return {
                    "conflict_id": conflict.conflict_id,
                    "status": "resolution_failed",
                    "resolution_data": resolution_data,
                    "validation": validation_result,
                    "error": validation_result.get("issues", [])
                }
                
        except json.JSONDecodeError:
            return {
                "conflict_id": conflict.conflict_id,
                "status": "resolution_error", 
                "error": "Failed to parse resolution response",
                "raw_response": response.content
            }
    
    async def _gather_conflict_context(self, state: AmendmentWorkflowState, 
                                     conflict: ConflictInfo) -> Dict[str, Any]:
        """Gather relevant context for resolving a specific conflict"""
        
        context = {
            "original_contract_excerpt": state.original_contract[:1000] if state.original_contract else None,
            "proposed_changes": state.proposed_changes,
            "affected_parties_info": {},
            "similar_conflicts": [],
            "precedents": []
        }
        
        # Get information about affected parties
        for party_id in conflict.affected_parties:
            if party_id in state.party_responses:
                response = state.party_responses[party_id]
                context["affected_parties_info"][party_id] = {
                    "organization": response.organization,
                    "current_position": response.status,
                    "comments": response.comments,
                    "proposed_changes": response.proposed_changes,
                    "conditions": response.conditions
                }
        
        # Look for similar conflicts that were resolved
        for other_conflict in state.conflicts:
            if (other_conflict.conflict_id != conflict.conflict_id and 
                other_conflict.resolution_status == "resolved" and
                other_conflict.conflict_type == conflict.conflict_type):
                
                context["similar_conflicts"].append({
                    "type": other_conflict.conflict_type,
                    "resolution_approach": "resolved",  # Could store more details
                    "affected_clauses": other_conflict.affected_clauses
                })
        
        return context
    
    def _select_resolution_strategy(self, conflict: ConflictInfo, complexity: str) -> str:
        """Select appropriate resolution strategy based on conflict characteristics"""
        
        # Strategy selection logic
        if conflict.severity == "high" and complexity == "complex":
            return "precedent_based"  # Use established legal precedents
        elif conflict.conflict_type == "contradictory_terms":
            return "compromise_based"  # Split the difference
        elif conflict.conflict_type == "policy_violation":
            return "alternative_approach"  # Find different way to achieve goals
        elif len(conflict.affected_parties) > 2:
            return "win_win_optimization"  # Optimize for all parties
        else:
            return "value_maximization"  # Maximize overall value
    
    async def _validate_resolution(self, state: AmendmentWorkflowState, 
                                 conflict: ConflictInfo, resolution_data: Dict) -> Dict[str, Any]:
        """Validate proposed resolution for legal and business viability"""
        
        validation_prompt = f"""
        Validate this proposed conflict resolution:
        
        Original Conflict: {conflict.description}
        Proposed Resolution: {resolution_data.get('proposed_solution', '')}
        Specific Changes: {resolution_data.get('specific_changes', [])}
        
        Check for:
        1. Legal validity and enforceability
        2. Business viability for all parties
        3. Consistency with existing contract terms
        4. Potential for creating new conflicts
        5. Implementation feasibility
        
        Return JSON:
        {{
            "is_valid": true/false,
            "confidence": 0.85,
            "issues": ["list of any issues found"],
            "recommendations": ["suggestions for improvement"],
            "legal_risks": ["potential legal issues"],
            "business_risks": ["potential business issues"]
        }}
        """
        
        messages = [
            SystemMessage(content="You are a legal and business analyst validating contract resolutions."),
            HumanMessage(content=validation_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "is_valid": False,
                "confidence": 0.0,
                "issues": ["Failed to parse validation response"],
                "raw_response": response.content
            }
    
    async def _apply_resolution(self, state: AmendmentWorkflowState, 
                              conflict: ConflictInfo, resolution_data: Dict) -> Dict[str, Any]:
        """Apply the validated resolution to the workflow state"""
        
        try:
            # Update conflict with resolution details
            conflict.resolution_suggestions = [resolution_data.get("proposed_solution", "")]
            
            # If resolution requires party approval, mark for re-review
            if resolution_data.get("requires_party_approval", False):
                # Add proposed changes to workflow state
                if "resolved_changes" not in state.node_outputs:
                    state.node_outputs["resolved_changes"] = {}
                
                state.node_outputs["resolved_changes"][conflict.conflict_id] = {
                    "resolution": resolution_data,
                    "requires_approval": True,
                    "affected_parties": conflict.affected_parties
                }
                
                # Flag that parties need to re-review
                for party_id in conflict.affected_parties:
                    if party_id in state.party_responses:
                        # Reset party status to pending for re-review
                        state.party_responses[party_id].status = "pending_re_review"
            
            # Update workflow metrics
            if "conflict_resolutions" not in state.node_outputs:
                state.node_outputs["conflict_resolutions"] = []
            
            state.node_outputs["conflict_resolutions"].append({
                "conflict_id": conflict.conflict_id,
                "resolution_strategy": resolution_data.get("resolution_type", "unknown"),
                "confidence": resolution_data.get("confidence_score", 0.5),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {
                "success": True,
                "applied_changes": len(resolution_data.get("specific_changes", [])),
                "requires_re_approval": resolution_data.get("requires_party_approval", False)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


    def _identify_conflicts(self, state: AmendmentWorkflowState) -> None:
        """
        Identifies new conflicts from party responses and adds them to the state.
        """
        # Get IDs of conflicts already processed to avoid duplication
        existing_conflict_parties = set()
        for conflict in state.conflicts:
            existing_conflict_parties.update(conflict.affected_parties)

        for party_id, response in state.party_responses.items():
            if party_id in existing_conflict_parties:
                continue # Skip parties that are already part of a conflict

            if response.status in ["rejected", "requested_changes"]:
                # Determine affected clauses from counter-proposals if they exist
                affected_clauses = []
                if response.proposed_changes and "proposed_modifications" in response.proposed_changes:
                    for mod in response.proposed_changes["proposed_modifications"]:
                        if "clause" in mod:
                            affected_clauses.append(mod["clause"])

                # Create a conflict description
                description = response.comments or "No specific comments provided."
                if response.status == "requested_changes":
                    description = f"Requested changes: {description}"
                else:
                    description = f"Rejected due to: {description}"

                # Determine severity from risk assessment if available
                severity = "medium"
                if response.risk_assessment and "overall_risk_level" in response.risk_assessment:
                    risk_level = response.risk_assessment["overall_risk_level"]
                    severity_map = {"high": "high", "medium": "medium", "low": "low"}
                    severity = severity_map.get(risk_level, "medium")

                conflict = ConflictInfo(
                    conflict_type="unacceptable_terms" if response.status == "rejected" else "counter_proposal",
                    description=description,
                    affected_parties=[party_id],
                    affected_clauses=affected_clauses or ["general"],
                    severity=severity,
                    resolution_suggestions=["Review counter-proposals" if response.status == "requested_changes" else "Re-evaluate proposal based on rejection feedback"]
                )

                state.add_conflict(conflict)
                print(f"   CONFLICT DETECTED: {response.organization} {response.status} the proposal. Added conflict {conflict.conflict_id}")
def create_conflict_resolution_node() -> ConflictResolutionNode:
    """Factory function to create conflict resolution node"""
    return ConflictResolutionNode()