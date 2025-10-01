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
import os
import hashlib
import json
from dotenv import load_dotenv

load_dotenv()


openai_api_key = os.getenv("OPENAI_API_KEY")


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
        
        response = self._llm.invoke(messages)
        
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
    "merge_amendments": AmendmentMergeTool(),
    "check_compliance": ComplianceCheckTool()
}


def get_contract_tools() -> List[BaseTool]:
    """Get all contract analysis tools"""
    return list(CONTRACT_TOOLS.values())


def get_tool_by_name(tool_name: str) -> Optional[BaseTool]:
    """Get specific tool by name"""
    return CONTRACT_TOOLS.get(tool_name)