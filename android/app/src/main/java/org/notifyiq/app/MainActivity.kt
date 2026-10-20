package org.notifyiq.app

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import com.google.android.material.switchmaterial.SwitchMaterial

class MainActivity : AppCompatActivity() {

    private lateinit var settingsManager: SettingsManager
    private lateinit var tvPermissionStatus: TextView
    private lateinit var tvCapturedCount: TextView
    private lateinit var btnOpenSettings: Button
    private lateinit var switchCapture: SwitchMaterial
    private lateinit var btnExportJson: Button
    private lateinit var btnClearData: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        settingsManager = SettingsManager(this)

        tvPermissionStatus = findViewById(R.id.tvPermissionStatus)
        tvCapturedCount = findViewById(R.id.tvCapturedCount)
        btnOpenSettings = findViewById(R.id.btnOpenSettings)
        switchCapture = findViewById(R.id.switchCapture)
        btnExportJson = findViewById(R.id.btnExportJson)
        btnClearData = findViewById(R.id.btnClearData)

        btnOpenSettings.setOnClickListener {
            // Explicitly direct user to system Notification Listener settings
            val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
            startActivity(intent)
        }

        switchCapture.isChecked = settingsManager.isCaptureEnabled
        switchCapture.setOnCheckedChangeListener { _, isChecked ->
            settingsManager.isCaptureEnabled = isChecked
            val stateStr = if (isChecked) "enabled" else "paused"
            Toast.makeText(this, "Notification capture $stateStr", Toast.LENGTH_SHORT).show()
        }

        btnExportJson.setOnClickListener {
            val file = JsonExporter.exportToExternalFile(this)
            if (file != null) {
                Toast.makeText(this, "Exported to: ${file.name}", Toast.LENGTH_LONG).show()
            } else {
                Toast.makeText(this, "No events to export or export failed", Toast.LENGTH_SHORT).show()
            }
            updateStatus()
        }

        btnClearData.setOnClickListener {
            JsonExporter.clearEvents(this)
            Toast.makeText(this, "Local event buffer cleared", Toast.LENGTH_SHORT).show()
            updateStatus()
        }
    }

    override fun onResume() {
        super.onResume()
        updateStatus()
    }

    private fun updateStatus() {
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

        val count = JsonExporter.loadEvents(this).size
        tvCapturedCount.text = "Captured Events in Buffer: $count"
    }

    private fun isNotificationAccessGranted(): Boolean {
        val enabledPackages = NotificationManagerCompat.getEnabledListenerPackages(this)
        return enabledPackages.contains(packageName)
    }
}
