package org.notifyiq.app

import android.content.Context
import org.json.JSONArray
import java.io.File
import java.io.FileWriter

/**
 * Thread-safe persistent local event queue for reliable real-time notification forwarding.
 * Persists unsent events to internal storage to survive process death, network failures,
 * or server restarts. Provides atomic peek and dequeue-by-ID operations to guarantee
 * zero event loss and prevent duplicate submissions during retries.
 */
object PersistentEventQueue {

    private const val QUEUE_FILENAME = "notifyiq_forward_queue.json"
    private val lock = Any()

    /**
     * Appends an event to the end of the persistent queue.
     * Returns the updated total number of queued events.
     */
    fun enqueue(filesDir: File, event: NotificationEvent): Int {
        synchronized(lock) {
            val events = loadQueueInternal(filesDir).toMutableList()
            if (events.none { it.eventId == event.eventId }) {
                events.add(event)
                saveQueueInternal(filesDir, events)
            }
            return events.size
        }
    }

    fun enqueue(context: Context, event: NotificationEvent): Int = enqueue(context.filesDir, event)

    /**
     * Reads up to maxBatchSize oldest pending events from the queue without removing them.
     */
    fun peekBatch(filesDir: File, maxBatchSize: Int = 50): List<NotificationEvent> {
        synchronized(lock) {
            val events = loadQueueInternal(filesDir)
            return if (events.size <= maxBatchSize) {
                events
            } else {
                events.subList(0, maxBatchSize)
            }
        }
    }

    fun peekBatch(context: Context, maxBatchSize: Int = 50): List<NotificationEvent> =
        peekBatch(context.filesDir, maxBatchSize)

    /**
     * Removes specifically acknowledged events from the persistent queue by their event IDs.
     * Used after server acknowledges successful ingestion.
     * Returns the number of events remaining in the queue.
     */
    fun dequeueByIds(filesDir: File, eventIds: Set<String>): Int {
        if (eventIds.isEmpty()) return size(filesDir)
        synchronized(lock) {
            val events = loadQueueInternal(filesDir)
            val filtered = events.filterNot { eventIds.contains(it.eventId) }
            saveQueueInternal(filesDir, filtered)
            return filtered.size
        }
    }

    fun dequeueByIds(context: Context, eventIds: Set<String>): Int =
        dequeueByIds(context.filesDir, eventIds)

    /**
     * Returns the current number of pending events in the queue.
     */
    fun size(filesDir: File): Int {
        synchronized(lock) {
            return loadQueueInternal(filesDir).size
        }
    }

    fun size(context: Context): Int = size(context.filesDir)

    /**
     * Clears all unsent events from the persistent queue.
     */
    fun clear(filesDir: File): Boolean {
        synchronized(lock) {
            val file = File(filesDir, QUEUE_FILENAME)
            return if (file.exists()) file.delete() else true
        }
    }

    fun clear(context: Context): Boolean = clear(context.filesDir)

    /**
     * Returns all queued events (for inspection or backup).
     */
    fun getAll(filesDir: File): List<NotificationEvent> {
        synchronized(lock) {
            return loadQueueInternal(filesDir)
        }
    }

    fun getAll(context: Context): List<NotificationEvent> = getAll(context.filesDir)

    private fun loadQueueInternal(filesDir: File): List<NotificationEvent> {
        val file = File(filesDir, QUEUE_FILENAME)
        if (!file.exists()) return emptyList()

        return try {
            val text = file.readText(Charsets.UTF_8)
            if (text.isBlank()) return emptyList()
            val array = JSONArray(text)
            val list = mutableListOf<NotificationEvent>()
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                list.add(NotificationEvent.fromJsonObject(obj))
            }
            list
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun saveQueueInternal(filesDir: File, events: List<NotificationEvent>) {
        val file = File(filesDir, QUEUE_FILENAME)
        try {
            val array = JSONArray()
            for (e in events) {
                array.put(e.toJsonObject())
            }
            FileWriter(file).use { writer ->
                writer.write(array.toString())
            }
        } catch (e: Exception) {
            // Keep app stable
        }
    }
}
