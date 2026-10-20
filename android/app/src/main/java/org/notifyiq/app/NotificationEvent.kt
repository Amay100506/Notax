package org.notifyiq.app

import org.json.JSONObject
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * Normalized Android Notification Event.
 * Matches the NotifyIQ documented JSON schema (schema_version = 1).
 */
data class NotificationEvent(
    val schemaVersion: Int = 1,
    val eventId: String = UUID.randomUUID().toString(),
    val packageName: String,
    val title: String,
    val text: String,
    val postedAt: String = DateTimeFormatter.ISO_INSTANT.format(Instant.now()),
    val eventType: String = "posted"
) {
    fun toJsonObject(): JSONObject {
        val json = JSONObject()
        json.put("schema_version", schemaVersion)
        json.put("event_id", eventId)
        json.put("package_name", packageName)
        json.put("title", title)
        json.put("text", text)
        json.put("posted_at", postedAt)
        json.put("event_type", eventType)
        return json
    }

    companion object {
        fun fromJsonObject(json: JSONObject): NotificationEvent {
            return NotificationEvent(
                schemaVersion = json.optInt("schema_version", 1),
                eventId = json.optString("event_id", UUID.randomUUID().toString()),
                packageName = json.optString("package_name", "unknown"),
                title = json.optString("title", ""),
                text = json.optString("text", ""),
                postedAt = json.optString("posted_at", DateTimeFormatter.ISO_INSTANT.format(Instant.now())),
                eventType = json.optString("event_type", "posted")
            )
        }
    }
}
