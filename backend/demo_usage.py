# Example Usage Script - Demo the Complete System

import asyncio
import json
from datetime import datetime
from backend.core.orchestrator import initiate_contract_amendment, get_amendment_status

async def demo_three_party_amendment():
    """
    Demonstrate a complete three-party contract amendment workflow
    """
    
    print("🚀 Starting Contract Amendment Orchestration Demo")
    print("="*60)
    
    # Sample contract content
    original_contract = """
    MASTER SERVICE AGREEMENT
    
    This Master Service Agreement is entered into between:
    - TechCorp Inc. (Client)
    - DevStudio LLC (Primary Provider) 
    - CloudOps Solutions (Infrastructure Partner)
    
    1. SCOPE OF WORK
    Primary Provider will deliver custom software development services.
    Infrastructure Partner will provide cloud hosting and DevOps support.
    
    2. FINANCIAL TERMS
    Total Project Value: $500,000
    Payment Schedule: 25% upfront, 25% at milestone 1, 25% at milestone 2, 25% at completion
    Payment Terms: Net 30 days
    
    3. TIMELINE
    Project Start: January 1, 2025
    Estimated Completion: June 30, 2025
    
    4. INTELLECTUAL PROPERTY
    All deliverables will be owned by Client upon full payment.
    """
    
    # Define the three parties with different risk profiles
    parties = [
        {
            "id": "techcorp",
            "organization": "TechCorp Inc.",
            "policies": {
                "risk_tolerance": "low",
                "budget_limit": 600000,
                "approval_threshold": 50000,
                "required_clauses": ["ip_ownership", "termination_protection", "liability_caps"],
                "prohibited_clauses": ["unlimited_liability", "exclusivity"]
            }
        },
        {
            "id": "devstudio", 
            "organization": "DevStudio LLC",
            "policies": {
                "risk_tolerance": "medium",
                "budget_limit": 750000,
                "approval_threshold": 75000,
                "preferred_terms": {
                    "payment_terms": "Net 15 days",
                    "change_order_rate": "$200/hour"
                },
                "required_clauses": ["scope_change_protection", "payment_guarantees"]
            }
        },
        {
            "id": "cloudops",
            "organization": "CloudOps Solutions", 
            "policies": {
                "risk_tolerance": "high",
                "budget_limit": 200000,
                "approval_threshold": 25000,
                "constraints": {
                    "no_exclusivity": True,
                    "sla_requirements": "99.9% uptime minimum"
                },
                "required_clauses": ["sla_definitions", "scalability_provisions"]
            }
        }
    ]
    
    # Proposed amendments - these will create interesting conflicts
    proposed_changes = {
        "budget_increase": {
            "section": "2. FINANCIAL TERMS",
            "old_value": "$500,000",
            "new_value": "$650,000",
            "justification": "Additional security requirements and third-party integrations"
        },
        "timeline_extension": {
            "section": "3. TIMELINE", 
            "old_value": "June 30, 2025",
            "new_value": "September 30, 2025",
            "justification": "More comprehensive testing and user training required"
        },
        "payment_terms_change": {
            "section": "2. FINANCIAL TERMS",
            "old_value": "Net 30 days",
            "new_value": "Net 15 days",
            "justification": "Improve cash flow for development team"
        },
        "new_sla_requirements": {
            "section": "5. SERVICE LEVEL AGREEMENTS",
            "content": """
            5.1 System Availability: 99.95% uptime guarantee
            5.2 Response Times: API responses under 200ms for 95% of requests
            5.3 Support Response: 4-hour response time for critical issues
            5.4 Data Backup: Daily automated backups with 99.99% reliability
            5.5 Security Compliance: SOC 2 Type II certification required
            """,
            "justification": "Enhanced reliability requirements for enterprise deployment"
        },
        "intellectual_property_clarification": {
            "section": "4. INTELLECTUAL PROPERTY",
            "addition": """
            4.2 Open Source Components: Any open source libraries remain under their original licenses
            4.3 Development Tools: Provider retains rights to proprietary development frameworks
            4.4 Data Ownership: Client maintains exclusive ownership of all business data
            """,
            "justification": "Clarify IP boundaries for development tools and data"
        }
    }
    
    print("\n📋 Amendment Details:")
    print(f"   Original Contract Value: $500,000")
    print(f"   Proposed New Value: $650,000") 
    print(f"   Timeline Extension: 3 months")
    print(f"   Parties: {len(parties)} organizations")
    print(f"   Proposed Changes: {len(proposed_changes)} sections")
    
    # Initiate the workflow
    print(f"\n🎬 Initiating LangGraph Workflow...")
    start_time = datetime.now()
    
    workflow_id = await initiate_contract_amendment(
        contract_id="MSA_2025_001",
        parties=parties,
        proposed_changes=proposed_changes,
        original_contract=original_contract,
        workflow_config={
            "timeout_minutes": 180,  # 3 hours
            "require_legal_review": True,
            "enable_ai_mediation": True,
            "auto_approve_threshold": 0.85
        }
    )
    
    print(f"   ✅ Workflow initiated: {workflow_id}")
    
    # Monitor the workflow progress
    print(f"\n📊 Monitoring Workflow Progress:")
    print(f"   {'Time':<12} {'Status':<20} {'Progress':<10} {'Conflicts':<10} {'Details'}")
    print(f"   {'-'*12} {'-'*20} {'-'*10} {'-'*10} {'-'*30}")
    
    max_iterations = 60  # 5 minutes maximum
    iteration = 0
    previous_status = None
    workflow_events = []
    
    while iteration < max_iterations:
        try:
            current_time = datetime.now()
            elapsed = (current_time - start_time).total_seconds()
            
            status = await get_amendment_status(workflow_id)
            
            if status.get("error"):
                print(f"   ❌ Error: {status['error']}")
                break
            
            current_status = status.get("status", "unknown")
            progress = status.get("progress", 0)
            conflicts = status.get("conflicts", 0)
            
            # Log significant changes
            if current_status != previous_status:
                workflow_events.append({
                    "timestamp": current_time,
                    "status": current_status,
                    "progress": progress,
                    "conflicts": conflicts,
                    "elapsed_seconds": elapsed
                })
                
                time_str = f"{elapsed:.0f}s"
                progress_str = f"{progress:.1f}%"
                conflicts_str = f"{conflicts}"
                
                # Status-specific details
                details = ""
                if current_status == "under_review":
                    parties_status = status.get("parties_status", {})
                    responded = sum(1 for s in parties_status.values() if s != "pending")
                    details = f"{responded}/{len(parties)} responded"
                elif current_status == "conflicts_detected":
                    details = f"Resolving {conflicts} conflicts"
                elif current_status == "legal_review":
                    details = "Compliance checking"
                elif current_status == "consensus_building":
                    details = "Finalizing agreement"
                
                print(f"   {time_str:<12} {current_status:<20} {progress_str:<10} {conflicts_str:<10} {details}")
                previous_status = current_status
            
            # Check for completion
            if current_status in ["completed", "approved", "failed", "rejected"]:
                print(f"\n🏁 Workflow completed with status: {current_status}")
                break
                
        except Exception as e:
            print(f"   ⚠️  Monitor error: {str(e)}")
            
        await asyncio.sleep(5)
        iteration += 1
    
    # Final summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    print(f"\n📈 Workflow Summary:")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   Total Duration: {total_duration:.1f} seconds")
    print(f"   Workflow Events: {len(workflow_events)}")
    print(f"   Final Status: {workflow_events[-1]['status'] if workflow_events else 'Unknown'}")
    
    # Get final detailed status
    try:
        final_status = await get_amendment_status(workflow_id)
        
        if final_status.get("parties_status"):
            print(f"\n👥 Final Party Status:")
            for party_id, status in final_status["parties_status"].items():
                party_name = next((p["organization"] for p in parties if p["id"] == party_id), party_id)
                print(f"   {party_name}: {status}")
        
        if final_status.get("conflicts") > 0:
            print(f"\n⚠️  Conflicts: {final_status['conflicts']} detected")
        
        if final_status.get("estimated_completion"):
            print(f"   Estimated Completion: {final_status['estimated_completion']}")
            
    except Exception as e:
        print(f"   Could not retrieve final status: {str(e)}")
    
    print(f"\n🎉 Demo Complete!")
    return workflow_id


