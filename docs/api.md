# NotifyIQ — REST API Reference

The NotifyIQ backend exposes a local FastAPI service (default bound to `http://127.0.0.1:8000` or `http://0.0.0.0:8000`).

---

## 1. Endpoints Overview

### Core & Notifications

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health, model status, and DB readiness |
| `POST` | `/notifications/import` | Validate and import a batch of Android notification events |
| `POST` | `/notifications/process` | Process a single notification event through AI pipeline |
| `GET` | `/notifications` | Paginated notification list with filters |
| `GET` | `/notifications/{id}` | Detailed notification record with explanations |
| `DELETE` | `/notifications/{id}` | Delete notification and its cascade |

### Actions & Human Feedback

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/actions` | List detected action items |
| `GET` | `/actions/upcoming` | List actions with upcoming deadlines |
| `PATCH` | `/actions/{id}` | Update action status (`open`, `completed`, `dismissed`) |
| `POST` | `/feedback` | Submit user correction on classification or priority |
| `GET` | `/feedback` | List historical user feedback |

### Analytics & System Settings

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/summary` | Aggregate statistics (total, high priority, actions, etc.) |
| `GET` | `/analytics/categories` | Counts and average confidence by category |
| `GET` | `/analytics/priorities` | Counts and average score by priority level |
| `GET` | `/settings` | Retrieve application settings (including exclusions and quiet hours) |
| `PATCH` | `/settings` | Update validated configuration settings |
| `POST` | `/retention/cleanup` | Execute automated retention cleanup for expired notifications |
| `POST` | `/privacy/purge` | Purge all stored notifications, actions, and feedback |

### Shopping Intelligence (Local-First)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/shopping/summary` | Aggregate metrics (deal counts, average discount, coupons, price drops) |
| `GET` | `/shopping/deals` | List curated deals sorted by deal quality score |
| `GET` | `/shopping/price-history/{product_title}` | Historical price observations and trends for a product |
| `POST` | `/shopping/analyze` | Analyze notification text for prices, deal scores, coupons, and drops |
| `GET` | `/shopping/coupons` | List harvested promo codes and discount vouchers |
| `POST` | `/shopping/price-history` | Record a price observation point for tracking |

