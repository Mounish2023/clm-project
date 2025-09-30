# backend/core/tools/contract_tools.py
"""
Contract Analysis Tools for LangGraph Nodes

These tools provide contract-specific functionality that can be used
by various nodes in the amendment workflow.
"""

from typing import Dict, List, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import re
import hashlib
import json
from dotenv import load_dotenv

load_dotenv()

import os
openai_api_key = os.getenv("OPENAI_API_KEY")

class ContractAnalysisInput(BaseModel):
    """Input schema for contract analysis tool"""
    contract_content: str = Field(description="Full contract text to analyze")
    analysis_type: str = Field(description="Type of analysis: structure, obligations, risks, clauses")
    focus_areas: Optional[List[str]] = Field(description="Specific areas to focus on")


class ContractAnalysisTool(BaseTool):
    """Tool for analyzing contract content using LLM"""
    
    name: str = "contract_analyzer"
    description: str = "Analyze contract content to extract structure, obligations, risks, and key clauses"
    # args_schema: ContractAnalysisInput
    _llm: ChatOpenAI = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    def _run(self, contract_content: str, analysis_type: str, 
           focus_areas: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze contract content"""
        
        analysis_prompts = {
            "structure": self._get_structure_prompt(),
            "obligations": self._get_obligations_prompt(),
            "risks": self._get_risk_analysis_prompt(),
            "clauses": self._get_clause_extraction_prompt()
        }
        
        prompt = analysis_prompts.get(analysis_type, analysis_prompts["structure"])
        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"\n\nPay special attention to these areas: {', '.join(focus_areas)}"
        
        messages = [
            SystemMessage(content=prompt + focus_instruction),
            HumanMessage(content=f"Contract to analyze:\n\n{contract_content}")
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            # Try to parse as JSON if possible
            analysis_result = json.loads(response.content)
        except json.JSONDecodeError:
            # Fall back to structured text parsing
            analysis_result = self._parse_text_response(response.content, analysis_type)
        
        return {
            "analysis_type": analysis_type,
            "result": analysis_result,
            "content_hash": hashlib.md5(contract_content.encode()).hexdigest(),
            "timestamp": "now"
        }
    
    def _get_structure_prompt(self) -> str:
        return """
        Analyze the contract structure and return a JSON object with:
        {
            "contract_type": "type of contract",
            "parties": ["list of parties with roles"],
            "sections": [
                {
                    "title": "section title",
                    "content_summary": "brief summary",
                    "importance": "high/medium/low"
                }
            ],
            "key_dates": {
                "effective_date": "date",
                "expiration_date": "date",
                "renewal_dates": ["dates"]
            },
            "governing_law": "jurisdiction",
            "amendment_procedures": "how amendments are handled"
        }
        """
    
    def _get_obligations_prompt(self) -> str:
        return """
        Extract all obligations from the contract and return JSON:
        {
            "obligations": [
                {
                    "party": "responsible party",
                    "obligation": "description of obligation",
                    "deadline": "if any",
                    "conditions": ["conditions that trigger this obligation"],
                    "consequences": "what happens if not fulfilled",
                    "priority": "high/medium/low"
                }
            ],
            "mutual_obligations": ["obligations that apply to all parties"],
            "conditional_obligations": ["obligations that depend on certain conditions"]
        }
        """
    
    def _get_risk_analysis_prompt(self) -> str:
        return """
        Analyze risks in the contract and return JSON:
        {
            "financial_risks": [
                {
                    "risk": "description",
                    "impact": "high/medium/low",
                    "likelihood": "high/medium/low",
                    "mitigation": "suggested mitigation"
                }
            ],
            "legal_risks": ["list of legal risks"],
            "operational_risks": ["list of operational risks"],
            "compliance_risks": ["regulatory/compliance concerns"],
            "overall_risk_score": "1-10 scale"
        }
        """
    
    def _get_clause_extraction_prompt(self) -> str:
        return """
        Extract and categorize key clauses from the contract:
        {
            "termination_clauses": ["clauses related to termination"],
            "payment_clauses": ["payment terms and conditions"],
            "liability_clauses": ["liability and indemnification"],
            "intellectual_property": ["IP related clauses"],
            "confidentiality": ["confidentiality and NDA clauses"],
            "dispute_resolution": ["how disputes are resolved"],
            "force_majeure": ["force majeure provisions"],
            "modification_clauses": ["how contract can be modified"]
        }
        """
    
    def _parse_text_response(self, response: str, analysis_type: str) -> Dict[str, Any]:
        """Parse non-JSON text response into structured format"""
        # Implement text parsing logic based on analysis type
        return {"raw_response": response, "parsed": False}


class ConflictDetectionInput(BaseModel):
    """Input schema for conflict detection tool"""
    original_contract: str = Field(description="Original contract content")
    proposed_changes: List[Dict[str, Any]] = Field(description="List of proposed changes from different parties")


class ConflictDetectionTool(BaseTool):
    """Tool for detecting conflicts between proposed amendments"""
    
    name: str = "conflict_detector"
    description: str = "Detect conflicts and inconsistencies between proposed contract amendments"
    # args_schema: ConflictDetectionInput
    _llm: ChatOpenAI = PrivateAttr()
    
    def __init__(self, **data):
        super().__init__(**data)
        self._llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    def _run(self, original_contract: str, proposed_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect conflicts between proposed changes"""
        
        conflict_prompt = f"""
        Analyze the original contract and proposed changes to identify conflicts:
        
        Original Contract:
        {original_contract}
        
        Proposed Changes:
        {json.dumps(proposed_changes, indent=2)}
        
        Identify conflicts and return JSON:
        {{
            "conflicts": [
                {{
                    "conflict_id": "unique_id",
                    "type": "contradictory_terms|overlapping_sections|policy_violation|legal_inconsistency",
                    "description": "detailed description",
                    "affected_parties": ["parties involved"],
                    "affected_clauses": ["specific clauses"],
                    "severity": "high|medium|low",
                    "resolution_suggestions": ["possible solutions"]
                }}
            ],
            "compatible_changes": ["changes that don't conflict"],
            "requires_mediation": ["changes needing human mediation"],
            "auto_resolvable": ["conflicts that can be automatically resolved"]
        }}
        """
        
        messages = [
            SystemMessage(content="You are an expert contract analyst specializing in conflict detection."),
            HumanMessage(content=conflict_prompt)
        ]
        
        response = self._llm.invoke(messages)
        
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"raw_response": response.content, "conflicts": []}
        
        return result


