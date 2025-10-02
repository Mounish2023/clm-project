# backend/api/main.py
"""
FastAPI Main Application with LangGraph Integration

This is the main FastAPI application that provides REST APIs for the
contract amendment orchestration system powered by LangGraph.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import asyncio
import json
from datetime import datetime, timezone

from backend.app.core.orchestrator import (
    orchestrator, 
    initiate_contract_amendment, 
    get_amendment_status
)
# Removed unused import AmendmentStatus
from backend.app.services.notification_service import NotificationService
from backend.app.db.models import Contract, Amendment, ContractVersion
from backend.app.db.databases import get_db, init_database, drop_tables
from sqlalchemy.orm import Session
from uuid import uuid4

from scalar_fastapi import get_scalar_api_reference
import os
import logging
from dotenv import load_dotenv

load_dotenv()


def lifespan_handler(app: FastAPI):
    init_database()
    os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")
    os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "")
    os.environ["LANGSMITH_PROJECT_NAME"] = os.getenv("LANGSMITH_PROJECT_NAME", "")

    yield
    drop_tables()


# Initialize FastAPI app
app = FastAPI(
    title="Contract Amendment Orchestrator",
    description="AI-powered multi-party contract amendment orchestration using LangGraph",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan_handler
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global services
notification_service = NotificationService()


# Pydantic models for API
class PartyConfig(BaseModel):
    """Configuration for a party in the amendment process"""
    id: str = Field(description="Unique party identifier")
    organization: str = Field(description="Organization name")
    policies: Dict[str, Any] = Field(
        default_factory=dict,
        description="Organization policies and constraints"
    )
    contact_email: Optional[str] = None
    notification_preferences: Dict[str, Any] = Field(default_factory=dict)


class AmendmentRequest(BaseModel):
    """Request to initiate contract amendment"""
    contract_id: str = Field(description="ID of contract to amend")
    parties: List[PartyConfig] = Field(description="Parties involved in amendment")
    proposed_changes: Dict[str, Any] = Field(description="Proposed changes to contract")
    original_contract: Optional[str] = Field(
        default=None, 
        description="Full text of original contract"
    )
    workflow_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Workflow configuration overrides"
    )
    priority: str = Field(default="normal", description="Priority level: low, normal, high, urgent")
    deadline: Optional[datetime] = Field(default=None, description="Amendment deadline")


class AmendmentResponse(BaseModel):
    """Response from amendment initiation"""
    workflow_id: str
    status: str
    message: str
    # estimated_completion: Optional[datetime] = None


class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    workflow_id: str
    status: str
    parties_status: Dict[str, str]
    conflicts: int
    created_at: datetime
    updated_at: datetime
    # estimated_completion: Optional[datetime] = None


class PartyResponseUpdate(BaseModel):
    """Update from a party regarding the amendment"""
    party_id: str
    status: str  # approved, rejected, requested_changes, pending
    comments: Optional[str] = None
    proposed_changes: Optional[Dict[str, Any]] = None
    conditions: Optional[List[str]] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, workflow_id: str):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, workflow_id: str):
        if workflow_id in self.active_connections:
            self.active_connections[workflow_id].remove(websocket)
            
    async def broadcast_to_workflow(self, workflow_id: str, message: dict):
        if workflow_id in self.active_connections:
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except (RuntimeError, WebSocketDisconnect) as e:
                    # Remove broken connections
                    logging.warning(f"WebSocket connection error: {e}")
                    self.active_connections[workflow_id].remove(connection)


manager = ConnectionManager()


# API Routes

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Contract Amendment Orchestrator API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "orchestrator": "operational",
            "database": "operational", 
            "llm": "operational"
        }
    }

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        # Your OpenAPI document
        openapi_url=app.openapi_url,
        # Avoid CORS issues (optional)
        scalar_proxy_url="https://proxy.scalar.com",
    )

@app.post("/api/v1/amendments/initiate", response_model=AmendmentResponse)
async def initiate_amendment(
    request: AmendmentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Initiate a new multi-party contract amendment workflow
    """
    try:
        print(f"🚀 API: Initiating amendment for contract {request.contract_id}")
        
        # Convert PartyConfig objects to dictionaries
        parties_dict = [party.model_dump() for party in request.parties]
        
        workflow_id = str(uuid4())  # generate ID first

        # Save "initiated" right away
        amendment = Amendment(
            id=workflow_id,
            contract_id=request.contract_id,
            proposed_changes=request.proposed_changes,
            parties_involved=[party.id for party in request.parties],
            status="initiated",
            created_at=datetime.now(timezone.utc)
        )
        db.add(amendment)
        db.commit()

        # Kick off initiation in background
        background_tasks.add_task(
            initiate_contract_amendment,
            workflow_id=workflow_id,
            contract_id=request.contract_id,
            parties=parties_dict,
            proposed_changes=request.proposed_changes,
            original_contract=request.original_contract,
            workflow_config=request.workflow_config
        )

        # # Monitor as well
        # background_tasks.add_task(monitor_workflow, workflow_id)

        status = await get_amendment_status(workflow_id)
        
        return AmendmentResponse(
            workflow_id=workflow_id,
            status=status.get("status", "initiated"),
            message="Amendment workflow initiated successfully",
            # estimated_completion=datetime.fromisoformat(status["estimated_completion"]) if status.get("estimated_completion") else None
        )
        
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate amendment: {str(e)}")


