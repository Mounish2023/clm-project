# backend/services/notification_service.py
"""
Notification Service for Contract Amendment Workflows

This service handles all notifications, alerts, and real-time updates
for the contract amendment orchestration system.
"""

from typing import Dict, List, Any, Optional
import asyncio
import json
from datetime import datetime
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..core.graph_state import AmendmentWorkflowState, AmendmentStatus


class NotificationType(str, Enum):
    """Types of notifications"""
    WORKFLOW_INITIATED = "workflow_initiated"
    PARTY_RESPONSE_REQUESTED = "party_response_requested"
    CONFLICT_DETECTED = "conflict_detected"
    CONSENSUS_REACHED = "consensus_reached"
    LEGAL_REVIEW_REQUIRED = "legal_review_required"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    DEADLINE_APPROACHING = "deadline_approaching"
    ESCALATION_REQUIRED = "escalation_required"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    WEBSOCKET = "websocket"
    SMS = "sms"
    SLACK = "slack"
    TEAMS = "teams"
    WEBHOOK = "webhook"


class NotificationService:
    """
    Centralized notification service for workflow events
    """
    
    def __init__(self):
        self.active_subscriptions: Dict[str, List[Dict]] = {}
        self.notification_history: List[Dict] = []
        self.websocket_connections: Dict[str, List] = {}
        
        # Configuration (would come from environment/config)
        self.email_config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",  # Set from environment
            "password": "",  # Set from environment
            "from_email": "noreply@contractorchestrator.com"
        }
        
        self.enabled_channels = [
            NotificationChannel.EMAIL,
            NotificationChannel.WEBSOCKET
        ]
    
    async def subscribe_to_workflow(self, workflow_id: str, subscriber_info: Dict[str, Any]):
        """
        Subscribe a user/party to workflow notifications
        
        Args:
            workflow_id: The workflow to subscribe to
            subscriber_info: {
                "user_id": "user123",
                "email": "user@company.com",
                "channels": ["email", "websocket"],
                "notification_types": ["all"] or ["specific", "types"]
            }
        """
        
        if workflow_id not in self.active_subscriptions:
            self.active_subscriptions[workflow_id] = []
        
        subscription = {
            "user_id": subscriber_info.get("user_id"),
            "email": subscriber_info.get("email"),
            "channels": subscriber_info.get("channels", ["email", "websocket"]),
            "notification_types": subscriber_info.get("notification_types", ["all"]),
            "subscribed_at": datetime.utcnow(),
            "preferences": subscriber_info.get("preferences", {})
        }
        
        self.active_subscriptions[workflow_id].append(subscription)
        print(f"📧 User {subscription['user_id']} subscribed to workflow {workflow_id}")
    
    async def notify_workflow_event(self, workflow_id: str, event_type: NotificationType, 
                                  state: AmendmentWorkflowState, additional_data: Optional[Dict] = None):
        """
        Send notifications for a workflow event
        """
        
        if workflow_id not in self.active_subscriptions:
            print(f"⚠️  No subscribers for workflow {workflow_id}")
            return
        
        # Prepare notification content
        notification_content = await self._prepare_notification_content(
            event_type, state, additional_data
        )
        
        # Send to all subscribers
        subscribers = self.active_subscriptions[workflow_id]
        
        for subscriber in subscribers:
            # Check if subscriber wants this type of notification
            if not self._should_notify_subscriber(subscriber, event_type):
                continue
            
            # Send via each subscribed channel
            for channel in subscriber["channels"]:
                if channel in [c.value for c in self.enabled_channels]:
                    await self._send_notification(
                        channel=channel,
                        recipient=subscriber,
                        content=notification_content,
                        workflow_id=workflow_id
                    )
        
        # Log notification
        self.notification_history.append({
            "workflow_id": workflow_id,
            "event_type": event_type.value,
            "timestamp": datetime.utcnow(),
            "recipients_count": len(subscribers),
            "content_summary": notification_content["subject"]
        })
    
    async def notify_party_response_requested(self, workflow_id: str, party_id: str, 
                                            state: AmendmentWorkflowState):
        """Notify specific party that their response is needed"""
        
        await self.notify_workflow_event(
            workflow_id=workflow_id,
            event_type=NotificationType.PARTY_RESPONSE_REQUESTED,
            state=state,
            additional_data={"target_party": party_id}
        )
    
    async def notify_conflict_detected(self, workflow_id: str, state: AmendmentWorkflowState,
                                     conflicts: List[Dict]):
        """Notify about detected conflicts"""
        
        await self.notify_workflow_event(
            workflow_id=workflow_id,
            event_type=NotificationType.CONFLICT_DETECTED,
            state=state,
            additional_data={"conflicts": conflicts}
        )
    
    async def notify_consensus_reached(self, workflow_id: str, state: AmendmentWorkflowState):
        """Notify that consensus has been reached"""
        
        await self.notify_workflow_event(
            workflow_id=workflow_id,
            event_type=NotificationType.CONSENSUS_REACHED,
            state=state
        )
    
    async def notify_workflow_completed(self, workflow_id: str, state: AmendmentWorkflowState):
        """Notify that workflow has completed successfully"""
        
        await self.notify_workflow_event(
            workflow_id=workflow_id,
            event_type=NotificationType.WORKFLOW_COMPLETED,
            state=state,
            additional_data={"final_document_available": bool(state.final_document)}
        )
    
    async def add_websocket_connection(self, workflow_id: str, websocket):
        """Add WebSocket connection for real-time updates"""
        
        if workflow_id not in self.websocket_connections:
            self.websocket_connections[workflow_id] = []
        
        self.websocket_connections[workflow_id].append(websocket)
        print(f"🔌 WebSocket connected for workflow {workflow_id}")
    
    async def remove_websocket_connection(self, workflow_id: str, websocket):
        """Remove WebSocket connection"""
        
        if workflow_id in self.websocket_connections:
            try:
                self.websocket_connections[workflow_id].remove(websocket)
                print(f"🔌 WebSocket disconnected for workflow {workflow_id}")
            except ValueError:
                pass  # Connection not in list
    
    async def broadcast_real_time_update(self, workflow_id: str, update_data: Dict):
        """Broadcast real-time update via WebSockets"""
        
        if workflow_id not in self.websocket_connections:
            return
        
        message = json.dumps({
            "type": "workflow_update",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": update_data
        })
        
        connections = self.websocket_connections[workflow_id].copy()
        
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Failed to send WebSocket message: {e}")
                # Remove broken connection
                await self.remove_websocket_connection(workflow_id, websocket)
    
    async def _prepare_notification_content(self, event_type: NotificationType, 
                                          state: AmendmentWorkflowState,
                                          additional_data: Optional[Dict] = None) -> Dict[str, str]:
        """Prepare notification content based on event type"""
        
        content_templates = {
            NotificationType.WORKFLOW_INITIATED: {
                "subject": f"Contract Amendment Initiated - {state.contract_id}",
                "body": f"""
                A new contract amendment workflow has been initiated.
                
                Contract ID: {state.contract_id}
                Workflow ID: {state.workflow_id}
                Parties Involved: {', '.join(state.parties)}
                Proposed Changes: {len(state.proposed_changes)} sections
                
                Please review and respond to the proposed changes.
                """
            },
            
            NotificationType.PARTY_RESPONSE_REQUESTED: {
                "subject": f"Response Required - Contract Amendment {state.contract_id}",
                "body": f"""
                Your response is requested for a contract amendment.
                
                Contract ID: {state.contract_id}
                Workflow ID: {state.workflow_id}
                Deadline: {state.metrics.estimated_completion}
                
                Please review the proposed changes and provide your response.
                """
            },
            
            NotificationType.CONFLICT_DETECTED: {
                "subject": f"Conflicts Detected - Contract Amendment {state.contract_id}",
                "body": f"""
                Conflicts have been detected in the contract amendment process.
                
                Contract ID: {state.contract_id}
                Active Conflicts: {len(state.active_conflicts)}
                
                AI mediation is working to resolve these conflicts.
                You may be contacted for additional input.
                """
            },
            
            NotificationType.CONSENSUS_REACHED: {
                "subject": f"Consensus Reached - Contract Amendment {state.contract_id}",
                "body": f"""
                Consensus has been reached for the contract amendment.
                
                Contract ID: {state.contract_id}
                All parties have agreed to the proposed changes.
                
                The amendment is now proceeding to final processing.
                """
            },
            
            NotificationType.WORKFLOW_COMPLETED: {
                "subject": f"Amendment Complete - Contract {state.contract_id}",
                "body": f"""
                The contract amendment has been completed successfully.
                
                Contract ID: {state.contract_id}
                Completion Date: {state.completed_at}
                
                The final amended contract is now available for download.
                """
            }
        }
        
        template = content_templates.get(event_type, {
            "subject": f"Contract Amendment Update - {state.contract_id}",
            "body": f"An update occurred for contract amendment {state.contract_id}"
        })
        
        # Customize with additional data if provided
        if additional_data:
            template["body"] += f"\n\nAdditional Information:\n{json.dumps(additional_data, indent=2)}"
        
        return template
    
    def _should_notify_subscriber(self, subscriber: Dict, event_type: NotificationType) -> bool:
        """Check if subscriber should receive this notification type"""
        
        notification_types = subscriber.get("notification_types", ["all"])
        
        if "all" in notification_types:
            return True
        
        if event_type.value in notification_types:
            return True
        
        # Check for category-based subscriptions
        categories = {
            "critical": [NotificationType.CONFLICT_DETECTED, NotificationType.WORKFLOW_FAILED],
            "updates": [NotificationType.CONSENSUS_REACHED, NotificationType.LEGAL_REVIEW_REQUIRED],
            "completion": [NotificationType.WORKFLOW_COMPLETED]
        }
        
        for category, types in categories.items():
            if category in notification_types and event_type in types:
                return True
        
        return False
    
    async def _send_notification(self, channel: str, recipient: Dict, content: Dict, workflow_id: str):
        """Send notification via specific channel"""
        
        try:
            if channel == NotificationChannel.EMAIL.value:
                await self._send_email_notification(recipient, content)
            
            elif channel == NotificationChannel.WEBSOCKET.value:
                await self._send_websocket_notification(workflow_id, content, recipient)
            
            elif channel == NotificationChannel.WEBHOOK.value:
                await self._send_webhook_notification(recipient, content, workflow_id)
            
            print(f"✅ Sent {channel} notification to {recipient.get('user_id')}")
            
        except Exception as e:
            print(f"❌ Failed to send {channel} notification: {str(e)}")
    
    async def _send_email_notification(self, recipient: Dict, content: Dict):
        """Send email notification"""
        
        if not recipient.get("email") or not self.email_config.get("username"):
            return  # Email not configured
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config["from_email"]
            msg['To'] = recipient["email"]
            msg['Subject'] = content["subject"]
            
            body = content["body"]
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (in production, use proper email service)
            # For demo, just log the email content
            print(f"📧 EMAIL TO: {recipient['email']}")
            print(f"📧 SUBJECT: {content['subject']}")
            print(f"📧 BODY: {content['body'][:100]}...")
            
        except Exception as e:
            print(f"Email send error: {str(e)}")
    
    async def _send_websocket_notification(self, workflow_id: str, content: Dict, recipient: Dict):
        """Send WebSocket notification"""
        
        message = {
            "type": "notification",
            "notification_type": "workflow_event",
            "recipient": recipient.get("user_id"),
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_real_time_update(workflow_id, message)
    
    async def _send_webhook_notification(self, recipient: Dict, content: Dict, workflow_id: str):
        """Send webhook notification"""
        
        webhook_url = recipient.get("webhook_url")
        if not webhook_url:
            return
        
        # In production, use aiohttp to POST to webhook
        payload = {
            "workflow_id": workflow_id,
            "recipient": recipient.get("user_id"),
            "notification": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"🔗 WEBHOOK TO: {webhook_url}")
        print(f"🔗 PAYLOAD: {json.dumps(payload, indent=2)}")
    
    def get_notification_history(self, workflow_id: Optional[str] = None) -> List[Dict]:
        """Get notification history"""
        
        if workflow_id:
            return [n for n in self.notification_history if n["workflow_id"] == workflow_id]
        
        return self.notification_history
    
    def get_active_subscriptions(self, workflow_id: Optional[str] = None) -> Dict:
        """Get active subscriptions"""
        
        if workflow_id:
            return {workflow_id: self.active_subscriptions.get(workflow_id, [])}
        
        return self.active_subscriptions


# Global notification service instance
notification_service = NotificationService()