"""
FastAPI Routes for NotifyIQ.
Provides local endpoints for health checks, notification ingestion, AI processing,
actions management, active feedback, settings, and privacy purge.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse, FileResponse
import io
import socket
import qrcode
from backend.ai.pipeline import AIPipeline
from backend.api.schemas import (
    ActionItemResponse,
    ActionStatusUpdate,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    NotificationImportBatch,
    NotificationImportItem,
    NotificationListResponse,
    NotificationResponse,
    ProcessNotificationRequest,
    PurgeResponse,
    SettingsUpdate,
)
from backend.database.repository import Repository
from backend.services.import_service import ImportReport, ImportService
from backend.utils.configuration import settings
from backend.utils.logging_config import logger

router = APIRouter()
repo = Repository()
pipeline = AIPipeline(repository=repo)
import_service = ImportService(repository=repo)


def get_lan_ip() -> str:
    """Discovers host LAN IP address for mobile pairing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Mobile client connected via WebSocket. Active clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("Mobile client disconnected. Active clients: %d", len(self.active_connections))

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """Real-time live WebSocket stream for mobile PWA companion."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/mobile/qr")
def get_mobile_qr():
    """Generates a dynamic QR code for quick mobile camera pairing."""
    lan_ip = get_lan_ip()
    mobile_url = f"http://{lan_ip}:8000/mobile"
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(mobile_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#4F46E5", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/mobile/info")
def get_mobile_connection_info():
    """Returns local network pairing parameters for mobile companion."""
    lan_ip = get_lan_ip()
    return {
        "lan_ip": lan_ip,
        "port": 8000,
        "mobile_url": f"http://{lan_ip}:8000/mobile",
        "ws_url": f"ws://{lan_ip}:8000/ws/notifications",
        "active_clients": len(manager.active_connections),
    }


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Returns application health and model availability without exposing sensitive data."""
    is_model_loaded = pipeline.classifier.model is not None
    model_type = "tfidf_logistic_regression" if is_model_loaded else "rule_fallback"
    db_exists = Path(settings.db_path).exists()
    return HealthResponse(
        status="healthy",
        model_loaded=is_model_loaded,
        model_type=model_type,
        db_initialized=db_exists,
        version="1.0.0",
    )


@router.post("/notifications/import", response_model=ImportReport)
async def import_notifications(batch: NotificationImportBatch):
    """Imports one or more validated notification events from Android."""
    items = [item.model_dump() for item in batch.notifications]
    report = import_service.validate_and_filter_events(items)
    
    # Process and persist accepted items
    for event in report.accepted_records:
        res = pipeline.process_notification(event, persist=True)
        await manager.broadcast({"type": "NEW_NOTIFICATION", "payload": res})

    return report


@router.post("/notifications/process", response_model=NotificationResponse)
async def process_single_notification(req: ProcessNotificationRequest):
    """Processes a single notification through the AI pipeline."""
    event_dict = req.notification.model_dump()
    if req.persist:
        existing = repo.get_notification_by_event_id(event_dict["event_id"])
        if existing:
            return NotificationResponse(**existing)
    result = pipeline.process_notification(event_dict, persist=req.persist)
    # Broadcast to connected mobile devices in real time
    await manager.broadcast({"type": "NEW_NOTIFICATION", "payload": result})
    return NotificationResponse(**result)


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = None,
    priority_level: Optional[str] = None,
    package_name: Optional[str] = None,
    action_detected: Optional[bool] = None,
    deadline_detected: Optional[bool] = None,
    is_duplicate: Optional[bool] = None,
    search: Optional[str] = None,
):
    """Returns paginated notifications matching filter criteria."""
    items, total = repo.list_notifications(
        limit=limit,
        offset=offset,
        category=category,
        priority_level=priority_level,
        package_name=package_name,
        action_detected=action_detected,
        deadline_detected=deadline_detected,
        is_duplicate=is_duplicate,
        search=search,
    )
    return NotificationListResponse(
        items=[NotificationResponse(**item) for item in items],
        total_count=total,
        limit=limit,
        offset=offset,
    )


