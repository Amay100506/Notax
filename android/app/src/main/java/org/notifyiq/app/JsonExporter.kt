package org.notifyiq.app

import android.content.Context
import org.json.JSONArray
import java.io.File
import java.io.FileWriter
import java.time.Instant
import java.time.format.DateTimeFormatter

/**
 * Handles JSON persistence and export of captured notification events.
 */
object JsonExporter {

    private const val BUFFER_FILENAME = "notifyiq_events_buffer.json"

    @Synchronized
    fun saveEvent(context: Context, event: NotificationEvent) {
        val events = loadEvents(context).toMutableList()
        events.add(event)
        writeEvents(context, events)
    }

    @Synchronized
    fun loadEvents(context: Context): List<NotificationEvent> {
        val file = File(context.filesDir, BUFFER_FILENAME)
        if (!file.exists()) return emptyList()

        return try {
            val content = file.readText(Charsets.UTF_8)
            val jsonArray = JSONArray(content)
            val list = mutableListOf<NotificationEvent>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                list.add(NotificationEvent.fromJsonObject(obj))
            }
            list
        } catch (e: Exception) {
            emptyList()
        }
    }

    @Synchronized
    fun getEventsJsonString(context: Context): String {
        val events = loadEvents(context)
        val jsonArray = JSONArray()
        events.forEach { jsonArray.put(it.toJsonObject()) }
        return jsonArray.toString(2)
    }

    @Synchronized
    fun clearEvents(context: Context): Boolean {
        val file = File(context.filesDir, BUFFER_FILENAME)
        return if (file.exists()) file.delete() else true
    }

    @Synchronized
    fun exportToExternalFile(context: Context): File? {
        val eventsJson = getEventsJsonString(context)
        val timestamp = DateTimeFormatter.ISO_INSTANT.format(Instant.now()).replace(":", "-")
        val exportFile = File(context.getExternalFilesDir(null), "notifyiq_export_$timestamp.json")
        return try {
            FileWriter(exportFile).use { it.write(eventsJson) }
            exportFile
        } catch (e: Exception) {
            null
        }
    }

    private fun writeEvents(context: Context, events: List<NotificationEvent>) {
        val file = File(context.filesDir, BUFFER_FILENAME)
        val jsonArray = JSONArray()
        events.forEach { jsonArray.put(it.toJsonObject()) }
        FileWriter(file).use { it.write(jsonArray.toString()) }
    }
}
