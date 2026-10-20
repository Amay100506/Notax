package org.notifyiq.app

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import com.google.android.material.switchmaterial.SwitchMaterial

class MainActivity : AppCompatActivity() {

    private lateinit var settingsManager: SettingsManager

    // Permission & capture views
    private lateinit var tvPermissionStatus: TextView
    private lateinit var btnOpenSettings: Button
    private lateinit var switchCapture: SwitchMaterial

    // Real-Time LAN Forwarding views
    private lateinit var switchForwarding: SwitchMaterial
    private lateinit var etServerHost: EditText
    private lateinit var etServerPort: EditText
    private lateinit var etApiKey: EditText
    private lateinit var btnSaveSettings: Button
    private lateinit var btnTestConnection: Button
    private lateinit var tvTestStatus: TextView
    private lateinit var tvQueueCount: TextView
    private lateinit var btnFlushQueue: Button
    private lateinit var btnClearQueue: Button

    // Fallback Offline Buffer views
    private lateinit var tvCapturedCount: TextView
    private lateinit var btnExportJson: Button
    private lateinit var btnClearData: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        settingsManager = SettingsManager(this)

        // Initialize views
        tvPermissionStatus = findViewById(R.id.tvPermissionStatus)
        btnOpenSettings = findViewById(R.id.btnOpenSettings)
        switchCapture = findViewById(R.id.switchCapture)

        switchForwarding = findViewById(R.id.switchForwarding)
        etServerHost = findViewById(R.id.etServerHost)
        etServerPort = findViewById(R.id.etServerPort)
        etApiKey = findViewById(R.id.etApiKey)
        btnSaveSettings = findViewById(R.id.btnSaveSettings)
        btnTestConnection = findViewById(R.id.btnTestConnection)
        tvTestStatus = findViewById(R.id.tvTestStatus)
        tvQueueCount = findViewById(R.id.tvQueueCount)
        btnFlushQueue = findViewById(R.id.btnFlushQueue)
        btnClearQueue = findViewById(R.id.btnClearQueue)

        tvCapturedCount = findViewById(R.id.tvCapturedCount)
        btnExportJson = findViewById(R.id.btnExportJson)
        btnClearData = findViewById(R.id.btnClearData)

        // Populate fields from persistent settings
        etServerHost.setText(settingsManager.serverHost)
        etServerPort.setText(settingsManager.serverPort.toString())
        etApiKey.setText(settingsManager.apiKey)
        switchCapture.isChecked = settingsManager.isCaptureEnabled
        switchForwarding.isChecked = settingsManager.isForwardingEnabled

        // Notification permission request
        btnOpenSettings.setOnClickListener {
            val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
            startActivity(intent)
        }

        // Capture toggle
        switchCapture.setOnCheckedChangeListener { _, isChecked ->
            settingsManager.isCaptureEnabled = isChecked
            val state = if (isChecked) "enabled" else "paused"
            Toast.makeText(this, "Notification capture $state", Toast.LENGTH_SHORT).show()
        }

        // Forwarding toggle
        switchForwarding.setOnCheckedChangeListener { _, isChecked ->
            settingsManager.isForwardingEnabled = isChecked
            val state = if (isChecked) "enabled" else "paused"
            Toast.makeText(this, "Real-time forwarding $state", Toast.LENGTH_SHORT).show()
        }

        // Save server configuration
        btnSaveSettings.setOnClickListener {
            saveSettingsFromUi()
            Toast.makeText(this, "Forwarding settings saved", Toast.LENGTH_SHORT).show()
        }

        // Test server connection
        btnTestConnection.setOnClickListener {
            saveSettingsFromUi()
            tvTestStatus.text = "Testing connection..."
            tvTestStatus.setTextColor(getColor(R.color.text_secondary))

            NotificationForwarder.testConnection(
                host = settingsManager.serverHost,
                port = settingsManager.serverPort,
                apiKey = settingsManager.apiKey
            ) { success, message ->
                tvTestStatus.text = message
                if (success) {
                    tvTestStatus.setTextColor(getColor(R.color.status_green))
                    Toast.makeText(this, "Connection verified!", Toast.LENGTH_SHORT).show()
                } else {
                    tvTestStatus.setTextColor(getColor(R.color.status_red))
                    Toast.makeText(this, "Connection failed", Toast.LENGTH_SHORT).show()
                }
            }
        }

        // Manual queue flush
        btnFlushQueue.setOnClickListener {
            saveSettingsFromUi()
            btnFlushQueue.isEnabled = false
            btnFlushQueue.text = "Flushing..."

            NotificationForwarder.triggerFlush(this) { sent, remaining ->
                btnFlushQueue.isEnabled = true
                btnFlushQueue.text = getString(R.string.btn_flush_queue)
                updateCounts()
                Toast.makeText(this, "Flushed $sent events. Remaining: $remaining", Toast.LENGTH_SHORT).show()
            }
        }

        // Clear forwarding queue
        btnClearQueue.setOnClickListener {
            PersistentEventQueue.clear(this)
            updateCounts()
            Toast.makeText(this, "Forwarding queue cleared", Toast.LENGTH_SHORT).show()
        }

        // Fallback JSON export
        btnExportJson.setOnClickListener {
            val file = JsonExporter.exportToExternalFile(this)
            if (file != null) {
                Toast.makeText(this, "Exported to: ${file.name}", Toast.LENGTH_LONG).show()
            } else {
                Toast.makeText(this, "No events to export or export failed", Toast.LENGTH_SHORT).show()
            }
            updateCounts()
        }

        // Fallback buffer clear
        btnClearData.setOnClickListener {
            JsonExporter.clearEvents(this)
            Toast.makeText(this, "Local event buffer cleared", Toast.LENGTH_SHORT).show()
            updateCounts()
        }
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
        updateCounts()
    }

    private fun saveSettingsFromUi() {
        settingsManager.serverHost = etServerHost.text.toString().trim()
        val port = etServerPort.text.toString().trim().toIntOrNull() ?: 8000
        settingsManager.serverPort = port
        settingsManager.apiKey = etApiKey.text.toString().trim()
    }

    private fun updatePermissionStatus() {
        val isGranted = isNotificationAccessGranted()
        if (isGranted) {
            tvPermissionStatus.text = getString(R.string.status_granted)
            tvPermissionStatus.setTextColor(getColor(R.color.status_green))
            btnOpenSettings.text = "Notification Access Enabled"
            btnOpenSettings.isEnabled = false
        } else {
            tvPermissionStatus.text = getString(R.string.status_not_granted)
            tvPermissionStatus.setTextColor(getColor(R.color.status_red))
            btnOpenSettings.text = getString(R.string.btn_open_settings)
            btnOpenSettings.isEnabled = true
        }
    }

    private fun updateCounts() {
        val queueSize = PersistentEventQueue.size(this)
        tvQueueCount.text = "Unsent Queued Events: $queueSize"

        val bufferSize = JsonExporter.loadEvents(this).size
        tvCapturedCount.text = "Captured Events in Local Buffer: $bufferSize"
    }

    private fun isNotificationAccessGranted(): Boolean {
        val enabledPackages = NotificationManagerCompat.getEnabledListenerPackages(this)
        return enabledPackages.contains(packageName)
    }
}