@app.get("/api/v1/amendments/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get current status of an amendment workflow
    """
    try:
        status = await get_amendment_status(workflow_id)
        
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
        
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=status["status"],
            parties_status=status["parties_status"],
            conflicts=status["conflicts"],
            created_at=datetime.fromisoformat(status["created_at"]),
            updated_at=datetime.fromisoformat(status["updated_at"]),
            # estimated_completion=datetime.fromisoformat(status["estimated_completion"]) if status.get("estimated_completion") else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")

@app.post("/api/v1/amendments/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    updates: Optional[Dict[str, Any]] = None
):
    """
    Resume a paused or interrupted workflow
    """
    try:
        success = await orchestrator.resume_workflow(workflow_id, updates)
        
        if success:
            return {
                "message": "Workflow resumed successfully",
                "workflow_id": workflow_id
            }
        else:
            raise HTTPException(status_code=404, detail="Workflow not found or cannot be resumed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {str(e)}")


class ContractVersionResponse(BaseModel):
    version_number: int
    created_at: datetime
    changes_summary: Optional[str]

    class Config:
        from_attributes = True

class ContractResponse(BaseModel):
    id: str
    title: str
    content: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    parties: List[dict] = []
    latest_version: Optional[ContractVersionResponse] = None

    class Config:
        from_attributes = True


@app.get("/api/v1/contracts", response_model=List[ContractResponse])
async def list_contracts(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Contract)

        if status:
            query = query.filter(Contract.status == status)

        contracts = (
            query.order_by(Contract.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results: List[ContractResponse] = []
        for contract in contracts:
            latest_version = (
                db.query(ContractVersion)
                .filter(ContractVersion.contract_id == contract.id)
                .order_by(ContractVersion.version_number.desc())
                .first()
            )

            results.append(
                ContractResponse(
                    id=contract.id,
                    title=contract.title,
                    content=contract.content,
                    status=contract.status,
                    created_at=contract.created_at,
                    updated_at=contract.updated_at,
                    parties=contract.parties or [],
                    latest_version=(
                        ContractVersionResponse(
                            version_number=latest_version.version_number,
                            created_at=latest_version.created_at,
                            changes_summary=latest_version.changes_summary,
                        )
                        if latest_version
                        else None
                    ),
                )
            )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list contracts: {str(e)}")


@app.get("/api/v1/amendments")
async def list_amendments(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all amendment workflows with optional filtering
    """
    try:
        query = db.query(Amendment)
        
        if status:
            query = query.filter(Amendment.status == status)
        
        amendments = query.order_by(Amendment.created_at.desc())
        amendments = amendments.offset(offset).limit(limit).all()
        
        return {
            "amendments": [
                {
                    "workflow_id": a.id,
                    "contract_id": a.contract_id,
                    "status": a.status,
                    "parties": a.parties_involved,
                    "created_at": a.created_at.isoformat(),
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None
                }
                for a in amendments
            ],
            "total": query.count(),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list amendments: {str(e)}")


@app.delete("/api/v1/amendments/{workflow_id}")
async def cancel_amendment(
    workflow_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Cancel an active amendment workflow
    """
    try:
        # Update database
        amendment = db.query(Amendment).filter(Amendment.id == workflow_id).first()
        if not amendment:
            raise HTTPException(status_code=404, detail="Amendment not found")
        
        amendment.status = "cancelled"
        amendment.updated_at = datetime.utcnow()
        db.commit()
        
        # Broadcast cancellation
        await manager.broadcast_to_workflow(workflow_id, {
            "type": "workflow_cancelled",
            "reason": reason or "Cancelled by user",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {
            "message": "Amendment workflow cancelled successfully",
            "workflow_id": workflow_id,
            "reason": reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel amendment: {str(e)}")


# WebSocket endpoint for real-time updates
@app.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """
    WebSocket endpoint for real-time workflow updates
    """
    await manager.connect(websocket, workflow_id)
    
    # Send initial status
    try:
        status = await get_amendment_status(workflow_id)
        await websocket.send_text(json.dumps({
            "type": "status_update",
            "data": status
        }))
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Failed to get initial status: {str(e)}"
        }))
    
    try:
        while True:
            # Wait for any messages from client (keepalives, etc.)
            data = await websocket.receive_text()
            
            # Echo back for now (could implement client commands)
            await websocket.send_text(json.dumps({
                "type": "echo",
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)
        print(f"WebSocket disconnected for workflow {workflow_id}")


# Background tasks
async def monitor_workflow(workflow_id: str):
    """
    Background task to monitor workflow progress and send updates
    """
    print(f"🔍 Starting workflow monitor for {workflow_id}")
    
    max_iterations = 100  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        try:
            status = await get_amendment_status(workflow_id)
            
            # Broadcast status update
            await manager.broadcast_to_workflow(workflow_id, {
                "type": "status_update",
                "data": status,
                "timestamp": datetime.now(datetime.timezone.utc).isoformat()
            })
            
            # Check if workflow is complete
            if status.get("status") in ["completed", "failed", "cancelled"]:
                print(f"✅ Workflow {workflow_id} finished with status: {status.get('status')}")
                break
            
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds
            iteration += 1
            
        except Exception as e:
            print(f"❌ Monitor error for {workflow_id}: {str(e)}")
            await asyncio.sleep(60)  # Wait longer on error
            
    print(f"🏁 Workflow monitor for {workflow_id} finished")