class AmendmentMergeInput(BaseModel):
    """Input schema for amendment merging tool"""
    base_contract: str = Field(description="Base contract content")
    approved_changes: List[Dict[str, Any]] = Field(description="List of approved changes to merge")
    merge_strategy: str = Field(description="Merge strategy: conservative, aggressive, balanced")


class AmendmentMergeTool(BaseTool):
    """Tool for intelligently merging approved amendments"""
    
    name: str = "amendment_merger"
    description: str = "Merge approved amendments into the base contract while maintaining legal consistency"
    # args_schema: AmendmentMergeInput
    _llm: ChatOpenAI = PrivateAttr()
    
    def __init__(self, **data):
        super().__init__(**data)
        self._llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    def _run(self, base_contract: str, approved_changes: List[Dict[str, Any]], 
           merge_strategy: str = "balanced") -> Dict[str, Any]:
        """Merge approved changes into base contract"""
        
        merge_prompt = f"""
        Merge the approved changes into the base contract using a {merge_strategy} strategy:
        
        Base Contract:
        {base_contract}
        
        Approved Changes:
        {json.dumps(approved_changes, indent=2)}
        
        Merge Strategy Guidelines:
        - Conservative: Minimal changes, preserve original structure
        - Aggressive: Optimize for efficiency, may restructure significantly  
        - Balanced: Reasonable changes while maintaining readability
        
        Return JSON:
        {{
            "merged_contract": "complete merged contract text",
            "changes_applied": [
                {{
                    "change_id": "id",
                    "section": "affected section",
                    "description": "what was changed",
                    "original_text": "original text",
                    "new_text": "new text"
                }}
            ],
            "merge_notes": "notes about the merge process",
            "validation_required": ["areas requiring additional validation"],
            "merge_quality_score": "1-10 score"
        }}
        """
        
        messages = [
            SystemMessage(content="You are an expert legal document editor specializing in contract amendments."),
            HumanMessage(content=merge_prompt)
        ]
            
        response = self._llm.invoke(messages)
        
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {
                "merged_contract": response.content,
                "changes_applied": [],
                "merge_notes": "Failed to parse structured response"
            }
        
        return result


class ComplianceCheckInput(BaseModel):
    """Input schema for compliance checking tool"""
    contract_content: str = Field(description="Contract content to check")
    jurisdiction: str = Field(description="Legal jurisdiction")
    contract_type: str = Field(description="Type of contract")
    regulations: Optional[List[str]] = Field(description="Specific regulations to check against")


class ComplianceCheckTool(BaseTool):
    """Tool for checking contract compliance with regulations"""
    
    name: str = "compliance_checker"
    description: str = "Check contract compliance with relevant laws and regulations"
    # args_schema: ComplianceCheckInput
    _llm: ChatOpenAI = PrivateAttr()
    
    def __init__(self, **data):
        super().__init__(**data)
        self._llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    def _run(self, contract_content: str, jurisdiction: str, contract_type: str,
           regulations: Optional[List[str]] = None) -> Dict[str, Any]:
        """Check contract for compliance issues"""
        
        reg_focus = ""
        if regulations:
            reg_focus = f"\nPay special attention to: {', '.join(regulations)}"
        
        compliance_prompt = f"""
        Review this {contract_type} contract for compliance with {jurisdiction} law:{reg_focus}
        
        Contract:
        {contract_content}
        
        Return JSON:
        {{
            "compliance_status": "compliant|non_compliant|requires_review",
            "violations": [
                {{
                    "regulation": "specific regulation violated",
                    "section": "contract section",
                    "description": "description of violation",
                    "severity": "high|medium|low",
                    "remediation": "suggested fix"
                }}
            ],
            "recommendations": ["general compliance recommendations"],
            "required_clauses": ["clauses that must be added"],
            "problematic_clauses": ["clauses that should be removed/modified"],
            "compliance_score": "1-10 score"
        }}
        """
        
        messages = [
            SystemMessage(content="You are a compliance expert specializing in contract law."),
            HumanMessage(content=compliance_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {
                "compliance_status": "requires_review",
                "raw_response": response.content
            }
        
        return result


# Tool registry for easy access
CONTRACT_TOOLS = {
    "analyze_contract": ContractAnalysisTool(),
    "detect_conflicts": ConflictDetectionTool(), 
    "merge_amendments": AmendmentMergeTool(),
    "check_compliance": ComplianceCheckTool()
}


def get_contract_tools() -> List[BaseTool]:
    """Get all contract analysis tools"""
    return list(CONTRACT_TOOLS.values())


def get_tool_by_name(tool_name: str) -> Optional[BaseTool]:
    """Get specific tool by name"""
    return CONTRACT_TOOLS.get(tool_name)