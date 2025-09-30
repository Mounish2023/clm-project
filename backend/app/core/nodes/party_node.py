# backend/core/nodes/party_node.py
"""
Party Agent Node for LangGraph Amendment Workflow

This node represents individual parties in the contract amendment process.
Each party evaluates proposed changes based on their organizational policies and constraints.
"""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from datetime import datetime
import json

from ..graph_state import AmendmentWorkflowState, PartyResponse, ConflictInfo
from ..tools.contract_tools import get_contract_tools


class PartyAgentNode:
    """
    Represents a party in the contract amendment process
    """
    
    def __init__(self, party_id: str, organization: str, policies: Dict[str, Any]):
        self.party_id = party_id
        self.organization = organization
        self.policies = policies
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.3)
        self.tools = get_contract_tools()
        
        # Load organization-specific constraints and preferences
        self.constraints = self._load_organizational_constraints()
        self.risk_tolerance = policies.get("risk_tolerance", "medium")
        self.approval_authority = policies.get("approval_authority", "standard")
    
    async def __call__(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """
        Evaluate amendment proposal from this party's perspective
        """
        print(f"🏢 PARTY AGENT ({self.organization}): Evaluating amendment {state.amendment_id}")
        
        start_time = datetime.utcnow()
        
        try:
            # Check if this party has already responded
            if self.party_id in state.party_responses:
                existing_response = state.party_responses[self.party_id]
                if existing_response.status != "pending":
                    print(f"   Already responded with status: {existing_response.status}")
                    return {"action": "no_action_needed", "reason": "already_responded"}
            
            # Evaluate the proposed changes
            evaluation_result = await self._evaluate_amendment_proposal(state)
            
            party_response = PartyResponse(
                party_id=self.party_id,
                organization=self.organization,
                status=evaluation_result["recommendation"],
                comments=evaluation_result.get("comments"),
                proposed_changes=evaluation_result.get("counter_proposals"),
                conditions=evaluation_result.get("conditions"),
                risk_assessment=evaluation_result.get("risk_assessment")
            )
            
            # Add response to state
            state.add_party_response(self.party_id, party_response)

            # Identify and add conflicts based on the evaluation
            await self._identify_and_add_conflicts(state, evaluation_result)
            
            # Log execution
            duration = (datetime.utcnow() - start_time).total_seconds()
            state.log_execution(
                f"party_agent_{self.party_id}", 
                {"amendment_id": state.amendment_id}, 
                evaluation_result, 
                duration, 
                True
            )
            
            print(f"   Decision: {evaluation_result['recommendation']}")
            
            return {
                "party_id": self.party_id,
                "organization": self.organization,
                "decision": evaluation_result["recommendation"],
                "evaluation_details": evaluation_result
            }
            
        except Exception as e:
            error_response = PartyResponse(
                party_id=self.party_id,
                organization=self.organization,
                status="error",
                comments=f"Error during evaluation: {str(e)}"
            )
            state.add_party_response(self.party_id, error_response)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            state.log_execution(
                f"party_agent_{self.party_id}", 
                {"amendment_id": state.amendment_id}, 
                {"error": str(e)}, 
                duration, 
                False
            )
            
            return {"error": str(e), "party_id": self.party_id}
    
    async def _evaluate_amendment_proposal(self, state: AmendmentWorkflowState) -> Dict[str, Any]:
        """
        Comprehensive evaluation of the amendment proposal
        """
        
        # Prepare evaluation context
        evaluation_context = {
            "original_contract": state.original_contract,
            "proposed_changes": state.proposed_changes,
            "other_parties": [p for p in state.parties if p != self.party_id],
            "organizational_policies": self.policies,
            "constraints": self.constraints,
            "risk_tolerance": self.risk_tolerance
        }
        
        # Analyze contract changes
        contract_analysis = await self._analyze_contract_changes(evaluation_context)
        
        # Assess business impact
        business_impact = await self._assess_business_impact(evaluation_context)
        
        # Evaluate legal and compliance aspects
        legal_evaluation = await self._evaluate_legal_aspects(evaluation_context)
        
        # Generate risk assessment
        risk_assessment = await self._assess_risks(evaluation_context)
        
        # Make final recommendation
        recommendation = await self._make_recommendation(
            contract_analysis, business_impact, legal_evaluation, risk_assessment
        )
        
        return {
            "recommendation": recommendation["decision"],
            "confidence": recommendation["confidence"],
            "comments": recommendation["rationale"],
            "counter_proposals": recommendation.get("counter_proposals"),
            "conditions": recommendation.get("conditions"),
            "risk_assessment": risk_assessment,
            "analysis_details": {
                "contract_analysis": contract_analysis,
                "business_impact": business_impact,
                "legal_evaluation": legal_evaluation
            }
        }
    
    async def _analyze_contract_changes(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the specific contract changes proposed"""
        
        analysis_prompt = f"""
        As a representative of {self.organization}, analyze these proposed contract changes:
        
        Original Contract: {context['original_contract'][:1500] if context['original_contract'] else 'Not provided'}
        
        Proposed Changes: {json.dumps(context['proposed_changes'], indent=2)}
        
        Organization Policies: {json.dumps(self.policies, indent=2)}
        
        Analyze the changes and return JSON:
        {{
            "changes_summary": "brief summary of all changes",
            "favorable_changes": ["changes that benefit our organization"],
            "unfavorable_changes": ["changes that may hurt our interests"],
            "neutral_changes": ["changes with minimal impact"],
            "clause_by_clause_analysis": {{
                "clause_id": {{
                    "original_text": "original clause",
                    "proposed_text": "new clause",
                    "impact": "positive/negative/neutral",
                    "reasoning": "why this impacts us this way"
                }}
            }},
            "overall_impact_score": "1-10 where 10 is most favorable"
        }}
        """
        
        messages = [
            SystemMessage(content=f"You are a contract analyst representing {self.organization}'s interests."),
            HumanMessage(content=analysis_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_analysis": response.content, "parse_error": True}
    
    async def _assess_business_impact(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess business impact of proposed changes"""
        
        impact_prompt = f"""
        Assess the business impact of these contract changes for {self.organization}:
        
        Proposed Changes: {json.dumps(context['proposed_changes'], indent=2)}
        
        Our Business Constraints: {json.dumps(self.constraints, indent=2)}
        Risk Tolerance: {self.risk_tolerance}
        
        Evaluate and return JSON:
        {{
            "financial_impact": {{
                "cost_increase": "estimated increase/decrease",
                "revenue_impact": "potential revenue effect",
                "cash_flow_impact": "effect on cash flow"
            }},
            "operational_impact": {{
                "workflow_changes": "required operational changes",
                "resource_requirements": "additional resources needed",
                "timeline_impact": "effect on project timelines"
            }},
            "strategic_impact": {{
                "alignment_with_goals": "how well this aligns with our strategy",
                "competitive_advantage": "competitive implications",
                "relationship_impact": "effect on business relationships"
            }},
            "overall_business_score": "1-10 where 10 is most beneficial"
        }}
        """
        
        messages = [
            SystemMessage(content=f"You are a business analyst for {self.organization}."),
            HumanMessage(content=impact_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_impact": response.content, "parse_error": True}
    
    async def _evaluate_legal_aspects(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate legal and compliance aspects"""
        
        legal_prompt = f"""
        Evaluate legal aspects of these contract changes for {self.organization}:
        
        Proposed Changes: {json.dumps(context['proposed_changes'], indent=2)}
        
        Consider:
        - Legal risks and liabilities
        - Compliance requirements
        - Enforceability issues
        - Regulatory implications
        
        Return JSON:
        {{
            "legal_risks": [
                {{
                    "risk": "description of legal risk",
                    "severity": "high/medium/low",
                    "mitigation": "suggested mitigation"
                }}
            ],
            "compliance_issues": ["any compliance concerns"],
            "enforceability_concerns": ["enforceability issues"],
            "recommended_legal_review": "yes/no and why",
            "legal_score": "1-10 where 10 is legally sound"
        }}
        """
        
        messages = [
            SystemMessage(content="You are a legal analyst specializing in contract law."),
            HumanMessage(content=legal_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_legal": response.content, "parse_error": True}
    
    async def _assess_risks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive risk assessment"""
        
        risk_prompt = f"""
        Perform comprehensive risk assessment for {self.organization}:
        
        Proposed Changes: {json.dumps(context['proposed_changes'], indent=2)}
        Risk Tolerance: {self.risk_tolerance}
        
        Assess all types of risks and return JSON:
        {{
            "financial_risks": [
                {{
                    "risk": "description",
                    "probability": "high/medium/low",
                    "impact": "high/medium/low",
                    "mitigation": "how to mitigate"
                }}
            ],
            "operational_risks": ["operational risk descriptions"],
            "reputational_risks": ["reputational risk descriptions"],
            "strategic_risks": ["strategic risk descriptions"],
            "overall_risk_level": "high/medium/low",
            "risk_score": "1-10 where 1 is highest risk",
            "acceptable_given_tolerance": "yes/no based on our risk tolerance"
        }}
        """
        
        messages = [
            SystemMessage(content=f"You are a risk analyst for {self.organization}."),
            HumanMessage(content=risk_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_risk": response.content, "parse_error": True}
    
    async def _make_recommendation(self, contract_analysis: Dict, business_impact: Dict, 
                                  legal_evaluation: Dict, risk_assessment: Dict) -> Dict[str, Any]:
        """Make final recommendation based on all analyses"""
        
        # Extract scores
        contract_score = contract_analysis.get("overall_impact_score", 5)
        business_score = business_impact.get("overall_business_score", 5)
        legal_score = legal_evaluation.get("legal_score", 5)
        risk_score = risk_assessment.get("risk_score", 5)
        
        # Convert scores to numeric if they're strings
        try:
            contract_score = float(contract_score)
            business_score = float(business_score)
            legal_score = float(legal_score)
            risk_score = float(risk_score)
        except (ValueError, TypeError):
            contract_score = business_score = legal_score = risk_score = 5.0
        
        # Calculate weighted overall score
        weights = {
            "contract": 0.25,
            "business": 0.35, 
            "legal": 0.20,
            "risk": 0.20
        }
        
        overall_score = (
            contract_score * weights["contract"] +
            business_score * weights["business"] +
            legal_score * weights["legal"] +
            risk_score * weights["risk"]
        )
        
        # Determine recommendation based on score and risk tolerance
        if overall_score >= 7.0 and risk_assessment.get("acceptable_given_tolerance") != "no":
            decision = "approved"
            confidence = min(0.9, overall_score / 10)
        elif overall_score >= 5.0:
            decision = "requested_changes"
            confidence = 0.6
        else:
            decision = "rejected"
            confidence = min(0.8, (10 - overall_score) / 10)
        
        # Generate rationale
        rationale_prompt = f"""
        Generate a concise rationale for {self.organization}'s decision to {decision} this amendment:
        
        Overall Score: {overall_score:.1f}/10
        Contract Analysis: {contract_analysis.get('changes_summary', 'N/A')}
        Business Impact: {business_impact.get('overall_business_score', 'N/A')}
        Legal Score: {legal_score}
        Risk Level: {risk_assessment.get('overall_risk_level', 'N/A')}
        
        Provide a brief, professional explanation in 2-3 sentences.
        """
        
        messages = [
            SystemMessage(content=f"You are writing on behalf of {self.organization}."),
            HumanMessage(content=rationale_prompt)
        ]
        
        rationale_response = await self.llm.ainvoke(messages)
        
        result = {
            "decision": decision,
            "confidence": confidence,
            "overall_score": overall_score,
            "rationale": rationale_response.content.strip()
        }
        
        # Add counter-proposals if requesting changes
        if decision == "requested_changes":
            result["counter_proposals"] = await self._generate_counter_proposals(
                contract_analysis, business_impact
            )
        
        return result
    
    async def _generate_counter_proposals(self, contract_analysis: Dict, 
                                        business_impact: Dict) -> Dict[str, Any]:
        """Generate counter-proposals to address concerns"""
        
        counter_prompt = f"""
        Based on our analysis, generate counter-proposals to address {self.organization}'s concerns:
        
        Unfavorable Changes: {contract_analysis.get('unfavorable_changes', [])}
        Business Concerns: {business_impact}
        
        Generate specific alternative language or modifications that would make this amendment acceptable.
        Return JSON:
        {{
            "proposed_modifications": [
                {{
                    "clause": "which clause to modify",
                    "current_proposal": "current proposed text",
                    "our_proposal": "our alternative text",
                    "justification": "why this is better"
                }}
            ],
            "additional_conditions": ["conditions we'd need added"],
            "negotiable_items": ["items we're willing to discuss"]
        }}
        """
        
        messages = [
            SystemMessage(content=f"You are negotiating on behalf of {self.organization}."),
            HumanMessage(content=counter_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_counter_proposals": response.content}
    
    def _load_organizational_constraints(self) -> Dict[str, Any]:
        """Load organization-specific constraints and policies"""
        
        # This would typically load from a database or configuration
        # For now, we'll use policy-based defaults
        base_constraints = {
            "budget_limit": self.policies.get("budget_limit", 1000000),
            "approval_required_above": self.policies.get("approval_threshold", 50000),
            "prohibited_clauses": self.policies.get("prohibited_clauses", []),
            "required_clauses": self.policies.get("required_clauses", []),
            "preferred_terms": self.policies.get("preferred_terms", {}),
            "escalation_triggers": self.policies.get("escalation_triggers", [])
        }
        
        return base_constraints

    async def _identify_and_add_conflicts(self, state: AmendmentWorkflowState, evaluation_result: Dict[str, Any]) -> None:
        """
        Identifies conflicts based on evaluation and adds them to the state.
        """
        recommendation = evaluation_result.get("recommendation")

        if recommendation in ["rejected", "requested_changes"]:
            # Extract details from the evaluation to create a conflict
            analysis_details = evaluation_result.get("analysis_details", {})
            contract_analysis = analysis_details.get("contract_analysis", {})
            unfavorable_changes = contract_analysis.get("unfavorable_changes", [])
            
            # Determine affected clauses
            affected_clauses = []
            if unfavorable_changes:
                for change in unfavorable_changes:
                    if isinstance(change, dict) and "clause" in change:
                        affected_clauses.append(change["clause"])
                    elif isinstance(change, str):
                        affected_clauses.append(change)

            # Create a conflict description
            description = evaluation_result.get("comments", "No specific comments provided.")
            if recommendation == "requested_changes":
                description = f"Requested changes: {description}"
            else:
                description = f"Rejected due to: {description}"

            # Determine severity
            risk_assessment = evaluation_result.get("risk_assessment", {})
            overall_risk = risk_assessment.get("overall_risk_level", "medium")
            severity_map = {"high": "high", "medium": "medium", "low": "low"}
            severity = severity_map.get(overall_risk, "medium")

            conflict = ConflictInfo(
                conflict_type="unacceptable_terms" if recommendation == "rejected" else "counter_proposal",
                description=description,
                affected_parties=[self.party_id],
                affected_clauses=affected_clauses or ["general"],
                severity=severity,
                resolution_suggestions=["Review counter-proposals" if recommendation == "requested_changes" else "Re-evaluate proposal based on rejection feedback"]
            )

            state.add_conflict(conflict)
            print(f"   CONFLICT DETECTED: {self.organization} {recommendation} the proposal. Added conflict {conflict.conflict_id}")

            # state.update_status(AmendmentStatus.CONFLICTS_DETECTED, "Conflicts detected in party responses")



def create_party_node(party_id: str, organization: str, policies: Dict[str, Any]) -> PartyAgentNode:
    """Factory function to create a party agent node"""
    return PartyAgentNode(party_id, organization, policies)