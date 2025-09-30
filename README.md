# Quick Start Guide for Contract Amendment Orchestrator

## 🚀 Getting Started

### 1. Environment Setup

```bash
# Clone and setup
git clone <repository>
cd contract-orchestrator

# Create environment file
cp .env.example .env
# Edit .env with your API keys:
# OPENAI_API_KEY=your_openai_key
# ANTHROPIC_API_KEY=your_anthropic_key

# Start with Docker (recommended)
docker-compose up -d

# OR start manually
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Basic Usage

```python
from backend.core.orchestrator import initiate_contract_amendment

# Define parties
parties = [
    {
        "id": "company_a",
        "organization": "Company A",
        "policies": {
            "risk_tolerance": "low",
            "budget_limit": 100000,
            "required_clauses": ["termination_protection"]
        }
    },
    {
        "id": "company_b", 
        "organization": "Company B",
        "policies": {
            "risk_tolerance": "medium",
            "budget_limit": 150000
        }
    }
]

# Define changes
changes = {
    "payment_terms": {
        "old_value": "Net 30 days",
        "new_value": "Net 15 days"
    },
    "budget_increase": {
        "old_value": "$50,000",
        "new_value": "$75,000"
    }
}

# Start workflow
workflow_id = await initiate_contract_amendment(
    contract_id="CONTRACT_001",
    parties=parties,
    proposed_changes=changes,
    original_contract="Your contract text here..."
)

# Monitor progress
status = await get_amendment_status(workflow_id)
print(f"Status: {status['status']}")
print(f"Progress: {status['progress']}%")
```

### 3. API Usage

```bash
# Start the API
uvicorn backend.api.main:app --reload

# Initiate amendment via REST API
curl -X POST "http://localhost:8000/api/v1/amendments/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "contract_id": "CONTRACT_001",
    "parties": [...],
    "proposed_changes": {...}
  }'

# Check status
curl "http://localhost:8000/api/v1/amendments/{workflow_id}/status"
```

### 4. WebSocket Real-time Updates

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${workflowId}`);

ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    console.log('Workflow update:', update);
};
```

### 5. Run Demo

```python
# Run the complete demo
python demo_usage.py
```

## 🏗️ Architecture Overview

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   FastAPI Backend   │────│  LangGraph Engine    │────│   AI Agents         │
│   - REST APIs       │    │  - Workflow State    │    │   - Coordinator     │
│   - WebSockets      │    │  - Node Routing      │    │   - Party Agents    │
│   - Authentication  │    │  - Error Handling    │    │   - Legal Review    │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   PostgreSQL DB     │    │   Redis Cache        │    │   Weaviate Vector   │
│   - Contract Data   │    │   - Session Data     │    │   - Embeddings      │
│   - Workflow State  │    │   - Message Queue    │    │   - Semantic Search │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run specific test
pytest tests/integration/test_multi_party_workflow.py::TestMultiPartyWorkflow::test_successful_three_party_amendment -v -s
```

## 🔧 Key Components

### LangGraph Workflow Nodes
- **Coordinator Node**: Central orchestration and routing
- **Party Nodes**: Represent each organization's interests  
- **Conflict Resolution**: AI-powered mediation
- **Legal Review**: Compliance checking
- **Version Control**: Document merging and versioning

### Tools & Capabilities
- **Contract Analysis**: Extract structure, obligations, risks
- **Conflict Detection**: Identify contradictory requirements
- **Amendment Merging**: Intelligent document combination
- **Compliance Checking**: Regulatory validation

### State Management
- **Workflow State**: Complete amendment process tracking
- **Party Responses**: Individual organization decisions
- **Conflict Tracking**: Issues identification and resolution
- **Version History**: Document change management

## 🎯 Use Cases

1. **Multi-Party Service Agreements**: 3+ organizations modifying terms
2. **Budget & Timeline Changes**: Financial and schedule amendments
3. **Compliance Updates**: Regulatory requirement changes
4. **Scope Modifications**: Adding/removing deliverables
5. **Risk Rebalancing**: Liability and insurance adjustments

## 🚨 Common Issues

**LangGraph not routing properly?**
- Check state transitions in `conditions/routing_conditions.py`
- Validate node return formats match expected schema

**Agents not responding?**
- Verify OpenAI API key is valid
- Check agent policies are properly configured
- Monitor logs for LLM call failures

**WebSocket disconnections?**
- Implement reconnection logic in frontend
- Check network stability and proxy settings

**Database connection errors?**
- Ensure PostgreSQL is running
- Verify connection string in environment

## 📚 Advanced Configuration

### Custom Party Policies
```python
party_policies = {
    "risk_tolerance": "low|medium|high|very_low|very_high",
    "budget_limit": 100000,
    "approval_threshold": 25000,
    "required_clauses": ["list of must-have clauses"],
    "prohibited_clauses": ["list of forbidden clauses"],
    "preferred_terms": {"key": "value"},
    "escalation_triggers": ["conditions that require human review"]
}
```

### Workflow Configuration
```python
workflow_config = {
    "timeout_minutes": 120,
    "require_legal_review": True,
    "enable_ai_mediation": True, 
    "auto_approve_threshold": 0.85,
    "conflict_resolution_timeout": 60,
    "max_retries": 3
}
```

### Monitoring & Observability
- Prometheus metrics at `:9090`
- Grafana dashboards at `:3001` 
- Application logs via `docker-compose logs app`
- Workflow state inspection via API endpoints

Ready to revolutionize contract management with AI! 🚀