### Mobile Gateway & Companion

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/mobile/qr` | Dynamic QR code PNG for instant mobile pairing |
| `GET` | `/mobile/info` | Connection details and LAN IP address |
| `WS` | `/ws/notifications` | Real-time WebSocket event stream for mobile PWA |

---

## 2. Notification Endpoints

### Import Notification Batch
`POST /notifications/import`

Validate and import multiple notifications from Android export:

```json
{
  "notifications": [
    {
      "schema_version": 1,
      "event_id": "evt-android-001",
      "package_name": "com.university.portal",
      "title": "Assignment Deadline",
      "text": "Please submit your capstone report before tomorrow 5 PM.",
      "posted_at": "2026-10-19T10:00:00Z",
      "event_type": "posted"
    }
  ]
}
```

Response (`200 OK`):
```json
{
  "total_records": 1,
  "accepted_count": 1,
  "rejected_count": 0,
  "already_processed_count": 0,
  "accepted_records": [...],
  "rejected_records": [],
  "warnings": []
}
```

### Process Single Notification
`POST /notifications/process`

Process a single notification event synchronously with optional persistence:

```json
{
  "notification": {
    "schema_version": 1,
    "event_id": "evt-002",
    "package_name": "com.amazon.mShop.android.shopping",
    "title": "Lightning Deal: Sony WH-1000XM5",
    "text": "Huge savings! Now ₹24,999 down from ₹34,990. Use code SONY2000 for extra ₹2,000 off! Expires in 4 hours.",
    "posted_at": "2026-10-19T14:00:00Z",
    "event_type": "posted"
  },
  "persist": true
}
```

---

## 3. Shopping Intelligence Endpoints

All shopping extraction runs 100% locally on your machine without external cloud API calls.

### Shopping Summary
`GET /shopping/summary`

Returns aggregated intelligence across shopping apps, including deal counts, discount metrics, and top shopping merchants.

Response (`200 OK`):
```json
{
  "total_shopping_notifications": 42,
  "active_deals_count": 18,
  "coupons_count": 12,
  "average_discount_pct": 28.5,
  "top_stores": [
    {"package_name": "com.amazon.mShop.android.shopping", "count": 22},
    {"package_name": "com.flipkart.android", "count": 14}
  ],
  "recent_price_drops": [
    {
      "product_title": "Sony WH-1000XM5",
      "package_name": "com.amazon.mShop.android.shopping",
      "current_price": 24999.0,
      "previous_price": 29990.0,
      "drop_amount": 4991.0,
      "drop_percentage": 16.64,
      "detected_at": "2026-10-19T14:05:00Z"
    }
  ]
}
```

### List Curated Deals
`GET /shopping/deals?limit=50&min_score=50.0`

Query Parameters:
- `limit` (integer, optional, default: 50, max: 200): Maximum deals to return.
- `min_score` (float, optional, default: 0.0, max: 100.0): Filter deals with deal score at or above threshold.

Response (`200 OK`):
```json
[
  {
    "id": "deal-001",
    "product_title": "Apple iPad Air 11-inch",
    "package_name": "com.flipkart.android",
    "current_price": 49900.0,
    "original_price": 59900.0,
    "discount_percentage": 16.69,
    "currency": "INR",
    "deal_score": 82.5,
    "deal_quality": "Great Deal",
    "detected_at": "2026-10-19T12:00:00Z"
  }
]
```

### Product Price History
`GET /shopping/price-history/{product_title}?limit=50`

Path Parameters:
- `product_title` (string, required): Product title or query substring.

Response (`200 OK`):
```json
{
  "product_title": "Sony WH-1000XM5",
  "data_points": 3,
  "min_price": 24999.0,
  "max_price": 34990.0,
  "current_price": 24999.0,
  "history": [
    {"price": 34990.0, "currency": "INR", "recorded_at": "2026-10-01T10:00:00Z", "package_name": "com.amazon.mShop.android.shopping"},
    {"price": 29990.0, "currency": "INR", "recorded_at": "2026-10-10T11:00:00Z", "package_name": "com.amazon.mShop.android.shopping"},
    {"price": 24999.0, "currency": "INR", "recorded_at": "2026-10-19T14:00:00Z", "package_name": "com.amazon.mShop.android.shopping"}
  ]
}
```

### Analyze Notification for Shopping Intelligence
`POST /shopping/analyze`

Analyzes notification text for prices, coupons, and historical price drops without requiring a full pipeline run.

Request Body:
```json
{
  "title": "Price Drop: Samsung Galaxy S24 Ultra",
  "text": "Grab now for ₹1,09,999 down from ₹1,29,999! Use coupon ULTRA5K for additional ₹5,000 instant discount.",
  "package_name": "com.samsung.e-store",
  "category": "promotional",
  "persist": true
}
```

Response (`200 OK`):
```json
{
  "product_title": "Samsung Galaxy S24 Ultra",
  "current_price": 109999.0,
  "original_price": 129999.0,
  "discount_percentage": 15.38,
  "currency": "INR",
  "deal_score": 78.4,
  "deal_quality": "Good Deal",
  "coupons": [
    {
      "code": "ULTRA5K",
      "discount_amount": 5000.0,
      "currency": "INR"
    }
  ],
  "price_drop_alert": {
    "is_price_drop": true,
    "drop_amount": 20000.0,
    "drop_percentage": 15.38
  }
}
```

### List Harvested Coupons
`GET /shopping/coupons`

Returns all active coupon codes, promo vouchers, and referral discount codes harvested from promotional notifications.

Response (`200 OK`):
```json
[
  {
    "code": "SONY2000",
    "description": "Extra ₹2,000 discount",
    "package_name": "com.amazon.mShop.android.shopping",
    "first_seen": "2026-10-19T14:00:00Z"
  },
  {
    "code": "ULTRA5K",
    "description": "₹5,000 instant discount",
    "package_name": "com.samsung.e-store",
    "first_seen": "2026-10-19T15:30:00Z"
  }
]
```

### Record Price Observation
`POST /shopping/price-history`

Manually or programmatically record a price observation point for a product.

Request Body:
```json
{
  "product_title": "Sony WH-1000XM5",
  "package_name": "com.amazon.mShop.android.shopping",
  "price": 24999.0,
  "currency": "INR",
  "notification_id": "optional-notification-uuid"
}
```

Response (`201 Created`):
```json
{
  "status": "recorded",
  "product_title": "Sony WH-1000XM5",
  "price": 24999.0,
  "currency": "INR",
  "recorded_at": "2026-10-19T15:35:00Z"
}
```

---

## 4. Settings & Policy Configuration

The `/settings` endpoints manage dynamic application behavior, privacy boundaries, and scheduling.

### Retrieve Settings
`GET /settings`

Response (`200 OK`):
```json
{
  "confidence_threshold": "0.6",
  "near_dup_threshold": "0.85",
  "timezone": "Asia/Kolkata",
  "redaction_enabled": "true",
  "recency_tau_hours": "24.0",
  "excluded_packages": "[\"com.bank.app\", \"org.thoughtcrime.securesms\"]",
  "quiet_hours_enabled": "true",
  "quiet_hours_start": "22",
  "quiet_hours_end": "7"
}
```

### Package Exclusion Management
`PATCH /settings`

To exclude specific apps (e.g., banking or personal chat apps) from being ingested by the AI pipeline:

```json
{
  "settings": {
    "excluded_packages": "[\"com.chase.sig.android\", \"com.whatsapp\", \"org.thoughtcrime.securesms\"]"
  }
}
```

Response (`200 OK`):
```json
{
  "status": "settings_updated",
  "updated": ["excluded_packages"]
}
```

> [!NOTE]
> When a package is in the exclusion list, notifications from that package are skipped during ingestion and batch processing, leaving zero trace in the SQLite database.

### Quiet Hours Configuration
`PATCH /settings`

Configure quiet hours (24-hour integers from `0` to `23`) to defer notifications arriving during focus or sleep periods:

```json
{
  "settings": {
    "quiet_hours_enabled": "true",
    "quiet_hours_start": "22",
    "quiet_hours_end": "7"
  }
}
```

- Notifications arriving during quiet hours are persisted for historical integrity but flagged as `is_deferred: true`.
- Real-time mobile alerts and WebSocket broadcasts are silenced during this period.

To disable quiet hours:
```json
{
  "settings": {
    "quiet_hours_enabled": "false"
  }
}
```

---

## 5. Retention Cleanup & Data Purge

### Retention Cleanup
`POST /retention/cleanup`

Deletes notifications whose `retention_expires_at` timestamp has passed (calculated based on `retention_days_default`, default 30 days).

Response (`200 OK`):
```json
{
  "status": "cleanup_completed",
  "deleted_count": 14
}
```

### Complete Data Purge
`POST /privacy/purge`

Immediately and permanently wipes all notifications, action items, duplicate groups, and feedback records from the local SQLite database.

Response (`200 OK`):
```json
{
  "status": "purged",
  "deleted_notifications": 150,
  "deleted_actions": 35,
  "deleted_feedback": 8,
  "deleted_groups": 12
}
```

---

## 6. Running the API

Start the service using Uvicorn:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

To enable LAN mobile companion pairing:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Interactive OpenAPI Swagger UI is available at `http://127.0.0.1:8000/docs`.
ReDoc documentation is available at `http://127.0.0.1:8000/redoc`.
