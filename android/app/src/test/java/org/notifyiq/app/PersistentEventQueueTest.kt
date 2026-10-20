package org.notifyiq.app

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

class PersistentEventQueueTest {

    private lateinit var tempDir: File

    @Before
    fun setUp() {
        tempDir = Files.createTempDirectory("notifyiq_queue_test").toFile()
    }

    @After
    fun tearDown() {
        tempDir.deleteRecursively()
    }

    @Test
    fun testEnqueueAndPeekBatch() {
        assertEquals(0, PersistentEventQueue.size(tempDir))

        val event1 = NotificationEvent(
            eventId = "evt-1",
            packageName = "com.google.android.gm",
            title = "Email 1",
            text = "Body 1"
        )
        val event2 = NotificationEvent(
            eventId = "evt-2",
            packageName = "com.slack",
            title = "Slack Msg",
            text = "Body 2"
        )

        PersistentEventQueue.enqueue(tempDir, event1)
        PersistentEventQueue.enqueue(tempDir, event2)

        assertEquals(2, PersistentEventQueue.size(tempDir))

        // Peek should not alter the queue size
        val batch = PersistentEventQueue.peekBatch(tempDir, maxBatchSize = 10)
        assertEquals(2, batch.size)
        assertEquals("evt-1", batch[0].eventId)
        assertEquals("evt-2", batch[1].eventId)
        assertEquals(2, PersistentEventQueue.size(tempDir))
    }

    @Test
    fun testDuplicateEnqueuePrevention() {
        val event = NotificationEvent(
            eventId = "unique-id-999",
            packageName = "com.whatsapp",
            title = "Chat",
            text = "Hello"
        )

        PersistentEventQueue.enqueue(tempDir, event)
        assertEquals(1, PersistentEventQueue.size(tempDir))

        // Enqueueing same eventId again should not duplicate
        PersistentEventQueue.enqueue(tempDir, event)
        assertEquals(1, PersistentEventQueue.size(tempDir))
    }

    @Test
    fun testDequeueAcknowledgedIdsPreservesUnacked() {
        val event1 = NotificationEvent(eventId = "ack-1", packageName = "app1", title = "T1", text = "B1")
        val event2 = NotificationEvent(eventId = "unack-2", packageName = "app2", title = "T2", text = "B2")
        val event3 = NotificationEvent(eventId = "ack-3", packageName = "app3", title = "T3", text = "B3")

        PersistentEventQueue.enqueue(tempDir, event1)
        PersistentEventQueue.enqueue(tempDir, event2)
        PersistentEventQueue.enqueue(tempDir, event3)
        assertEquals(3, PersistentEventQueue.size(tempDir))

        // Dequeue ack-1 and ack-3
        val remaining = PersistentEventQueue.dequeueByIds(tempDir, setOf("ack-1", "ack-3"))
        assertEquals(1, remaining)
        assertEquals(1, PersistentEventQueue.size(tempDir))

        val batch = PersistentEventQueue.peekBatch(tempDir, maxBatchSize = 10)
        assertEquals(1, batch.size)
        assertEquals("unack-2", batch[0].eventId)
    }

    @Test
    fun testClearQueue() {
        val event = NotificationEvent(eventId = "del-1", packageName = "app1", title = "T1", text = "B1")
        PersistentEventQueue.enqueue(tempDir, event)
        assertEquals(1, PersistentEventQueue.size(tempDir))

        assertTrue(PersistentEventQueue.clear(tempDir))
        assertEquals(0, PersistentEventQueue.size(tempDir))
    }
}
