package org.notifyiq.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class NotificationEventTest {

    @Test
    fun testEventSerializationAndDeserialization() {
        val event = NotificationEvent(
            schemaVersion = 1,
            eventId = "test-uuid-1234",
            packageName = "com.google.android.gm",
            title = "Project Meeting",
            text = "Please submit the quarterly review before 5 PM",
            postedAt = "2026-10-19T10:30:00Z",
            eventType = "posted"
        )

        val json = event.toJsonObject()
        assertEquals(1, json.getInt("schema_version"))
        assertEquals("test-uuid-1234", json.getString("event_id"))
        assertEquals("com.google.android.gm", json.getString("package_name"))
        assertEquals("Project Meeting", json.getString("title"))
        assertEquals("Please submit the quarterly review before 5 PM", json.getString("text"))
        assertEquals("2026-10-19T10:30:00Z", json.getString("posted_at"))
        assertEquals("posted", json.getString("event_type"))

        val deserialized = NotificationEvent.fromJsonObject(json)
        assertEquals(event.eventId, deserialized.eventId)
        assertEquals(event.packageName, deserialized.packageName)
        assertEquals(event.title, deserialized.title)
        assertEquals(event.text, deserialized.text)
        assertEquals(event.postedAt, deserialized.postedAt)
    }

    @Test
    fun testSafeHandlingOfMissingFields() {
        val json = JSONObject()
        json.put("schema_version", 1)
        json.put("package_name", "com.unknown.app")

        val event = NotificationEvent.fromJsonObject(json)
        assertNotNull(event.eventId)
        assertEquals("com.unknown.app", event.packageName)
        assertEquals("", event.title)
        assertEquals("", event.text)
    }
}
