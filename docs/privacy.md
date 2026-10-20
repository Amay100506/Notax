# NotifyIQ — Privacy & Security Architecture

## 1. Privacy Principles

NotifyIQ is built on the principle of **radical data minimization and local user sovereignty**.

1. **Local-First Processing**: All ML vectorization, classification, deadline parsing, priority calculations, and shopping intelligence run offline on your machine.
2. **Zero Third-Party Cloud AI**: Notification bodies are **never** transmitted to OpenAI, Anthropic, Google Gemini API, or any external LLM service.
3. **No Unsolicited Network Transmission**: The application does not require an active internet connection to parse, prioritize, or analyze notifications.
4. **No Raw Notification Text in Logs**: Application logs strictly log event IDs, status codes, and timings. Notification titles, bodies, and personal metadata are never written to application logs.
5. **No Autonomous Actions**: NotifyIQ is a decision-support tool. It does not automatically dismiss notifications, send replies, or conduct transactions on the user's behalf.

---

## 2. Android Permission & Capture Lifecycle

- **Explicit Access Required**: Android notification capture relies on Android's `NotificationListenerService`. The OS strictly prevents apps from accessing notifications without the user manually navigating to system settings and granting access.
- **Package Allowlist & Pause**: Users can pause capture at any time using a single switch, or exclude sensitive applications (e.g., banking or personal messengers) from capture before data is recorded.
- **Notification Removal Handling**: When Android reports a notification was dismissed in the system shade (`onNotificationRemoved`), NotifyIQ records the removal event metadata separately without purging historical records unless explicitly instructed by the user or retention policy.

---

## 3. Sensitive Data Redaction

NotifyIQ includes an automated rule-based redaction engine (`backend/ai/preprocess.py`) that masks common sensitive patterns prior to classification and database storage:
- **Email addresses** $\rightarrow$ `[EMAIL]`
- **Telephone numbers** $\rightarrow$ `[PHONE]`
- **Credit card & 13–19 digit account sequences** $\rightarrow$ `[ACCOUNT]`
- **URLs and web links** $\rightarrow$ `[URL]`
- **One-time passwords (OTP) and verification codes** $\rightarrow$ `[CODE]`

> [!NOTE]
> Redaction is rule-based pattern matching and is not guaranteed to catch every personal identifier. Users retain the choice to exclude sensitive apps from capture entirely.

---

## 4. Package Exclusion & Zero-Capture Privacy Controls

Package exclusion provides a hard privacy boundary at both the Android device and the backend ingestion layer:

- **Client-Side Exclusion (`SettingsManager.isPackageAllowed`)**: On Android, any package included in the user's exclusion list is discarded immediately in `NotificationCaptureService`. The notification body is never serialized to JSON or buffered in device memory.
- **Backend Ingestion Filtering (`NotificationService.is_package_excluded`)**: When importing batches or processing real-time notifications, the service verifies package identifiers against the persisted exclusion list (`settings.excluded_packages`).
- **Privacy Benefits**:
  - Sensitive applications such as mobile banking (`com.bank.*`), password managers (`com.bitwarden.*`, `com.1password.*`), healthcare apps, and encrypted private messengers (`org.thoughtcrime.securesms`) can be entirely excluded from the intelligence pipeline.
  - Zero attack surface for excluded apps: their notification data never touches the SQLite database, vectorizers, or analytical caches.

---

## 5. Quiet Hours & Notification Deferral

The Quiet Hours subsystem balances notification awareness with cognitive rest and privacy during scheduled hours:

- **Timezone-Aware Schedule**: Users configure a time window (e.g., 22:00 to 07:00) using local timezone settings (`settings.timezone`). Overnight ranges that cross midnight are handled seamlessly.
- **Deferred Processing & Auditing**:
  - Notifications arriving during quiet hours are captured and securely persisted to SQLite, ensuring zero loss of critical context.
  - The notification is flagged with `is_deferred = True` and annotated with `"Deferred: Received during quiet hours"` in its priority explanation list.
- **Privacy & Notification Muting**:
  - Real-time mobile push notifications and haptic alerts through the WebSocket companion are suppressed during quiet hours.
  - High-priority and action items remain safely preserved in the database for the user to review in the Smart Inbox once quiet hours conclude.

---

## 6. Retention Policy & Data Lifecycle Automation

NotifyIQ enforces deterministic, configurable retention limits to prevent unbounded data accumulation:

- **How `retention_expires_at` Works**:
  - Each incoming notification is assigned a retention expiration timestamp calculated as:
    $$\text{retention\_expires\_at} = \text{received\_at} + (\text{retention\_days\_default} \times 86400\text{ seconds})$$
  - The default retention window is 30 days (configurable via `settings.retention_days_default`).
  - The ISO-8601 expiration timestamp is stored in the `retention_expires_at` column of the `notifications` table.
- **Automated Cleanup**:
  - `NotificationService.cleanup_expired_retention()` executes parameterized queries:
    ```sql
    DELETE FROM notifications
    WHERE retention_expires_at IS NOT NULL
      AND retention_expires_at <= ?
    ```
  - Expired records are deleted along with foreign key cascades, keeping database storage compact and privacy-compliant.
  - The retention cleanup routine can be invoked programmatically or triggered via `POST /retention/cleanup`.
- **One-Click Purge**: Users can permanently wipe all captured notifications, actions, feedback, and duplicate groups at any time via the Settings & Privacy dashboard or `POST /privacy/purge`.
- **Local Persistence Security**: The SQLite database is stored locally at `data/notifyiq.db` with WAL mode enabled and is strictly excluded from version control via `.gitignore`.

---

## 7. Shopping Intelligence & Local Price Tracking

NotifyIQ includes an offline shopping intelligence module (`backend/ai/shopping/`) that extracts discounts, coupons, and price histories from promotional alerts:

- **Local-Only Price Extraction**: Unlike commercial browser extensions (such as Honey or BuyHatke) that send browsing URLs, cart contents, and search histories to remote servers, NotifyIQ executes all price parsing entirely on the local machine.
- **Zero Remote Tracking & Affiliate Telemetry**:
  - No external price-comparison APIs, affiliate tracking links, or cloud scrapers are queried.
  - Product titles, original prices, discounted prices, currencies, and coupon codes are extracted locally using deterministic regex and keyword heuristics (`price_extractor.py`, `coupon_detector.py`).
- **Private Price History**:
  - Historical price records are stored strictly in the user's local SQLite database table `shopping_price_history`.
  - Price drop calculations compare current prices only against the user's historical notification observations.
  - No shopping behavioral data, shopping lists, or spending patterns ever leave the device.

---

## 8. Real-Time LAN Forwarding & Threat Model

NotifyIQ allows users to pair their Android device via local Wi-Fi to forward notifications in real time to the laptop FastAPI backend:

### Architecture & Data Flow
1. **NotificationListenerService**: Android OS delivers notification posted events after explicit user consent.
2. **Pre-Transmission Filtering**: Excluded applications are immediately discarded *before* serialization or disk storage.
3. **Local Persistent Queue (`PersistentEventQueue`)**: Unsent events are buffered in internal private app storage (`context.filesDir`).
4. **Authenticated HTTP Ingestion**: Android sends POST requests to `/notifications/forward` with a pre-shared cryptographic API key (`X-NotifyIQ-API-Key`).
5. **Idempotent Deduplication**: SQLite indexes prevent duplicate event submissions when client retries transient network interruptions.
6. **Zero Raw Text Logging**: Neither Android nor FastAPI ever logs raw notification titles or text bodies; only event IDs, package names, timestamps, and error codes are recorded.

### Threat Model & Trust Assumptions
1. **Pre-Shared API Key Authentication**:
   - Ingestion requires a cryptographically generated API key (`notifyiq_sec_<hex32>`) or environment variable.
   - Keys are compared in constant time (`secrets.compare_digest`) to prevent timing side-channel attacks.
2. **Trusted Network Boundary & Plain HTTP Limitations**:
   - The system is designed for trusted private home or office Wi-Fi networks.
   - **Plain HTTP Limitation**: On untrusted public Wi-Fi networks (coffee shops, airports, shared dorms), plain HTTP traffic can be intercepted by adversaries on the same wireless segment.
   - **Security Recommendation**: On untrusted networks, users MUST operate through an encrypted private overlay network (e.g., Tailscale, WireGuard) or terminate TLS using a local reverse proxy (Caddy/Nginx) with HTTPS.
3. **Zero Public Internet Exposure by Default**:
   - The backend runs on `127.0.0.1` by default and only binds to local LAN interfaces when LAN mode is explicitly enabled by the user.
   - No external cloud servers, UPnP ports, or third-party webhooks are utilized.