async def demo_conflict_scenario():
    """
    Demonstrate a scenario with intentional conflicts that require AI mediation
    """
    
    print(f"\n🔥 Conflict Resolution Demo")
    print(f"="*40)
    
    # Create conflicting requirements
    conflicting_parties = [
        {
            "id": "conservative_corp",
            "organization": "Conservative Corp",
            "policies": {
                "risk_tolerance": "very_low",
                "budget_limit": 100000,
                "required_clauses": ["termination_at_will", "payment_guarantees", "liability_caps"],
                "prohibited_clauses": ["unlimited_scope", "cost_plus_pricing"]
            }
        },
        {
            "id": "aggressive_startup",
            "organization": "Aggressive Startup", 
            "policies": {
                "risk_tolerance": "very_high",
                "budget_limit": 1000000,
                "required_clauses": ["equity_participation", "unlimited_scope", "rapid_delivery"],
                "prohibited_clauses": ["liability_caps", "termination_at_will"]
            }
        }
    ]
    
    conflicting_changes = {
        "liability_clause": {
            "conservative_wants": "Provider liability capped at 10% of contract value",
            "startup_wants": "Unlimited liability for both parties",
            "creates_conflict": True
        },
        "termination_terms": {
            "conservative_wants": "Either party can terminate with 7 days notice",
            "startup_wants": "Minimum 6-month commitment, penalties for early termination",
            "creates_conflict": True
        },
        "scope_flexibility": {
            "conservative_wants": "Fixed scope, change orders require written approval",
            "startup_wants": "Flexible scope, continuous iteration without formal approvals", 
            "creates_conflict": True
        }
    }
    
    workflow_id = await initiate_contract_amendment(
        contract_id="CONFLICT_TEST_001",
        parties=conflicting_parties,
        proposed_changes=conflicting_changes,
        original_contract="Simple test contract for conflict resolution",
        workflow_config={
            "enable_ai_mediation": True,
            "conflict_resolution_timeout": 30,  # 30 minutes
            "max_mediation_rounds": 3
        }
    )
    
    print(f"   Conflict scenario initiated: {workflow_id}")
    print(f"   Expected conflicts: 3 major areas")
    print(f"   AI mediation: Enabled")
    
    return workflow_id


if __name__ == "__main__":
    # Run the main demo
    asyncio.run(demo_three_party_amendment())
    
    # Optionally run conflict demo
    # asyncio.run(demo_conflict_scenario())