@router.get("/notifications/{notification_id}", response_model=NotificationResponse)
def get_notification(notification_id: str):
    """Returns details for a single notification record."""
    item = repo.get_notification_by_id(notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationResponse(**item)


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_200_OK)
def delete_notification(notification_id: str):
    """Deletes a notification and cascades to actions/feedback."""
    success = repo.delete_notification(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found or already deleted")
    return {"status": "deleted", "id": notification_id}


@router.get("/actions", response_model=list[ActionItemResponse])
def list_actions(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Lists detected action items."""
    actions = repo.list_actions(status=status_filter, limit=limit, offset=offset)
    return [ActionItemResponse(**a) for a in actions]


@router.get("/actions/upcoming", response_model=list[ActionItemResponse])
def list_upcoming_actions(limit: int = 20):
    """Lists open action items with deadlines."""
    actions = repo.list_actions(status="open", limit=limit)
    upcoming = [a for a in actions if a.get("deadline_at")]
    return [ActionItemResponse(**a) for a in upcoming]


@router.patch("/actions/{action_id}", status_code=status.HTTP_200_OK)
def update_action_status(action_id: str, update: ActionStatusUpdate):
    """Updates the status of an action (open, completed, dismissed)."""
    success = repo.update_action_status(action_id, update.status)
    if not success:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"status": "updated", "action_id": action_id, "new_status": update.status}


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(fb: FeedbackRequest):
    """Records user corrections for active learning and model tuning."""
    notif = repo.get_notification_by_id(fb.notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    result = repo.record_feedback(
        notification_id=fb.notification_id,
        feedback_type=fb.feedback_type,
        original_value=fb.original_value,
        corrected_value=fb.corrected_value,
    )
    return FeedbackResponse(**result)


@router.get("/feedback", response_model=list[FeedbackResponse])
def list_feedback(limit: int = 50):
    """Returns stored feedback records."""
    fb_list = repo.list_feedback(limit=limit)
    return [FeedbackResponse(**f) for f in fb_list]


@router.get("/analytics/summary")
def get_analytics_summary():
    """Returns overall calculated aggregate statistics."""
    return repo.get_analytics_summary()


@router.get("/analytics/categories")
def get_analytics_categories():
    """Returns notification category counts and average confidence."""
    return repo.get_category_counts()


@router.get("/analytics/priorities")
def get_analytics_priorities():
    """Returns notification priority distribution."""
    return repo.get_priority_counts()


@router.get("/settings")
def get_application_settings():
    """Returns current non-sensitive application settings."""
    stored = repo.get_all_settings()
    # Merge defaults with stored settings
    merged = {
        "confidence_threshold": stored.get("confidence_threshold", str(settings.confidence_threshold)),
        "near_dup_threshold": stored.get("near_dup_threshold", str(settings.near_dup_threshold)),
        "timezone": stored.get("timezone", settings.timezone),
        "redaction_enabled": stored.get("redaction_enabled", str(settings.redaction_enabled)),
        "recency_tau_hours": stored.get("recency_tau_hours", str(settings.recency_tau_hours)),
    }
    merged.update(stored)
    return merged


@router.patch("/settings")
def update_application_settings(req: SettingsUpdate):
    """Updates validated application settings."""
    for k, v in req.settings.items():
        repo.set_setting(k, str(v))
    return {"status": "settings_updated", "updated": list(req.settings.keys())}


@router.post("/retention/cleanup")
def cleanup_retention():
    """Removes notifications that have exceeded their retention expiration timestamp."""
    deleted = repo.cleanup_expired_retention()
    return {"status": "cleanup_completed", "deleted_count": deleted}


@router.post("/privacy/purge", response_model=PurgeResponse)
def purge_all_data():
    """Purges all locally retained notification data, actions, and feedback."""
    summary = repo.purge_all_data()
    logger.info("Purged all notification data on user request: %s", str(summary))
    return PurgeResponse(
        status="purged",
        deleted_notifications=summary["deleted_notifications"],
        deleted_actions=summary["deleted_actions"],
        deleted_feedback=summary["deleted_feedback"],
        deleted_groups=summary["deleted_groups"],
    )
