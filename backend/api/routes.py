"""
FastAPI Routes for NotifyIQ.
Provides local endpoints for health checks, notification ingestion, AI processing,
actions management, active feedback, settings, and privacy purge.
"""

from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Security, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import io
import socket
import qrcode
from backend.ai.pipeline import AIPipeline
from backend.utils.calendar_sync import (
    generate_ics_content,
    generate_google_calendar_url,
    generate_outlook_calendar_url,
)
from backend.api.schemas import (
    ActionItemResponse,
    ActionStatusUpdate,
    FeedbackRequest,
    FeedbackResponse,
    ForwardAuthInfoResponse,
    ForwardNotificationBatch,
    ForwardNotificationItem,
    ForwardingAckResponse,
    ForwardingStatusResponse,
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
from backend.services.shopping_service import ShoppingService
from backend.services.digest_service import DigestService, DailyDigest
from backend.utils.webhook_notifier import WebhookNotifier
from backend.utils.configuration import settings
from backend.utils.logging_config import logger

router = APIRouter()
repo = Repository()
pipeline = AIPipeline(repository=repo)
import_service = ImportService(repository=repo)
shopping_service = ShoppingService(repository=repo)
digest_service = DigestService(repository=repo)
webhook_notifier = WebhookNotifier(repository=repo)


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

security_bearer = HTTPBearer(auto_error=False)


def get_or_create_api_key(repository: Repository) -> str:
    """
    Retrieves the local network API authentication key.
    Checks environment/settings first, then database, or generates a secure random token.
    Never hardcoded and safe across restarts.
    """
    if settings.api_key:
        return settings.api_key
    
    stored = repository.get_setting("api_key")
    if stored and stored.strip():
        return stored.strip()
    
    new_key = f"notifyiq_sec_{secrets.token_hex(16)}"
    repository.set_setting("api_key", new_key)
    logger.info("Generated new secure NotifyIQ local network API key.")
    return new_key


def verify_api_key(
    x_notifyiq_api_key: Optional[str] = Header(None, alias="X-NotifyIQ-API-Key"),
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> str:
    """
    Verifies that the incoming request contains a valid API key.
    Accepts X-NotifyIQ-API-Key header or Authorization: Bearer <key>.
    Uses constant-time comparison to prevent timing attacks.
    """
    valid_key = get_or_create_api_key(repo)
    provided_key = None
    if x_notifyiq_api_key:
        provided_key = x_notifyiq_api_key.strip()
    elif auth_credentials and auth_credentials.credentials:
        provided_key = auth_credentials.credentials.strip()

    if not provided_key or not secrets.compare_digest(provided_key, valid_key):
        logger.warning("Unauthorized forwarding attempt rejected (invalid or missing API key).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing NotifyIQ API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return provided_key


@router.get("/forward/status", response_model=ForwardingStatusResponse)
def get_forwarding_status(
    x_notifyiq_api_key: Optional[str] = Header(None, alias="X-NotifyIQ-API-Key"),
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
):
    """
    Health and connection test endpoint for the Android client.
    Allows Android client to test network connectivity and verify whether provided credentials are valid.
    """
    valid_key = get_or_create_api_key(repo)
    provided_key = None
    if x_notifyiq_api_key:
        provided_key = x_notifyiq_api_key.strip()
    elif auth_credentials and auth_credentials.credentials:
        provided_key = auth_credentials.credentials.strip()

    is_authenticated = bool(provided_key and secrets.compare_digest(provided_key, valid_key))
    lan_ip = get_lan_ip()
    server_time = datetime.now(timezone.utc).isoformat()

    return ForwardingStatusResponse(
        status="online",
        authenticated=is_authenticated,
        version="1.0.0",
        lan_mode=settings.lan_mode,
        server_time=server_time,
        lan_ip=lan_ip,
        port=settings.port,
    )


@router.get("/forward/auth-info", response_model=ForwardAuthInfoResponse)
def get_forward_auth_info():
    """
    Returns local network pairing parameters and authentication key for companion app setup.
    Only intended for display in the local dashboard and pairing screens.
    """
    lan_ip = get_lan_ip()
    api_key = get_or_create_api_key(repo)
    pairing_url = f"notifyiq://pair?host={lan_ip}&port={settings.port}&key={api_key}"
    return ForwardAuthInfoResponse(
        lan_ip=lan_ip,
        port=settings.port,
        api_key=api_key,
        pairing_url=pairing_url,
        lan_mode=settings.lan_mode,
    )


@router.post("/forward/auth-key/regenerate")
def regenerate_forward_api_key():
    """Regenerates a new secure API key, invalidating previous companion app credentials."""
    new_key = f"notifyiq_sec_{secrets.token_hex(16)}"
    repo.set_setting("api_key", new_key)
    logger.info("Regenerated NotifyIQ local network API key.")
    return {"status": "regenerated", "api_key": new_key}


@router.post("/notifications/forward", response_model=ForwardingAckResponse)
async def forward_notifications(
    batch: ForwardNotificationBatch,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """
    Real-time authenticated notification ingestion endpoint for Android companion app.
    Validates batch limits, verifies timestamps and schema, performs idempotent deduplication,
    passes new notifications through the AI pipeline and shopping intelligence,
    persists results to SQLite, broadcasts live via WebSockets, and returns acknowledgments.
    Never logs raw notification content.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_bytes:
        logger.warning(
            "Rejected forwarding request: Content-Length %s exceeds limit %d",
            content_length,
            settings.max_request_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload exceeds maximum allowed size of {settings.max_request_bytes} bytes.",
        )

    if len(batch.notifications) > settings.max_batch_size:
        logger.warning(
            "Rejected forwarding request: Batch size %d exceeds limit %d",
            len(batch.notifications),
            settings.max_batch_size,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch size {len(batch.notifications)} exceeds maximum allowed limit {settings.max_batch_size}.",
        )

    accepted_count = 0
    duplicate_count = 0
    acknowledged_ids: list[str] = []

    excluded_str = repo.get_setting("excluded_packages") or ""
    excluded_set = {p.strip().lower() for p in excluded_str.split(",") if p.strip()}

    for item in batch.notifications:
        event_id = item.event_id
        pkg = (item.package_name or "").lower()

        # Check package exclusions
        if pkg in excluded_set:
            logger.info("Skipped excluded package notification for event %s", event_id)
            acknowledged_ids.append(event_id)
            continue

        # Idempotency deduplication check against SQLite database
        existing = repo.get_notification_by_event_id(event_id)
        if existing:
            duplicate_count += 1
            acknowledged_ids.append(event_id)
            logger.info("Idempotent skip for already processed event %s (pkg: %s)", event_id, item.package_name)
            continue

        # Process new event through AI pipeline and persist to SQLite
        event_dict = item.model_dump()
        try:
            res = pipeline.process_notification(event_dict, persist=True)
            try:
                shopping_service.analyze_and_store(res)
            except Exception as se:
                logger.debug("Shopping analysis skipped for event %s: %s", event_id, se)

            # Broadcast to live UI via WebSocket
            await manager.broadcast({"type": "NEW_NOTIFICATION", "payload": res})

            accepted_count += 1
            acknowledged_ids.append(event_id)
            logger.info("Accepted and processed forwarded event %s (pkg: %s)", event_id, item.package_name)
        except Exception as e:
            # Never expose notification content in error logs!
            logger.error("Failed to process event %s (pkg: %s): %s", event_id, item.package_name, type(e).__name__)

    server_now = datetime.now(timezone.utc).isoformat()
    repo.set_setting("latest_forward_ingestion_at", server_now)
    current_fwd_count = int(repo.get_setting("total_forwarded_count") or "0") + accepted_count
    repo.set_setting("total_forwarded_count", str(current_fwd_count))

    return ForwardingAckResponse(
        status="ok",
        accepted_count=accepted_count,
        duplicate_count=duplicate_count,
        acknowledged_event_ids=acknowledged_ids,
        server_timestamp=server_now,
    )



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
        try:
            shopping_service.analyze_and_store(res)
        except Exception:
            pass
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
    if req.persist:
        try:
            shopping_service.analyze_and_store(result)
        except Exception:
            pass
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


@router.get("/actions/{action_id}/calendar.ics")
def export_action_ics(action_id: str):
    """Exports an action with a deadline as a standard RFC 5545 iCalendar (.ics) file."""
    action = repo.get_action_by_id(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action item not found")

    deadline_str = action.get("deadline_at")
    if not deadline_str:
        raise HTTPException(status_code=400, detail="Action item does not have a parseable deadline")

    try:
        dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid deadline timestamp: {e}")

    title = action.get("action_text") or action.get("notification_title") or "Task Reminder"
    desc = f"Action: {action.get('action_text', '')}\nSource App: {action.get('package_name', '')}\nDetails: {action.get('notification_text', '')}"
    ics_text = generate_ics_content(
        title=title,
        description=desc,
        deadline_at=dt,
        event_uid=f"notifyiq-act-{action_id}",
    )

    filename = f"action_{action_id[:8]}.ics"
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/actions/{action_id}/calendar-links")
def get_action_calendar_links(action_id: str):
    """Returns direct one-click web calendar URLs for Google Calendar and Outlook."""
    action = repo.get_action_by_id(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action item not found")

    deadline_str = action.get("deadline_at")
    if not deadline_str:
        raise HTTPException(status_code=400, detail="Action item does not have a parseable deadline")

    try:
        dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid deadline timestamp: {e}")

    title = action.get("action_text") or action.get("notification_title") or "Task Reminder"
    desc = f"Action: {action.get('action_text', '')}\nSource App: {action.get('package_name', '')}"
    google_url = generate_google_calendar_url(title=title, description=desc, deadline_at=dt)
    outlook_url = generate_outlook_calendar_url(title=title, description=desc, deadline_at=dt)

    return {
        "action_id": action_id,
        "title": title,
        "deadline_at": deadline_str,
        "google_calendar_url": google_url,
        "outlook_calendar_url": outlook_url,
        "ics_download_url": f"/api/v1/actions/{action_id}/calendar.ics",
    }


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


@router.get("/analytics/digest", response_model=DailyDigest)
def get_daily_digest():
    """Generates an offline AI daily digest and executive briefing."""
    return digest_service.generate_daily_digest()


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


class WebhookConfigRequest(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    webhooks_enabled: Optional[bool] = None


@router.get("/settings/webhooks")
def get_webhook_settings():
    """Returns current webhook configuration status (tokens masked for security)."""
    cfg = webhook_notifier.get_config()
    tok = cfg.get("telegram_bot_token", "")
    masked_tok = f"{tok[:4]}...{tok[-4:]}" if len(tok) > 8 else ("configured" if tok else "")
    disc = cfg.get("discord_webhook_url", "")
    masked_disc = f"{disc[:12]}...{disc[-6:]}" if len(disc) > 18 else ("configured" if disc else "")
    return {
        "webhooks_enabled": cfg["webhooks_enabled"],
        "has_telegram": bool(tok and cfg["telegram_chat_id"]),
        "has_discord": bool(disc),
        "telegram_token_preview": masked_tok,
        "discord_url_preview": masked_disc,
    }


@router.post("/settings/webhooks")
def update_webhook_settings(req: WebhookConfigRequest):
    """Updates external webhook parameters in SQLite settings."""
    webhook_notifier.save_config(
        telegram_bot_token=req.telegram_bot_token,
        telegram_chat_id=req.telegram_chat_id,
        discord_webhook_url=req.discord_webhook_url,
        webhooks_enabled=req.webhooks_enabled,
    )
    return {"status": "saved", "webhooks_enabled": req.webhooks_enabled}


@router.post("/settings/webhooks/test")
def test_webhook_alerts():
    """Dispatches a test notification across configured webhooks."""
    sent = webhook_notifier.notify_urgent_alert(
        title="Test Alert from NotifyIQ",
        text="Your webhook configuration is active and working properly!",
        priority_score=92.5,
    )
    return {"status": "dispatched" if sent else "not_sent", "sent": sent}

