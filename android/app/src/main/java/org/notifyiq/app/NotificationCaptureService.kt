package org.notifyiq.app

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * Android NotificationListenerService implementation for NotifyIQ.
 * Runs in the background only when explicitly granted permission by the user.
 * Captures, normalizes, and buffers notification metadata locally.
 */
class NotificationCaptureService : NotificationListenerService() {

    private lateinit var settingsManager: SettingsManager

    companion object {
        private const val TAG = "NotifyIQService"
    }

    override fun onCreate() {
        super.onCreate()
        settingsManager = SettingsManager(applicationContext)
        Log.i(TAG, "NotificationCaptureService created.")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null) return

        val packageName = sbn.packageName ?: "unknown"
        if (!settingsManager.isPackageAllowed(packageName)) {
            Log.d(TAG, "Notification from excluded or paused package: $packageName")
            return
        }

        val notification = sbn.notification ?: return
        val extras = notification.extras ?: return

        // Extract title and text safely
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()?.trim()
            ?: extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()?.trim()
            ?: ""

        // Skip completely empty events
        if (title.isEmpty() && text.isEmpty()) {
            return
        }

        val postTimeMillis = sbn.postTime
        val postedAtIso = try {
            DateTimeFormatter.ISO_INSTANT.format(Instant.ofEpochMilli(postTimeMillis))
        } catch (e: Exception) {
            DateTimeFormatter.ISO_INSTANT.format(Instant.now())
        }

        val event = NotificationEvent(
            schemaVersion = 1,
            eventId = UUID.randomUUID().toString(),
            packageName = packageName,
            title = title,
            text = text,
            postedAt = postedAtIso,
            eventType = "posted"
        )

        // Save locally to JSON buffer as persistent fallback
        JsonExporter.saveEvent(applicationContext, event)
        Log.i(TAG, "Captured notification event ${event.eventId} from package $packageName")

        // If real-time forwarding is enabled, enqueue into persistent queue and trigger network flush
        if (settingsManager.isForwardingEnabled) {
            PersistentEventQueue.enqueue(applicationContext, event)
            NotificationForwarder.triggerFlush(applicationContext)
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        if (sbn == null) return

        val packageName = sbn.packageName ?: "unknown"
        if (!settingsManager.isPackageAllowed(packageName)) return

        // Handle removal event separately from history deletion
        val event = NotificationEvent(
            schemaVersion = 1,
            eventId = UUID.randomUUID().toString(),
            packageName = packageName,
            title = "",
            text = "",
            postedAt = DateTimeFormatter.ISO_INSTANT.format(Instant.now()),
            eventType = "removed"
        )

        // Save locally to JSON buffer
        JsonExporter.saveEvent(applicationContext, event)
        Log.d(TAG, "Recorded notification removal event for $packageName")
    }
}
