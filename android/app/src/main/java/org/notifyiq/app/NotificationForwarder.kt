package org.notifyiq.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Handles authenticated real-time HTTP notification forwarding from Android to the NotifyIQ backend.
 * Implements bounded exponential backoff retries, persistent local queue flushes,
 * connection tests, and strict privacy logging (never logs notification content).
 */
object NotificationForwarder {

    private const val TAG = "NotificationForwarder"
    private val scope = CoroutineScope(Dispatchers.IO + Job())
    private val isFlushing = AtomicBoolean(false)
    private val mainHandler = Handler(Looper.getMainLooper())

    private const val CONNECT_TIMEOUT_MS = 5000
    private const val READ_TIMEOUT_MS = 8000
    private const val INITIAL_BACKOFF_MS = 1000L
    private const val MAX_BACKOFF_MS = 30000L
    private const val MAX_CONSECUTIVE_FAILURES = 5

    /**
     * Tests connectivity to the NotifyIQ local server and verifies the configured API key.
     * Invokes callback on Main thread with result status. Never crashes on connection error.
     */
    fun testConnection(
        host: String,
        port: Int,
        apiKey: String,
        callback: (Boolean, String) -> Unit
    ) {
        scope.launch {
            try {
                val cleanHost = host.trim().removePrefix("http://").removePrefix("https://").trimEnd('/')
                val urlString = "http://$cleanHost:$port/forward/status"
                val url = URL(urlString)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = CONNECT_TIMEOUT_MS
                    readTimeout = READ_TIMEOUT_MS
                    setRequestProperty("Accept", "application/json")
                    if (apiKey.isNotBlank()) {
                        setRequestProperty("X-NotifyIQ-API-Key", apiKey.trim())
                    }
                }

                val responseCode = conn.responseCode
                if (responseCode == 200) {
                    val reader = BufferedReader(InputStreamReader(conn.inputStream))
                    val body = reader.readText()
                    reader.close()
                    val json = JSONObject(body)
                    val isAuthenticated = json.optBoolean("authenticated", false)
                    val serverTime = json.optString("server_time", "")

                    mainHandler.post {
                        if (isAuthenticated) {
                            callback(true, "Connected & Authenticated! Server Time: $serverTime")
                        } else {
                            callback(false, "Server reachable, but API key is invalid or missing.")
                        }
                    }
                } else if (responseCode == 401) {
                    mainHandler.post {
                        callback(false, "Authentication Failed (HTTP 401): Check your API key.")
                    }
                } else {
                    mainHandler.post {
                        callback(false, "Server returned HTTP status $responseCode")
                    }
                }
                conn.disconnect()
            } catch (e: Exception) {
                mainHandler.post {
                    callback(false, "Connection failed: ${e.localizedMessage ?: e.javaClass.simpleName}")
                }
            }
        }
    }

    /**
     * Triggers asynchronous flushing of the persistent queue to the configured server.
     * Respects forwarding setting, applies bounded exponential backoff, and updates status.
     */
    fun triggerFlush(context: Context, onComplete: ((sent: Int, remaining: Int) -> Unit)? = null) {
        val settings = SettingsManager(context)
        if (!settings.isForwardingEnabled) {
            onComplete?.let { mainHandler.post { it(0, PersistentEventQueue.size(context)) } }
            return
        }

        if (!isFlushing.compareAndSet(false, true)) {
            // Flush already in progress
            return
        }

        scope.launch {
            var totalSent = 0
            var consecutiveFailures = 0
            var currentBackoff = INITIAL_BACKOFF_MS

            try {
                while (PersistentEventQueue.size(context) > 0 && consecutiveFailures < MAX_CONSECUTIVE_FAILURES) {
                    val batch = PersistentEventQueue.peekBatch(context, maxBatchSize = 50)
                    if (batch.isEmpty()) break

                    val success = sendBatch(context, settings, batch)
                    if (success.first) {
                        val ackedIds = success.second
                        PersistentEventQueue.dequeueByIds(context, ackedIds)
                        totalSent += ackedIds.size
                        consecutiveFailures = 0
                        currentBackoff = INITIAL_BACKOFF_MS
                        Log.i(TAG, "Successfully forwarded and acknowledged ${ackedIds.size} events.")
                    } else {
                        consecutiveFailures++
                        Log.w(TAG, "Forwarding attempt failed (attempt $consecutiveFailures). Backing off for ${currentBackoff}ms.")
                        delay(currentBackoff)
                        currentBackoff = (currentBackoff * 2).coerceAtMost(MAX_BACKOFF_MS)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error in forwarder loop: ${e.javaClass.simpleName}")
            } finally {
                isFlushing.set(false)
                val remaining = PersistentEventQueue.size(context)
                onComplete?.let { cb ->
                    mainHandler.post { cb(totalSent, remaining) }
                }
            }
        }
    }

    /**
     * Sends a batch of events via HTTP POST to /notifications/forward.
     * Returns Pair(isSuccess, setOfAcknowledgedIds).
     * Never logs raw notification content.
     */
    private fun sendBatch(
        context: Context,
        settings: SettingsManager,
        events: List<NotificationEvent>
    ): Pair<Boolean, Set<String>> {
        val host = settings.serverHost.trim().removePrefix("http://").removePrefix("https://").trimEnd('/')
        val port = settings.serverPort
        val apiKey = settings.apiKey.trim()

        if (host.isBlank()) {
            Log.w(TAG, "Server host is empty, skipping forward.")
            return Pair(false, emptySet())
        }

        var conn: HttpURLConnection? = null
        try {
            val url = URL("http://$host:$port/notifications/forward")
            conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
                if (apiKey.isNotBlank()) {
                    setRequestProperty("X-NotifyIQ-API-Key", apiKey)
                }
            }

            // Construct payload according to schema
            val payload = JSONObject()
            val notificationsArray = JSONArray()
            for (event in events) {
                // Ensure excluded notification content is never transmitted
                if (settings.isPackageAllowed(event.packageName)) {
                    notificationsArray.put(event.toJsonObject())
                }
            }
            payload.put("notifications", notificationsArray)
            payload.put("client_version", "1.0.0")

            val writer = OutputStreamWriter(conn.outputStream, Charsets.UTF_8)
            writer.write(payload.toString())
            writer.flush()
            writer.close()

            val responseCode = conn.responseCode
            if (responseCode == 200) {
                val reader = BufferedReader(InputStreamReader(conn.inputStream, Charsets.UTF_8))
                val responseText = reader.readText()
                reader.close()

                val ackJson = JSONObject(responseText)
                val ackArray = ackJson.optJSONArray("acknowledged_event_ids")
                val ackSet = mutableSetOf<String>()
                if (ackArray != null) {
                    for (i in 0 until ackArray.length()) {
                        ackSet.add(ackArray.getString(i))
                    }
                }
                return Pair(true, ackSet)
            } else if (responseCode == 401) {
                Log.w(TAG, "Authentication failed (HTTP 401). Check API key.")
                return Pair(false, emptySet())
            } else {
                Log.w(TAG, "Server returned HTTP status $responseCode during forwarding.")
                return Pair(false, emptySet())
            }
        } catch (e: Exception) {
            Log.w(TAG, "Network failure during forwarding: ${e.localizedMessage ?: e.javaClass.simpleName}")
            return Pair(false, emptySet())
        } finally {
            conn?.disconnect()
        }
    }
}
